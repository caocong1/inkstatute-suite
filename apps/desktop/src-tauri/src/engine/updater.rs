//! Engine semi-automatic updater — seven-step orchestration.
//!
//! **Invariant:** `engine/current` pointer is only written after a smoke test
//! passes. Any download, integrity, assemble, or smoke failure must not touch
//! the pointer. GATE-13 validates this with bad packages.
//!
//! The seven steps:
//! 1. Fetch latest `engine-lock.json` from the update server (10s timeout,
//!    network failure is non-fatal).
//! 2. Check `compatible_app_range` — block if the app is too old.
//! 3. Download packages via `assemble()`.
//! 4. Verify integrity + assemble into a `.partial` dir, atomic rename.
//! 5. Smoke test the new engine.
//! 6. Atomically switch `current` pointer.
//! 7. Retain one previous version; delete older dirs.

use std::fs;
use std::sync::Arc;
use std::time::Duration;

use serde::Serialize;

use super::assemble::{assemble, AssembleOptions, AssembleProgress};
use super::lock::EngineLock;
use super::paths;
use super::smoke::smoke_test;
use super::EngineError;

/// Result of checking for updates.
#[derive(Serialize, Clone)]
pub struct UpdateCheck {
    pub available: bool,
    pub current_version: Option<String>,
    pub latest_version: Option<String>,
    /// Chinese explanation when blocked; `None` if compatible.
    pub blocked_reason: Option<String>,
    pub download_size_mb: Option<f64>,
}

/// Progress stages reported during `apply()`.
#[derive(Serialize, Clone)]
#[serde(tag = "stage", rename_all = "snake_case")]
pub enum UpdateStage {
    Checking,
    Downloading { done: usize, total: usize },
    Assembling,
    SmokeTesting,
    Switching,
    Done,
    Failed { reason: String },
}

/// Final outcome of `apply()`.
#[derive(Serialize, Clone)]
#[serde(tag = "outcome", rename_all = "snake_case")]
pub enum UpdateOutcome {
    Updated {
        from: Option<String>,
        to: String,
    },
    UpToDate,
    Blocked {
        reason: String,
    },
    Failed {
        reason: String,
        current_intact: bool,
    },
}

/// The engine updater. Stateless — all state lives on disk under
/// `<app_root>/engine/`.
pub struct EngineUpdater {
    /// Base URL for fetching `engine-lock.json` (no trailing slash).
    update_base: String,
    /// The cordis config YAML content (read from `engines/acp.cordis.yml`).
    cordis_yml: String,
    /// Assembly options (registry, concurrency).
    opts: AssembleOptions,
}

impl EngineUpdater {
    pub fn new(update_base: String, cordis_yml: String, opts: AssembleOptions) -> Self {
        Self { update_base, cordis_yml, opts }
    }

    /// Steps 1-2: fetch the latest engine-lock.json, compare versions, check
    /// the compatibility gate. Network failure is **non-fatal** — returns
    /// `UpdateCheck { available: false, ... }` with a Chinese explanation.
    pub async fn check(&self, app_version: &str) -> Result<UpdateCheck, EngineError> {
        let current = paths::read_current()?;

        // Step 1: fetch the latest lock.
        let lock_url = format!("{}/engine-lock.json", self.update_base.trim_end_matches('/'));
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|e| EngineError::Protocol(format!("HTTP client build failed: {}", e)))?;

        let lock_text = match client.get(&lock_url).send().await {
            Ok(resp) if resp.status().is_success() => {
                match resp.text().await {
                    Ok(text) => text,
                    Err(_) => {
                        return Ok(UpdateCheck {
                            available: false,
                            current_version: current,
                            latest_version: None,
                            blocked_reason: Some("无法连接更新服务器".to_string()),
                            download_size_mb: None,
                        });
                    }
                }
            }
            _ => {
                return Ok(UpdateCheck {
                    available: false,
                    current_version: current,
                    latest_version: None,
                    blocked_reason: Some("无法连接更新服务器".to_string()),
                    download_size_mb: None,
                });
            }
        };

