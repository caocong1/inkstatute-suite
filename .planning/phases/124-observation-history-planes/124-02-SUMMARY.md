---
phase: 124-observation-history-planes
plan: "02"
subsystem: database
tags: [sqlite, fts5, read-only, history-plane, session-query-db]

requires:
  - phase: 122-engine-base-rebuild
    provides: engine writing session-query.db with persisted_sessions + persisted_docs FTS5
provides:
  - "history.rs: read-only HistoryStore over session-query.db (list, count, search, session_docs, title resolution)"
  - "Three Tauri commands: list_conversations, search_conversations, get_conversation_docs"
  - "FTS5 query escaping — bare *, ^, AND/OR/NOT become harmless quoted phrases"
  - "Write-rejection safety guarantee (unit tested)"
affects: [125-ui-wiring, 127-delivery]

actuals:
  tokens: 1100
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Read-only SQLite: read_only(true) + create_if_missing(false) + busy_timeout(150ms)"
    - "FTS5 MATCH escaping: split → double-quote → double internal quotes → join"
    - "SQLITE_BUSY/LOCKED retry: 3x with 50ms backoff, rebuild Query each attempt"

key-files:
  created:
    - apps/desktop/src-tauri/src/engine/history.rs
    - apps/desktop/src-tauri/src/commands/history.rs
    - apps/desktop/src-tauri/tests/history_test.rs
  modified:
    - apps/desktop/src-tauri/src/engine/mod.rs
    - apps/desktop/src-tauri/src/commands/mod.rs
    - apps/desktop/src-tauri/src/lib.rs

key-decisions:
  - "SqliteConnectOptions::new().filename() not from_url() — sqlx 0.8 API"
  - "busy_timeout(150ms) at SQLite level + application-level 3x retry as secondary safety net"
  - "CJK search under unicode61 is no-panic not guaranteed-hit — CJK runs are single tokens"
  - "offline_cache removed from generate_handler! per plan; legacy file slated for 125 deletion"

patterns-established:
  - "History commands return empty arrays when DB missing, never error to UI"
  - "Error details go to stderr only; UI sees 读取会话历史失败"

requirements-completed: [RTM-04]

coverage:
  - id: D1
    description: "Read-only HistoryStore over session-query.db"
    requirement: RTM-04
    verification:
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#open_missing_db_returns_none
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#list_sessions_and_count
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#write_is_rejected
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#search_hits_with_mark
        status: pass
    human_judgment: false
  - id: D2
    description: "FTS5 query escaping — special input does not produce SQL errors"
    requirement: RTM-04
    verification:
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#search_special_chars_no_error
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#search_cjk_no_panic
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/history.rs#escape_fts5_examples
        status: pass
    human_judgment: false
  - id: D3
    description: "Tauri commands: list_conversations, search_conversations, get_conversation_docs"
    requirement: RTM-04
    verification:
      - kind: integration
        ref: apps/desktop/src-tauri/tests/history_test.rs#missing_db_command_returns_empty
        status: pass
      - kind: integration
        ref: apps/desktop/src-tauri/tests/history_test.rs#missing_db_list_returns_empty_vec
        status: pass
    human_judgment: false
  - id: D4
    description: "Real-engine history query — ≥2 sessions, titles, search hits"
    requirement: RTM-04
    verification:
      - kind: integration
        ref: apps/desktop/src-tauri/tests/history_test.rs#query_real_engine_history
        status: unknown
    human_judgment: true
    rationale: "#[ignore] test requires network + node + engine assembly. Run manually with cargo test -- --ignored query_real_engine_history."

duration: 12min
completed: 2026-08-15
status: complete
---

# Phase 124 Plan 02: Read-Only History Plane Summary

**Read-only SQLite history plane with FTS5 search, write-rejection safety, and three Tauri commands replacing the legacy offline_cache handler**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-15
- **Completed:** 2026-08-15
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `history.rs` opens the engine-owned `session-query.db` **read-only** (`read_only(true)` + `create_if_missing(false)` + `busy_timeout(150ms)`) and exposes `list_sessions`, `session_count`, `search`, `session_docs`, and title resolution (first `session/title` doc, else first 40 chars of first `user/message` doc). Missing DB returns `Ok(None)`.
- FTS5 query escaping: each whitespace-split term is double-quoted with internal `"` doubled — bare `*`, `^`, `AND`/`OR`/`NOT` become harmless quoted phrases. `SQLITE_BUSY`/`LOCKED` retried 3× with 50ms backoff (Query rebuilt each attempt since it's single-use).
- Three Tauri commands registered: `list_conversations`, `search_conversations`, `get_conversation_docs`. Defaults: `limit=50`, `offset=0`. Missing DB → empty arrays. Errors surface user-readable Chinese `读取会话历史失败`; details go to stderr only. All 8 `offline_cache::*` entries removed from `generate_handler!`.
- Unit test `write_is_rejected` proves an `INSERT` against the read-only pool fails — the key safety guarantee. Production code has zero write statements (awk-verified past `#[cfg(test)]`).

## Task Commits

1. **Task 1: history.rs** - `bbbdd605` (feat)
2. **Task 2: commands + handler** - `ee316cb6` (feat)
3. **Task 3: integration tests** - `3510ad34` (test)

## Files Created/Modified
- `apps/desktop/src-tauri/src/engine/history.rs` - read-only HistoryStore
- `apps/desktop/src-tauri/src/commands/history.rs` - three Tauri commands
- `apps/desktop/src-tauri/src/commands/mod.rs` - register history module
- `apps/desktop/src-tauri/src/engine/mod.rs` - register history module + EngineError::Sqlx
- `apps/desktop/src-tauri/src/lib.rs` - register history commands, remove offline_cache
- `apps/desktop/src-tauri/tests/history_test.rs` - integration tests + #[ignore] real-engine

## Decisions Made
- `SqliteConnectOptions::new().filename()` not `from_url()` — sqlx 0.8 API.
- `busy_timeout(150ms)` at SQLite level + application-level 3× retry as secondary safety net.
- CJK search under `unicode61` is no-panic not guaranteed-hit — CJK runs are single tokens. The plan's test requirement is "works without panic," not "returns results."
- `offline_cache` removed from `generate_handler!` per plan; legacy file slated for deletion in Phase 125.

## Deviations from Plan

### Auto-fixed Issues

**1. [Parallel test flakiness] AtomicU64 counter for temp DB directories**
- **Found during:** Task 3 (integration tests)
- **Issue:** `build_sample_db` used nanosecond timestamps for temp directory names; parallel tests got the same value and collided.
- **Fix:** Replaced with a `static AtomicU64` counter (`DB_COUNTER.fetch_add`).
- **Files modified:** `src/engine/history.rs`
- **Verification:** All 8 unit tests pass under `cargo test --lib engine::history`.
- **Committed in:** `3510ad34`

---

**Total deviations:** 1 auto-fixed (parallel test safety)
**Impact on plan:** No scope creep — test infrastructure fix only.

## Issues Encountered
- `SqliteConnectOptions::from_url()` is private in sqlx 0.8; switched to `new().filename()`.
- `sqlx::Query` is single-use (`'static` lifetime); closures that capture borrows don't work. Fixed by cloning owned `String`s into each `bind()` call.
- `db.code()` returns `Cow<'_, str>`, not `&str`; `matches!` pattern needed adjustment.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- History plane ready for Phase 125's ConversationDrawer and search panel UI wiring.
- `session_docs` available for replay (RTM-07) to pull prior turns from the history plane.
- Real-engine history test deferred to manual run (network + node required).

---
*Phase: 124-observation-history-planes*
*Completed: 2026-08-15*
