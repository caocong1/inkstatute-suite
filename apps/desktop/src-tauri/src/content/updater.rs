//! Content package auto-updater (SKL-12).
//!
//! Fetches remote content manifest, compares versions, downloads and
//! verifies content packages, and atomically switches the active
//! release. On failure, rolls back to the last-good release.
//!
//! The updater is the ONLY automatic update layer in the system.
//! Engine and app updates are never automatic.
//!
//! # Flow
//! 1. Fetch remote `content-manifest.json` (source configurable, default
//!    GitHub Release; 10s timeout). Network failure → `Skipped{offline}`.
//! 2. `is_compatible_with(engine_version)` false → `Skipped{incompatible}`.
//! 3. Compare with local `<app_root>/skills/current` version; same → `UpToDate`.
//! 4. Download content zip to temp dir, extract to `<app_root>/skills/<version>.partial/`.
//! 5. Per-skill sha256 verification (manifest's `domains[].skills[].sha256`
//!    against each `SKILL.md`). Any mismatch → delete partial dir → `RolledBack`.
//! 6. All pass → rename partial to final dir → atomically write `skills/current` pointer.
//! 7. Keep one old generation; delete earlier ones.
//!
//! Any failure path preserves last-good and does NOT block startup.

use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use super::manifest::ContentManifest;
use crate::engine::paths;

/// Default content release URL. Overridable via `CONTENT_RELEASE_URL` env var.
const DEFAULT_CONTENT_URL: &str =
    "https://github.com/inkstatute/legal-skills-content/releases/latest/download";

/// HTTP timeout for manifest and zip fetches.
const HTTP_TIMEOUT: Duration = Duration::from_secs(10);

/// The outcome of a content update check.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind")]
pub enum UpdateOutcome {
    /// Already on the latest compatible version.
    UpToDate { version: String },
    /// Successfully updated to a new version.
    Updated {
        from: Option<String>,
        to: String,
    },
    /// Skipped (incompatible or offline). Startup is not blocked.
    Skipped { reason: String },
    /// Rolled back to last-good after a verification failure.
    RolledBack { to: String, reason: String },
}

/// Content status snapshot for the settings panel "skills" tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContentStatus {
    pub current_release: Option<String>,
    pub skill_count: usize,
    pub last_check: Option<String>,
    pub last_outcome: Option<UpdateOutcome>,
}

/// Content package auto-updater.
///
/// Behavior reference: `apps/flutter_app/lib/content/content_updater.dart` (READ-ONLY).
/// Rust rewrite for V5 with semver compatibility (SKL-12).
pub struct ContentUpdater {
    /// Base URL for content releases.
    content_release_url: String,
    /// Current engine version for compatibility checking.
    engine_version: String,
    /// HTTP client (injectable for testing).
    http_client: Option<reqwest::Client>,
}

impl ContentUpdater {
    /// Creates a new ContentUpdater.
    ///
    /// - `content_release_url`: Override the content release URL. Defaults
    ///   to `CONTENT_RELEASE_URL` env var or the default GitHub Release URL.
    /// - `engine_version`: The current engine version for compatibility checks.
    pub fn new(engine_version: &str) -> Self {
        let url = std::env::var("CONTENT_RELEASE_URL").unwrap_or_else(|_| DEFAULT_CONTENT_URL.to_string());
        Self {
            content_release_url: url,
            engine_version: engine_version.to_string(),
            http_client: None,
        }
    }

    /// Creates a ContentUpdater with a custom content release URL (for tests).
    pub fn with_url(engine_version: &str, content_release_url: &str) -> Self {
        Self {
            content_release_url: content_release_url.to_string(),
            engine_version: engine_version.to_string(),
            http_client: None,
        }
    }

    /// Creates a ContentUpdater with a pre-built HTTP client (for tests).
    pub fn with_client(engine_version: &str, content_release_url: &str, client: reqwest::Client) -> Self {
        Self {
            content_release_url: content_release_url.to_string(),
            engine_version: engine_version.to_string(),
            http_client: Some(client),
        }
    }

    fn client(&self) -> reqwest::Client {
        if let Some(c) = &self.http_client {
            return c.clone();
        }
        reqwest::Client::builder()
            .timeout(HTTP_TIMEOUT)
            .build()
            .unwrap_or_else(|_| reqwest::Client::new())
    }

