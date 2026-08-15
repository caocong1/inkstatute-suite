pub mod acp;
pub mod assemble;
pub mod credentials;
pub mod events;
pub mod history;
pub mod lock;
pub mod mapper;
pub mod paths;
pub mod replay;
pub mod runtime;
pub mod session_map;
pub mod smoke;
pub mod supervisor;
pub mod tailer;

use thiserror::Error;

#[derive(Debug, Error)]
pub enum EngineError {
    #[error("engine lock schema {0} is not supported")]
    UnsupportedLockSchema(String),
    #[error("lock entry {0} has malformed integrity")]
    BadIntegrity(String),
    #[error("integrity check failed for {0}")]
    IntegrityMismatch(String),
    #[error("destination is not empty: {0}")]
    DestNotEmpty(String),
    #[error("tar entry escapes destination")]
    PathTraversal,
    #[error("acp.cordis.yml does not match lock sha256")]
    CordisConfigMismatch,
    #[error("assembled engine is missing lib/bin.js")]
    MissingEntrypoint,
    #[error("failed to download {0} from both registries")]
    DownloadFailed(String),
    #[error("app data directory not resolvable")]
    NoAppRoot,
    #[error("API key not available for provider {0}")]
    MissingApiKey(String),
    #[error("prompt is already in flight for session {0}")]
    PromptInFlight(String),
    #[error("current working directory must be an absolute path")]
    CwdNotAbsolute,
    #[error("engine disconnected")]
    Disconnected,
    #[error("engine protocol error: {0}")]
    Protocol(String),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Http(#[from] reqwest::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Sqlx(#[from] sqlx::Error),
    #[error("credential store error: {0}")]
    Credential(String),
}
