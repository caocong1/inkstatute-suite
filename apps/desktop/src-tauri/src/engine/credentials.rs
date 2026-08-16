use std::collections::HashMap;
use std::fmt;
use std::path::Path;

use regex::Regex;
use serde::{Deserialize, Serialize};

use super::EngineError;

const KEYRING_SERVICE: &str = "com.sorawatcher.inkstatute";
const TEST_API_KEY_ENV: &str = "INKSTATUTE_TEST_API_KEY";

/// Provider identifiers used by the ACP engine configuration.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Provider {
    DeepSeek,
    OpenAI,
    Anthropic,
    Google,
    Groq,
    XAI,
    Zhipu,
    Qwen,
    Custom,
}

impl Provider {
    pub fn id(&self) -> &'static str {
        match self {
            Provider::DeepSeek => "deepseek",
            Provider::OpenAI => "openai",
            Provider::Anthropic => "anthropic",
            Provider::Google => "google",
            Provider::Groq => "groq",
            Provider::XAI => "xai",
            Provider::Zhipu => "zhipu",
            // Matches the provider key used in engines/acp.cordis.yml.
            Provider::Qwen => "qwen-token-plan-cn",
            Provider::Custom => "custom",
        }
    }

    pub fn env_var(&self) -> &'static str {
        match self {
            Provider::DeepSeek => "DEEPSEEK_API_KEY",
            Provider::OpenAI => "OPENAI_API_KEY",
            Provider::Anthropic => "ANTHROPIC_API_KEY",
            Provider::Google => "GOOGLE_API_KEY",
            Provider::Groq => "GROQ_API_KEY",
            Provider::XAI => "XAI_API_KEY",
            Provider::Zhipu => "ZHIPU_API_KEY",
            Provider::Qwen => "QWEN_API_KEY",
            Provider::Custom => "CUSTOM_API_KEY",
        }
    }

    pub fn display_name(&self) -> &'static str {
        match self {
            Provider::DeepSeek => "DeepSeek",
            Provider::OpenAI => "OpenAI",
            Provider::Anthropic => "Anthropic",
            Provider::Google => "Google",
            Provider::Groq => "Groq",
            Provider::XAI => "xAI",
            Provider::Zhipu => "智谱",
            Provider::Qwen => "通义千问",
            Provider::Custom => "自定义",
        }
    }

    pub fn from_id(id: &str) -> Option<Self> {
        match id {
            "deepseek" => Some(Provider::DeepSeek),
            "openai" => Some(Provider::OpenAI),
            "anthropic" => Some(Provider::Anthropic),
            "google" => Some(Provider::Google),
            "groq" => Some(Provider::Groq),
            "xai" => Some(Provider::XAI),
            "zhipu" => Some(Provider::Zhipu),
            // Allow both the user-facing id and the engine's config key.
            "qwen" | "qwen-token-plan-cn" => Some(Provider::Qwen),
            "custom" => Some(Provider::Custom),
            _ => None,
        }
    }

    pub fn all() -> &'static [Provider] {
        &[
            Provider::DeepSeek,
            Provider::OpenAI,
            Provider::Anthropic,
            Provider::Google,
            Provider::Groq,
            Provider::XAI,
            Provider::Zhipu,
            Provider::Qwen,
            Provider::Custom,
        ]
    }
}

// ─── Debug-only developer credential file ──────────────────────────────────
//
// macOS Keychain grants access per *binary*. Every `cargo build` produces a new
// unsigned executable, so the OS treats each run as an unknown program asking
// for the entry and pops a password prompt. `list_providers` probes all nine
// providers, which turns opening the settings panel into nine prompts. That is
// unworkable on a dev machine and impossible when nobody is at the keyboard.
//
// Debug builds therefore keep credentials in a plain JSON file under the user's
// home directory. It is a development convenience with no protection against a
// local attacker — which is acceptable for development and is why the whole
// module is `#[cfg(debug_assertions)]`. Release builds never compile it and read
// only the OS credential store, so the Windows delivery keeps the V5 constraint
// "密钥只存 OS 凭据库" intact.
//
// The file lives outside the repository so it cannot be committed by accident.

