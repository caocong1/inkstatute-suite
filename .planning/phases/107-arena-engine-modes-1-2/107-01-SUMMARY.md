---
phase: 107-arena-engine-modes-1-2
plan: 01
status: complete
requirements: [ENGINE-05, ENGINE-06, ENGINE-08]
---

# Plan 01: Package Scaffold + MockACPBackendAdapter + SlotRunner + Gate Tests - Summary

## What Was Built

- Created `packages/arena-engine` package with `pyproject.toml` (zero non-stdlib dependencies beyond `platform-contract`)
- Implemented `MockACPBackendAdapter` — a deterministic offline `BackendAdapter` implementing all 9 Protocol methods with no subprocesses, no network, no LLM providers
- Implemented `SlotRunner` (`run_agent_slot` + `_run_with_retry`) with asyncio exception isolation — never raises, all failures converted to `SlotResult`
- Created `SlotResult` frozen slotted dataclass with fields: `slot_id`, `status`, `content`, `events`, `metadata`, `run_id`
- Created two AST gate tests: `test_no_llm_imports.py` (ENGINE-05) and `test_fresh_context.py` (ENGINE-06) using pure static analysis (`ast.parse` + `ast.walk`)

## Tasks Completed

- [x] Task 1: Create arena-engine package scaffold + MockACPBackendAdapter
- [x] Task 2: SlotRunner with exception isolation + retry logic
- [x] Task 3: AST gate tests for ENGINE-05 (no LLM imports) and ENGINE-06 (fresh context)

## Verification Results

All verify commands passed:

- `test_mock_acp.py`: 6/6 tests OK (deterministic IDs, stream events with agent_slot metadata, crash simulation, timeout simulation, incrementing run IDs, cancel)
- `test_slot_runner.py`: 6/6 tests OK (healthy slot, crash isolation, timeout isolation, retry-after-crash, concurrent TaskGroup isolation, event collection with agent_slot)
- `test_no_llm_imports.py`: 2/2 tests OK (no direct LLM provider imports, no indirect LLM provider imports)
- `test_fresh_context.py`: 2/2 tests OK (no session/resume calls, no resume_session method definitions)
- Full suite: 37/37 tests OK (includes pre-existing phase 107 tests)

## Artifacts Produced

- `packages/arena-engine/pyproject.toml` — package metadata, dependency on `platform-contract` only
- `packages/arena-engine/src/arena_engine/__init__.py` — package init with `__version__ = "0.1.0"`
- `arena_engine.mock_acp.MockACPBackendAdapter` — deterministic mock adapter implementing all 9 `BackendAdapter` Protocol methods
- `arena_engine.slot_runner.SlotResult` — frozen slotted result dataclass
- `arena_engine.slot_runner.run_agent_slot` — exception-isolated slot execution function (never raises)
- `arena_engine.slot_runner._run_with_retry` — retry-with-backoff internal function
- `tests/test_mock_acp.py::MockACPAdapterTests` — 6 test cases
- `tests/test_slot_runner.py::SlotRunnerFailureTests` — 6 test cases
- `tests/test_no_llm_imports.py::TestNoLLMImports` — 2 AST gate tests (ENGINE-05)
- `tests/test_fresh_context.py::TestFreshContext` — 2 AST gate tests (ENGINE-06)

## Notes

- `MockACPBackendAdapter` uses `FakeIdFactory` from `platform_runtime.fakes` for deterministic run IDs (`mock-run-001`, `mock-run-002`, …) and `FakeRuntimeClock` for deterministic `occurred_at` timestamps
- `run_agent_slot` wraps both `submit_run` and `stream_events` collection in `asyncio.wait_for` for timeout enforcement; the stream is collected via a regular coroutine (`_collect_all_events`) rather than an async generator to be compatible with `asyncio.wait_for`
- The `_FlakyMockAdapter` test helper subclasses `MockACPBackendAdapter` to simulate crash-then-succeed retry scenarios
- TaskGroup concurrent isolation test confirms that a crashing slot does not cancel sibling slots — `run_agent_slot`'s never-raise invariant is critical for this
- The AST gate tests use only `ast`, `pathlib`, and `unittest` — no runtime imports of arena-engine modules
- The `__init__.py` was pre-existing with references to `artifact_store`, `guardrail_boundary`, and `provenance` modules (from other plans in this phase); updated to also document `mock_acp` and `slot_runner`
