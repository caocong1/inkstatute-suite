---
phase: 39
plan: 39-01
title: "Codex Adapter Package Structure, Manifest, and Capability Probe"
wave: 1
requirements:
  - ADAPTER-01
status: complete
commits:
  - efa4361
  - 54845d4
---

# Plan 39-01 — Summary

## Tasks Completed

### Task 39-01-01 — Package structure + CodexBackendAdapter + manifest (commit efa4361)

Created the `packages/backends/codex/` package mirroring the Hermes adapter pattern:

- **pyproject.toml** — `name = "inkstatute-backends-codex"`, `dependencies = []`, `requires-python = ">=3.11"`
- **README.md** — prototype description with `production_ready: false`, `no_channel_io: true`
- **config.py** — `CodexBackendConfig` frozen dataclass with `exec_command`, `codex_binary`, `output_last_message_path` defaults
- **manifest.py** — `build_codex_manifest()` returning `AgentBackendManifest` with `mode=AgentBackendMode.CODEX`, `metadata["production_ready"]=False`, `capabilities.no_channel_io=True`; `codex_prototype_capabilities()` returning 14-field `AdapterCapabilitySet`
- **adapter.py** — `CodexBackendAdapter` implementing all 9 `BackendAdapter` Protocol methods:
  - `backend_id()`, `capabilities()`, `bootstrap_check()`, `submit_run()`, `get_run()`, `stream_events()`, `cancel_run()`, `submit_approval()`, `collect_artifacts()`
  - `submit_run` delegates to injectable `CodexExecRunner` Protocol (raises `RuntimeError("codex exec runner not configured")` when no runner injected — real runner wired in Plan 39-02)
  - `CodexExecResult` frozen dataclass with `status`, `result`, `thread_id`, `artifact_refs`, `raw_payload_ref`, `metadata`
  - Reference-first metadata with privacy sanitization (`_sanitize_metadata`, `_sanitize_value` copied from Hermes pattern)
- **probe.py** — `CodexCapabilityProbe` with injectable `CodexProbeTransport` Protocol (created in Task 01 because `__init__.py` imports from it — see Deviations)
- **__init__.py** — public re-exports for all adapter, config, manifest, and probe classes
- **tests/test_adapter.py** — 10 unit tests covering manifest validation, selector compatibility, 14-field count, reference-first metadata, privacy sanitization, boundary isolation
- **tests/__init__.py** — empty test package init

### Task 39-01-02 — Capability probe tests (commit 54845d4)

- **tests/test_probe.py** — 4 unit tests:
  - `test_probe_returns_14_field_capability_set` — verifies 14 fields, `no_channel_io=True`, `codex_version`
  - `test_probe_does_not_invoke_codex_exec` — source text assertion that probe.py never contains `"codex exec"`
  - `test_probe_failure_returns_ok_false_with_issue` — transport error → `ok=False`, `issues[0].code == "codex_binary_unavailable"`
  - `test_probe_report_capabilities_validate_in_manifest` — probe capabilities match manifest capabilities, both from `codex_prototype_capabilities()`
- **probe.py docstring fix** — removed literal `"codex exec"` from docstrings to satisfy source text assertion

## Test Results

| Test File | Tests | Passed | Failed |
|-----------|-------|--------|--------|
| test_adapter.py | 10 | 10 | 0 |
| test_probe.py | 4 | 4 | 0 |
| **Total** | **14** | **14** | **0** |

Verification commands used:
- `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m unittest discover -s packages/backends/codex/tests -p "test_adapter.py" -v` — 10/10 passed
- `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_probe.py" -v` — 4/4 passed
- `python -m compileall packages/backends/codex/src -q` — no syntax errors
- `PYTHONPATH=... python -m pytest packages/backends/codex/tests/ -q` — 14/14 passed

## Files Modified/Created

| File | Action |
|------|--------|
| `packages/backends/codex/pyproject.toml` | Created |
| `packages/backends/codex/README.md` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/config.py` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/probe.py` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` | Created |
| `packages/backends/codex/tests/__init__.py` | Created |
| `packages/backends/codex/tests/test_adapter.py` | Created |
| `packages/backends/codex/tests/test_probe.py` | Created |

## Deviations from Plan

1. **probe.py created in Task 01 instead of Task 02**: The plan's `__init__.py` (Task 01) re-exports `CodexCapabilityProbe`, `CodexProbeReport`, `CodexProbeIssue`, `CodexProbeTransport` from `probe.py`. Without `probe.py` existing, the `import inkstatute_backends_codex` in Task 01 tests would fail. The full `probe.py` implementation was created in Task 01; Task 02 then only needed to create `test_probe.py` and fix the docstring. This is a sequencing deviation — all files listed in `files_modified` were created across both tasks as specified.

2. **test_adapter.py privacy assertion uses `"'raw_payload':"` instead of `"raw_payload"`**: The plan specified `assertNotIn("raw_payload", repr(run.metadata))`, but `"raw_payload"` is a substring of the legitimate metadata key `"raw_payload_ref"`. The Hermes reference test uses `"'raw_payload':"` (the dict key representation pattern) which correctly checks that the sensitive `raw_payload` key (containing raw content) is sanitized from runner metadata without false-positive matching `raw_payload_ref`. This follows the established Hermes adapter test pattern.

3. **probe.py docstring reworded**: The probe.py docstring originally contained the literal string `"codex exec"` (in the context of "must never invoke codex exec"). The test `test_probe_does_not_invoke_codex_exec` asserts that `"codex exec"` does not appear anywhere in the probe source text. The docstring was reworded to say "the Codex execution subcommand" instead, preserving the semantic meaning while satisfying the source text assertion.

## Acceptance Criteria Verification

- [x] `validate_agent_backend_manifest(build_codex_manifest())` returns `[]` (zero issues)
- [x] `build_codex_manifest().metadata["production_ready"]` is `False`
- [x] `build_codex_manifest().capabilities.no_channel_io` is `True`
- [x] `build_codex_manifest().mode` equals `AgentBackendMode.CODEX`
- [x] `select_agent_backend({"agent_backend": {"mode": "codex"}}, [build_codex_manifest()])` returns `live_acceptance_allowed=False`, `contract_compatible=True`
- [x] `len(fields(AdapterCapabilitySet)) == 14`
- [x] `CodexBackendAdapter` has exactly 9 callable BackendAdapter methods
- [x] `submit_run` without a runner raises `RuntimeError("codex exec runner not configured")`
- [x] `platform-runtime` source contains no `inkstatute_backends_codex` or `CodexBackendAdapter` import
- [x] Raw request content does not appear in `repr(run)` or run metadata
- [x] `cancel_run` returns `metadata["reason"] == "unsupported_by_codex_prototype"`
- [x] `submit_approval` returns `metadata["reason"] == "approval_unsupported_by_codex_prototype"`
- [x] `CodexCapabilityProbe(FakeTransport()).probe().ok` is `True`
- [x] Probe module source does NOT contain the string `"codex exec"`
- [x] Probe failure returns `ok=False` with `issues[0].code == "codex_binary_unavailable"`
- [x] `compileall` on `packages/backends/codex/src` succeeds

## EXECUTION COMPLETE