#[cfg(debug_assertions)]
mod dev_store {
    use super::{EngineError, Provider};
    use std::collections::HashMap;
    use std::path::PathBuf;

    /// `$INKSTATUTE_DEV_CREDENTIALS`, else `~/.inkstatute/dev-credentials.json`.
    pub fn path() -> Option<PathBuf> {
        if let Ok(p) = std::env::var("INKSTATUTE_DEV_CREDENTIALS") {
            if !p.is_empty() {
                return Some(PathBuf::from(p));
            }
        }
        let home = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE"))?;
        Some(PathBuf::from(home).join(".inkstatute").join("dev-credentials.json"))
    }

    fn read_all() -> HashMap<String, String> {
        path()
            .and_then(|p| std::fs::read_to_string(p).ok())
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    fn write_all(map: &HashMap<String, String>) -> Result<(), EngineError> {
        let p = path().ok_or_else(|| EngineError::Credential("no home directory".into()))?;
        if let Some(parent) = p.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let body = serde_json::to_string_pretty(map)
            .map_err(|e| EngineError::Credential(e.to_string()))?;
        std::fs::write(&p, body)?;
        // Owner-only. Best effort: a failure here must not lose the key.
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o600));
        }
        Ok(())
    }

    pub fn load(p: Provider) -> Option<String> {
        read_all().get(p.id()).filter(|s| !s.is_empty()).cloned()
    }

    pub fn store(p: Provider, key: &str) -> Result<(), EngineError> {
        let mut map = read_all();
        map.insert(p.id().to_string(), key.to_string());
        write_all(&map)
    }

    pub fn delete(p: Provider) -> Result<(), EngineError> {
        let mut map = read_all();
        map.remove(p.id());
        write_all(&map)
    }
}

/// Stores an API key.
///
/// Release builds write to the OS credential store. Debug builds write to the
/// developer credential file instead, so a rebuilt binary never triggers a
/// keychain authorization prompt. The key is never written to the repository,
/// to logs, to telemetry, or to command-line arguments in either mode.
pub fn store_key(p: Provider, key: &str) -> Result<(), EngineError> {
    #[cfg(debug_assertions)]
    {
        return dev_store::store(p, key);
    }
    #[cfg(not(debug_assertions))]
    {
        let entry = keyring::Entry::new(KEYRING_SERVICE, p.id())
            .map_err(|e| EngineError::Credential(e.to_string()))?;
        entry
            .set_password(key)
            .map_err(|e| EngineError::Credential(e.to_string()))
    }
}

/// Loads an API key from the OS credential store.
///
/// In **debug builds only**, the environment variable `INKSTATUTE_TEST_API_KEY`
/// takes precedence over the store, so integration tests can inject a value
/// without touching the developer's real credentials. That override is compiled
/// out of release builds: a shipped binary reads the OS credential store and
/// nothing else, per the V5 constraint "密钥只存 OS 凭据库".
///
/// Note the override is provider-agnostic — one variable answers for every
/// provider — which is another reason it must never reach a release build.
///
/// Returns `Ok(None)` when no source has a value.
pub fn load_key(p: Provider) -> Result<Option<String>, EngineError> {
    // Debug order: test env override → developer credential file → OS store.
    // Reaching the OS store on macOS costs a password prompt per rebuilt binary,
    // so the file layer is what keeps day-to-day development quiet.
    #[cfg(debug_assertions)]
    {
        if let Ok(test_key) = std::env::var(TEST_API_KEY_ENV) {
            if !test_key.is_empty() {
                return Ok(Some(test_key));
            }
        }
        if let Some(key) = dev_store::load(p) {
            return Ok(Some(key));
        }
        // No developer credential: report absence rather than touching the
        // keychain, which would prompt with nobody there to answer.
        return Ok(None);
    }
    #[allow(unreachable_code)]
    {
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, p.id()).map_err(|e| EngineError::Credential(e.to_string()))?;
    match entry.get_password() {
        Ok(key) => Ok(Some(key)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(EngineError::Credential(e.to_string())),
    }
    }
}

