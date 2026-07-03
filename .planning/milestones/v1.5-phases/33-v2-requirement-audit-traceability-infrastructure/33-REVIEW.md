# Phase 33 Code Review — V2 Requirement Audit & Traceability Infrastructure

**Phase:** 33
**Milestone:** v1.5 V2 Acceptance Closure
**Reviewer:** gsd-code-review (automated)
**Date:** 2026-07-03
**Scope:** `scripts/audit_v2_requirements.py` (new), `scripts/run_v2_gates.py` (modified), `packages/contract-test-suite/tests/test_audit_v2_requirements.py` (new), `acceptance/v2-traceability.json` (generated)

## Summary

The phase delivers a stdlib-only, deterministic V2 requirement audit that maps 10 unchecked V2 Active requirements to concrete code evidence and classifies each via three-level verification (schema → library surface → production wiring). A 9th V2 gate (`v2-acceptance-traceability`) fails only on `gap` status. The core design is sound: the three-level scheme genuinely catches the MEM-07/MEM-16 false-positive pattern (L1+L2 pass, L3 fail → `partial`), output is byte-identical across runs (verified MD5 `1d876cca1917b45d20e81bb838fa911c`), and the gate correctly ignores `partial`/`human_gate`.

The review found **6 findings (1 moderate, 5 low)**. All actionable findings were fixed in-place during the review fix chain; the remaining items are documentation notes. After fixes: 24/24 audit tests pass, determinism holds, the committed sidecar is byte-identical to regeneration, the working tree is no longer corrupted by the test suite, and all 9 gates remain green.

## Constraint Compliance

| Constraint | Status | Evidence |
|------------|--------|----------|
| Stdlib-only (no new dependencies) | PASS | audit script imports only `argparse, ast, json, re, sys, dataclasses, pathlib, collections.abc, typing` |
| Deterministic (byte-identical output) | PASS | `generated_at="deterministic"`, `sort_keys=True`, sorted `rglob`/`iterdir`, no timestamps; MD5 identical across runs and vs. committed sidecar |
| Three-level verification catches MEM-07/MEM-16 | PASS | L3 wiring probe (`re.search` on production entrypoints) fails when infra present but unwired → `partial`; covered by `test_three_level_catches_partial` |
| 9th gate fails only on `gap`, not `partial`/`human_gate` | PASS | `--check-gaps` counts only `status == "gap"`; `partial`/`human_gate` exit 0; covered by `test_check_gaps_exits_*` |

## Findings

### F1 [MODERATE, FIXED] — Test suite deleted the committed traceability sidecar

**File:** `packages/contract-test-suite/tests/test_audit_v2_requirements.py` (lines 64-83, 96-123)
**Symptom:** `test_audit_produces_json_sidecar` and `test_audit_deterministic_via_subprocess` wrote to the real `acceptance/v2-traceability.json` and then `unlink()`ed it in cleanup. Running the 24-test suite left the working tree dirty:
```
$ git status --short -- acceptance/
 D acceptance/v2-traceability.json
```
**Root cause:** `write_sidecar` uses a fixed `SIDECAR_REL`, so the tests wrote to the committed path and deleted it on cleanup instead of restoring the original content.
**Fix:** Both tests now back up the existing file bytes before writing and restore them in a `finally` block (only unlinking if the file did not exist beforehand). Verified: after the full suite, `git status -- acceptance/` is clean.
**Severity rationale:** Corrupts a committed acceptance artifact on every test run; CI or a developer running tests would see a spurious deletion and could accidentally commit it.

### F2 [LOW, FIXED] — `run_verification` silently overwrote duplicate-level probes

**File:** `scripts/audit_v2_requirements.py` (`run_verification`, ~line 996)
**Symptom:** The original loop did `levels[probe.level] = {...}`, so a second probe at the same level would silently overwrite the first; the first probe's result would be lost and never influence classification.
**Root cause:** No aggregation or uniqueness guard. Currently safe (each requirement has exactly one probe per level), but a latent fragility for future maintainers.
**Fix:** `run_verification` now aggregates: a level passes only when *every* probe at that level passes, and evidence strings are concatenated in stable probe order. Behavior is unchanged for the current registry (one probe per level), so the generated sidecar remains byte-identical (verified).

### F3 [LOW, FIXED] — Unused `field` import

**File:** `scripts/audit_v2_requirements.py` (line 24)
**Symptom:** `from dataclasses import dataclass, field` — `field` had zero call sites.
**Fix:** Reduced to `from dataclasses import dataclass`.

