---
phase: 107
slug: arena-engine-modes-1-2
status: complete
created: 2026-08-09
---

# Phase 107 — Technical Research

## 1. Arena Engine Package Structure

**Findings:**
- No existing `packages/arena-engine/` directory — new package to be created
- Phase 105 defined contract foundation: `ArenaWorkflowConfig`, `ArenaHandle`, `ArenaStatus`, `ArenaUserAction` (arena_contract.py), `ArenaWorkflow` Protocol (protocols.py lines 284-291), 8 Arena event types (enums.py lines 126-133), Arena event payloads (unified_events.py lines 163-230)
- `FakeArenaWorkflow` exists in platform-runtime/fakes.py (lines 321-375) as protocol mock
- Gate coverage meta-test enforces all `packages/*/src` directories must be covered by a gate

**Recommended package structure:**
```
packages/arena-engine/
├── pyproject.toml
├── src/
│   └── arena_engine/
│       ├── __init__.py
│       ├── engine.py              # ArenaEngine class implementing ArenaWorkflow
│       ├── mode1.py               # Mode 1 (standard parallel)
│       ├── mode2.py               # Mode 2 (self-score iteration)
│       ├── slot_runner.py         # Per-agent-slot execution + exception isolation
│       ├── artifact_store.py      # Structured output persistence
│       ├── guardrail_boundary.py  # Post-hoc guardrails for external ACP agents
│       ├── provenance.py          # Provenance logging (agent → reviewer → source)
│       └── mock_acp.py            # Mock ACP adapter for testing
└── tests/
    ├── test_engine.py
    ├── test_mode1.py
    ├── test_mode2.py
    ├── test_slot_runner.py
    ├── test_artifact_store.py
    ├── test_guardrail_boundary.py
    ├── test_provenance.py
    ├── test_no_llm_imports.py     # ENGINE-05 gate
    └── test_fresh_context.py      # ENGINE-06 gate
```

**Zero runtime dependencies** — only stdlib asyncio + existing platform packages.

## 2. Mode 1 (Standard Parallel) Design

**Findings:**
- `ArenaWorkflowStartedPayload` includes `agent_slots: list[str]` (unified_events.py lines 163-168)
- `ArenaUserAction` has `selected_slot: str | None` (arena_contract.py lines 40-44)
- `ACPBackendAdapter.submit_run()` spawns per-session subprocess (adapter.py lines 260-324)
- `asyncio.create_task()` for background event collection (adapter.py line 312)

**Implementation approach (mode1.py):**
- `run_mode1_parallel(config, agent_adapters, event_emitter)` — uses `asyncio.TaskGroup` to run N agents in parallel
- Each agent slot runs via `slot_runner.run_agent_slot()` which calls `adapter.submit_run()` + `adapter.stream_events()`
- All events tagged with `metadata={"arena_id": ..., "agent_slot": slot_id, "arena_phase": "mode1_parallel"}`
- User selects result via `submit_user_action()` with `action="select"` and `selected_slot`
- Emits `arena.workflow_started` at start, `arena.workflow_completed` at end

**Patterns to follow:**
- `asyncio.TaskGroup` (Python 3.11+) for structured concurrency
- `ACPBackendAdapter._collect_events()` pattern for background event streaming (adapter.py lines 500-527)
- `FakeBackendAdapter.append_message_delta()` for event injection (fakes.py lines 168-186)

**Anti-patterns:**
- Do NOT use `asyncio.gather()` without TaskGroup — exceptions won't be isolated
- Do NOT share state between agent slots — each slot must be independent
- Do NOT emit events without `agent_slot` metadata — demultiplexing will fail

## 3. Mode 2 (Self-score Iteration) Design

**Findings:**
- `ArenaScoreRecordedPayload` exists (unified_events.py lines 181-186) with `arena_id`, `agent_slot`, `round`, `score`
- `ArenaWorkflowConfig.max_rounds` defaults to 3 (arena_contract.py line 17)
- User triggers stop via `submit_user_action()` with `action="stop"`
- `ArenaEarlyStopTriggeredPayload` for early stop events (unified_events.py lines 220-230)