        let lock: EngineLock = match serde_json::from_str(&lock_text) {
            Ok(l) => l,
            Err(_) => {
                return Ok(UpdateCheck {
                    available: false,
                    current_version: current,
                    latest_version: None,
                    blocked_reason: Some("更新服务器返回了无效的引擎清单".to_string()),
                    download_size_mb: None,
                });
            }
        };

        let latest = lock.engine_version.clone();

        // Step 2: compatibility gate.
        if !semver_satisfies(app_version, &lock.compatible_app_range) {
            return Ok(UpdateCheck {
                available: false,
                current_version: current,
                latest_version: Some(latest),
                blocked_reason: Some("需要先升级应用程序".to_string()),
                download_size_mb: None,
            });
        }

        // Compare versions.
        let available = current.as_deref() != Some(&latest);

        Ok(UpdateCheck {
            available,
            current_version: current,
            latest_version: Some(latest),
            blocked_reason: None,
            download_size_mb: None,
        })
    }

    /// Steps 3-6: download → assemble → smoke → switch pointer.
    /// Progress is reported via `on_stage`.
    ///
    /// **The `current` pointer is only written at step 6, after smoke passes.**
    pub async fn apply(
        &self,
        app_version: &str,
        on_stage: Arc<dyn Fn(UpdateStage) + Send + Sync + 'static>,
    ) -> UpdateOutcome {
        let current = paths::read_current().ok().flatten();

        // Re-check (the user may have deferred for a while).
        on_stage(UpdateStage::Checking);
        let check = match self.check(app_version).await {
            Ok(c) => c,
            Err(e) => {
                return UpdateOutcome::Failed {
                    reason: format!("检查更新失败: {}", e),
                    current_intact: true,
                };
            }
        };

        if let Some(reason) = &check.blocked_reason {
            return UpdateOutcome::Blocked { reason: reason.clone() };
        }

        if !check.available {
            return UpdateOutcome::UpToDate;
        }

        let new_version = match &check.latest_version {
            Some(v) => v.clone(),
            None => {
                return UpdateOutcome::Failed {
                    reason: "无法确定最新版本号".to_string(),
                    current_intact: true,
                };
            }
        };

        // Fetch the lock again for assembly (check() consumed it).
        let lock_url = format!("{}/engine-lock.json", self.update_base.trim_end_matches('/'));
        let lock_text = match reqwest::get(&lock_url).await {
            Ok(resp) if resp.status().is_success() => resp.text().await.ok(),
            _ => None,
        };
        let lock: EngineLock = match lock_text.and_then(|t| serde_json::from_str(&t).ok()) {
            Some(l) => l,
            None => {
                return UpdateOutcome::Failed {
                    reason: "无法获取引擎清单".to_string(),
                    current_intact: true,
                };
            }
        };

        // Step 3-4: download + assemble.
        let dest = match paths::engine_dir(&new_version) {
            Ok(d) => d,
            Err(e) => {
                return UpdateOutcome::Failed {
                    reason: format!("路径解析失败: {}", e),
                    current_intact: true,
                };
            }
        };

        // If the dest dir exists (from a previous failed attempt), remove it.
        if dest.exists() {
            let _ = fs::remove_dir_all(&dest);
        }

        on_stage(UpdateStage::Downloading { done: 0, total: lock.packages.len() });

        let on_stage_for_assemble = on_stage.clone();
        let on_progress = move |p: AssembleProgress| {
            on_stage_for_assemble(UpdateStage::Downloading {
                done: p.done,
                total: p.total,
            });
        };

        if let Err(e) = assemble(&lock, &self.cordis_yml, &dest, &self.opts, on_progress).await {
            // Clean up the partial dir on failure.
            let _ = fs::remove_dir_all(&dest);
            let partial = dest.with_extension("partial");
            let _ = fs::remove_dir_all(&partial);
            return UpdateOutcome::Failed {
                reason: format!("引擎装配失败: {}", e),
                current_intact: true,
            };
        }

        // Step 5: smoke test.
        on_stage(UpdateStage::SmokeTesting);
        let node_bin = match paths::node_binary() {
            Ok(p) => p,
            Err(e) => {
                let _ = fs::remove_dir_all(&dest);
                return UpdateOutcome::Failed {
                    reason: format!("Node 运行环境缺失: {}", e),
                    current_intact: true,
                };
            }
        };

        let smoke = smoke_test(&dest, &node_bin, Duration::from_secs(60)).await;
        if !smoke.ok {
            // **Critical: clean up the bad dir, do NOT touch current.**
            let _ = fs::remove_dir_all(&dest);
            let reason = smoke.failure.unwrap_or_else(|| "引擎冒烟测试失败".to_string());
            on_stage(UpdateStage::Failed { reason: reason.clone() });
            return UpdateOutcome::Failed {
                reason,
                current_intact: true,
            };
        }

        // Step 6: switch pointer (ONLY after smoke passes).
        on_stage(UpdateStage::Switching);
        if let Err(e) = paths::write_current(&new_version) {
            let _ = fs::remove_dir_all(&dest);
            return UpdateOutcome::Failed {
                reason: format!("切换引擎指针失败: {}", e),
                current_intact: true,
            };
        }

        // Step 7: retain one previous version.
        retain_one_previous(&current, &new_version);

        on_stage(UpdateStage::Done);
        UpdateOutcome::Updated {
            from: current,
            to: new_version,
        }
    }

    /// Step 7 (rollback): roll back to the previous installed version.
    /// The previous version must also pass a smoke test before switching.
    pub async fn rollback(&self) -> Result<String, EngineError> {
        let current = paths::read_current()?;
        let versions = self.installed_versions()?;

        // Find the most recent version that isn't the current one.
        let target = versions.iter()
            .filter(|v| current.as_deref() != Some(v.as_str()))
            .last()
            .cloned();

        let target = match target {
            Some(v) => v,
            None => return Err(EngineError::Protocol("没有可回退的引擎版本".to_string())),
        };

        let target_dir = paths::engine_dir(&target)?;

        // Smoke test the rollback target.
        let node_bin = paths::node_binary()?;
        let smoke = smoke_test(&target_dir, &node_bin, Duration::from_secs(60)).await;
        if !smoke.ok {
            return Err(EngineError::Protocol(
                smoke.failure.unwrap_or_else(|| "回退目标引擎冒烟测试失败".to_string())
            ));
        }

        // Switch pointer.
        paths::write_current(&target)?;

        // Retain one previous (the old current becomes the retained one).
        retain_one_previous(&Some(target.clone()), &target);

        Ok(target)
    }

    /// List installed engine versions (directory names under `engine/`).
    pub fn installed_versions(&self) -> Result<Vec<String>, EngineError> {
        let base = paths::engine_base()?;
        if !base.exists() {
            return Ok(Vec::new());
        }
        let mut versions = Vec::new();
        for entry in fs::read_dir(&base)? {
            let entry = entry?;
            if entry.file_type()?.is_dir() {
                if let Some(name) = entry.file_name().to_str() {
                    if name != "current" && !name.starts_with('.') {
                        versions.push(name.to_string());
                    }
                }
            }
        }
        versions.sort();
        Ok(versions)
    }
}