### F4 [LOW, FIXED] — No exception handling around probe checkers / file reads

**File:** `scripts/audit_v2_requirements.py` (`run_verification`, `_check_library_surface`)
**Symptom:** A probe checker that raised (e.g. `UnicodeDecodeError`/`OSError` from `read_text`, or a malformed regex) would abort the entire audit and the 9th gate, instead of classifying that requirement as failed. `_check_library_surface` only caught `SyntaxError`.
**Fix:** `run_verification` now wraps each `probe.checker(repo_root)` call in `try/except`; an exception is recorded as a failed probe (`"<kind> probe error: <exc>"`) so the audit stays robust and the gate fails gracefully on the offending requirement rather than crashing.

### F5 [LOW, FIXED] — VERIFICATION.md inaccuracies

**File:** `.planning/phases/33-v2-requirement-audit-traceability-infrastructure/33-VERIFICATION.md`
**Symptom:** (a) Line 163 listed `subprocess` and `importlib` as audit-script dependencies — the audit script does not use them (they are used by the test module). (b) Line 20 stated the 9th gate "fails when any requirement is `gap` or evidence is missing" — the implementation fails only on `gap` status; missing evidence does not independently fail the gate.
**Fix:** Corrected the module list to `argparse, ast, json, re, sys, dataclasses, pathlib, collections.abc, typing` (with a note that the test module additionally uses `importlib, subprocess, unittest.mock`), and reworded the gate-fail condition to "fails when any requirement is classified as `gap` (does not fail on `partial` or `human_gate`, by design)".

### F6 [LOW, FIXED] — Mocked gap test leaked output to stdout

**File:** `packages/contract-test-suite/tests/test_audit_v2_requirements.py` (`test_check_gaps_exits_nonzero_on_gap`)
**Symptom:** The test called `audit.main(["--check-gaps"])` directly, printing `FAIL: 1 requirement(s) classified as gap: WECOM-01` to real stdout. The test passed but polluted test-runner output with a misleading `FAIL:` line.
**Fix:** Wrapped the call in `contextlib.redirect_stdout(io.StringIO())`. Test still asserts exit code 1.

## Verification After Fixes

```
$ python -m unittest discover -s packages/contract-test-suite/tests -p "test_audit_v2_requirements.py"
Ran 24 tests in 0.684s
OK

$ git status --short -- acceptance/
(clean — no spurious deletion)

$ python scripts/audit_v2_requirements.py --json  # regenerate
$ md5sum acceptance/v2-traceability.json
1d876cca1917b45d20e81bb838fa911c  acceptance/v2-traceability.json
# byte-identical to committed version (no diff)

$ python scripts/audit_v2_requirements.py --check-gaps
PASS: no requirements classified as gap   (EXIT=0)

$ python scripts/run_v2_gates.py --list | wc -l
9

$ python -m compileall scripts/audit_v2_requirements.py scripts/run_v2_gates.py packages/contract-test-suite/tests/test_audit_v2_requirements.py
OK
```

## Files Changed During Review (Fix Chain)

| File | Change |
|------|--------|
| `scripts/audit_v2_requirements.py` | Removed unused `field` import (F3); rewrote `run_verification` to aggregate per-level probes and handle checker exceptions (F2, F4) |
| `packages/contract-test-suite/tests/test_audit_v2_requirements.py` | Back up/restore committed sidecar in two tests (F1); removed now-unused `tempfile` import; redirect stdout in mocked gap test (F6) |
| `.planning/phases/33-.../33-VERIFICATION.md` | Corrected stdlib module list and 9th-gate fail-condition wording (F5) |

## Notes / Non-Blocking Observations

- The `generated_at: "deterministic"` placeholder is a deliberate determinism choice; it intentionally does **not** record a real generation time. This is correct for the byte-identical-output requirement, but consumers should not treat it as a freshness signal.
- Evidence collection (files/tests/fixtures) does not influence classification — only the three-level probes do. This is by design (the audit proves traceability; `run_v2_gates.py` proves gate-passing), but it means "missing evidence" alone will not fail the 9th gate. The VERIFICATION.md wording has been corrected to reflect this.
- `run_verification` aggregation uses probe iteration order (stable, tuple-bound) for evidence concatenation, preserving determinism.

## Result

**PASS with fixes applied.** All 6 findings resolved; 24/24 tests green; determinism and byte-identical sidecar confirmed; 9 gates remain green; stdlib-only constraint preserved; three-level verification and gap-only gate semantics unchanged.
