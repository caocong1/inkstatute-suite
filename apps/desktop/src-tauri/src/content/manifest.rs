//! Content manifest serde model (SKL-12).
//!
//! Parses `content-manifest.json` produced by the Phase 114 skill pipeline.
//! Used by the content auto-updater to compare local vs remote manifest
//! versions and verify sha256 integrity.
//!
//! # Schema
//! ```json
//! {
//!   "schema_version": "1.0.0",
//!   "release_version": "1.0.0",
//!   "released_at": "2026-08-14T00:00:00Z",
//!   "min_engine_version": "0.1.0-rc.6",
//!   "domains": {
//!     "legal-core": { "skills": [{"name": "...", "sha256": "..."}] }
//!   }
//! }
//! ```
//!
//! ## v5 semantic change: semver compatibility
//! V4 used string equality (`engineVersion == minEngineVersion`). V5 changes
//! this to semver range comparison because DSH now uses semver pre-release
//! versions (e.g. `0.1.0-rc.6`). Pre-release versions are handled specially
//! because the `semver` crate's `VersionReq` does not match pre-release
//! versions by default — we fall back to direct `Version` comparison when
//! the engine version contains a pre-release identifier.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// A single skill entry in a content manifest domain.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkillEntry {
    pub name: String,
    pub sha256: String,
}

/// A domain entry containing its skill list.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainEntry {
    pub skills: Vec<SkillEntry>,
}

impl DomainEntry {
    /// Number of skills in this domain.
    pub fn skill_count(&self) -> usize {
        self.skills.len()
    }
}

/// The top-level content manifest.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContentManifest {
    #[serde(rename = "schema_version")]
    pub schema_version: String,
    #[serde(rename = "release_version")]
    pub release_version: String,
    #[serde(rename = "released_at")]
    pub released_at: String,
    #[serde(rename = "min_engine_version")]
    pub min_engine_version: String,
    pub domains: HashMap<String, DomainEntry>,
}

impl ContentManifest {
    /// Total skill count across all domains.
    pub fn total_skill_count(&self) -> usize {
        self.domains.values().map(|d| d.skill_count()).sum()
    }

    /// Domain names present in this manifest.
    pub fn domain_names(&self) -> Vec<&str> {
        self.domains.keys().map(|s| s.as_str()).collect()
    }

    /// Whether this manifest is compatible with the given engine version.
    ///
    /// V5: Uses semver range comparison instead of V4's string equality.
    /// `min_engine_version` can be an exact version (`0.1.0-rc.6`) or a
    /// range (`>=0.1.0-rc.6`).
    ///
    /// # Pre-release handling
    /// The `semver` crate's `VersionReq::matches` does **not** match
    /// pre-release versions by default. When the engine version contains a
    /// pre-release identifier, we fall back to direct `Version` comparison:
    /// if `min_engine_version` is an exact version (not a range), compare
    /// the two `Version`s directly; if it's a range, parse the range and
    /// the engine version, then check if the engine version satisfies the
    /// range using explicit pre-release-aware logic.
    ///
    /// Parse failures return `false` (conservative reject) — never panic.
    pub fn is_compatible_with(&self, engine_version: &str) -> bool {
        let min = &self.min_engine_version;

        // Parse the engine version. If it fails, conservatively reject.
        let engine_ver = match semver::Version::parse(engine_version) {
            Ok(v) => v,
            Err(_) => return false,
        };

        // If min_engine_version is an exact version (parseable as Version),
        // use direct comparison: engine >= min.
        // This handles pre-release correctly: 0.1.0-rc.6 >= 0.1.0-rc.5 is true.
        if let Ok(min_ver) = semver::Version::parse(min) {
            return engine_ver >= min_ver;
        }

        // min_engine_version is a range (e.g. ">=0.1.0-rc.6").
        // VersionReq::matches does not match pre-release versions, so when
        // the engine version has a pre-release, we need special handling.
        if let Ok(req) = semver::VersionReq::parse(min) {
            // If the engine version has no pre-release, standard matches works.
            if engine_ver.pre.is_empty() {
                return req.matches(&engine_ver);
            }

            // Engine version has a pre-release. VersionReq::matches won't
            // match it. Check each comparator manually with pre-release awareness.
            return engine_satisfies_range_with_prerelease(&engine_ver, &req);
        }

        // Could not parse min_engine_version as either Version or VersionReq.
        false
    }
}

