use std::fmt;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, ChildStderr, Command};
use tokio::time::timeout;

use super::acp::AcpClient;
use super::credentials::{build_engine_env, Provider};
use super::EngineError;

pub struct SpawnConfig {
    pub engine_dir: PathBuf,
    pub node_bin: PathBuf,
    pub dsh_home: PathBuf,
    pub provider: Provider,
}

#[derive(Debug)]
pub enum ShutdownResult {
    CleanExit { code: i32 },
    ForceKilled { pid: u32 },
    NotRunning,
}

impl fmt::Display for ShutdownResult {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ShutdownResult::CleanExit { code } => write!(f, "CleanExit({})", code),
            ShutdownResult::ForceKilled { pid } => write!(f, "ForceKilled({})", pid),
            ShutdownResult::NotRunning => write!(f, "NotRunning"),
        }
    }
}

pub struct HealthReport {
    pub protocol_version: u32,
    pub agent_name: String,
    pub agent_version: String,
    pub elapsed_ms: u128,
}

pub struct EngineSupervisor {
    child: Child,
    pid: u32,
    acp: Arc<AcpClient>,
    stderr_tail: Arc<Mutex<Vec<String>>>,
    _stderr_handle: tokio::task::JoinHandle<()>,
}

impl EngineSupervisor {
    /// Spawns the engine child process and takes over its stdio.
    /// No API key is passed on the command line.
    pub async fn spawn(cfg: SpawnConfig) -> Result<Self, EngineError> {
        let bin = cfg
            .engine_dir
            .join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
        let config = cfg.engine_dir.join("acp.cordis.yml");
        let envs = build_engine_env(cfg.provider, &cfg.dsh_home)?;

        let mut cmd = Command::new(&cfg.node_bin);
        cmd.arg(&bin)
            .arg("--config")
            .arg(&config)
            .current_dir(&cfg.engine_dir)
            .envs(envs)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .stdin(std::process::Stdio::piped())
            .kill_on_drop(true);

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }

        let mut child = cmd.spawn()?;
        let pid = child
            .id()
            .ok_or_else(|| EngineError::Protocol("failed to get child pid".to_string()))?;

        let stderr = child.stderr.take().ok_or_else(|| EngineError::Io(
            std::io::Error::new(std::io::ErrorKind::Other, "stderr not piped"),
        ))?;

