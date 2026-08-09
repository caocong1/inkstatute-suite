---
phase: 111
plan: 111-05
status: complete
started: 2026-08-09T06:20:00Z
completed: 2026-08-09T06:34:42Z
---

# Plan 111-05 Summary

## Objective
Wire Phase 106's `FSSandbox.read_text_file` + `ReferenceSanitizer` into arena-engine's `_build_run_request` so that when `ArenaWorkflowConfig.reference_dir` is set, reference files are read through the sandbox, sanitized, and injected into the agent context — without ever bypassing the path sandbox.

## Tasks Completed
| Task | Description | Commit | Verification |
|------|-------------|--------|--------------|
| Task 1 | Wire FSSandbox + ReferenceSanitizer into `_build_run_request`; add `test_reference_dir_wiring.py` (11 tests); update arena-engine gate PYTHONPATH to include `acp_client_src` | 1810ea0 | `python -m unittest discover -s packages/arena-engine/tests -p test_reference_dir_wiring.py` → 11/11 PASS; full arena-engine suite 139/139 PASS |

## Artifacts Produced
- `packages/arena-engine/src/arena_engine/mode1.py` (modified) — added `_collect_reference_context(config)` helper + wired it into `_build_run_request`; added `from pathlib import Path`; lazy imports of `inkstatute_acp_client.fs_sandbox` (`FSSandbox`, `FSSandboxConfig`, `FSSandboxError`) and `inkstatute_acp_client.sanitizer` (`ReferenceSanitizer`) inside the helper.
- `packages/arena-engine/tests/test_reference_dir_wiring.py` (new, 11 tests) — content injection, path-in-delimiter, no-reference_dir baseline (None + empty string), no-sandbox-call-when-None, `FSSandbox.read_text_file` actually called (autospec spy), traversal rejection, symlink-escape rejection + run continues, `FSSandboxError` swallowed, empty dir, non-text-file skipping.
- `scripts/run_v2_gates.py` (modified) — arena-engine gate PYTHONPATH now includes `acp_client_src` (necessary because arena-engine now legitimately depends on acp-client for reference_dir reading).

## Deviations
- **Rule 1 — Supporting change (file outside `files_modified`):** `scripts/run_v2_gates.py` was modified to add `acp_client_src` to the arena-engine gate's `PYTHONPATH`. Rationale: arena-engine now has a runtime dependency on `inkstatute_acp_client` (for `FSSandbox`/`ReferenceSanitizer`); without this update the arena-engine gate (`python -m unittest discover -s packages/arena-engine/tests`) fails with `ModuleNotFoundError: No module named 'inkstatute_acp_client'` because the new test file triggers the lazy import. This is required to keep gates green (AGENTS.md binding constraint: "all 41 gates must stay green"). The change is minimal (one tuple element appended) and does not alter gate semantics.
- **Verify command adaptation:** The plan's `<verify><automated>` block specifies `python -m unittest packages.arena_engine.tests.test_reference_dir_wiring -v`, which does not match this repo's layout (tests import `arena_engine.mode1` directly with `src/` on `PYTHONPATH`, not the `packages.arena_engine` dotted path). The equivalent working command is `PYTHONPATH=<src dirs> python -m unittest discover -s packages/arena-engine/tests -p test_reference_dir_wiring.py -v`, which is what the arena-engine gate actually runs. All 11 tests pass under both the adapted command and the full gate suite.

## Deferred Issues
- **mode2/mode3/mode4 reference_dir wiring:** The plan's action step 4 asked to consider applying the same change to `mode2.py`/`mode3.py`/`mode4.py`. `mode2.py` has its own `_build_run_request` (different signature: takes `round`, `prev_content`, `prev_score`); `mode3.py`/`mode4.py` build `RunRequest` via differently-named helpers (`_build_review_run_request`, `_build_synthesis_run_request`, etc.). The plan's `files_modified`, `artifacts`, and `key_links` scope this plan to `mode1.py` only, so per the binding rule "Keep changes scoped to the active GSD phase and its plan" the reusable `_collect_reference_context` helper was placed in `mode1.py` and only mode1's `_build_run_request` was wired. The helper is importable (`from arena_engine.mode1 import _collect_reference_context`) so modes 2-4 can adopt it in a follow-up plan without re-implementing the sandbox/sanitizer logic.

## Verification Results
- `python -m unittest discover -s packages/arena-engine/tests -p test_reference_dir_wiring.py -v` → **PASS** (11/11 tests)
- `python -m unittest discover -s packages/arena-engine/tests` (full suite, gate PYTHONPATH incl. acp_client_src) → **PASS** (139/139 tests, no regressions)
- `grep "FSSandbox" packages/arena-engine/src/arena_engine/mode1.py` → present (8 matches)
- `grep "ReferenceSanitizer" packages/arena-engine/src/arena_engine/mode1.py` → present (4 matches)
- Path sandboxing NOT bypassed: every reference file read goes through `sandbox.read_text_file` (5-layer validation + size cap); raw `open()`/`Path.read_text()` are never used for reference content. Verified by the `test_fssandbox_read_text_file_called` spy test and the traversal/symlink rejection tests.
- Legal guardrails not bypassed: reference content is injected as delimiter-wrapped untrusted context appended to the task instruction; it does not alter the research-gate / ask-user-enforcement / citation audit / de-AI polish guardrail flow (those run post-hoc on agent output, unaffected by input context augmentation).
- No adapter changes made (per RESEARCH.md: `backend_family()` try/except fallback in `_build_backend_families` handles the missing method).
