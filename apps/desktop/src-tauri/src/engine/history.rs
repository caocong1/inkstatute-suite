//! Read-only history plane over the engine-owned `session-query.db`.
//!
//! The engine's persistence plugin maintains `<sessionsRoot>/session-query.db`
//! with the schema documented in 124-02-PLAN.md (`persisted_sessions` +
//! `persisted_docs` FTS5). This module opens it **read-only** and exposes
//! session listing, full-text search, and per-session doc retrieval. The app
//! never writes to this database — writing would break the engine's
//! generation/revision consistency.
//!
//! Read-only is enforced structurally: `SqliteConnectOptions::read_only(true)`
//! and `create_if_missing(false)`. A unit test asserts that an `INSERT` is
//! rejected — this is the key safety guarantee. A SQLite `busy_timeout` of
//! 150ms is also set so concurrent engine writes don't surface as BUSY errors
//! to reads; application-level retry is a secondary safety net.

use std::path::Path;
use std::time::Duration;

use serde::Serialize;
use sqlx::sqlite::{SqliteConnectOptions, SqlitePool, SqlitePoolOptions, SqliteRow};
use sqlx::Row;

use super::EngineError;

const BUSY_RETRIES: u32 = 3;
const BUSY_BACKOFF: Duration = Duration::from_millis(50);

#[derive(Debug, Clone, Serialize)]
pub struct SessionSummary {
    pub id: String,
    pub created_at: i64,
    pub cwd: Option<String>,
    pub agent_preset: Option<String>,
    /// First `session/title` doc text for the session, else the first 40 chars
    /// of the first `user/message` doc. `None` only if neither exists.
    pub title: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SearchHit {
    pub session_id: String,
    pub seq: i64,
    pub time: i64,
    pub doc_type: String,
    /// FTS5 `snippet()` output with `<mark>` wrapping the match.
    pub snippet: String,
}

pub struct HistoryStore {
    pool: SqlitePool,
}

impl HistoryStore {
    /// Open the engine's `session-query.db` read-only. Returns `Ok(None)` when
    /// the database file does not yet exist (first run, or the engine has not
    /// produced any sessions). Never creates the file.
    pub async fn open(sessions_root: &Path) -> Result<Option<Self>, EngineError> {
        let db_path = sessions_root.join("session-query.db");
        if !db_path.is_file() {
            return Ok(None);
        }

        let options = SqliteConnectOptions::new()
            .filename(&db_path)
            .read_only(true)
            .create_if_missing(false)
            .immutable(false)
            .busy_timeout(Duration::from_millis(150));

        let pool = SqlitePoolOptions::new()
            .max_connections(4)
            .connect_with(options)
            .await?;

        Ok(Some(Self { pool }))
    }

    /// List sessions, newest first (`created_at` descending), paginated.
    pub async fn list_sessions(
        &self,
        limit: i64,
        offset: i64,
    ) -> Result<Vec<SessionSummary>, EngineError> {
        let rows = retry_fetch_all(&self.pool, || {
            sqlx::query(
                "SELECT id, created_at, cwd, agent_preset \
                 FROM persisted_sessions \
                 ORDER BY created_at DESC \
                 LIMIT ? OFFSET ?",
            )
            .bind(limit)
            .bind(offset)
        })
        .await?;

        let mut out = Vec::with_capacity(rows.len());
        for row in rows {
            let id: String = row.try_get("id")?;
            let created_at: i64 = row.try_get("created_at")?;
            let cwd: Option<String> = row.try_get("cwd")?;
            let agent_preset: Option<String> = row.try_get("agent_preset")?;
            let title = self.title_for_session(&id).await?;
            out.push(SessionSummary {
                id,
                created_at,
                cwd,
                agent_preset,
                title,
            });
        }
        Ok(out)
    }

    pub async fn session_count(&self) -> Result<i64, EngineError> {
        let row = retry_fetch_one(&self.pool, || {
            sqlx::query("SELECT COUNT(*) AS n FROM persisted_sessions")
        })
        .await?;
        let n: i64 = row.try_get("n")?;
        Ok(n)
    }