        let (stderr_handle, stderr_tail) = spawn_stderr_reader(stderr, 200);

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| EngineError::Io(std::io::Error::new(
                std::io::ErrorKind::Other,
                "stdin not piped",
            )))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| EngineError::Io(std::io::Error::new(
                std::io::ErrorKind::Other,
                "stdout not piped",
            )))?;

        let acp = Arc::new(AcpClient::new(stdin, stdout));

        Ok(Self {
            child,
            pid,
            acp,
            stderr_tail,
            _stderr_handle: stderr_handle,
        })
    }

    pub fn pid(&self) -> u32 {
        self.pid
    }

    pub fn is_alive(&mut self) -> bool {
        matches!(self.child.try_wait(), Ok(None))
    }

    /// Runs the ACP `initialize` handshake and verifies `protocolVersion == 1`.
    pub async fn health_probe(&self, dur: Duration) -> Result<HealthReport, EngineError> {
        let start = std::time::Instant::now();
        let init = self.acp.initialize(dur).await?;
        if init.protocol_version != 1 {
            return Err(EngineError::Protocol(format!(
                "protocol version {} is not supported",
                init.protocol_version
            )));
        }
        Ok(HealthReport {
            protocol_version: init.protocol_version,
            agent_name: init.agent_info.name.clone(),
            agent_version: init.agent_info.version.clone(),
            elapsed_ms: start.elapsed().as_millis(),
        })
    }

    /// Graceful shutdown: close stdin, wait up to 10s, then SIGTERM (Unix) and
    /// wait 5s, then force kill. Idempotent.
    pub async fn shutdown(&mut self) -> Result<ShutdownResult, EngineError> {
        if !self.is_alive() {
            return Ok(ShutdownResult::NotRunning);
        }

        // Close stdin first; the engine should exit when its input pipe closes.
        self.acp.close().await;

        if let Ok(Ok(status)) = timeout(Duration::from_secs(10), self.child.wait()).await {
            return Ok(ShutdownResult::CleanExit {
                code: status.code().unwrap_or(-1),
            });
        }

        // Send SIGTERM on Unix, then wait.
        #[cfg(unix)]
        {
            let raw_pid = self.pid as i32;
            unsafe {
                let _ = libc::kill(raw_pid, libc::SIGTERM);
            }
            if let Ok(Ok(status)) = timeout(Duration::from_secs(5), self.child.wait()).await {
                return Ok(ShutdownResult::CleanExit {
                    code: status.code().unwrap_or(-1),
                });
            }
        }

        // Final force kill (SIGKILL on Unix, TerminateProcess on Windows).
        if let Err(e) = self.child.kill().await {
            // If the process is already gone, treat as clean.
            if !self.is_alive() {
                return Ok(ShutdownResult::NotRunning);
            }
            return Err(e.into());
        }

        // Wait briefly for the OS to collect the process.
        let _ = timeout(Duration::from_secs(5), self.child.wait()).await;

        Ok(ShutdownResult::ForceKilled { pid: self.pid })
    }

    /// Returns `true` if the process is no longer in the OS process table.
    pub async fn assert_no_orphans(&mut self) -> Result<bool, EngineError> {
        if matches!(self.child.try_wait(), Ok(None)) {
            return Ok(false);
        }

        // Reap the child so it no longer appears in the process table.
        let _ = self.child.wait().await;

        #[cfg(target_os = "windows")]
        {
            // On Windows, `tasklist` may still show the PID for a brief period
            // after the process has exited and been reaped. Retry a few times
            // with a small delay to avoid false-positive orphan reports.
            //
            // Locale independence: `tasklist` localizes its "no tasks" info
            // message (e.g. "信息: ..." on Chinese Windows). Instead of
            // filtering by the "INFO:" prefix, we detect a real process entry
            // by checking for a CSV row that contains the PID as a quoted
            // field — a real entry looks like `"node.exe","12345",...`.
            let pid_str = self.pid.to_string();
            for attempt in 0..5 {
                let output = Command::new("tasklist")
                    .args([
                        "/FI",
                        &format!("PID eq {}", self.pid),
                        "/FO",
                        "CSV",
                        "/NH",
                    ])
                    .output()
                    .await?;
                let text = String::from_utf8_lossy(&output.stdout);
                // A real process row in CSV format starts with `"` and contains
                // `"<pid>"` as a field. An info/error message does neither.
                let still_running = text.lines().any(|l| {
                    let l = l.trim();
                    l.starts_with('"') && l.contains(&format!("\"{}\"", pid_str))
                });
                if !still_running {
                    return Ok(true);
                }
                if attempt < 4 {
                    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
                }
            }
            Ok(false)
        }

        #[cfg(not(target_os = "windows"))]
        {
            let output = Command::new("ps")
                .args(["-p", &self.pid.to_string()])
                .output()
                .await?;
            // ps exits 0 if the PID exists, non-zero otherwise.
            Ok(!output.status.success())
        }
    }

    pub async fn dispose(&mut self) -> Result<ShutdownResult, EngineError> {
        let result = self.shutdown().await?;
        self.assert_no_orphans().await?;
        Ok(result)
    }

    pub fn stderr_tail(&self) -> Vec<String> {
        let guard = self.stderr_tail.lock().unwrap();
        guard.clone()
    }

    pub fn acp_client(&self) -> Arc<AcpClient> {
        Arc::clone(&self.acp)
    }
}

impl Drop for EngineSupervisor {
    fn drop(&mut self) {
        if self.is_alive() {
            // Best-effort kill; do not block the drop.
            let _ = self.child.start_kill();
        }
    }
}

fn spawn_stderr_reader(
    stderr: ChildStderr,
    capacity: usize,
) -> (tokio::task::JoinHandle<()>, Arc<Mutex<Vec<String>>>) {
    let tail: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::with_capacity(capacity)));
    let tail_clone = tail.clone();
    let handle = tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let mut guard = tail_clone.lock().unwrap();
            if guard.len() >= capacity {
                guard.remove(0);
            }
            guard.push(line);
        }
    });
    (handle, tail)
}