/// Deletes an API key.
pub fn delete_key(p: Provider) -> Result<(), EngineError> {
    #[cfg(debug_assertions)]
    {
        return dev_store::delete(p);
    }
    #[cfg(not(debug_assertions))]
    {
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, p.id()).map_err(|e| EngineError::Credential(e.to_string()))?;
    match entry.delete_credential() {
        Ok(_) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(EngineError::Credential(e.to_string())),
    }
    }
}

/// Returns whether a key exists in the OS credential store for this provider.
/// This never returns the key content, so it is safe to call from UI code.
pub fn has_key(p: Provider) -> bool {
    // Must follow the same resolution order as load_key. Probing the keychain
    // directly here is what turned opening the settings panel into nine
    // password prompts (list_providers calls this for every provider).
    matches!(load_key(p), Ok(Some(s)) if !s.is_empty())
}

/// Returns providers that have a configured API key, in `Provider::all()`
/// order. Used by `build_engine_env` to decide which env vars to inject, and
/// by the UI to report how much cross-review capability is available
/// (Phase 128 / MMR-01..02).
pub fn configured_providers() -> Vec<Provider> {
    Provider::all().iter().copied().filter(|p| has_key(*p)).collect()
}

/// Cross-vendor review capability, judged by how many *distinct vendors* have
/// a configured key — not how many models. Reviewer/challenger subagents need
/// a vendor different from the drafting model to avoid same-vendor blind
/// spots (see `engines/acp.cordis.yml` reviewer-a/reviewer-b/challenger).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReviewCapability {
    /// Only one vendor configured. Same-vendor different-model review is
    /// still possible, but with limited effect.
    SingleVendor { provider: Provider },
    /// Two or more vendors configured — full cross-vendor review.
    CrossVendor { providers: Vec<Provider> },
    /// No vendor configured at all.
    None,
}

/// Determines the current review capability from configured providers.
pub fn review_capability() -> ReviewCapability {
    classify_review_capability(configured_providers())
}

/// Pure classification, split out from `review_capability` so the 0/1/many
/// branch selection is unit-testable without going through the credential
/// store (see `provider_env_pairs` below for why that I/O boundary matters
/// for test determinism in this crate).
fn classify_review_capability(providers: Vec<Provider>) -> ReviewCapability {
    match providers.len() {
        0 => ReviewCapability::None,
        1 => ReviewCapability::SingleVendor {
            provider: providers[0],
        },
        _ => ReviewCapability::CrossVendor { providers },
    }
}

/// Builds the environment variables passed to the engine subprocess.
/// Inherits the current process environment and adds `DSH_HOME`,
/// `INKSTATUTE_SKILL_DIRS` (the comma-separated absolute paths to
/// materialized domain skill directories), and the API key variable for
/// every *configured* provider — not just `active`. The extra keys let
/// review/challenge subagents (Phase 128 / MMR-01..02) call a vendor
/// different from the drafting model; a provider with no key configured is
/// simply absent, which is the SingleVendor degradation path (see
/// `review_capability`). `active` alone is a hard requirement: its key must
/// exist, or this returns `MissingApiKey`. The returned value must not be
/// logged.
pub fn build_engine_env(
    active: Provider,
    dsh_home: &Path,
) -> Result<Vec<(String, String)>, EngineError> {
    let mut envs: Vec<(String, String)> = std::env::vars().collect();
    envs.push((
        "DSH_HOME".to_string(),
        dsh_home.to_string_lossy().to_string(),
    ));

    // INKSTATUTE_SKILL_DIRS: runtime-injected skill directories for acp.cordis.yml.
    // The yml reads this env var to populate customSkillDirs, so content updates
    // only need a restart — no yml rewrite. (Phase 126 / SKL-11)
    let skill_dirs = crate::content::presets::build_skill_dirs_env(dsh_home)?;
    envs.push((
        crate::content::presets::SKILL_DIRS_ENV.to_string(),
        skill_dirs,
    ));

    let active_key =
        load_key(active)?.ok_or_else(|| EngineError::MissingApiKey(active.id().to_string()))?;
    let mut provider_keys = vec![(active, active_key)];
    for p in configured_providers() {
        if p.env_var() == active.env_var() {
            continue; // already queued above
        }
        if let Some(key) = load_key(p)? {
            provider_keys.push((p, key));
        }
    }

    envs.extend(provider_env_pairs(&provider_keys));
    Ok(envs)
}

