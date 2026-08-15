pub mod assemble;
pub mod lock;
pub mod paths;
pub mod smoke;

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
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Http(#[from] reqwest::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}