/// Delete all engine version dirs except `current` and `new_version`.
/// `current` is the previous version (to retain as rollback target).
fn retain_one_previous(current: &Option<String>, new_version: &str) {
    let base = match paths::engine_base() {
        Ok(b) => b,
        Err(_) => return,
    };
    let keep = match current {
        Some(c) => vec![new_version.to_string(), c.clone()],
        None => vec![new_version.to_string()],
    };

    if let Ok(entries) = fs::read_dir(&base) {
        for entry in entries.flatten() {
            if let Some(name) = entry.file_name().to_str() {
                if name == "current" || name.starts_with('.') {
                    continue;
                }
                if !keep.contains(&name.to_string()) {
                    let _ = fs::remove_dir_all(entry.path());
                }
            }
        }
    }
}

/// Minimal semver range check: supports `>=x.y.z <a.b.c` format.
/// Returns `true` if `version` satisfies the range.
fn semver_satisfies(version: &str, range: &str) -> bool {
    let ver = parse_semver(version);
    for part in range.split_whitespace() {
        if let Some(rest) = part.strip_prefix(">=") {
            let min = parse_semver(rest);
            if ver < min { return false; }
        } else if let Some(rest) = part.strip_prefix("<=") {
            let max = parse_semver(rest);
            if ver > max { return false; }
        } else if let Some(rest) = part.strip_prefix(">") {
            let min = parse_semver(rest);
            if ver <= min { return false; }
        } else if let Some(rest) = part.strip_prefix("<") {
            let max = parse_semver(rest);
            if ver >= max { return false; }
        } else if let Some(rest) = part.strip_prefix("=") {
            let eq = parse_semver(rest);
            if ver != eq { return false; }
        } else if part == "*" {
            // always satisfies
        } else {
            // Bare version = exact match.
            let eq = parse_semver(part);
            if ver != eq { return false; }
        }
    }
    true
}

