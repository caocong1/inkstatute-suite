use std::env;
use std::path::{Path, PathBuf};

use super::EngineError;

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

/// `<app_root>/node/node.exe` on Windows, `<app_root>/node/bin/node` elsewhere.
pub fn node_binary() -> Result<PathBuf, EngineError> {
    if cfg!(target_os = "windows") {
        Ok(app_root()?.join("node/node.exe"))
    } else {
        Ok(app_root()?.join("node/bin/node"))
    }
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

    #[test]
    fn paths_roundtrip_with_override() {
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
}
