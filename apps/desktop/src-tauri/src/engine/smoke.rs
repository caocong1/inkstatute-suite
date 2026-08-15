use std::path::Path;
use std::process::Stdio;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;
use tokio::time::timeout;

type SmokeLines = tokio::io::Lines<BufReader<tokio::process::ChildStdout>>;

#[derive(Debug, Clone)]
pub struct SmokeResult {
    pub ok: bool,
    pub protocol_version: Option<u32>,
    pub agent_name: Option<String>,
    pub session_id: Option<String>,
    pub elapsed_ms: u128,
    pub failure: Option<String>,
    pub stderr_tail: Vec<String>,
}

/// Run a smoke test against an assembled engine. No real API key is needed.
pub async fn smoke_test(
    engine_dir: &Path,
    node_bin: &Path,
    timeout_dur: Duration,
) -> SmokeResult {
    let start = Instant::now();
    let temp_dsh_home = std::env::temp_dir().join(format!(
        "inkstatute-smoke-dsh-home-{}",
        std::process::id()
    ));
    let temp_cwd = std::env::temp_dir().join(format!(
        "inkstatute-smoke-cwd-{}",
        std::process::id()
    ));

    let _ = std::fs::remove_dir_all(&temp_dsh_home);
    let _ = std::fs::remove_dir_all(&temp_cwd);
    std::fs::create_dir_all(&temp_dsh_home).ok();
    std::fs::create_dir_all(&temp_cwd).ok();

    let bin = engine_dir.join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
    let config = engine_dir.join("acp.cordis.yml");

    let mut child = match spawn_engine(node_bin, &bin, &config, &temp_dsh_home, &temp_cwd) {
        Ok(c) => c,
        Err(e) => {
            return SmokeResult {
                ok: false,
                protocol_version: None,
                agent_name: None,
                session_id: None,
                elapsed_ms: start.elapsed().as_millis(),
                failure: Some("引擎无法启动，安装可能不完整".to_string()),
                stderr_tail: vec![format!("{}", e)],
            };
        }
    };

    let (stderr_tx, mut stderr_rx) = mpsc::channel::<String>(32);
    let stderr_handle = {
        let stderr = child
            .stderr
            .take()
            .expect("stderr is piped");
        tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            let mut tail: Vec<String> = Vec::with_capacity(20);
            while let Ok(Some(line)) = reader.next_line().await {
                if tail.len() >= 20 {
                    tail.remove(0);
                }
                tail.push(line.clone());
                let _ = stderr_tx.send(line).await;
            }
            tail
        })
    };

    let stdout = child
        .stdout
        .take()
        .expect("stdout is piped");
    let mut lines: SmokeLines = BufReader::new(stdout).lines();
    let mut stdin = child
        .stdin
        .take()
        .expect("stdin is piped");

    let mut result = SmokeResult {
        ok: false,
        protocol_version: None,
        agent_name: None,
        session_id: None,
        elapsed_ms: 0,
        failure: None,
        stderr_tail: vec![],
    };

    // initialize
    let init_req = json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": 1,
            "clientCapabilities": {
                "fs": { "readTextFile": false, "writeTextFile": false },
                "terminal": false
            }
        }
    });

    if let Err(e) = send_request(&mut stdin, &init_req).await {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, &format!("引擎无响应: {}", e), &mut stderr_rx, timeout_dur).await;
    }

    let init_resp = match wait_for_response(&mut lines, 1, timeout_dur).await {
        Ok(v) => v,
        Err(e) => return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, &format!("引擎无响应: {}", e), &mut stderr_rx, timeout_dur).await,
    };

    if let Some(p) = init_resp
        .get("result")
        .and_then(|r| r.get("protocolVersion"))
        .and_then(|v| v.as_u64())
    {
        if p != 1 {
            return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, "引擎版本不兼容", &mut stderr_rx, timeout_dur).await;
        }
        result.protocol_version = Some(p as u32);
    } else {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, "引擎版本不兼容", &mut stderr_rx, timeout_dur).await;
    }

    if let Some(name) = init_resp
        .get("result")
        .and_then(|r| r.get("agentInfo"))
        .and_then(|a| a.get("name"))
        .and_then(|v| v.as_str())
    {
        result.agent_name = Some(name.to_string());
    }

    // session/new
    let new_req = json!({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "session/new",
        "params": {
            "cwd": temp_cwd.to_string_lossy(),
            "mcpServers": []
        }
    });

    if let Err(e) = send_request(&mut stdin, &new_req).await {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, &format!("引擎会话创建失败: {}", e), &mut stderr_rx, timeout_dur).await;
    }

    let new_resp = match wait_for_response(&mut lines, 2, timeout_dur).await {
        Ok(v) => v,
        Err(e) => return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, &format!("引擎会话创建失败: {}", e), &mut stderr_rx, timeout_dur).await,
    };

    if let Some(sid) = new_resp
        .get("result")
        .and_then(|r| r.get("sessionId"))
        .and_then(|v| v.as_str())
    {
        result.session_id = Some(sid.to_string());
    } else {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, "引擎会话创建失败", &mut stderr_rx, timeout_dur).await;
    }

    if !temp_dsh_home.join("sessions").exists() {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, "引擎会话创建失败", &mut stderr_rx, timeout_dur).await;
    }

    if engine_dir.join("${DSH_HOME}").exists() {
        return cleanup(&mut child, &temp_dsh_home, &temp_cwd, start, &mut result, "引擎配置异常：会话目录位置错误", &mut stderr_rx, timeout_dur).await;
    }

    // Close stdin and give the engine a short chance to exit, then kill it if
    // it is still running. The test only cares that the session was created
    // and that the process is not left as an orphan.
    let _ = stdin.shutdown().await;
    let _ = wait_exit(&mut child, Duration::from_secs(3)).await;
    let _ = child.kill().await;
    let _ = wait_exit(&mut child, Duration::from_secs(5)).await;

    result.ok = true;
    result.elapsed_ms = start.elapsed().as_millis();
    result.stderr_tail = drain_tail(&mut stderr_rx).await;

    let _ = std::fs::remove_dir_all(&temp_dsh_home);
    let _ = std::fs::remove_dir_all(&temp_cwd);

    result
}