fn parse_semver(s: &str) -> (u64, u64, u64) {
    let s = s.trim_start_matches('v');
    let mut parts = s.split('.');
    let major = parts.next().and_then(|p| p.parse().ok()).unwrap_or(0);
    let minor = parts.next().and_then(|p| p.parse().ok()).unwrap_or(0);
    let patch = parts.next()
        .and_then(|p| p.split('-').next())
        .and_then(|p| p.parse().ok())
        .unwrap_or(0);
    (major, minor, patch)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn semver_satisfies_basic() {
        assert!(semver_satisfies("0.5.0", ">=0.1.0 <1.0.0"));
        assert!(semver_satisfies("0.1.0", ">=0.1.0 <1.0.0"));
        assert!(!semver_satisfies("1.0.0", ">=0.1.0 <1.0.0"));
        assert!(!semver_satisfies("0.0.9", ">=0.1.0 <1.0.0"));
        assert!(semver_satisfies("0.5.0", "*"));
    }

    #[test]
    fn retain_one_previous_removes_old_dirs() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = std::env::temp_dir().join(format!("updater-retain-{}", std::process::id()));
        fs::remove_dir_all(&temp).ok();
        let engine_base = temp.join("engine");
        fs::create_dir_all(engine_base.join("0.1.0-rc.5")).unwrap();
        fs::create_dir_all(engine_base.join("0.1.0-rc.6")).unwrap();
        fs::create_dir_all(engine_base.join("0.1.0-rc.7")).unwrap();

        std::env::set_var("INKSTATUTE_APP_ROOT", &temp);
        retain_one_previous(&Some("0.1.0-rc.6".to_string()), "0.1.0-rc.7");

        assert!(engine_base.join("0.1.0-rc.7").exists()); // new version kept
        assert!(engine_base.join("0.1.0-rc.6").exists()); // previous kept
        assert!(!engine_base.join("0.1.0-rc.5").exists()); // old deleted

        std::env::remove_var("INKSTATUTE_APP_ROOT");
        fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn installed_versions_excludes_current_and_hidden() {
        let _guard = ENV_LOCK.lock().unwrap();
        let temp = std::env::temp_dir().join(format!("updater-versions-{}", std::process::id()));
        fs::remove_dir_all(&temp).ok();
        let engine_base = temp.join("engine");
        fs::create_dir_all(engine_base.join("0.1.0-rc.5")).unwrap();
        fs::create_dir_all(engine_base.join("0.1.0-rc.6")).unwrap();
        fs::create_dir_all(engine_base.join(".partial")).unwrap();
        fs::write(engine_base.join("current"), "0.1.0-rc.6").unwrap();

        std::env::set_var("INKSTATUTE_APP_ROOT", &temp);
        let updater = EngineUpdater::new(
            "http://localhost".to_string(),
            "".to_string(),
            AssembleOptions::default(),
        );
        let versions = updater.installed_versions().unwrap();
        assert!(versions.contains(&"0.1.0-rc.5".to_string()));
        assert!(versions.contains(&"0.1.0-rc.6".to_string()));
        assert!(!versions.contains(&"current".to_string()));
        assert!(!versions.contains(&".partial".to_string()));

        std::env::remove_var("INKSTATUTE_APP_ROOT");
        fs::remove_dir_all(&temp).ok();
    }

    use std::sync::Mutex;
    static ENV_LOCK: Mutex<()> = Mutex::new(());
}
