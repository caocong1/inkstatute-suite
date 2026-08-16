use std::env;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use super::EngineError;

/// The Tauri resource directory, injected once at app startup by [`init`].
/// In production this is where bundled `resources/node/node.exe` lives.
/// In dev it may be unset (resource not bundled), in which case [`node_binary`]
/// falls back to `INKSTATUTE_NODE_BIN` then PATH.
static RESOURCE_DIR: OnceLock<Option<PathBuf>> = OnceLock::new();

/// Inject the Tauri resource directory once at app startup.
/// Called from `lib.rs` setup with `app.path().resource_dir()`.
/// Passing `None` (resource dir unavailable) is legal — [`node_binary`] will
/// fall through to the dev/test fallbacks.
pub fn init(resource_dir: Option<PathBuf>) {
    // First writer wins; subsequent calls are no-ops (idempotent across re-entry).
    let _ = RESOURCE_DIR.set(resource_dir);
}

/// The injected resource directory, if any.
fn resource_dir() -> Option<&'static Path> {
    RESOURCE_DIR.get().and_then(|opt| opt.as_deref())
}

/// `%LOCALAPPDATA%\InkStatute` on Windows, `~/.local/share/InkStatute` elsewhere.
/// The `INKSTATUTE_APP_ROOT` environment variable overrides this **for tests only**.
pub fn app_root() -> Result<PathBuf, EngineError> {
    if let Ok(override_root) = env::var("INKSTATUTE_APP_ROOT") {
        return Ok(PathBuf::from(override_root));
    }

    if cfg!(target_os = "windows") {
        let local_app_data = env::var("LOCALAPPDATA")
            .or_else(|_| env::var("USERPROFILE").map(|p| format!("{}\\AppData\\Local", p)))
            .map_err(|_| EngineError::NoAppRoot)?;
        Ok(PathBuf::from(local_app_data).join("InkStatute"))
    } else {
        let home = env::var("HOME").map_err(|_| EngineError::NoAppRoot)?;
        Ok(PathBuf::from(home).join(".local/share/InkStatute"))
    }
}

/// `<app_root>/engine`
pub fn engine_base() -> Result<PathBuf, EngineError> {
    Ok(app_root()?.join("engine"))
}

/// `<app_root>/engine/<version>`
pub fn engine_dir(version: &str) -> Result<PathBuf, EngineError> {
    Ok(engine_base()?.join(version))
}

/// `<app_root>/engine/current` — a single-line file containing the active version.
pub fn current_pointer() -> Result<PathBuf, EngineError> {
    Ok(engine_base()?.join("current"))
}

/// Read the current pointer; returns `Ok(None)` if the file is missing or empty.
pub fn read_current() -> Result<Option<String>, EngineError> {
    let path = current_pointer()?;
    match std::fs::read_to_string(&path) {
        Ok(text) => {
            let trimmed = text.trim();
            if trimmed.is_empty() {
                Ok(None)
            } else {
                Ok(Some(trimmed.to_string()))
            }
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(e.into()),
    }
}

/// Atomically write the current pointer by writing to a temp file and renaming.
pub fn write_current(version: &str) -> Result<(), EngineError> {
    let path = current_pointer()?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, version)?;
    std::fs::rename(&tmp, &path)?;
    Ok(())
}

/// `<app_root>/runtime/.dsh` — DSH_HOME, matches `acp.cordis.yml`.
pub fn dsh_home() -> Result<PathBuf, EngineError> {
    Ok(app_root()?.join("runtime/.dsh"))
}

/// `<dsh_home>/sessions`
pub fn sessions_root() -> Result<PathBuf, EngineError> {
    Ok(dsh_home()?.join("sessions"))
}

/// Resolve the Node binary used to spawn the engine subprocess.
///
/// Fallback chain (first hit wins):
/// 1. **Production** — `<resource_dir>/node/node.exe` (Windows) or
///    `<resource_dir>/node/node` (other), where `resource_dir` is the Tauri
///    bundled-resources directory injected by [`init`]. This is an absolute
///    path that does not depend on PATH.
/// 2. **Dev/test override** — `INKSTATUTE_NODE_BIN` env var (absolute path).
/// 3. **Dev PATH lookup** — first `node.exe`/`node` on PATH.
/// 4. If all three miss → [`EngineError::NodeRuntimeMissing`].
///
/// The engine is **always** spawned via an absolute path; we never rely on the
/// OS to resolve `node` from PATH in production (defect D3 — zero-config).
pub fn node_binary() -> Result<PathBuf, EngineError> {
    let node_name = if cfg!(target_os = "windows") { "node.exe" } else { "node" };
    let env_override = env::var("INKSTATUTE_NODE_BIN").ok();
    resolve_node_binary(resource_dir(), env_override.as_deref(), |name| {
        node_from_path(name)
    }, node_name)
}