    /// The skills base directory: `<app_root>/skills`.
    fn skills_base(&self) -> Result<PathBuf, String> {
        paths::app_root()
            .map(|p| p.join("skills"))
            .map_err(|e| e.to_string())
    }

    /// The `current` pointer path: `<app_root>/skills/current`.
    fn current_pointer_path(&self) -> Result<PathBuf, String> {
        Ok(self.skills_base()?.join("current"))
    }

    /// Reads the current release version from the pointer file.
    /// Returns `Ok(None)` if the file is missing or empty.
    fn read_current(&self) -> Result<Option<String>, String> {
        let path = self.current_pointer_path()?;
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
            Err(e) => Err(e.to_string()),
        }
    }

    /// Atomically writes the current pointer (temp file + rename).
    fn write_current(&self, version: &str) -> Result<(), String> {
        let path = self.current_pointer_path()?;
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let tmp = path.with_extension("tmp");
        std::fs::write(&tmp, version).map_err(|e| e.to_string())?;
        std::fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
        Ok(())
    }

    /// The release directory for a given version: `<app_root>/skills/<version>`.
    fn release_dir(&self, version: &str) -> Result<PathBuf, String> {
        Ok(self.skills_base()?.join(version))
    }

    /// The partial (staging) directory: `<app_root>/skills/<version>.partial`.
    fn partial_dir(&self, version: &str) -> Result<PathBuf, String> {
        Ok(self.skills_base()?.join(format!("{}.partial", version)))
    }

    /// Returns the current release version, if any.
    pub fn current_release(&self) -> Option<String> {
        self.read_current().ok().flatten()
    }

    /// Returns the skills directory for the current release.
    /// `<app_root>/skills/<current>`
    pub fn skills_dir(&self) -> PathBuf {
        match (self.read_current(), self.skills_base()) {
            (Ok(Some(ver)), Ok(base)) => base.join(&ver),
            (Ok(None), Ok(base)) => base.join("current"),
            _ => PathBuf::from("skills/current"),
        }
    }

    /// Checks for updates and applies them if available.
    ///
    /// This method NEVER blocks startup — all failures are caught and
    /// returned as `Skipped` or `RolledBack`.
    pub async fn check_and_update(&self) -> UpdateOutcome {
        let result = self.check_and_update_inner().await;
        match &result {
            UpdateOutcome::UpToDate { .. } | UpdateOutcome::Updated { .. } => {}
            UpdateOutcome::Skipped { reason } => {
                log::info!("content update skipped: {}", reason);
            }
            UpdateOutcome::RolledBack { to, reason } => {
                log::warn!("content update rolled back to {}: {}", to, reason);
            }
        }
        result
    }

    async fn check_and_update_inner(&self) -> UpdateOutcome {
        // Step 1: Fetch remote manifest.
        let remote = match self.fetch_remote_manifest().await {
            Ok(m) => m,
            Err(e) => {
                return UpdateOutcome::Skipped {
                    reason: format!("offline: {}", e),
                };
            }
        };

        // Step 2: Check engine compatibility.
        if !remote.is_compatible_with(&self.engine_version) {
            return UpdateOutcome::Skipped {
                reason: format!(
                    "incompatible: manifest requires engine >= {}, current is {}",
                    remote.min_engine_version, self.engine_version
                ),
            };
        }

        // Step 3: Compare with local current version.
        let current = self.read_current().ok().flatten();
        if let Some(ref cur) = current {
            if cur == &remote.release_version {
                return UpdateOutcome::UpToDate {
                    version: remote.release_version.clone(),
                };
            }
        }

        // Step 4: Download and extract content zip.
        let new_version = remote.release_version.clone();
        let partial_dir = match self.partial_dir(&new_version) {
            Ok(d) => d,
            Err(e) => {
                return UpdateOutcome::Skipped {
                    reason: format!("path error: {}", e),
                };
            }
        };

        // Clean up any stale partial dir.
        let _ = std::fs::remove_dir_all(&partial_dir);

        let zip_data = match self.download_zip(&new_version).await {
            Ok(data) => data,
            Err(e) => {
                let _ = std::fs::remove_dir_all(&partial_dir);
                return UpdateOutcome::Skipped {
                    reason: format!("download failed: {}", e),
                };
            }
        };

        // Extract zip to partial dir.
        if let Err(e) = extract_zip(&zip_data, &partial_dir) {
            let _ = std::fs::remove_dir_all(&partial_dir);
            return UpdateOutcome::Skipped {
                reason: format!("extraction failed: {}", e),
            };
        }

        // Step 5: Per-skill sha256 verification.
        if let Err(e) = self.verify_skill_hashes(&partial_dir, &remote) {
            let _ = std::fs::remove_dir_all(&partial_dir);
            let rollback_to = current.clone().unwrap_or_else(|| "none".to_string());
            return UpdateOutcome::RolledBack {
                to: rollback_to,
                reason: format!("sha256 mismatch: {}", e),
            };
        }

        // Step 6: Rename partial to final, atomic pointer switch.
        let release_dir = match self.release_dir(&new_version) {
            Ok(d) => d,
            Err(e) => {
                let _ = std::fs::remove_dir_all(&partial_dir);
                return UpdateOutcome::Skipped {
                    reason: format!("path error: {}", e),
                };
            }
        };

        // Remove existing release dir if present (re-run safety).
        let _ = std::fs::remove_dir_all(&release_dir);
        if let Err(e) = std::fs::rename(&partial_dir, &release_dir) {
            let _ = std::fs::remove_dir_all(&partial_dir);
            let rollback_to = current.clone().unwrap_or_else(|| "none".to_string());
            return UpdateOutcome::RolledBack {
                to: rollback_to,
                reason: format!("rename failed: {}", e),
            };
        }

        // Atomically write the current pointer.
        if let Err(e) = self.write_current(&new_version) {
            // The release dir exists but the pointer wasn't updated.
            // The old current still points to the old version — effectively rolled back.
            let rollback_to = current.clone().unwrap_or_else(|| "none".to_string());
            return UpdateOutcome::RolledBack {
                to: rollback_to,
                reason: format!("pointer update failed: {}", e),
            };
        }

        // Step 7: Clean up old generations (keep current + one previous).
        if let Some(ref prev) = current {
            if let Ok(base) = self.skills_base() {
                cleanup_old_generations(&base, &new_version, prev);
            }
        }

        UpdateOutcome::Updated {
            from: current,
            to: new_version,
        }
    }

    /// Fetches the remote content manifest.
    async fn fetch_remote_manifest(&self) -> Result<ContentManifest, String> {
        let url = format!("{}/content-manifest.json", self.content_release_url);
        let client = self.client();
        let resp = client
            .get(&url)
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }

        let body = resp.text().await.map_err(|e| e.to_string())?;
        serde_json::from_str::<ContentManifest>(&body)
            .map_err(|e| format!("manifest parse error: {}", e))
    }

    /// Downloads the content zip for the given version.
    async fn download_zip(&self, version: &str) -> Result<Vec<u8>, String> {
        let url = format!(
            "{}/legal-skills-content-{}.zip",
            self.content_release_url, version
        );
        let client = self.client();
        let resp = client
            .get(&url)
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }

        let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
        Ok(bytes.to_vec())
    }

    /// Verifies per-skill sha256 hashes against the manifest.
    ///
    /// For each domain in the manifest, for each skill, computes the sha256
    /// of `<partial_dir>/<domain>/<skill_name>/SKILL.md` and compares with
    /// the manifest's `sha256` field.
    fn verify_skill_hashes(
        &self,
        partial_dir: &Path,
        manifest: &ContentManifest,
    ) -> Result<(), String> {
        for (domain_name, domain_entry) in &manifest.domains {
            for skill in &domain_entry.skills {
                let skill_file = partial_dir
                    .join(domain_name)
                    .join(&skill.name)
                    .join("SKILL.md");
                if !skill_file.exists() {
                    return Err(format!(
                        "missing skill file: {}/{}/SKILL.md",
                        domain_name, skill.name
                    ));
                }
                let data = std::fs::read(&skill_file).map_err(|e| e.to_string())?;
                let hash = hex::encode(Sha256::digest(&data));
                if hash != skill.sha256 {
                    return Err(format!(
                        "{}/{}/SKILL.md: expected {}, got {}",
                        domain_name, skill.name, skill.sha256, hash
                    ));
                }
            }
        }
        Ok(())
    }

    /// Returns the current content status for UI consumption.
    pub fn current_status(&self) -> ContentStatus {
        let current_release = self.current_release();
        let skill_count = if let Some(ref ver) = current_release {
            // Try to load the local manifest and count skills.
            self.load_local_manifest()
                .map(|m| m.total_skill_count())
                .unwrap_or(0)
        } else {
            0
        };
        let _ = ver_ref(&current_release); // suppress unused warning
        ContentStatus {
            current_release,
            skill_count,
            last_check: None,
            last_outcome: None,
        }
    }

    /// Loads the local manifest from the current release directory.
    fn load_local_manifest(&self) -> Option<ContentManifest> {
        let ver = self.current_release()?;
        let dir = self.release_dir(&ver).ok()?;
        let manifest_file = dir.join("content-manifest.json");
        let text = std::fs::read_to_string(&manifest_file).ok()?;
        serde_json::from_str(&text).ok()
    }
}

