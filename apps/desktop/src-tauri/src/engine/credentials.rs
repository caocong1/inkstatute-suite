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

/// Stores an API key in the OS credential store.
/// The key is never written to files, logs, or command-line arguments.
pub fn store_key(p: Provider, key: &str) -> Result<(), EngineError> {
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, p.id()).map_err(|e| EngineError::Credential(e.to_string()))?;
    entry
        .set_password(key)
        .map_err(|e| EngineError::Credential(e.to_string()))
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
    #[cfg(debug_assertions)]
    if let Ok(test_key) = std::env::var(TEST_API_KEY_ENV) {
        if !test_key.is_empty() {
            return Ok(Some(test_key));
        }
    }
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, p.id()).map_err(|e| EngineError::Credential(e.to_string()))?;
    match entry.get_password() {
        Ok(key) => Ok(Some(key)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(EngineError::Credential(e.to_string())),
    }
}

/// Deletes an API key from the OS credential store.
pub fn delete_key(p: Provider) -> Result<(), EngineError> {
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, p.id()).map_err(|e| EngineError::Credential(e.to_string()))?;
    match entry.delete_credential() {
        Ok(_) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(EngineError::Credential(e.to_string())),
    }
}

/// Returns whether a key exists in the OS credential store for this provider.
/// This never returns the key content, so it is safe to call from UI code.
pub fn has_key(p: Provider) -> bool {
    match keyring::Entry::new(KEYRING_SERVICE, p.id()) {
        Ok(entry) => matches!(entry.get_password(), Ok(s) if !s.is_empty()),
        Err(_) => false,
    }
}

/// Builds the environment variables passed to the engine subprocess.
/// Inherits the current process environment and adds `DSH_HOME`, the
/// active provider's API key variable, and `INKSTATUTE_SKILL_DIRS` (the
/// comma-separated absolute paths to materialized domain skill directories).
/// The returned value must not be logged.
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

    let key = load_key(active)?.ok_or_else(|| EngineError::MissingApiKey(active.id().to_string()))?;
    envs.push((active.env_var().to_string(), key));
    Ok(envs)
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
}