/// Pure: turns `(provider, key)` pairs into the `(env var name, value)`
/// pairs `build_engine_env` appends. Kept separate from the credential-store
/// I/O so the "only configured providers are injected" invariant is
/// unit-testable with synthetic input, instead of depending on
/// has_key()/load_key() across all nine providers reflecting a clean
/// process-global credential state inside a test binary shared with other
/// test modules (`engine::supervisor`'s spawn tests set
/// `INKSTATUTE_TEST_API_KEY` and never clear it, so a test that expects an
/// *absent* provider would be order-dependent on which tests ran first).
fn provider_env_pairs(provider_keys: &[(Provider, String)]) -> Vec<(String, String)> {
    provider_keys
        .iter()
        .map(|(p, key)| (p.env_var().to_string(), key.clone()))
        .collect()
}

/// Redacts strings that look like API keys. Safe to use in error messages.
pub fn redact(s: &str) -> String {
    static RE: std::sync::OnceLock<Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| {
        Regex::new(r"(?i)(sk-[a-z0-9_-]{12,}|gsk_[a-z0-9_-]{12,}|xai-[a-z0-9_-]{12,})").unwrap()
    });
    re.replace_all(s, "****").to_string()
}

/// Reads `apiKeyEnv` values from the engine's `acp.cordis.yml` and returns them
/// keyed by provider id. This is used by unit tests to verify that the Rust
/// `Provider` enum stays in sync with the engine configuration.
pub fn provider_api_key_envs_from_cordis(cordis_yml: &str) -> Result<HashMap<String, String>, EngineError> {
    #[derive(Debug, Deserialize)]
    struct CordisItem {
        id: String,
        config: Option<CordisConfig>,
    }
    #[derive(Debug, Deserialize)]
    struct CordisConfig {
        providers: Option<HashMap<String, ProviderConfig>>,
    }
    #[derive(Debug, Deserialize)]
    struct ProviderConfig {
        #[serde(rename = "apiKeyEnv")]
        api_key_env: String,
    }

    let items: Vec<CordisItem> = serde_yaml::from_str(cordis_yml)
        .map_err(|e| EngineError::Credential(format!("failed to parse acp.cordis.yml: {e}")))?;
    let llm = items
        .into_iter()
        .find(|i| i.id == "llm")
        .ok_or_else(|| EngineError::Credential("acp.cordis.yml missing llm entry".to_string()))?;
    let providers = llm
        .config
        .ok_or_else(|| EngineError::Credential("acp.cordis.yml llm entry missing config".to_string()))?
        .providers
        .ok_or_else(|| EngineError::Credential("llm config missing providers".to_string()))?;
    Ok(providers
        .into_iter()
        .map(|(k, v)| (k, v.api_key_env))
        .collect())
}