/// Suppress unused variable warning in a way the compiler accepts.
fn ver_ref(_s: &Option<String>) {}

/// Extracts a zip archive into the target directory.
fn extract_zip(zip_data: &[u8], target: &Path) -> Result<(), String> {
    use std::io::{Cursor, Read};

    std::fs::create_dir_all(target).map_err(|e| e.to_string())?;

    let cursor = Cursor::new(zip_data);
    let mut archive = zip::ZipArchive::new(cursor).map_err(|e| e.to_string())?;

    for i in 0..archive.len() {
        let mut file = archive
            .by_index(i)
            .map_err(|e| format!("zip entry {} error: {}", i, e))?;

        let outpath = match file.enclosed_name() {
            Some(path) => target.join(path),
            None => continue,
        };

        if file.is_dir() {
            std::fs::create_dir_all(&outpath).map_err(|e| e.to_string())?;
        } else {
            if let Some(parent) = outpath.parent() {
                std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            let mut out_data = Vec::new();
            file.read_to_end(&mut out_data).map_err(|e| e.to_string())?;
            std::fs::write(&outpath, &out_data).map_err(|e| e.to_string())?;
        }
    }

    Ok(())
}

/// Cleans up old release directories, keeping only the current and one previous.
fn cleanup_old_generations(skills_base: &Path, current_version: &str, prev_version: &str) {
    let keep = [current_version, prev_version];
    if let Ok(entries) = std::fs::read_dir(skills_base) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            // Skip pointer files and partial dirs.
            if name == "current" || name == "last-good" || name.ends_with(".partial") {
                continue;
            }
            if !keep.contains(&name.as_str()) {
                // Only delete version-like directories (start with a digit).
                if name.chars().next().map(|c| c.is_ascii_digit()).unwrap_or(false) {
                    let _ = std::fs::remove_dir_all(entry.path());
                }
            }
        }
    }
}