#[cfg(test)]
mod tests {
    use super::{EngineSupervisor, ShutdownResult, SpawnConfig};
    use super::super::credentials::Provider;
    use std::env;
    use std::fs;
    use std::path::PathBuf;
    use tokio::time::{sleep, Duration};

    fn node_bin() -> PathBuf {
        if let Ok(override_bin) = env::var("INKSTATUTE_NODE_BIN") {
            return PathBuf::from(override_bin);
        }
        env::var("PATH")
            .ok()
            .and_then(|path| {
                path.split(if cfg!(target_os = "windows") { ';' } else { ':' })
                    .map(PathBuf::from)
                    .find_map(|dir| {
                        let candidate = dir.join(if cfg!(target_os = "windows") { "node.exe" } else { "node" });
                        candidate.is_file().then_some(candidate)
                    })
            })
            .expect("node binary for tests")
    }

    async fn spawn_with_script(
        script_name: &str,
        script: &str,
        provider: Provider,
    ) -> EngineSupervisor {
        let temp = env::temp_dir().join(format!("supervisor-test-{}-{}", script_name, std::process::id()));
        fs::remove_dir_all(&temp).ok();
        fs::create_dir_all(&temp).unwrap();

        // Write a fake node script that mimics a working engine for shutdown tests.
        let fake_bin = temp.join("fake_engine.js");
        fs::write(&fake_bin, script).unwrap();
        let config = temp.join("acp.cordis.yml");
        fs::write(&config, "---\n").unwrap();

        let dsh_home = temp.join(".dsh");
        fs::create_dir_all(&dsh_home).unwrap();

        // Disable credential store for unit tests.
        env::set_var("INKSTATUTE_TEST_API_KEY", "sk-test-no-real");

        let cfg = SpawnConfig {
            engine_dir: temp.clone(),
            node_bin: node_bin(),
            dsh_home,
            provider,
        };

        // Use the script directly as the "bin" by lying about the path.
        // Supervisor expects bin at node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js.
        let bin_path = temp.join("node_modules/@deepseek-ai/dsh-acp-demo/lib");
        fs::create_dir_all(&bin_path).unwrap();
        fs::copy(&fake_bin, bin_path.join("bin.js")).unwrap();

        EngineSupervisor::spawn(cfg).await.unwrap()
    }

    #[tokio::test]
    async fn shutdown_clean_exit() {
        let script = r#"
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
rl.on('close', () => process.exit(0));
"#;
        let mut sup = spawn_with_script("clean", script, Provider::DeepSeek).await;
        assert!(sup.is_alive());
        let result = sup.shutdown().await.unwrap();
        assert!(matches!(result, ShutdownResult::CleanExit { code: 0 }));
        assert!(sup.assert_no_orphans().await.unwrap());
    }

    #[tokio::test]
    async fn shutdown_force_killed() {
        let script = r#"
process.stdin.on('data', () => {});
process.stdin.resume();
setInterval(() => {}, 1000);
process.on('SIGTERM', () => {});
"#;
        let mut sup = spawn_with_script("force", script, Provider::DeepSeek).await;
        let result = sup.shutdown().await.unwrap();
        assert!(matches!(result, ShutdownResult::ForceKilled { .. }));
        assert!(sup.assert_no_orphans().await.unwrap());
    }

    #[tokio::test]
    async fn shutdown_idempotent() {
        let script = r#"
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
rl.on('close', () => process.exit(0));
"#;
        let mut sup = spawn_with_script("idempotent", script, Provider::DeepSeek).await;
        let _ = sup.shutdown().await.unwrap();
        let second = sup.shutdown().await.unwrap();
        assert!(matches!(second, ShutdownResult::NotRunning));
    }

    #[tokio::test]
    async fn assert_no_orphans_after_exit() {
        let script = r#"process.exit(0);"#;
        let mut sup = spawn_with_script("gone", script, Provider::DeepSeek).await;
        // Give the process a moment to exit.
        sleep(Duration::from_millis(100)).await;
        assert!(sup.assert_no_orphans().await.unwrap());
    }

    #[test]
    fn no_naive_pid_match() {
        // This is a structural regression guard: the source must not contain
        // the dangerous pattern "contains(&" + "pid" that would match PID 123 inside 1234.
        let src = include_str!("supervisor.rs");
        let needle = "contains(&".to_string() + "pid";
        assert!(!src.contains(&needle));
    }
}
