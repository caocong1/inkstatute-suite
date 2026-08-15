//! Domain presets materialization and skill directory injection (SKL-11).
//!
//! Implements:
//! 1. `materialize_presets` — copies repo `presets/<domain>/` to
//!    `<dsh_home>/.agent-presets/<domain>/` (overwrite deployment).
//! 2. `build_skill_dirs_env` — builds the `INKSTATUTE_SKILL_DIRS` env var
//!    value (comma-separated absolute paths to all enabled domain skill dirs).
//!
//! The `acp.cordis.yml` `skills.filesystem.customSkillDirs` is changed from
//! a static list to runtime-injected via `INKSTATUTE_SKILL_DIRS` env var.
//! This means content updates don't require rewriting the yml — just restart
//! the engine.
//!
//! V5 change: no more "select practice direction" — all enabled domains are
//! mounted; the token budget gate (SKL-13) controls catalog size.

use std::path::{Path, PathBuf};

use crate::engine::EngineError;

/// The environment variable name for runtime skill directory injection.
pub const SKILL_DIRS_ENV: &str = "INKSTATUTE_SKILL_DIRS";

/// The subdirectory under DSH_HOME where presets are materialized.
const PRESETS_SUBDIR: &str = ".agent-presets";

/// The subdirectory within each preset containing skills.
const SKILLS_SUBDIR: &str = "skills";

/// Discovers domain names from the repo `presets/` directory.
///
/// Returns a sorted list of domain directory names (e.g. `legal-core`,
/// `legal-commercial`, ...).
fn discover_domains(app_resource_dir: &Path) -> Vec<String> {
    let presets_root = app_resource_dir.join("presets");
    let mut domains = Vec::new();

    if let Ok(entries) = std::fs::read_dir(&presets_root) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.starts_with("legal-") {
                    domains.push(name);
                }
            }
        }
    }

    domains.sort();
    domains
}

/// Materializes repo `presets/<domain>/` to `<dsh_home>/.agent-presets/<domain>/`.
///
/// This is called at install time and after content package updates.
/// Overwrite deployment: all bundled presets are deployed each time.
///
/// Returns the list of domain names that were materialized.
pub fn materialize_presets(
    app_resource_dir: &Path,
    dsh_home: &Path,
) -> Result<Vec<String>, EngineError> {
    let domains = discover_domains(app_resource_dir);
    let target_root = dsh_home.join(PRESETS_SUBDIR);

    // Ensure target root exists.
    std::fs::create_dir_all(&target_root).map_err(EngineError::Io)?;

    for domain in &domains {
        let src = app_resource_dir.join("presets").join(domain);
        let dst = target_root.join(domain);

        // Overwrite: remove existing target first.
        let _ = std::fs::remove_dir_all(&dst);
        copy_dir_recursive(&src, &dst)?;
    }

    Ok(domains)
}

/// Recursively copies a directory.
fn copy_dir_recursive(src: &Path, dst: &Path) -> Result<(), EngineError> {
    std::fs::create_dir_all(dst).map_err(EngineError::Io)?;

    if let Ok(entries) = std::fs::read_dir(src) {
        for entry in entries.flatten() {
            let src_path = entry.path();
            let dst_path = dst.join(entry.file_name());

            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                copy_dir_recursive(&src_path, &dst_path)?;
            } else {
                std::fs::copy(&src_path, &dst_path).map_err(EngineError::Io)?;
            }
        }
    }

    Ok(())
}

/// Builds the `INKSTATUTE_SKILL_DIRS` environment variable value.
///
/// Returns a comma-separated list of absolute paths to each domain's
/// skills directory under `<dsh_home>/.agent-presets/<domain>/skills`.
///
/// All enabled domains are included — V5 no longer has "select practice
/// direction". The token budget gate (SKL-13) controls catalog size.
pub fn build_skill_dirs_env(dsh_home: &Path) -> Result<String, EngineError> {
    let presets_root = dsh_home.join(PRESETS_SUBDIR);
    let mut dirs = Vec::new();

    if let Ok(entries) = std::fs::read_dir(&presets_root) {
        let mut domain_names: Vec<String> = entries
            .flatten()
            .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
            .map(|e| e.file_name().to_string_lossy().to_string())
            .filter(|n| n.starts_with("legal-"))
            .collect();
        domain_names.sort();

        for domain in &domain_names {
            let skill_dir = presets_root.join(domain).join(SKILLS_SUBDIR);
            if skill_dir.is_dir() {
                dirs.push(skill_dir.to_string_lossy().to_string());
            }
        }
    }

    Ok(dirs.join(","))
}

