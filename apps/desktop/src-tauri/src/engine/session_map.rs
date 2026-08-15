use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use tokio::sync::Mutex;

use super::acp::AcpClient;
use super::EngineError;

/// In-process mapping from app conversation id to ACP session id.
/// The map is reset when the engine process is restarted.
#[derive(Clone)]
pub struct SessionMap {
    inner: Arc<Mutex<HashMap<String, SessionEntry>>>,
}

#[derive(Debug, Clone)]
pub struct SessionEntry {
    pub acp_session_id: String,
    pub cwd: PathBuf,
    /// Has this session already received a replay seed in this process lifetime?
    pub seeded: bool,
}

impl SessionMap {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Returns the existing session for `conversation_id` or creates a new one.
    /// Concurrent calls with the same `conversation_id` only create one session.
    pub async fn ensure(
        &self,
        conversation_id: &str,
        cwd: &Path,
        client: &AcpClient,
    ) -> Result<String, EngineError> {
        let mut guard = self.inner.lock().await;

        if let Some(entry) = guard.get(conversation_id) {
            return Ok(entry.acp_session_id.clone());
        }

        std::fs::create_dir_all(cwd)?;
        let acp_session_id = client.new_session(cwd).await?;
        let entry = SessionEntry {
            acp_session_id: acp_session_id.clone(),
            cwd: cwd.to_path_buf(),
            seeded: false,
        };
        guard.insert(conversation_id.to_string(), entry);

        Ok(acp_session_id)
    }

    pub fn get(&self, conversation_id: &str) -> Option<SessionEntry> {
        // The lock is held briefly; `try_lock` is fine for sync access.
        match self.inner.try_lock() {
            Ok(guard) => guard.get(conversation_id).cloned(),
            Err(_) => None,
        }
    }

    pub fn mark_seeded(&self, conversation_id: &str) {
        if let Ok(mut guard) = self.inner.try_lock() {
            if let Some(entry) = guard.get_mut(conversation_id) {
                entry.seeded = true;
            }
        }
    }

    pub fn clear(&self) {
        if let Ok(mut guard) = self.inner.try_lock() {
            guard.clear();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::process::Stdio;

    async fn make_client() -> (AcpClient, tokio::process::Child) {
        let script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/fixtures/mock_acp_server.mjs");
        let node = env::var("PATH")
            .ok()
            .and_then(|path| {
                path.split(if cfg!(target_os = "windows") { ';' } else { ':' })
                    .map(PathBuf::from)
                    .find_map(|dir| {
                        let candidate = dir.join(if cfg!(target_os = "windows") { "node.exe" } else { "node" });
                        candidate.is_file().then_some(candidate)
                    })
            })
            .expect("node binary for tests");

        let mut child = tokio::process::Command::new(node)
            .arg(&script)
            .stdout(Stdio::piped())
            .stdin(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();

        let stdin = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let client = AcpClient::new(stdin, stdout);
        client.initialize(std::time::Duration::from_secs(5)).await.unwrap();
        (client, child)
    }

    #[tokio::test]
    async fn concurrent_ensure_creates_one_session() {
        let (client, mut child) = make_client().await;
        let map = SessionMap::new();
        let temp = env::temp_dir().join(format!("session-map-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        let cwd = temp.join("conv-1");
        let mut futs = Vec::new();
        for _ in 0..10 {
            futs.push(async {
                map.ensure("conv-1", &cwd, &client).await
            });
        }

        let results: Vec<String> = futures::future::try_join_all(futs)
            .await
            .unwrap();

        let first = &results[0];
        for r in &results {
            assert_eq!(r, first, "concurrent ensure should return the same session");
        }

        client.close().await;
        let _ = child.wait().await;
        std::fs::remove_dir_all(&temp).ok();
    }

    #[tokio::test]
    async fn clear_then_ensure_creates_new_session() {
        let (client, mut child) = make_client().await;
        let map = SessionMap::new();
        let temp = env::temp_dir().join(format!("session-map-clear-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        let first = map.ensure("conv-2", &temp.join("conv-2"), &client).await.unwrap();
        map.clear();
        let second = map.ensure("conv-2", &temp.join("conv-2"), &client).await.unwrap();

        assert_ne!(first, second, "after clear a new session should be created");

        client.close().await;
        let _ = child.wait().await;
        std::fs::remove_dir_all(&temp).ok();
    }

    #[tokio::test]
    async fn workspace_directory_is_created() {
        let (client, mut child) = make_client().await;
        let map = SessionMap::new();
        let temp = env::temp_dir().join(format!("session-map-workspace-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();

        let workspace = temp.join("workspaces/conv-3");
        map.ensure("conv-3", &workspace, &client).await.unwrap();

        assert!(workspace.is_dir(), "workspace directory should be created");
        assert!(workspace.is_absolute(), "workspace directory should be absolute");

        client.close().await;
        let _ = child.wait().await;
        std::fs::remove_dir_all(&temp).ok();
    }
}