**Implementation approach (mode2.py):**
- `run_mode2_iteration(config, agent_adapters, event_emitter, stop_signal)` — iteration loop
- Each round: run all agents → self-score via 10-point framework → emit `arena.score_recorded` → track best
- `asyncio.Event` for cooperative cancellation (stop signal)
- On stop: emit `arena.early_stop_triggered` with `reason="user_stopped"` + preserve best results
- 10-point framework is **free-form** (not fixed dimensions) per research
- Best result per slot preserved in `best_results: dict[str, IterationState]`

**Anti-patterns:**
- Do NOT auto-stop on convergence — user must manually stop
- Do NOT use fixed scoring dimensions — framework is free-form
- Do NOT lose previous best results on iteration

## 4. Mock ACP Client

**Findings:**
- `ACPClient` in client.py (lines 234-439), `ACPBackendAdapter` wraps it (adapter.py lines 123-527)
- `FakeBackendAdapter` in platform-runtime/fakes.py (lines 62-262) — in-memory mock with deterministic IDs, event buffering, scripted status transitions

**Implementation approach (mock_acp.py):**
- `MockACPBackendAdapter` — implements BackendAdapter Protocol
- Configurable response sequences per slot: `__init__(*, backend_id, responses: list[str])`
- `submit_run()` returns `RunHandle` with deterministic run_id
- `stream_events()` yields scripted `RunEvent`s with `metadata.agent_slot`
- Supports: timeout simulation, crash simulation (exception in stream_events), partial result simulation
- Uses `FakeIdFactory` for deterministic run IDs

**Anti-patterns:**
- Do NOT spawn real subprocesses — tests must be fast and deterministic
- Do NOT require network access — mock must work offline
- Do NOT use random IDs — breaks test determinism

## 5. Orchestrator Never Produces Content (ENGINE-05)

**Findings:**
- Agent-core has LLM provider imports in `model/` subdirectory (openai_runner.py, anthropic_runner.py, ollama_runner.py)
- AGENTS.md: "Output boundary is enforced twice"

**Gate test (test_no_llm_imports.py):**
- AST-parse all `.py` files in `packages/arena-engine/src/`
- Assert no `import openai`, `import anthropic`, `import ollama` (or `from openai/anthropic/ollama import ...`)
- Use `ast.walk()` to check `ast.Import` and `ast.ImportFrom` nodes
- Forbidden modules: `{"openai", "anthropic", "ollama"}`
- Test should be fast (< 1 second, static analysis)

**Anti-patterns:**
- Do NOT use runtime import checks — tests should be static
- Do NOT allow indirect imports via agent-core — must be direct import check
- Do NOT make exceptions for "testing only" — gate must be absolute

## 6. Fresh Context Per Round (ENGINE-06)

**Findings:**
- ACP client has `new_session()` (client.py lines 342-359) and NO `resume_session()` method
- Each round must create a new session, never resume

**Gate test (test_fresh_context.py):**
- AST-parse all `.py` files in `packages/arena-engine/src/`
- Assert no calls to `session.resume` or `resume_session` (check `ast.Call` nodes with `func.attr == "resume"` or `func.id == "resume_session"`)
- Implementation: each round calls `adapter.submit_run()` with fresh `RunRequest` (new turn_id)

**Anti-patterns:**
- Do NOT reuse sessions across rounds — violates fresh context invariant
- Do NOT call `session.resume` — doesn't exist in ACP v1
- Do NOT cache session state — each round starts fresh

## 7. Artifact Persistence (ENGINE-07)

**Findings:**
- `ArtifactRecord` dataclass in protocols.py (lines 165-170) with `artifact_id`, `kind`, `uri_ref`, `name`
- AGENTS.md: "Contract logs prefer references such as `raw_payload_ref`"

**Implementation approach (artifact_store.py):**
- `RoundArtifact` frozen dataclass: `arena_id`, `agent_slot`, `round`, `content`, `raw_payload_ref`, `metadata`
- `ArtifactStore` class: file-based storage, `store_round_output()` returns `raw_payload_ref` (file path), `get_artifact()` retrieves
- Storage: JSON files per (arena_id, agent_slot, round) tuple in `storage_dir`
- Reference-first: store file path reference, not full content in logs

**Anti-patterns:**
- Do NOT store full content in memory — violates reference-first logging
- Do NOT store sensitive payloads in logs — use refs only
- Do NOT use complex database — file-based is sufficient

