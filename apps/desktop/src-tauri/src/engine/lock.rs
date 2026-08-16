use std::collections::HashMap;

use base64::{engine::general_purpose, Engine};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha512};

use super::EngineError;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct EngineLock {
    pub schema_version: String,
    pub engine_version: String,
    pub node_version: String,
    pub target_platform: String,
    pub compatible_app_range: String,
    pub cordis_config_sha256: String,
    pub generated_at: String,
    #[serde(default)]
    pub prune: HashMap<String, Vec<String>>,
    pub packages: HashMap<String, LockedPackage>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct LockedPackage {
    pub name: String,
    pub version: String,
    pub integrity: String,
    pub tarball_path: String,
}

impl EngineLock {
    pub fn from_json(text: &str) -> Result<Self, EngineError> {
        let lock: Self = serde_json::from_str(text)?;

        if lock.schema_version != "1.0.0" {
            return Err(EngineError::UnsupportedLockSchema(lock.schema_version));
        }

        if lock.packages.is_empty() {
            return Err(EngineError::UnsupportedLockSchema(
                "empty packages".to_string(),
            ));
        }

        for (key, pkg) in &lock.packages {
            if !key.starts_with("node_modules/") {
                return Err(EngineError::UnsupportedLockSchema(format!(
                    "unexpected package key: {key}"
                )));
            }
            if !pkg.integrity.starts_with("sha512-") {
                return Err(EngineError::BadIntegrity(key.clone()));
            }
        }

        Ok(lock)
    }

    pub fn entrypoint_key(&self) -> &str {
        "node_modules/@deepseek-ai/dsh-acp-demo"
    }

    pub fn entrypoint_path(&self) -> std::path::PathBuf {
        std::path::PathBuf::from(self.entrypoint_key()).join("lib/bin.js")
    }

    /// Hashes the cordis config with line endings normalized to LF.
    ///
    /// The generator may run on a Windows checkout where git's autocrlf hands
    /// it CRLF bytes, while the assembler on a user machine writes the LF file
    /// bundled with the app. Hashing raw bytes made those two disagree and
    /// every engine update failed with CordisConfigMismatch (observed after
    /// Phase 127 was executed on Windows). Both sides must hash the normalized
    /// form; `gen-engine-lock.mjs` applies the same `\r\n` → `\n` rewrite.
    pub fn sha256_cordis_config(cordis_yml: &str) -> String {
        let normalized = cordis_yml.replace("\r\n", "\n");
        format!("{:x}", sha2::Sha256::digest(normalized.as_bytes()))
    }
}

impl LockedPackage {
    pub fn verify_sha512(&self, bytes: &[u8]) -> Result<(), EngineError> {
        let expected = &self.integrity["sha512-".len()..];
        let mut hasher = Sha512::new();
        hasher.update(bytes);
        let actual = general_purpose::STANDARD.encode(hasher.finalize());
        if actual != expected {
            return Err(EngineError::IntegrityMismatch(self.name.clone()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_lock() -> EngineLock {
        EngineLock {
            schema_version: "1.0.0".to_string(),
            engine_version: "0.1.0-rc.6".to_string(),
            node_version: "24.19.0".to_string(),
            target_platform: "win32-x64".to_string(),
            compatible_app_range: ">=0.1.0 <1.0.0".to_string(),
            cordis_config_sha256: "deadbeef".to_string(),
            generated_at: "2026-08-15T00:00:00Z".to_string(),
            prune: HashMap::new(),
            packages: HashMap::new(),
        }
    }

    #[test]
    fn valid_lock_parses() {
        let mut lock = sample_lock();
        lock.packages.insert(
            "node_modules/@deepseek-ai/dsh-acp-demo".to_string(),
            LockedPackage {
                name: "@deepseek-ai/dsh-acp-demo".to_string(),
                version: "0.1.0-rc.6".to_string(),
                integrity: "sha512-".to_string()
                    + &general_purpose::STANDARD.encode([0u8; 64].as_slice()),
                tarball_path: "/@deepseek-ai/dsh-acp-demo/-/dsh-acp-demo-0.1.0-rc.6.tgz"
                    .to_string(),
            },
        );
        let json = serde_json::to_string(&lock).unwrap();
        assert!(EngineLock::from_json(&json).is_ok());
    }

    #[test]
    fn bad_integrity_prefix_rejected() {
        let mut lock = sample_lock();
        lock.packages.insert(
            "node_modules/@deepseek-ai/dsh-acp-demo".to_string(),
            LockedPackage {
                name: "@deepseek-ai/dsh-acp-demo".to_string(),
                version: "0.1.0-rc.6".to_string(),
                integrity: "md5-abc".to_string(),
                tarball_path: "/x".to_string(),
            },
        );
        let json = serde_json::to_string(&lock).unwrap();
        assert!(matches!(
            EngineLock::from_json(&json),
            Err(EngineError::BadIntegrity(_))
        ));
    }

    #[test]
    fn verify_sha512_matches_known_bytes() {
        let pkg = LockedPackage {
            name: "test".to_string(),
            version: "1.0.0".to_string(),
            integrity: format!("sha512-{}", general_purpose::STANDARD.encode(Sha512::digest(b"hello"))),
            tarball_path: "/test/-/test-1.0.0.tgz".to_string(),
        };
        assert!(pkg.verify_sha512(b"hello").is_ok());
        assert!(pkg.verify_sha512(b"world").is_err());
    }
}