/// Pure resolution logic, factored out so the fallback chain is unit-testable
/// without touching the process-global `RESOURCE_DIR` `OnceLock`.
///
/// - `resource_dir` — the bundled-resources dir (production), or `None`.
/// - `env_override` — the value of `INKSTATUTE_NODE_BIN`, if set.
/// - `path_lookup` — closure that scans PATH for the binary (injectable for tests).
/// - `node_name` — `"node.exe"` on Windows, `"node"` elsewhere.
pub(crate) fn resolve_node_binary(
    resource_dir: Option<&Path>,
    env_override: Option<&str>,
    path_lookup: impl Fn(&str) -> Option<PathBuf>,
    node_name: &str,
) -> Result<PathBuf, EngineError> {
    // 1. Bundled resource dir (production).
    if let Some(dir) = resource_dir {
        let candidate = dir.join("node").join(node_name);
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    // 2. Explicit dev/test override.
    if let Some(override_bin) = env_override {
        let p = PathBuf::from(override_bin);
        if p.is_file() {
            return Ok(p);
        }
    }

    // 3. PATH lookup (dev machines with a system Node).
    if let Some(found) = path_lookup(node_name) {
        return Ok(found);
    }

    // 4. Nothing usable — the user must reinstall (production) or set
    //    INKSTATUTE_NODE_BIN (dev). The文案 is user-facing Chinese.
    Err(EngineError::NodeRuntimeMissing)
}

/// Scan PATH for the first `node.exe` (Windows) / `node` (other) that exists.
fn node_from_path(node_name: &str) -> Option<PathBuf> {
    env::var("PATH").ok().and_then(|path| {
        path.split(if cfg!(target_os = "windows") { ';' } else { ':' })
            .map(Path::new)
            .find_map(|dir| {
                let candidate = dir.join(node_name);
                candidate.is_file().then_some(candidate)
            })
    })
}

/// Locate `node` from the current PATH or an explicit test override.
pub fn node_binary_for_test() -> Option<PathBuf> {
    if let Ok(override_bin) = env::var("INKSTATUTE_NODE_BIN") {
        return Some(PathBuf::from(override_bin));
    }
    env::var("PATH").ok().and_then(|path| {
        path.split(if cfg!(target_os = "windows") { ';' } else { ':' })
            .map(Path::new)
            .find_map(|dir| {
                let candidate = dir.join(if cfg!(target_os = "windows") {
                    "node.exe"
                } else {
                    "node"
                });
                candidate.is_file().then_some(candidate)
            })
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    // These tests mutate the process-wide INKSTATUTE_APP_ROOT env var and must
    // not run in parallel with each other.
    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    #[test]
    fn paths_roundtrip_with_override() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = std::env::temp_dir().join(format!(
            "inkstatute-paths-test-{}",
            std::process::id()
        ));
        fs::remove_dir_all(&temp).ok();
        fs::create_dir_all(&temp).unwrap();

        env::set_var("INKSTATUTE_APP_ROOT", &temp);

        write_current("1.0.0-rc.6").unwrap();
        assert_eq!(read_current().unwrap(), Some("1.0.0-rc.6".to_string()));

        env::remove_var("INKSTATUTE_APP_ROOT");
        fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn read_current_missing_is_none() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = std::env::temp_dir().join(format!(
            "inkstatute-current-missing-{}",
            std::process::id()
        ));
        fs::remove_dir_all(&temp).ok();
        fs::create_dir_all(&temp).unwrap();

        env::set_var("INKSTATUTE_APP_ROOT", &temp);
        assert_eq!(read_current().unwrap(), None);

        env::remove_var("INKSTATUTE_APP_ROOT");
        fs::remove_dir_all(&temp).ok();
    }

    // --- node_binary fallback chain (PKG-11) -------------------------------

    fn make_fake_node(dir: &Path, name: &str) -> PathBuf {
        fs::create_dir_all(dir.join("node")).unwrap();
        let bin = dir.join("node").join(name);
        fs::write(&bin, b"#!/bin/sh\nexit 0\n").unwrap();
        bin
    }

    #[test]
    fn node_binary_prefers_resource_dir() {
        let tmp = std::env::temp_dir().join(format!("ink-node-res-{}", std::process::id()));
        fs::remove_dir_all(&tmp).ok();
        // The lookup name must match the fake we created: hardcoding "node.exe"
        // here passed on the Windows machine that wrote this test and failed on
        // every other platform, where the fake is named "node".
        let name = if cfg!(target_os = "windows") { "node.exe" } else { "node" };
        let bin = make_fake_node(&tmp, name);

        let got = resolve_node_binary(Some(&tmp), None, |_| None, name).unwrap();
        assert_eq!(got, bin);
        fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn node_binary_falls_back_to_env_override() {
        let tmp = std::env::temp_dir().join(format!("ink-node-env-{}", std::process::id()));
        fs::remove_dir_all(&tmp).ok();
        fs::create_dir_all(&tmp).unwrap();
        let fake = tmp.join("custom-node");
        fs::write(&fake, b"#!/bin/sh\nexit 0\n").unwrap();

        // resource_dir is None; env override points to an existing file.
        let got = resolve_node_binary(None, Some(fake.to_str().unwrap()), |_| None, "node.exe").unwrap();
        assert_eq!(got, fake);
        fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn node_binary_falls_back_to_path_lookup() {
        let tmp = std::env::temp_dir().join(format!("ink-node-path-{}", std::process::id()));
        fs::remove_dir_all(&tmp).ok();
        fs::create_dir_all(&tmp).unwrap();
        let fake = tmp.join("node.exe");
        fs::write(&fake, b"#!/bin/sh\nexit 0\n").unwrap();

        let got = resolve_node_binary(None, None, |_| Some(fake.clone()), "node.exe").unwrap();
        assert_eq!(got, fake);
        fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn node_binary_missing_when_all_fail() {
        let got = resolve_node_binary(None, None, |_| None, "node.exe");
        assert!(matches!(got, Err(EngineError::NodeRuntimeMissing)));
    }

    #[test]
    fn node_binary_ignores_resource_dir_when_file_absent() {
        let tmp = std::env::temp_dir().join(format!("ink-node-empty-{}", std::process::id()));
        fs::remove_dir_all(&tmp).ok();
        fs::create_dir_all(&tmp).unwrap();
        // resource dir exists but has no node/ subdir → should fall through.
        let got = resolve_node_binary(Some(&tmp), None, |_| None, "node.exe");
        assert!(matches!(got, Err(EngineError::NodeRuntimeMissing)));
        fs::remove_dir_all(&tmp).ok();
    }
}
