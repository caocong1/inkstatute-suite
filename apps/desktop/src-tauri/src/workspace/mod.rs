//! Workspace indexing pipeline: scan → parse → chunk → per-root SQLite FTS5.
//!
//! Index DB path: `{app_data_dir}/workspaces/{root_hash}/index.db`
//!
//! Ported from lawyer-desktop. The FTS5 index is a desktop-specific enhancement
//! that allows lawyers to search their local workspace files.

pub mod chunker;
pub mod index_store;
pub mod manager;
pub mod parser;
pub mod scanner;

pub use index_store::ChunkDetail;
pub use manager::{
    bind_and_index, get_status, get_status_for_path, hash_root_path, list_files, read_chunk,
    read_file_relative, search, set_app_data_dir, IndexProgress, IndexStats, WorkspaceStatus,
};