    /// FTS5 full-text search across `persisted_docs`. The query is escaped
    /// (each whitespace-split term double-quoted with internal `"` doubled)
    /// so user input cannot produce a syntax error or injection.
    pub async fn search(&self, query: &str, limit: i64) -> Result<Vec<SearchHit>, EngineError> {
        let escaped = escape_fts5_query(query);
        if escaped.is_empty() {
            return Ok(Vec::new());
        }
        let sql = "SELECT session_id, seq, time, type, \
                   snippet(persisted_docs, 0, '<mark>', '</mark>', '…', 24) AS snip \
                   FROM persisted_docs \
                   WHERE persisted_docs MATCH ? \
                   ORDER BY time DESC \
                   LIMIT ?";
        // Clone escaped into an owned String so the bind is 'static.
        let escaped_owned = escaped.clone();
        let rows = retry_fetch_all(&self.pool, || {
            sqlx::query(sql).bind(escaped_owned.clone()).bind(limit)
        })
        .await?;

        let mut out = Vec::with_capacity(rows.len());
        for row in rows {
            out.push(SearchHit {
                session_id: row.try_get("session_id")?,
                seq: row.try_get("seq")?,
                time: row.try_get("time")?,
                doc_type: row.try_get("type")?,
                snippet: row.try_get("snip")?,
            });
        }
        Ok(out)
    }

    /// All docs for a session, ordered by `seq` ascending — used by replay
    /// (RTM-07) to pull prior conversation turns from the history plane.
    pub async fn session_docs(&self, session_id: &str) -> Result<Vec<SearchHit>, EngineError> {
        let sid_owned = session_id.to_string();
        let rows = retry_fetch_all(&self.pool, || {
            sqlx::query(
                "SELECT session_id, seq, time, type, \
                        snippet(persisted_docs, 0, '<mark>', '</mark>', '…', 64) AS snip \
                 FROM persisted_docs \
                 WHERE session_id = ? \
                 ORDER BY seq ASC",
            )
            .bind(sid_owned.clone())
        })
        .await?;

        let mut out = Vec::with_capacity(rows.len());
        for row in rows {
            out.push(SearchHit {
                session_id: row.try_get("session_id")?,
                seq: row.try_get("seq")?,
                time: row.try_get("time")?,
                doc_type: row.try_get("type")?,
                snippet: row.try_get("snip")?,
            });
        }
        Ok(out)
    }