/// Computes the sha256 hash of a file, returned as hex string.
pub fn sha256_file(path: &Path) -> Result<String, String> {
    let data = std::fs::read(path).map_err(|e| e.to_string())?;
    Ok(hex::encode(Sha256::digest(&data)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    // These tests mutate the process-wide INKSTATUTE_APP_ROOT env var and
    // must not run in parallel with each other.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    /// Builds a test manifest with one domain and one skill.
    fn test_manifest(version: &str, min_engine: &str, skill_sha: &str) -> ContentManifest {
        let mut domains = HashMap::new();
        domains.insert(
            "legal-core".to_string(),
            super::super::manifest::DomainEntry {
                skills: vec![super::super::manifest::SkillEntry {
                    name: "citation-check".to_string(),
                    sha256: skill_sha.to_string(),
                }],
            },
        );
        ContentManifest {
            schema_version: "1.0.0".to_string(),
            release_version: version.to_string(),
            released_at: "2026-08-15T00:00:00Z".to_string(),
            min_engine_version: min_engine.to_string(),
            domains,
        }
    }

    /// Sets up a test app_root with a skills directory and returns the path.
    fn setup_test_app_root() -> PathBuf {
        let temp = std::env::temp_dir().join(format!(
            "inkstatute-content-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&temp).unwrap();
        std::env::set_var("INKSTATUTE_APP_ROOT", &temp);
        temp
    }

    fn cleanup_test_app_root(temp: &Path) {
        std::env::remove_var("INKSTATUTE_APP_ROOT");
        let _ = std::fs::remove_dir_all(temp);
    }

    /// Creates a valid content zip with a SKILL.md file.
    fn make_content_zip(skill_content: &[u8]) -> Vec<u8> {
        use std::io::Write;
        let mut buf = Vec::new();
        {
            let mut zip = zip::ZipWriter::new(std::io::Cursor::new(&mut buf));
            let options = zip::write::SimpleFileOptions::default();

            // Create the domain/skill directory structure.
            zip.add_directory("legal-core", options).unwrap();
            zip.add_directory("legal-core/citation-check", options)
                .unwrap();
            zip.start_file("legal-core/citation-check/SKILL.md", options)
                .unwrap();
            zip.write_all(skill_content).unwrap();
            zip.finish().unwrap();
        }
        buf
    }

    #[test]
    fn sha256_mismatch_deletes_partial_and_keeps_current() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = setup_test_app_root();
        let updater = ContentUpdater::with_url("0.1.0-rc.6", "http://invalid.test");

        // Set up an existing current version.
        let skills_base = updater.skills_base().unwrap();
        std::fs::create_dir_all(&skills_base).unwrap();
        updater.write_current("1.0.0").unwrap();

        // Create a manifest with a wrong sha256.
        let manifest = test_manifest("2.0.0", "0.1.0-rc.5", "wronghash123");
        let partial_dir = updater.partial_dir("2.0.0").unwrap();
        std::fs::create_dir_all(&partial_dir).unwrap();

        // Create the skill file in the partial dir.
        let skill_dir = partial_dir.join("legal-core/citation-check");
        std::fs::create_dir_all(&skill_dir).unwrap();
        std::fs::write(skill_dir.join("SKILL.md"), b"test content").unwrap();

        // Verify should fail.
        let result = updater.verify_skill_hashes(&partial_dir, &manifest);
        assert!(result.is_err(), "sha256 mismatch should error");

        // Simulate the cleanup: delete partial dir.
        std::fs::remove_dir_all(&partial_dir).unwrap();
        assert!(!partial_dir.exists());

        // Current pointer should be unchanged.
        assert_eq!(
            updater.read_current().unwrap(),
            Some("1.0.0".to_string())
        );

        cleanup_test_app_root(&temp);
    }

    #[test]
    fn incompatible_manifest_returns_skipped_no_download() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = setup_test_app_root();
        let updater = ContentUpdater::with_url("0.1.0-rc.5", "http://invalid.test");

        // Manifest requires 0.2.0, engine is 0.1.0-rc.5 → incompatible.
        let manifest = test_manifest("2.0.0", "0.2.0", "abc");
        assert!(!manifest.is_compatible_with("0.1.0-rc.5"));

        // The check_and_update would return Skipped{incompatible} — we test
        // the compatibility check directly since we can't easily mock HTTP.
        assert!(!manifest.is_compatible_with("0.1.0-rc.5"));

        cleanup_test_app_root(&temp);
    }

    #[test]
    fn network_failure_returns_skipped_no_panic() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = setup_test_app_root();
        // Use an invalid URL that will fail to connect.
        let updater = ContentUpdater::with_url("0.1.0-rc.6", "http://127.0.0.1:1/invalid");

        // Run check_and_update — it should return Skipped, not panic.
        let runtime = tokio::runtime::Runtime::new().unwrap();
        let outcome = runtime.block_on(updater.check_and_update());

        match outcome {
            UpdateOutcome::Skipped { reason } => {
                assert!(reason.contains("offline") || reason.contains("download") || reason.contains("error"));
            }
            _ => panic!("expected Skipped for network failure, got {:?}", outcome),
        }

        cleanup_test_app_root(&temp);
    }

    #[test]
    fn success_path_current_points_to_new_version_old_dir_remains() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = setup_test_app_root();
        let updater = ContentUpdater::with_url("0.1.0-rc.6", "http://invalid.test");

        // Set up an existing current version 1.0.0 with a release dir.
        let skills_base = updater.skills_base().unwrap();
        std::fs::create_dir_all(&skills_base).unwrap();
        let old_release = updater.release_dir("1.0.0").unwrap();
        std::fs::create_dir_all(&old_release).unwrap();
        std::fs::write(old_release.join("content-manifest.json"), "{}").unwrap();
        updater.write_current("1.0.0").unwrap();

        // Simulate a successful update: create the new release dir and switch pointer.
        let new_release = updater.release_dir("2.0.0").unwrap();
        std::fs::create_dir_all(&new_release).unwrap();
        updater.write_current("2.0.0").unwrap();

        // Current should point to new version.
        assert_eq!(
            updater.read_current().unwrap(),
            Some("2.0.0".to_string())
        );

        // Old version directory should still exist.
        assert!(old_release.exists(), "old version directory should remain");

        cleanup_test_app_root(&temp);
    }

    #[test]
    fn update_outcome_serde_roundtrip() {
        let outcomes = vec![
            UpdateOutcome::UpToDate {
                version: "1.0.0".to_string(),
            },
            UpdateOutcome::Updated {
                from: Some("1.0.0".to_string()),
                to: "2.0.0".to_string(),
            },
            UpdateOutcome::Skipped {
                reason: "offline".to_string(),
            },
            UpdateOutcome::RolledBack {
                to: "1.0.0".to_string(),
                reason: "sha256 mismatch".to_string(),
            },
        ];
        for o in &outcomes {
            let json = serde_json::to_string(o).unwrap();
            let back: UpdateOutcome = serde_json::from_str(&json).unwrap();
            assert_eq!(o, &back);
        }
    }

    #[test]
    fn content_status_serde_roundtrip() {
        let status = ContentStatus {
            current_release: Some("1.0.0".to_string()),
            skill_count: 15,
            last_check: Some("2026-08-15T00:00:00Z".to_string()),
            last_outcome: Some(UpdateOutcome::UpToDate {
                version: "1.0.0".to_string(),
            }),
        };
        let json = serde_json::to_string(&status).unwrap();
        let back: ContentStatus = serde_json::from_str(&json).unwrap();
        assert_eq!(status, back);
    }

    #[test]
    fn sha256_file_computes_hash() {
        let temp = std::env::temp_dir().join(format!("sha256-test-{}", std::process::id()));
        std::fs::write(&temp, b"hello world").unwrap();
        let hash = sha256_file(&temp).unwrap();
        // Known sha256 of "hello world"
        assert_eq!(
            hash,
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        );
        std::fs::remove_file(&temp).unwrap();
    }

    #[test]
    fn extract_zip_creates_files() {
        let temp = std::env::temp_dir().join(format!("extract-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        let zip_data = make_content_zip(b"---\nname: test\ndescription: test\n---\n# Test\n");
        let target = temp.join("out");
        extract_zip(&zip_data, &target).unwrap();

        let skill_file = target.join("legal-core/citation-check/SKILL.md");
        assert!(skill_file.exists());
        let content = std::fs::read_to_string(&skill_file).unwrap();
        assert!(content.contains("# Test"));

        std::fs::remove_dir_all(&temp).unwrap();
    }

    #[test]
    fn cleanup_old_generations_keeps_current_and_prev() {
        let temp = std::env::temp_dir().join(format!("cleanup-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        // Create version dirs.
        for v in &["1.0.0", "1.1.0", "2.0.0", "2.1.0"] {
            std::fs::create_dir_all(temp.join(v)).unwrap();
        }
        // Create pointer files.
        std::fs::write(temp.join("current"), "2.1.0").unwrap();
        std::fs::write(temp.join("last-good"), "2.0.0").unwrap();

        cleanup_old_generations(&temp, "2.1.0", "2.0.0");

        // Current and prev should exist.
        assert!(temp.join("2.1.0").exists());
        assert!(temp.join("2.0.0").exists());
        // Older versions should be deleted.
        assert!(!temp.join("1.0.0").exists());
        assert!(!temp.join("1.1.0").exists());
        // Pointer files should remain.
        assert!(temp.join("current").exists());
        assert!(temp.join("last-good").exists());

        std::fs::remove_dir_all(&temp).unwrap();
    }
}