## 8. Agent Failure Recovery (ENGINE-08)

**Findings:**
- `asyncio.TaskGroup` provides structured exception handling (Python 3.11+)
- ACPBackendAdapter has background task cancellation (adapter.py lines 452-456)

**Implementation approach (slot_runner.py):**
- `run_agent_slot(slot_id, adapter, config, timeout)` — wraps in `asyncio.wait_for()` with timeout
- Returns `SlotResult(slot_id, status, content, metadata)` — status is "success"/"timeout"/"failed"
- On timeout: return `SlotResult(status="timeout", metadata={"error": "timeout", "partial": True})`
- On exception: return `SlotResult(status="failed", metadata={"error": str(exc), "partial": True})`
- Retry logic: `_run_agent_with_retry()` with `max_retries=2` and backoff
- `asyncio.TaskGroup` isolates exceptions per slot — one slot failure doesn't cancel others

**Anti-patterns:**
- Do NOT let exceptions propagate between slots — TaskGroup isolates but must handle
- Do NOT retry indefinitely — max_retries cap required
- Do NOT lose partial results on failure — must preserve and mark

## 9. User Stop/Pause/Cancel (ENGINE-09)

**Findings:**
- `ArenaWorkflow.cancel()` in protocol (protocols.py line 287)
- `ACPClient.cancel()` (client.py lines 418-422) and `shutdown()` (lines 430-432)

**Implementation approach (engine.py):**
- `cancel(arena_id)` — cancels all background tasks, closes all ACP sessions, shuts down all transports
- Uses `asyncio.Task.cancel()` for background tasks
- Calls `client.cancel(session_id)` + `client.close_session(session_id)` for each session
- Calls `client.shutdown()` to kill subprocesses
- Pause via `submit_user_action(action="pause")` — sets pause flag, iteration loop checks before each round
- Resume via `submit_user_action(action="resume")` — clears pause flag

**Zero orphaned processes test:**
- Track spawned PIDs, after cancel assert all are terminated
- For mock testing: assert all mock sessions are closed
- For real subprocess testing (Phase 109): use PID tracking

**Anti-patterns:**
- Do NOT forget to close sessions — leaves zombie processes
- Do NOT forget to shutdown transports — leaves orphaned subprocesses
- Do NOT block on cancel — must be fast and graceful

## 10. Legal Guardrails (SAFE-01..04)

**Findings:**
- v3.0 guardrails in `turn_loop.py` (lines 360-379): citation audit via `_run_citation_audit()`, de-AI polish via `de_ai_polish()`
- Guardrail functions in `guardrails.py`: `enforce_citation_audit()` (lines 245-266), `de_ai_polish()` (lines 301-317), `assert_skill_candidate_safety()` (lines 356-366)
- Citations package in `agent-core/citations/`: `extract_citations()`, `audit()`, `verify_items()`

**Implementation approach (guardrail_boundary.py):**
- `apply_post_hoc_guardrails(content, retrievals)` — for external ACP agents
  1. Citation audit via `inkstatute_agent_core.citations.audit()`
  2. De-AI polish via `inkstatute_agent_core.guardrails.de_ai_polish()`
  3. Mark high-risk conclusions with `requires_human_review=true`
- For self-built agents (agent-core): guardrails run in `turn_loop.py` automatically — no post-hoc needed
- For external ACP agents: apply post-hoc at arena-engine boundary
- `_is_high_risk_legal_conclusion(text)` — heuristic detection of high-risk keywords (违法, 无效, 撤销, 解除, 赔偿, 刑事责任)

**Anti-patterns:**
- Do NOT skip guardrails for external agents — critical pitfall
- Do NOT modify guardrail functions — use as-is from agent-core
- Do NOT auto-approve high-risk conclusions — SAFE-04 requires human review

## 11. Provenance Logging (SAFE-07)

**Findings:**
- `CitationAuditItem` has `tier` field for provenance (verify.py lines 100-122)
- Citation tiers: "L1-法规（本地库）", "L2-入库", etc. (verify.py lines 144-153)