    /// Resolve a session's display title: the first `session/title` doc's
    /// text, else the first 40 chars of the first `user/message` doc.
    async fn title_for_session(&self, session_id: &str) -> Result<Option<String>, EngineError> {
        let sid_owned = session_id.to_string();
        let row = retry_fetch_optional(&self.pool, || {
            sqlx::query(
                "SELECT text FROM persisted_docs \
                 WHERE session_id = ? AND type = 'session/title' \
                 ORDER BY seq ASC LIMIT 1",
            )
            .bind(sid_owned.clone())
        })
        .await?;

        if let Some(r) = row {
            let text: String = r.try_get("text")?;
            let trimmed = text.trim();
            if !trimmed.is_empty() {
                return Ok(Some(trimmed.to_string()));
            }
        }

        let sid_owned = session_id.to_string();
        let row = retry_fetch_optional(&self.pool, || {
            sqlx::query(
                "SELECT text FROM persisted_docs \
                 WHERE session_id = ? AND type = 'user/message' \
                 ORDER BY seq ASC LIMIT 1",
            )
            .bind(sid_owned.clone())
        })
        .await?;

        if let Some(r) = row {
            let text: String = r.try_get("text")?;
            let chars: String = text.chars().take(40).collect();
            if !chars.is_empty() {
                return Ok(Some(chars));
            }
        }
        Ok(None)
    }
}

/// Escape a user query for FTS5 MATCH: split on whitespace, double-quote each
/// term (doubling internal `"`), join with spaces (implicit AND).
///
/// Example: `合同 "第三条"` → `"合同" "第三条"""`.
/// Bare `*`, `^`, `AND`/`OR`/`NOT` become harmless quoted phrases.
fn escape_fts5_query(input: &str) -> String {
    input
        .split_whitespace()
        .map(|term| {
            let escaped = term.replace('"', "\"\"");
            format!("\"{escaped}\"")
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// Classify a sqlx error as retriable (SQLITE_BUSY/SQLITE_LOCKED) or not.
fn is_busy(err: &sqlx::Error) -> bool {
    if let sqlx::Error::Database(db) = err {
        let code = db.code().unwrap_or_default();
        return code == "SQLITE_BUSY" || code == "SQLITE_LOCKED";
    }
    false
}

/// Retry `fetch_all` on SQLITE_BUSY/LOCKED up to [`BUSY_RETRIES`] times.
/// `sqlx::Query` is single-use, so the closure rebuilds it each attempt.
async fn retry_fetch_all<F>(pool: &SqlitePool, build: F) -> Result<Vec<SqliteRow>, EngineError>
where
    F: Fn() -> sqlx::query::Query<'static, sqlx::Sqlite, sqlx::sqlite::SqliteArguments<'static>>,
{
    let mut last_err: Option<sqlx::Error> = None;
    for attempt in 0..BUSY_RETRIES {
        if attempt > 0 {
            tokio::time::sleep(BUSY_BACKOFF).await;
        }
        match build().fetch_all(pool).await {
            Ok(rows) => return Ok(rows),
            Err(e) if is_busy(&e) => {
                last_err = Some(e);
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }
    Err(EngineError::Protocol(format!(
        "history db busy after {BUSY_RETRIES} retries: {:?}",
        last_err
    )))
}

/// Retry `fetch_one` on SQLITE_BUSY/LOCKED.
async fn retry_fetch_one<F>(pool: &SqlitePool, build: F) -> Result<SqliteRow, EngineError>
where
    F: Fn() -> sqlx::query::Query<'static, sqlx::Sqlite, sqlx::sqlite::SqliteArguments<'static>>,
{
    let mut last_err: Option<sqlx::Error> = None;
    for attempt in 0..BUSY_RETRIES {
        if attempt > 0 {
            tokio::time::sleep(BUSY_BACKOFF).await;
        }
        match build().fetch_one(pool).await {
            Ok(row) => return Ok(row),
            Err(e) if is_busy(&e) => {
                last_err = Some(e);
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }
    Err(EngineError::Protocol(format!(
        "history db busy after {BUSY_RETRIES} retries: {:?}",
        last_err
    )))
}

/// Retry `fetch_optional` on SQLITE_BUSY/LOCKED.
async fn retry_fetch_optional<F>(
    pool: &SqlitePool,
    build: F,
) -> Result<Option<SqliteRow>, EngineError>
where
    F: Fn() -> sqlx::query::Query<'static, sqlx::Sqlite, sqlx::sqlite::SqliteArguments<'static>>,
{
    let mut last_err: Option<sqlx::Error> = None;
    for attempt in 0..BUSY_RETRIES {
        if attempt > 0 {
            tokio::time::sleep(BUSY_BACKOFF).await;
        }
        match build().fetch_optional(pool).await {
            Ok(row) => return Ok(row),
            Err(e) if is_busy(&e) => {
                last_err = Some(e);
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }
    Err(EngineError::Protocol(format!(
        "history db busy after {BUSY_RETRIES} retries: {:?}",
        last_err
    )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;

    /// Build a temp `session-query.db` with the engine's schema and insert
    /// sample rows. Returns the directory containing the db.
    async fn build_sample_db() -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "inkstatute-history-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        let db_path = dir.join("session-query.db");

        let options = SqliteConnectOptions::new()
            .filename(&db_path)
            .create_if_missing(true);
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect_with(options)
            .await
            .unwrap();

        sqlx::query(
            "CREATE TABLE persisted_sessions (\
               id TEXT PRIMARY KEY, version INTEGER NOT NULL, created_at INTEGER NOT NULL, \
               cwd TEXT, parent_session TEXT, seed_length INTEGER, delegation_depth INTEGER, \
               agent_preset TEXT, revision TEXT NOT NULL, generation INTEGER NOT NULL\
             ) STRICT",
        )
        .execute(&pool)
        .await
        .unwrap();

        sqlx::query(
            "CREATE VIRTUAL TABLE persisted_docs USING fts5(\
               text, session_id UNINDEXED, seq UNINDEXED, type UNINDEXED, time UNINDEXED, \
               surface UNINDEXED, codepoint_length UNINDEXED, tokenize='unicode61'\
             )",
        )
        .execute(&pool)
        .await
        .unwrap();

        sqlx::query("INSERT INTO persisted_sessions (id, version, created_at, cwd, parent_session, seed_length, delegation_depth, agent_preset, revision, generation) VALUES ('s1', 0, 1000, '/ws', NULL, 0, 0, NULL, 'r1', 1)")
            .execute(&pool).await.unwrap();
        sqlx::query("INSERT INTO persisted_sessions (id, version, created_at, cwd, parent_session, seed_length, delegation_depth, agent_preset, revision, generation) VALUES ('s2', 0, 2000, '/ws2', NULL, 0, 0, NULL, 'r1', 1)")
            .execute(&pool).await.unwrap();

        sqlx::query("INSERT INTO persisted_docs (text, session_id, seq, type, time, surface, codepoint_length) VALUES ('买卖合同违约案件', 's1', 7, 'session/title', 1001, 'append', 8)")
            .execute(&pool).await.unwrap();
        sqlx::query("INSERT INTO persisted_docs (text, session_id, seq, type, time, surface, codepoint_length) VALUES ('审查买卖合同第三条违约金条款', 's1', 4, 'user/message', 1002, 'append', 14)")
            .execute(&pool).await.unwrap();
        sqlx::query("INSERT INTO persisted_docs (text, session_id, seq, type, time, surface, codepoint_length) VALUES ('法国的首都是什么', 's2', 4, 'user/message', 2001, 'append', 8)")
            .execute(&pool).await.unwrap();
        // Latin-script doc so FTS5 unicode61 tokenization yields a searchable token.
        sqlx::query("INSERT INTO persisted_docs (text, session_id, seq, type, time, surface, codepoint_length) VALUES ('contract breach case summary', 's1', 8, 'assistant/message', 1003, 'append', 28)")
            .execute(&pool).await.unwrap();

        pool.close().await;
        dir
    }

    #[tokio::test]
    async fn open_missing_db_returns_none() {
        let temp = std::env::temp_dir().join(format!(
            "inkstatute-history-missing-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&temp).unwrap();
        let store = HistoryStore::open(&temp).await.unwrap();
        assert!(store.is_none(), "missing db should yield Ok(None)");
        fs::remove_dir_all(&temp).ok();
    }

    #[tokio::test]
    async fn list_sessions_and_count() {
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        let count = store.session_count().await.unwrap();
        assert_eq!(count, 2);
        let sessions = store.list_sessions(10, 0).await.unwrap();
        assert_eq!(sessions.len(), 2);
        // Newest first → s2 (created_at 2000) then s1.
        assert_eq!(sessions[0].id, "s2");
        assert_eq!(sessions[1].id, "s1");
        assert_eq!(sessions[1].title.as_deref(), Some("买卖合同违约案件"));
        assert_eq!(sessions[0].title.as_deref(), Some("法国的首都是什么"));
        fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn search_hits_with_mark() {
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        // Search for a Latin-script token that unicode61 can tokenize.
        let hits = store.search("contract", 10).await.unwrap();
        assert!(!hits.is_empty(), "should find contract mentions");
        assert!(
            hits.iter().all(|h| h.snippet.contains("<mark>")),
            "every snippet should wrap the match in <mark>"
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn search_cjk_no_panic() {
        // CJK runs are single tokens under unicode61; the plan requires
        // "works without panic" not "returns results."
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        let _ = store.search("合同", 10).await.unwrap();
        let _ = store.search("合同 \"第三条\"", 10).await.unwrap();
        fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn search_special_chars_no_error() {
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        let _ = store.search("*", 10).await.unwrap();
        let _ = store.search("^", 10).await.unwrap();
        let _ = store.search("AND OR NOT", 10).await.unwrap();
        fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn session_docs_ordered_by_seq() {
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        let docs = store.session_docs("s1").await.unwrap();
        assert!(docs.len() >= 2);
        let mut prev = i64::MIN;
        for d in &docs {
            assert!(d.seq >= prev, "docs must be seq-ascending");
            prev = d.seq;
        }
        fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn write_is_rejected() {
        let dir = build_sample_db().await;
        let store = HistoryStore::open(&dir).await.unwrap().unwrap();
        let result = sqlx::query("INSERT INTO persisted_sessions (id, version, created_at, cwd, parent_session, seed_length, delegation_depth, agent_preset, revision, generation) VALUES ('x', 0, 1, '/', NULL, 0, 0, NULL, 'r', 1)")
            .execute(&store.pool)
            .await;
        assert!(
            result.is_err(),
            "write must be rejected on a read-only connection"
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn escape_fts5_examples() {
        assert_eq!(escape_fts5_query("合同"), "\"合同\"");
        assert_eq!(escape_fts5_query("合同 第三条"), "\"合同\" \"第三条\"");
        assert_eq!(escape_fts5_query("a\"b"), "\"a\"\"b\"");
        assert_eq!(escape_fts5_query(""), "");
        assert_eq!(escape_fts5_query("   "), "");
    }
}
