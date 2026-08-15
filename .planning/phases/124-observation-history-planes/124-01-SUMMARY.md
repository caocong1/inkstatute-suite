---
phase: 124-observation-history-planes
plan: "01"
subsystem: infra
tags: [tailer, ndjson, session-log, observation-plane, dsh]

requires:
  - phase: 122-engine-base-rebuild
    provides: assembled DSH engine writing session.jsonl + session-query.db
provides:
  - "events.rs: DSH session event model (SessionHeader, SessionEvent, AssistantChunk) parsing session.jsonl 1:1"
  - "tailer.rs: polling log tailer — half-line safe, file-shrink reread, seq-gap tolerant, LogNotFound timeout"
  - "is_real_user_message() filter — the only barrier to rendering system-injected user/message lines"
  - "Measured fixtures: session-sample.jsonl (14-line failure turn) + session-success.jsonl (full success turn)"
affects: [124-03, 125-ui-wiring, 127-delivery]

actuals:
  tokens: 1380
  tasks: 4
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Polling over notify for log tailing — simpler, cross-platform, no extra dep"
    - "Unknown DSH event types degrade to Other(String) — pre-release engine must never crash the tailer"
    - "data.source.kind == 'user' is the only real-user-message discriminator"

key-files:
  created:
    - apps/desktop/src-tauri/src/engine/events.rs
    - apps/desktop/src-tauri/src/engine/tailer.rs
    - apps/desktop/src-tauri/tests/fixtures/session-sample.jsonl
    - apps/desktop/src-tauri/tests/fixtures/session-success.jsonl
    - apps/desktop/src-tauri/tests/tailer_test.rs
  modified:
    - apps/desktop/src-tauri/src/engine/mod.rs

key-decisions:
  - "Polling (100ms) over notify crate — plan's stated preference; zero new deps"
  - "Locate log by scanning sessionsRoot/*/<sessionId>/session.jsonl — cwd-dir name is lossy, never reverse-resolve it"
  - "seq gaps emit SeqGap but tailing continues; non-JSON lines ignored, never abort"

patterns-established:
  - "Observation-plane reads files only; no DSH plugin authored in this repo"
  - "Fixtures committed to tests/fixtures/ are the gate inputs for GATE-12 (Plan 124-03)"

requirements-completed: [RTM-03]

coverage:
  - id: D1
    description: "DSH session event model parsing session.jsonl 1:1 with the measured schema"
    requirement: RTM-03
    verification:
      - kind: unit
        ref: tests/fixtures/session-sample.jsonl#sample_parses_fully
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/events.rs#exactly_one_real_user_message
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/events.rs#assistant_chunk_seven_types
        status: pass
    human_judgment: false
  - id: D2
    description: "Log tailer: half-line safe, file-shrink reread, LogNotFound timeout, seq-gap tolerant, stop/Closed"
    requirement: RTM-03
    verification:
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/tailer.rs#half_line_buffered_until_completion
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/tailer.rs#truncated_file_reread_from_start
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/tailer.rs#file_never_appears_emits_lognotfound
        status: pass
      - kind: unit
        ref: apps/desktop/src-tauri/src/engine/tailer.rs#seq_gap_emitted_but_tailing_continues
        status: pass
    human_judgment: false
  - id: D3
    description: "Real-engine log tail integration — full event stream observed end-to-end"
    requirement: RTM-03
    verification:
      - kind: integration
        ref: apps/desktop/src-tauri/tests/tailer_test.rs#tail_real_engine_session
        status: unknown
    human_judgment: true
    rationale: "#[ignore] test requires network + node + engine assembly; not run in offline gate. Run manually with cargo test -- --ignored tail_real_engine_session."

duration: 18min
completed: 2026-08-15
status: complete
---

# Phase 124 Plan 01: Session Log Tailer Summary

**Polling NDJSON tailer + 1:1 DSH event model with system-injected-message filtering, validated against a measured 14-line failure-turn fixture**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-08-15
- **Completed:** 2026-08-15
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments
- `events.rs` parses `session.jsonl` lines 1:1 with the measured DSH schema: `SessionHeader`, `SessionEvent` (19 kinds + `Other` fallback), `AssistantChunk` (7 variants). `is_real_user_message()` filters system-injected `user/message` lines via `data.source.kind == "user"` — the only barrier to rendering runtime context snapshots and skill listings as user turns.
- `tailer.rs` locates `<sessionsRoot>/*/<sessionId>/session.jsonl` by scanning top-level dirs (cwd-dir name is lossy, never reverse-resolved), then incrementally reads new bytes every 100ms. Only complete `\n`-terminated lines are emitted; partial trailing reads are buffered. File shrink resets offset to 0 and rereads. `seq` gaps emit `SeqGap` but tailing continues. Non-JSON lines ignored. `stop()` and `Drop` both terminate the loop and emit `Closed`.
- Two committed fixtures: `session-sample.jsonl` (14-line measured failure turn) and `session-success.jsonl` (full success turn: text/reasoning/tool deltas, tool call+result, usage, assistant/message, turn/end stop). These are the gate inputs for GATE-12 in Plan 124-03.
- `#[ignore]` integration test `tail_real_engine_session` assembles + spawns the real engine, sends a prompt with a fake key (failed turn still produces the full event stream), and asserts the tailer observes Header/TurnStart/StepStart/exactly-one-real-user-message/SessionTitle/RequestHeader/RequestContext/TurnEnd. Records `session.jsonl` byte size for the volume assessment.

## Task Commits

1. **Task 1+2: event model + fixtures** - `0b96b0d0` (feat)
2. **Task 3: tailer** - `378a51b3` (feat)
3. **Task 4: real-engine integration test** - `c0077a46` (test)

## Files Created/Modified
- `apps/desktop/src-tauri/src/engine/events.rs` - DSH session event model + parse_line + is_real_user_message
- `apps/desktop/src-tauri/src/engine/tailer.rs` - polling log tailer
- `apps/desktop/src-tauri/src/engine/mod.rs` - register events + tailer modules
- `apps/desktop/src-tauri/tests/fixtures/session-sample.jsonl` - 14-line measured failure turn
- `apps/desktop/src-tauri/tests/fixtures/session-success.jsonl` - full success turn
- `apps/desktop/src-tauri/tests/tailer_test.rs` - #[ignore] real-engine integration test

## Decisions Made
- Polling (100ms) over `notify` crate — plan's stated preference; zero new deps, simpler and reliable cross-platform.
- Locate log by scanning `sessionsRoot/*/<sessionId>/session.jsonl` rather than reverse-engineering the lossy cwd-dir normalization.
- `seq` gaps emit `SeqGap` but tailing continues (engine crash-recovery may truncate); non-JSON lines ignored, never abort.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Observation-plane read primitives ready for Plan 124-03's event mapper (consumes `SessionEvent`/`AssistantChunk`).
- Fixtures ready for GATE-12's reducer end-to-end assertion.
- Real-engine integration test deferred to manual run (network + node required); offline gate uses the committed fixtures.

---
*Phase: 124-observation-history-planes*
*Completed: 2026-08-15*