impl fmt::Display for Provider {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.id())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::sync::Mutex;

    /// Serializes tests in this module that mutate the process-global
    /// `TEST_API_KEY_ENV` var. `cargo test` runs `#[test]` fns on a thread
    /// pool by default; without this, one test's `env::set_var` /
    /// `env::remove_var` interleaves with another's and both become
    /// order-dependent (observed: `configured_providers()` returning 1
    /// instead of 9 because a sibling test's cleanup cleared the var
    /// mid-assertion). Recovers from a poisoned lock instead of propagating
    /// the panic, so one failing test does not cascade-fail every later
    /// test that needs this lock.
    static ENV_TEST_LOCK: Mutex<()> = Mutex::new(());
    fn lock_env_tests() -> std::sync::MutexGuard<'static, ()> {
        ENV_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner())
    }

    #[test]
    fn provider_roundtrip() {
        for original in Provider::all() {
            let id = original.id();
            let recovered = Provider::from_id(id).expect("all ids roundtrip");
            assert_eq!(*original, recovered);
        }
    }

    #[test]
    fn env_vars_match_cordis_config() {
        let cordis_yml = include_str!("../../../../../engines/acp.cordis.yml");
        let envs = provider_api_key_envs_from_cordis(cordis_yml).unwrap();
        for p in Provider::all() {
            // The "custom" provider is an app-level OpenAI-compatible fallback;
            // it is not declared in the engine config and is injected with
            // CUSTOM_API_KEY when the user selects it.
            if matches!(p, Provider::Custom) {
                assert_eq!(p.env_var(), "CUSTOM_API_KEY");
                continue;
            }
            let expected = envs.get(p.id());
            assert_eq!(Some(p.env_var()), expected.map(|s| s.as_str()), "provider {}", p.id());
        }
    }

    #[test]
    fn redact_masks_keys() {
        let raw = "error: sk-abcdefghijklmnop in token"; // gate-allow-secret: fabricated literal proving redact() masks it
        let out = redact(raw);
        assert!(!out.contains("sk-abcdefghijklmnop")); // gate-allow-secret: same fabricated literal
        assert!(out.contains("****"));
    }

    #[test]
    fn build_engine_env_contains_dsh_home_and_provider_key() {
        let _guard = lock_env_tests();
        let temp = env::temp_dir().join(format!("inkstatute-build-env-test-{}", std::process::id()));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        // Use the test override so we do not touch the real credential store.
        env::set_var(TEST_API_KEY_ENV, "sk-test-1234567890");
        let envs = build_engine_env(Provider::DeepSeek, &temp).unwrap();

        assert!(envs.iter().any(|(k, v)| k == "DSH_HOME" && v == temp.to_string_lossy().as_ref()));
        assert!(envs.iter().any(|(k, v)| k == "DEEPSEEK_API_KEY" && v == "sk-test-1234567890"));
        // INKSTATUTE_SKILL_DIRS should be present (empty when no presets materialized).
        assert!(envs.iter().any(|(k, _)| k == "INKSTATUTE_SKILL_DIRS"));

        env::remove_var(TEST_API_KEY_ENV);
        std::fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn build_engine_env_skill_dirs_are_absolute_paths() {
        let _guard = lock_env_tests();
        let temp = env::temp_dir().join(format!(
            "inkstatute-build-env-skill-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        // Materialize some fake presets.
        let presets_src = temp.join("presets/legal-core/skills/test-skill");
        std::fs::create_dir_all(&presets_src).unwrap();
        std::fs::write(
            presets_src.join("SKILL.md"),
            "---\nname: test-skill\ndescription: test\n---\n# Test\n",
        )
        .unwrap();

        // Materialize to dsh_home.
        let dsh_home = temp.join("runtime/.dsh");
        std::fs::create_dir_all(&dsh_home).unwrap();
        crate::content::presets::materialize_presets(&temp, &dsh_home).unwrap();

        env::set_var(TEST_API_KEY_ENV, "sk-test-1234567890");
        let envs = build_engine_env(Provider::DeepSeek, &dsh_home).unwrap();

        let skill_dirs_val = envs
            .iter()
            .find(|(k, _)| k == "INKSTATUTE_SKILL_DIRS")
            .map(|(_, v)| v.as_str())
            .unwrap_or("");

        assert!(
            !skill_dirs_val.is_empty(),
            "INKSTATUTE_SKILL_DIRS should not be empty after materialization"
        );

        // Each path should be absolute.
        for path in skill_dirs_val.split(',') {
            assert!(
                std::path::Path::new(path).is_absolute(),
                "skill dir path should be absolute: {}",
                path
            );
        }

        env::remove_var(TEST_API_KEY_ENV);
        std::fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn load_key_prefers_test_env() {
        let _guard = lock_env_tests();
        env::set_var(TEST_API_KEY_ENV, "sk-prefer-test");
        let key = load_key(Provider::DeepSeek).unwrap();
        assert_eq!(key.as_deref(), Some("sk-prefer-test"));
        env::remove_var(TEST_API_KEY_ENV);
    }

    #[test]
    fn debug_never_prints_key() {
        let p = Provider::DeepSeek;
        let text = format!("{:?}", p);
        assert!(!text.starts_with("sk-"));
    }

    // --- Phase 128 / MMR-01..02: review capability ---

    #[test]
    fn classify_review_capability_variants_by_configured_count() {
        assert_eq!(classify_review_capability(vec![]), ReviewCapability::None);

        assert_eq!(
            classify_review_capability(vec![Provider::DeepSeek]),
            ReviewCapability::SingleVendor {
                provider: Provider::DeepSeek
            }
        );

        let three = vec![Provider::DeepSeek, Provider::OpenAI, Provider::Anthropic];
        assert_eq!(
            classify_review_capability(three.clone()),
            ReviewCapability::CrossVendor { providers: three }
        );
    }

    #[test]
    fn review_capability_debug_never_leaks_key_material() {
        let cap = classify_review_capability(vec![Provider::OpenAI, Provider::Anthropic]);
        let text = format!("{:?}", cap);
        // The Debug impl only ever formats Provider variant names (an enum
        // with no string payload) — it structurally cannot contain a key,
        // but assert the shape explicitly so this test fails loudly if a
        // future refactor adds a key-bearing field.
        assert!(!text.contains("sk-"));
        assert!(text.contains("OpenAI") && text.contains("Anthropic"));
    }

    #[test]
    fn provider_env_pairs_only_includes_given_providers() {
        let pairs = provider_env_pairs(&[
            (Provider::DeepSeek, "sk-a".to_string()),
            (Provider::OpenAI, "sk-b".to_string()),
        ]);
        assert_eq!(pairs.len(), 2);
        assert!(pairs
            .iter()
            .any(|(k, v)| k == "DEEPSEEK_API_KEY" && v == "sk-a"));
        assert!(pairs
            .iter()
            .any(|(k, v)| k == "OPENAI_API_KEY" && v == "sk-b"));
        // Anthropic was never in the input — proves build_engine_env only
        // ever emits vars for providers it was actually given, i.e. the
        // configured ones, and silently drops everything else.
        assert!(!pairs.iter().any(|(k, _)| k == "ANTHROPIC_API_KEY"));
    }

    #[test]
    fn configured_providers_and_build_engine_env_cover_every_provider_when_all_configured() {
        // TEST_API_KEY_ENV is provider-agnostic (see load_key's doc comment:
        // one value answers has_key() for every provider), so setting it
        // puts every provider into the "configured" state. That is exactly
        // what this test needs: prove configured_providers()/
        // build_engine_env() actually walk all nine providers, not just
        // `active`, end to end through the real credential-lookup path.
        let _guard = lock_env_tests();
        env::set_var(TEST_API_KEY_ENV, "sk-test-all-vendors");

        let configured = configured_providers();
        assert_eq!(configured.len(), 9, "every provider should report configured");

        let temp = env::temp_dir().join(format!(
            "inkstatute-build-env-multi-vendor-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::remove_dir_all(&temp).ok();
        std::fs::create_dir_all(&temp).unwrap();

        let envs = build_engine_env(Provider::DeepSeek, &temp).unwrap();
        for p in Provider::all() {
            assert!(
                envs.iter().any(|(k, v)| k == p.env_var() && !v.is_empty()),
                "expected {} to be injected for provider {}",
                p.env_var(),
                p.id()
            );
        }

        env::remove_var(TEST_API_KEY_ENV);
        std::fs::remove_dir_all(&temp).ok();
    }
}