**Implementation approach (provenance.py):**
- `ProvenanceChain` frozen dataclass: `claim`, `agent_slot`, `reviewer_slot` (None for Phase 107), `source`, `tier`, `timestamp`
- `ProvenanceLogger` class: `log_claim(claim, agent_slot, citation_audit, reviewer_slot=None)`, `get_chain(claim)`
- Storage: JSON file per arena_id
- For Phase 107 (Modes 1+2): `reviewer_slot` is None (cross-review is Phase 108)

**Anti-patterns:**
- Do NOT log sensitive full text — log claim references only
- Do NOT break chain on missing reviewer — reviewer_slot is optional
- Do NOT use complex graph database — simple list is sufficient

## 12. Gate Tests

**Findings:**
- Current gate count: 35 gates (after Phase 106 added fs-sandbox-escape)
- Gate structure in `scripts/run_v2_gates.py` (lines 49-306)
- Gate coverage meta-test enforces all `packages/*/src` are covered

**Gates to add:**
1. `arena-engine` — runs all arena-engine tests: `python -m unittest discover -s packages/arena-engine/tests`
2. Update gate count baseline: 35 → 36
3. Add arena-engine to compileall gate

**Gate test files (within arena-engine/tests/):**
- `test_no_llm_imports.py` — ENGINE-05: AST check for forbidden LLM provider imports
- `test_fresh_context.py` — ENGINE-06: AST check for session.resume calls
- Other tests cover: guardrail boundary, provenance, slot runner, artifact store, mode1, mode2

## Key Files to Create

1. `packages/arena-engine/pyproject.toml`
2. `packages/arena-engine/src/arena_engine/__init__.py`
3. `packages/arena-engine/src/arena_engine/engine.py` — ArenaEngine class
4. `packages/arena-engine/src/arena_engine/mode1.py` — Mode 1 parallel
5. `packages/arena-engine/src/arena_engine/mode2.py` — Mode 2 iteration
6. `packages/arena-engine/src/arena_engine/slot_runner.py` — Exception isolation
7. `packages/arena-engine/src/arena_engine/artifact_store.py` — Persistence
8. `packages/arena-engine/src/arena_engine/guardrail_boundary.py` — Post-hoc guardrails
9. `packages/arena-engine/src/arena_engine/provenance.py` — Provenance logging
10. `packages/arena-engine/src/arena_engine/mock_acp.py` — Mock adapter
11. `packages/arena-engine/tests/test_*.py` — 9 test files
12. `scripts/run_v2_gates.py` — Add arena-engine gate
13. `packages/contract-test-suite/tests/test_gate_coverage.py` — Update baseline

## Patterns to Follow

- `FakeArenaWorkflow` pattern for deterministic testing (fakes.py lines 321-375)
- `FakeIdFactory` and `FakeRuntimeClock` for deterministic ID/time
- `ACPBackendAdapter` subprocess management (adapter.py lines 260-324)
- `asyncio.TaskGroup` for structured concurrency
- Frozen slotted dataclasses for config/result types
- unittest (not pytest) with `IsolatedAsyncioTestCase` for async tests
- AST-based static analysis for gate tests (no runtime imports)

## Anti-Patterns to Avoid

1. Orchestrator produces content (gate-test enforced — ENGINE-05)
2. Guardrail bypass for external agents (post-hoc enforcement — SAFE-01..04)
3. Session reuse (fresh-context invariant — ENGINE-06)
4. Orphaned subprocesses (PID assertion — ENGINE-09)
5. Full-content logging (reference-first only — ENGINE-07)
6. LLM provider imports (forbidden — ENGINE-05)
7. Workflow frameworks (LangGraph, CrewAI, AutoGen — stdlib asyncio only)
8. Fixed scoring dimensions (free-form 10-point framework — ENGINE-02)
9. Auto-stop on convergence (user must manually stop — ENGINE-02)
10. Auto-approve high-risk conclusions (SAFE-04)

## Open Questions

None — all design decisions are clear from existing patterns and research.

## Assumptions

- `asyncio.TaskGroup` is available (Python 3.11+)
- Arena engine is a pure library (no service layer — that's Phase 109)
- Mock ACP client is sufficient for full testing (no real subprocess needed in Phase 107)
- File-based artifact storage is sufficient (no database needed)
- 10-point scoring framework is free-form (agent self-scores, not fixed dimensions)
- Provenance `reviewer_slot` is None for Phase 107 (cross-review is Phase 108)