/// Checks if a pre-release engine version satisfies a VersionReq.
///
/// This handles the case where `VersionReq::matches` fails for pre-release
/// versions. We extract the comparators from the VersionReq and check each
/// one manually with pre-release awareness.
fn engine_satisfies_range_with_prerelease(
    engine: &semver::Version,
    req: &semver::VersionReq,
) -> bool {
    use semver::Op;

    // VersionReq has a list of comparators. We need ALL to match.
    for comp in req.comparators.iter() {
        // Build a Version from the comparator's fields.
        // Comparator has: op, major (u64), minor (Option<u64>), patch (Option<u64>), pre.
        let major = comp.major;
        let minor = comp.minor.unwrap_or(0);
        let patch = comp.patch.unwrap_or(0);
        let comp_version = semver::Version {
            major,
            minor,
            patch,
            pre: comp.pre.clone(),
            build: semver::BuildMetadata::EMPTY,
        };

        let satisfies = match comp.op {
            Op::Exact => engine == &comp_version,
            Op::Greater => engine > &comp_version,
            Op::GreaterEq => engine >= &comp_version,
            Op::Less => engine < &comp_version,
            Op::LessEq => engine <= &comp_version,
            // Tilde, Caret, Wildcard need special handling, but for our
            // use case (min_engine_version is typically >= or exact), the
            // basic ops suffice. Conservative: return false for unknown ops.
            // `Op` is #[non_exhaustive], so a wildcard is required.
            _ => return false,
        };

        if !satisfies {
            return false;
        }
    }

    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_manifest(min_engine: &str) -> ContentManifest {
        ContentManifest {
            schema_version: "1.0.0".to_string(),
            release_version: "1.0.0".to_string(),
            released_at: "2026-08-14T00:00:00Z".to_string(),
            min_engine_version: min_engine.to_string(),
            domains: HashMap::new(),
        }
    }

    #[test]
    fn prerelease_rc6_vs_rc5_min_is_compatible() {
        // 0.1.0-rc.6 >= 0.1.0-rc.5 → true
        let m = make_manifest("0.1.0-rc.5");
        assert!(m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn prerelease_rc5_vs_rc6_min_is_incompatible() {
        // 0.1.0-rc.5 >= 0.1.0-rc.6 → false
        let m = make_manifest("0.1.0-rc.6");
        assert!(!m.is_compatible_with("0.1.0-rc.5"));
    }

    #[test]
    fn prerelease_rc6_vs_stable_0_2_0_is_incompatible() {
        // 0.1.0-rc.6 >= 0.2.0 → false (rc.6 is pre-release of 0.1.0, less than 0.2.0)
        let m = make_manifest("0.2.0");
        assert!(!m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn invalid_engine_version_returns_false_no_panic() {
        let m = make_manifest("0.1.0-rc.5");
        assert!(!m.is_compatible_with("not-a-version"));
    }

    #[test]
    fn invalid_min_engine_version_returns_false_no_panic() {
        let m = make_manifest("garbage");
        assert!(!m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn exact_version_match_is_compatible() {
        let m = make_manifest("0.1.0-rc.6");
        assert!(m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn stable_version_range_works() {
        let m = make_manifest(">=0.1.0");
        assert!(m.is_compatible_with("0.2.0"));
        assert!(!m.is_compatible_with("0.0.5"));
    }

    #[test]
    fn prerelease_with_range_min() {
        // >=0.1.0-rc.5 with engine 0.1.0-rc.6 → true
        let m = make_manifest(">=0.1.0-rc.5");
        assert!(m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn prerelease_with_range_min_lower_is_incompatible() {
        // >=0.1.0-rc.6 with engine 0.1.0-rc.5 → false
        let m = make_manifest(">=0.1.0-rc.6");
        assert!(!m.is_compatible_with("0.1.0-rc.5"));
    }

    #[test]
    fn prerelease_vs_stable_min_is_incompatible() {
        // 0.1.0-rc.6 >= 0.1.0 → false (pre-release is less than release)
        let m = make_manifest("0.1.0");
        assert!(!m.is_compatible_with("0.1.0-rc.6"));
    }

    #[test]
    fn stable_vs_prerelease_min_is_compatible() {
        // 0.1.0 >= 0.1.0-rc.6 → true (release is greater than pre-release)
        let m = make_manifest("0.1.0-rc.6");
        assert!(m.is_compatible_with("0.1.0"));
    }

    #[test]
    fn total_skill_count_across_domains() {
        let mut m = make_manifest("0.1.0");
        m.domains.insert(
            "legal-core".to_string(),
            DomainEntry {
                skills: vec![
                    SkillEntry {
                        name: "a".to_string(),
                        sha256: "hash_a".to_string(),
                    },
                    SkillEntry {
                        name: "b".to_string(),
                        sha256: "hash_b".to_string(),
                    },
                ],
            },
        );
        m.domains.insert(
            "legal-commercial".to_string(),
            DomainEntry {
                skills: vec![SkillEntry {
                    name: "c".to_string(),
                    sha256: "hash_c".to_string(),
                }],
            },
        );
        assert_eq!(m.total_skill_count(), 3);
    }

    #[test]
    fn serde_roundtrip() {
        let json = r#"{
            "schema_version": "1.0.0",
            "release_version": "2.0.0",
            "released_at": "2026-08-15T00:00:00Z",
            "min_engine_version": "0.1.0-rc.6",
            "domains": {
                "legal-core": {
                    "skills": [
                        {"name": "citation-check", "sha256": "abc123"}
                    ]
                }
            }
        }"#;
        let manifest: ContentManifest = serde_json::from_str(json).unwrap();
        assert_eq!(manifest.release_version, "2.0.0");
        assert_eq!(manifest.min_engine_version, "0.1.0-rc.6");
        assert_eq!(manifest.total_skill_count(), 1);
        assert_eq!(manifest.domain_names(), vec!["legal-core"]);

        // Serialize back
        let re_json = serde_json::to_string(&manifest).unwrap();
        let re_manifest: ContentManifest = serde_json::from_str(&re_json).unwrap();
        assert_eq!(manifest, re_manifest);
    }
}