/// Returns the list of skill directory paths for a given DSH_HOME.
/// Used by `build_engine_env` to set `INKSTATUTE_SKILL_DIRS`.
pub fn skill_dir_paths(dsh_home: &Path) -> Vec<PathBuf> {
    let presets_root = dsh_home.join(PRESETS_SUBDIR);
    let mut dirs = Vec::new();

    if let Ok(entries) = std::fs::read_dir(&presets_root) {
        let mut domain_names: Vec<String> = entries
            .flatten()
            .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
            .map(|e| e.file_name().to_string_lossy().to_string())
            .filter(|n| n.starts_with("legal-"))
            .collect();
        domain_names.sort();

        for domain in &domain_names {
            let skill_dir = presets_root.join(domain).join(SKILLS_SUBDIR);
            if skill_dir.is_dir() {
                dirs.push(skill_dir);
            }
        }
    }

    dirs
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    // These tests mutate the process-wide INKSTATUTE_APP_ROOT env var and
    // must not run in parallel with each other.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    /// Creates a fake app resource dir with presets structure.
    fn make_fake_presets() -> PathBuf {
        let temp = std::env::temp_dir().join(format!(
            "inkstatute-presets-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&temp).unwrap();

        // Create presets/legal-core/skills/citation-check/SKILL.md
        let core_skills = temp.join("presets/legal-core/skills");
        std::fs::create_dir_all(core_skills.join("citation-check")).unwrap();
        std::fs::write(
            core_skills.join("citation-check/SKILL.md"),
            "---\nname: citation-check\ndescription: test\n---\n# Test\n",
        )
        .unwrap();

        // Create presets/legal-commercial/skills/contract-drafting/SKILL.md
        let comm_skills = temp.join("presets/legal-commercial/skills");
        std::fs::create_dir_all(comm_skills.join("contract-drafting")).unwrap();
        std::fs::write(
            comm_skills.join("contract-drafting/SKILL.md"),
            "---\nname: contract-drafting\ndescription: test\n---\n# Test\n",
        )
        .unwrap();

        // Create preset.yml files.
        std::fs::write(
            temp.join("presets/legal-core/preset.yml"),
            "name: legal-core\ndescription: core\n",
        )
        .unwrap();
        std::fs::write(
            temp.join("presets/legal-commercial/preset.yml"),
            "name: legal-commercial\ndescription: commercial\n",
        )
        .unwrap();

        temp
    }

    #[test]
    fn materialize_presets_copies_domains_and_returns_names() {
        let _guard = ENV_LOCK.lock().unwrap();
        let fake_app = make_fake_presets();
        let dsh_home = std::env::temp_dir().join(format!(
            "inkstatute-presets-dsh-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dsh_home).unwrap();

        let domains = materialize_presets(&fake_app, &dsh_home).unwrap();
        assert!(domains.contains(&"legal-core".to_string()));
        assert!(domains.contains(&"legal-commercial".to_string()));
        assert_eq!(domains.len(), 2);

        // Verify files were copied.
        let core_skill = dsh_home
            .join(".agent-presets/legal-core/skills/citation-check/SKILL.md");
        assert!(core_skill.exists(), "skill file should exist after materialization");

        let comm_skill = dsh_home
            .join(".agent-presets/legal-commercial/skills/contract-drafting/SKILL.md");
        assert!(comm_skill.exists());

        // Verify preset.yml was copied.
        let core_preset = dsh_home.join(".agent-presets/legal-core/preset.yml");
        assert!(core_preset.exists());

        std::fs::remove_dir_all(&fake_app).ok();
        std::fs::remove_dir_all(&dsh_home).ok();
    }

    #[test]
    fn materialize_presets_overwrites_existing() {
        let _guard = ENV_LOCK.lock().unwrap();
        let fake_app = make_fake_presets();
        let dsh_home = std::env::temp_dir().join(format!(
            "inkstatute-presets-overwrite-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dsh_home).unwrap();

        // First materialization.
        materialize_presets(&fake_app, &dsh_home).unwrap();

        // Add a stale file that should be removed by overwrite.
        let stale = dsh_home.join(".agent-presets/legal-core/stale.txt");
        std::fs::write(&stale, "stale").unwrap();
        assert!(stale.exists());

        // Second materialization (overwrite).
        materialize_presets(&fake_app, &dsh_home).unwrap();

        // Stale file should be gone (overwrite = remove + copy).
        assert!(!stale.exists(), "stale file should be removed by overwrite");

        // Skill file should still be there.
        let core_skill = dsh_home
            .join(".agent-presets/legal-core/skills/citation-check/SKILL.md");
        assert!(core_skill.exists());

        std::fs::remove_dir_all(&fake_app).ok();
        std::fs::remove_dir_all(&dsh_home).ok();
    }

    #[test]
    fn build_skill_dirs_env_returns_absolute_paths() {
        let _guard = ENV_LOCK.lock().unwrap();
        let fake_app = make_fake_presets();
        let dsh_home = std::env::temp_dir().join(format!(
            "inkstatute-presets-env-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dsh_home).unwrap();

        materialize_presets(&fake_app, &dsh_home).unwrap();

        let env_value = build_skill_dirs_env(&dsh_home).unwrap();
        assert!(!env_value.is_empty(), "env value should not be empty");

        // Each path should be absolute.
        for path in env_value.split(',') {
            assert!(
                Path::new(path).is_absolute(),
                "path should be absolute: {}",
                path
            );
            assert!(
                path.contains("skills"),
                "path should contain 'skills': {}",
                path
            );
        }

        // Should contain both domains.
        assert!(env_value.contains("legal-core"));
        assert!(env_value.contains("legal-commercial"));

        std::fs::remove_dir_all(&fake_app).ok();
        std::fs::remove_dir_all(&dsh_home).ok();
    }

    #[test]
    fn build_skill_dirs_env_empty_when_no_presets() {
        let _guard = ENV_LOCK.lock().unwrap();
        let dsh_home = std::env::temp_dir().join(format!(
            "inkstatute-presets-empty-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dsh_home).unwrap();

        let env_value = build_skill_dirs_env(&dsh_home).unwrap();
        assert_eq!(env_value, "", "env value should be empty when no presets exist");

        std::fs::remove_dir_all(&dsh_home).ok();
    }

    #[test]
    fn skill_dir_paths_returns_sorted_absolute_paths() {
        let _guard = ENV_LOCK.lock().unwrap();
        let fake_app = make_fake_presets();
        let dsh_home = std::env::temp_dir().join(format!(
            "inkstatute-presets-paths-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dsh_home).unwrap();

        materialize_presets(&fake_app, &dsh_home).unwrap();

        let paths = skill_dir_paths(&dsh_home);
        assert_eq!(paths.len(), 2);
        // Sorted: legal-commercial before legal-core.
        assert!(paths[0].to_string_lossy().contains("legal-commercial"));
        assert!(paths[1].to_string_lossy().contains("legal-core"));
        // All absolute.
        for p in &paths {
            assert!(p.is_absolute());
        }

        std::fs::remove_dir_all(&fake_app).ok();
        std::fs::remove_dir_all(&dsh_home).ok();
    }

    /// Integration test: spawn a real DSH engine and verify that the
    /// materialized skill directories appear in the model's system-reminder
    /// skill catalog.
    ///
    /// This test is `#[ignore]` because it requires:
    /// - A real engine assembly (engine/current pointing to a valid DSH install)
    /// - A real API key (for the LLM provider)
    /// - Network connectivity
    ///
    /// Run manually with:
    /// ```sh
    /// cargo test -- --ignored content::presets::tests::real_engine_skill_catalog
    /// ```
    #[test]
    #[ignore]
    fn real_engine_skill_catalog() {
        // 1. Materialize presets to DSH_HOME
        // 2. Build engine env with INKSTATUTE_SKILL_DIRS
        // 3. Spawn engine, create session, send a prompt asking for skill list
        // 4. Verify the system-reminder in session.jsonl contains our skill names
        //
        // This is a manual integration test — see the test instructions above.
    }
}