async fn cleanup(
    child: &mut Child,
    dsh_home: &Path,
    cwd: &Path,
    start: Instant,
    result: &mut SmokeResult,
    failure: &str,
    stderr_rx: &mut mpsc::Receiver<String>,
    timeout_dur: Duration,
) -> SmokeResult {
    let _ = child.stdin.take();
    let _ = child.kill().await;
    let _ = wait_exit(child, timeout_dur).await;
    result.elapsed_ms = start.elapsed().as_millis();
    result.failure = Some(failure.to_string());
    result.stderr_tail = drain_tail(stderr_rx).await;
    let _ = std::fs::remove_dir_all(dsh_home);
    let _ = std::fs::remove_dir_all(cwd);
    result.clone()
}

async fn drain_tail(stderr_rx: &mut mpsc::Receiver<String>) -> Vec<String> {
    let mut tail = vec![];
    // The stderr task keeps pushing lines until the pipe closes. Drain them all.
    while let Ok(line) = stderr_rx.try_recv() {
        if tail.len() >= 20 {
            tail.remove(0);
        }
        tail.push(line);
    }
    tail
}

fn spawn_engine(
    node_bin: &Path,
    bin: &Path,
    config: &Path,
    dsh_home: &Path,
    cwd: &Path,
) -> Result<Child, std::io::Error> {
    Command::new(node_bin)
        .arg(bin)
        .arg("--config")
        .arg(config)
        .current_dir(cwd)
        .env("DSH_HOME", dsh_home)
        .env("DEEPSEEK_API_KEY", "sk-smoke-probe")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
}

async fn send_request(stdin: &mut tokio::process::ChildStdin, req: &Value) -> Result<(), String> {
    let mut text = serde_json::to_string(req).map_err(|e| e.to_string())?;
    text.push('\n');
    stdin
        .write_all(text.as_bytes())
        .await
        .map_err(|e| e.to_string())?;
    stdin.flush().await.map_err(|e| e.to_string())?;
    Ok(())
}

async fn wait_for_response(
    lines: &mut SmokeLines,
    id: u64,
    dur: Duration,
) -> Result<Value, String> {
    let deadline = tokio::time::Instant::now() + dur;
    while tokio::time::Instant::now() < deadline {
        let remaining = deadline - tokio::time::Instant::now();
        match timeout(remaining, lines.next_line()).await {
            Ok(Ok(Some(line))) => {
                if let Ok(v) = serde_json::from_str::<Value>(&line) {
                    if v.get("id").and_then(|i| i.as_u64()) == Some(id) {
                        return Ok(v);
                    }
                }
            }
            Ok(Ok(None)) => return Err("stdout closed".to_string()),
            Ok(Err(e)) => return Err(format!("read error: {}", e)),
            Err(_) => return Err("timeout".to_string()),
        }
    }
    Err("timeout".to_string())
}

async fn wait_exit(child: &mut Child, dur: Duration) -> Result<(), String> {
    match timeout(dur, child.wait()).await {
        Ok(Ok(_)) => Ok(()),
        Ok(Err(e)) => Err(format!("wait error: {}", e)),
        Err(_) => {
            let _ = child.kill().await;
            Err("exit timeout".to_string())
        }
    }
}
