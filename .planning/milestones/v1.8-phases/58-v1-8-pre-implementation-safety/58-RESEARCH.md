# Phase 58: v1.8 Pre-Implementation Safety - Research

**Researched:** 2026-07-07
**Domain:** Cross-cutting safety verification — V2 gate baseline, frozen contract surfaces, feature flag default-off, import isolation, dependency invariant
**Confidence:** HIGH

## Summary

Phase 58 is a verification-and-baseline-fix phase that establishes the safety floor before any v1.8 QQBot feature code is written. It is the direct analog of v1.6 Phase 36 (M2 Pre-Implementation Safety) and v1.7 Phase 45 (M3 Pre-Implementation Safety). The vast majority of safety infrastructure already exists from v1.6 and v1.7: the `qqbot_channel_enabled` flag already defaults to `False`, `test_no_wecom_import.py` already passes, `test_contract_count_freeze.py` already asserts frozen Protocol method counts, `test_contract_freeze.py` already checks SHA-256 baselines for 31 platform-contract files, and `dependencies = []` already holds in the QQBot channel `pyproject.toml`.

The single critical finding is that the `contract-test-suite` V2 gate is currently **FAILING** (exit 1) due to a missing file: `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`. This file was deleted during the v1.7→v1.8 milestone cleanup (commit `3b12f52`) when all v1.7 phase directories were cleared. The test `test_evidence_template_placeholder_rows_do_not_pass_live_acceptance` in `packages/contract-test-suite/tests/test_trial_acceptance.py` (line 126) reads this file and raises `FileNotFoundError`. This regression must be fixed in Phase 58 to restore the "all gates green" baseline. The file content is recoverable from git history (`git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`).

A secondary finding is that the success criteria references "24 V2 gates" but `scripts/run_v2_gates.py` currently defines **26 gates** (24 functional + 2 meta: `gate-coverage-meta-test` and `compileall`). The "24" count comes from the v1.7 milestone audit; 2 gates (`admin-web-ui`, `lawyer-web-chat`) were added in Phase 57-01 after the audit was written. Phase 58 should verify ALL 26 gates pass, not just 24.

**Primary recommendation:** Restore the deleted `08-TRIAL-EVIDENCE-TEMPLATE.json` file from git history, run the full 26-gate V2 suite to confirm green baseline, and add a v1.8-specific safety assertion test that consolidates the five success criteria into a single verification artifact.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
No locked decisions — discuss phase was skipped per `workflow.skip_discuss`.

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADAPTER-04 | All 24 existing V2 gates remain green throughout v1.8; frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules are not modified. | Existing `test_contract_count_freeze.py` asserts ChannelAdapter(6) + BackendAdapter(9) method counts; `test_contract_freeze.py` asserts SHA-256 baseline for 31 platform-contract files; `test_contract_freeze_not_violated.py` in qqbot package asserts FeedbackSource(4) + Channel.QQBOT + flag default. Phase 58 must fix the contract-test-suite gate regression and verify all gates green. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| V2 gate suite execution | `scripts/run_v2_gates.py` | — | Single entry point for all 26 gates; already used by CI and milestone audits |
| Frozen Protocol count assertion | `packages/contract-test-suite/tests/test_contract_count_freeze.py` | — | Runtime introspection via `dir()` + `dataclasses.fields()`; authoritative since v1.5 |
| Contract SHA-256 baseline | `packages/contract-test-suite/tests/test_contract_freeze.py` + `fixtures/contract_freeze_baseline.json` | — | 31-file SHA-256 baseline; detects any modification to platform-contract surface |
| Feature flag default-off | `packages/platform-runtime/src/platform_runtime/feature_flags.py` + `tests/test_feature_flags.py` | `packages/channels/qqbot/tests/test_feature_flag.py` | `RuntimeFeatureFlags` dataclass with `qqbot_channel_enabled: bool = False`; introspection-based test covers all flags |
| Import isolation | `packages/channels/qqbot/tests/test_no_wecom_import.py` | — | AST-based scan of adapter.py, config.py, __init__.py for `wecom_service` imports |
| Dependency invariant | `packages/channels/qqbot/pyproject.toml` | — | `dependencies = []` literal; verified by inspection and compileall gate |
| Trial evidence template | `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` | `packages/contract-test-suite/tests/test_trial_acceptance.py` | Template file consumed by contract-test-suite gate; **currently missing — must be restored** |

## Standard Stack

### Core

No external packages are installed in this phase. Phase 58 is purely verification and a single file restoration. All work uses the existing Python 3.14 stdlib (`unittest`, `dataclasses`, `pathlib`, `json`, `hashlib`, `ast`).

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.14 | `unittest`, `dataclasses.fields`, `dir()`, `hashlib.sha256`, `ast.parse` | Already used by all existing V2 gates and freeze tests [VERIFIED: codebase] |

### Supporting

None — no new packages needed.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Restoring template file from git | Modifying test to embed template inline | Restoring the file is simpler, preserves the original design intent (external template file), and avoids modifying a contract-test-suite test file during a safety phase |

**Installation:**

```bash
# No packages to install — phase is verification-only
```

## Package Legitimacy Audit

> No external packages are installed in this phase. The `dependencies = []` invariant is a success criterion, not a constraint to work around.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 58 Safety Verification                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  scripts/         │    │  Success Criteria Verification    │   │
│  │  run_v2_gates.py  │───▶│                                   │   │
│  │  (26 gates)       │    │  1. All gates green (1,547+ tests)│   │
│  └──────────────────┘    │  2. Protocol counts unchanged     │   │
│          │                │     ChannelAdapter: 6 methods     │   │
│          │                │     BackendAdapter: 9 methods     │   │
│          ▼                │     platform-contract SHA-256     │   │
│  ┌──────────────────┐    │     baseline (31 files) unchanged │   │
│  │  contract-test-   │    │  3. qqbot_channel_enabled=False   │   │
│  │  suite gate       │    │  4. test_no_wecom_import passes   │   │
│  │  (CURRENTLY       │    │  5. dependencies = [] holds       │   │
│  │   FAILING)        │    └──────────────────────────────────┘   │
│  └──────────────────┘                                           │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  FIX: Restore 08-TRIAL-EVIDENCE-TEMPLATE.json         │       │
│  │  from git history (commit 3b12f52^)                   │       │
│  │  → .planning/phases/08-lawyer-trial-acceptance/       │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

No new files or directories are created except:
- **Restore:** `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` (from git history)
- **Optional new test:** `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` (consolidates all 5 success criteria into one verification artifact)

```
.planning/
└── phases/
    └── 08-lawyer-trial-acceptance/
        └── 08-TRIAL-EVIDENCE-TEMPLATE.json   # RESTORE from git (deleted by 3b12f52)

packages/channels/qqbot/tests/
    └── test_v1_8_safety_baseline.py           # OPTIONAL: consolidated safety assertion
```

### Pattern 1: Runtime Introspection for Contract Freeze Verification
**What:** Use `dir()` and `dataclasses.fields()` to count Protocol methods and dataclass fields at test runtime, rather than parsing source text.
**When to use:** Always — this is the established pattern from `test_contract_count_freeze.py` and `test_contract_freeze_not_violated.py`.
**Example:**
```python
# Source: packages/contract-test-suite/tests/test_contract_count_freeze.py (existing)
from platform_runtime.protocols import ChannelAdapter, BackendAdapter

methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
assert len(methods) == 6  # channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health
```

### Pattern 2: AST-Based Import Isolation Verification
**What:** Parse Python source files with `ast.parse()` and walk `Import`/`ImportFrom` nodes to verify no forbidden module imports.
**When to use:** Always for import isolation checks — this is the established pattern from `test_no_wecom_import.py`.
**Example:**
```python
# Source: packages/channels/qqbot/tests/test_no_wecom_import.py (existing)
tree = ast.parse(source)
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and node.module.startswith("wecom_service"):
            self.fail(f"adapter.py imports from wecom_service: {node.module}")
```

### Pattern 3: SHA-256 Baseline File Comparison
**What:** Pre-compute SHA-256 hashes of all contract surface files, store in a JSON baseline, and compare at test time.
**When to use:** Always for file-level freeze verification — this is the established pattern from `test_contract_freeze.py`.
**Example:**
```python
# Source: packages/contract-test-suite/tests/test_contract_freeze.py (existing)
baseline = json.load(open(BASELINE_PATH))
for rel_path, expected_hash in baseline["files"].items():
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert actual_hash == expected_hash, f"contract file modified: {rel_path}"
```

### Anti-Patterns to Avoid
- **Modifying frozen Protocols or contract schemas:** Phase 58 is verification-only. If a Protocol method count or SHA-256 hash mismatches, the fix is to investigate WHY it changed, not to update the baseline to make the test pass. The baseline is only updated intentionally in the same PR that legitimately changes the contract.
- **Adding runtime dependencies to QQBot channel package:** The `dependencies = []` invariant is a hard constraint. v1.8 feature phases (59-67) must use stdlib only or optional/lazy imports.
- **Counting gates by hardcoded number:** The gate count grows over time (9→14→15→19→24→26). Use `len(_gates())` or `--list` dynamically, not a hardcoded count. The `gate-coverage-meta-test` already uses `assertGreaterEqual(len(_gates()), 19)` as a regression floor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Contract freeze verification | Custom source parser to count methods | `dir()` + `dataclasses.fields()` runtime introspection | Already implemented in `test_contract_count_freeze.py`; robust against formatting changes |
| Import isolation check | `grep` or string search for "wecom_service" | `ast.parse()` + `ast.walk()` | Already implemented in `test_no_wecom_import.py`; handles dynamic imports, re-exports, aliased imports |
| File hash baseline | Manual hash tracking | `hashlib.sha256` + JSON baseline file | Already implemented in `test_contract_freeze.py` with 31-file baseline |
| Gate execution | Custom test runner | `scripts/run_v2_gates.py` | Already defines all 26 gates with correct PYTHONPATH per gate |

**Key insight:** All safety verification infrastructure was built in v1.5 (Phase 33-35) and v1.6 (Phase 36). Phase 58 reuses it as-is. The only new work is fixing the regression and optionally adding a consolidated baseline test.

## Common Pitfalls

### Pitfall 1: Contract-Test-Suite Gate Failure from Missing Trial Evidence Template
**What goes wrong:** The `contract-test-suite` gate fails with `FileNotFoundError: .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` because the file was deleted during v1.7→v1.8 milestone cleanup (commit `3b12f52`).
**Why it happens:** The milestone cleanup script cleared all phase directories under `.planning/phases/`, including `08-lawyer-trial-acceptance/` which contained a template file that the contract-test-suite test depends on.
**How to avoid:** Restore the file from git history: `git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`. The file is 39 lines of JSON with placeholder trial task data.
**Warning signs:** `contract-test-suite` gate exits with code 1; error message contains `FileNotFoundError` and `08-TRIAL-EVIDENCE-TEMPLATE.json`.

### Pitfall 2: Gate Count Mismatch (24 vs 26)
**What goes wrong:** The success criteria says "24 V2 gates" but `run_v2_gates.py --list` shows 26 gates. A plan that only checks 24 gates might miss 2.
**Why it happens:** The "24" count comes from the v1.7 milestone audit, which was written before Phase 57-01 added the `admin-web-ui` and `lawyer-web-chat` gates (commit `551e3a3`). The current gate count is 26 (24 functional + `gate-coverage-meta-test` + `compileall`).
**How to avoid:** Run `python3 scripts/run_v2_gates.py` and verify exit code 0. Do not hardcode a gate count in the verification — use the dynamic count from the script.
**Warning signs:** Plan references "24 gates" but `run_v2_gates.py --list | wc -l` returns 26.

### Pitfall 3: Confusing "24 functional gates" with "26 total gates"
**What goes wrong:** The `gate-coverage-meta-test` and `compileall` gates are meta/infrastructure gates that don't run unit tests but still must pass. Excluding them from verification leaves a gap.
**Why it happens:** The meta gates don't produce a "Ran N tests" line, so they're easy to overlook when counting.
**How to avoid:** `run_v2_gates.py` runs ALL gates sequentially and exits non-zero on the first failure. Simply running the script and checking exit code 0 covers all 26 gates.
**Warning signs:** Manual gate-by-gate verification that skips `gate-coverage-meta-test` or `compileall`.

### Pitfall 4: Assuming Feature Flag Already Exists (It Does — But Verify)
**What goes wrong:** A plan might add `qqbot_channel_enabled` to `RuntimeFeatureFlags` thinking it doesn't exist, when it was already added in v1.6 Phase 43.
**Why it happens:** The flag has been in `feature_flags.py` since v1.6 (line 23). It's already tested by `test_feature_flag.py` and `test_contract_freeze_not_violated.py`.
**How to avoid:** Verify the flag exists with `RuntimeFeatureFlags().qqbot_channel_enabled is False` before attempting to add it. Do NOT re-add or modify it.
**Warning signs:** Plan includes a task to "add `qqbot_channel_enabled` flag" — this is already done.

## Code Examples

### Restoring the Trial Evidence Template (the one fix needed)

```bash
# Source: git history — commit 3b12f52 deleted this file during v1.7→v1.8 cleanup
git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json \
  > .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json
```

The file content (39 lines, verified from git history):
```json
{
  "milestone": "v1.0",
  "phase": "08-lawyer-trial-acceptance",
  "readiness_gates": {
    "local_v2_gates_passed": false,
    "lawyer_trial_scheduled": false
  },
  "repair_plan_ref": null,
  "trial_tasks": [
    {
      "task_ref": "trial-task-placeholder-001",
      "evidence_kind": "sanitized_runtime",
      "workday": "2026-06-29",
      "participant_alias": "lawyer-a",
      "category": "contract_review",
      "started_at": "2026-06-29T09:00:00Z",
      "completed_at": "2026-06-29T09:02:00Z",
      "duration_seconds": 120,
      "success": true,
      "clear_business_output": true,
      "feedback_captured": true,
      "positive_feedback": true,
      "negative_feedback": false,
      "route_mismatch": false,
      "response_action_ref": null,
      "response_action_at": null,
      "skill_candidate_ref": null,
      "routing_rule_candidate_ref": null,
      "output_boundary_checked": true,
      "hermes_meta_leak_detected": false,
      "turn_id": "turn-placeholder-001",
      "conversation_id": "conversation-placeholder-001",
      "trace_id": "trace-placeholder-001",
      "result_id": "result-placeholder-001",
      "feedback_id": "feedback-placeholder-001",
      "raw_payload_ref": "external://trial-evidence/raw-ref-placeholder-001"
    }
  ]
}
```
[VERIFIED: git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json]

### Running the Full V2 Gate Suite

```bash
# Source: scripts/run_v2_gates.py (existing, 26 gates)
python3 scripts/run_v2_gates.py
# Exit code 0 = all gates green
# Exit code non-zero = first failing gate

# List all gates
python3 scripts/run_v2_gates.py --list

# JSON summary (for evidence collection)
python3 scripts/run_v2_gates.py --json-summary
```
[VERIFIED: codebase — scripts/run_v2_gates.py lines 22-46]

### Optional: Consolidated v1.8 Safety Baseline Test

```python
# Source: pattern from test_contract_freeze_not_violated.py + test_feature_flag.py
# Optional new file: packages/channels/qqbot/tests/test_v1_8_safety_baseline.py
"""Consolidated v1.8 pre-implementation safety baseline (ADAPTER-04)."""

import unittest
from dataclasses import fields
from pathlib import Path

from platform_contract.enums import Channel, FeedbackSource
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter


class V18SafetyBaselineTests(unittest.TestCase):
    """All 5 Phase 58 success criteria in one verification artifact."""

    # SC-2: Frozen Protocol method counts
    def test_channel_adapter_has_exactly_6_methods(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 6)

    def test_backend_adapter_has_exactly_9_methods(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 9)

    # SC-3: Feature flag default-off
    def test_qqbot_channel_enabled_defaults_false(self) -> None:
        self.assertIs(RuntimeFeatureFlags().qqbot_channel_enabled, False)

    # SC-2: Platform-contract enums unchanged
    def test_feedback_source_has_exactly_4_values(self) -> None:
        values = [v.value for v in FeedbackSource]
        self.assertEqual(len(values), 4)

    def test_channel_enum_includes_qqbot(self) -> None:
        self.assertEqual(Channel.QQBOT.value, "qqbot")

    # SC-5: dependencies = [] invariant
    def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn("dependencies = []", content)
```
[VERIFIED: pattern from existing test_contract_freeze_not_violated.py + test_feature_flag.py]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual gate count (9→14→15→19) | Dynamic `len(_gates())` with `assertGreaterEqual` floor | Phase 44 (v1.6) | Gate-coverage meta-test prevents accidental gate removal |
| Static source parsing for Protocol counts | Runtime introspection via `dir()` + `dataclasses.fields()` | Phase 36 (v1.6) | Robust against formatting changes; catches actual method additions |
| String search for forbidden imports | AST-based `ast.parse()` + `ast.walk()` | Phase 43 (v1.6) | Handles dynamic imports, re-exports, aliased imports |
| Per-flag manual default-off tests | Introspection-based `test_all_flags_default_to_false_via_introspection` | Phase 36 (v1.6) | Automatically covers new flags added to `RuntimeFeatureFlags` |

**Deprecated/outdated:**
- Hardcoded gate counts in test assertions: `test_gate_count_meets_baseline` uses `assertGreaterEqual(len(_gates()), 19)` — the floor is intentionally low to avoid brittleness; the actual count is verified by running `run_v2_gates.py`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The "24 V2 gates" in success criteria refers to the 24 functional gates, excluding `gate-coverage-meta-test` and `compileall` meta gates | Summary, Pitfalls | LOW — running `run_v2_gates.py` covers all 26 regardless of how "24" is interpreted |
| A2 | The `08-TRIAL-EVIDENCE-TEMPLATE.json` file content from git history is still valid for the current test | Code Examples | LOW — the test only checks that placeholder rows don't pass live acceptance; the template content is static placeholder data |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

The 2 assumptions above are LOW risk and do not block planning. Both are verifiable by running the gate suite.

## Open Questions (RESOLVED)

1. **Should the `gate-coverage-meta-test` baseline floor be raised from 19 to 24 or 26?**
   - What we know: `test_gate_count_meets_baseline` uses `assertGreaterEqual(len(_gates()), 19)`. The current count is 26.
   - What's unclear: Whether Phase 58 should raise the floor as part of "baseline verification" or leave it for a future phase.
   - Recommendation: Optional — raising the floor to 24 or 26 is a nice-to-have but not a success criterion. The floor at 19 already prevents regression below v1.6 levels.
   - RESOLVED: Not raising the floor in Phase 58 — it is optional and not a success criterion. The existing floor at 19 is sufficient.

2. **Should a new consolidated `test_v1_8_safety_baseline.py` be created, or are the existing scattered tests sufficient?**
   - What we know: The 5 success criteria are already covered by existing tests across 3 packages (`contract-test-suite`, `platform-runtime`, `channels/qqbot`).
   - What's unclear: Whether a single consolidated test adds value or is redundant.
   - Recommendation: Optional — a consolidated test is nice for operator visibility but not strictly necessary. The existing tests already cover all criteria. If created, it should go in `packages/channels/qqbot/tests/` to be picked up by the `qqbot-channel` gate.
   - RESOLVED: Creating the consolidated test for operator visibility — Plan 58-01 Task 02 creates `test_v1_8_safety_baseline.py` in `packages/channels/qqbot/tests/`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All gates | ✓ | 3.14.6 | — |
| git | Restoring deleted template file | ✓ | (system) | — |
| `run_v2_gates.py` | Gate suite execution | ✓ | (repo script) | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | none — tests use `unittest discover` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest discover -s packages/channels/qqbot/tests` |
| Full suite command | `python3 scripts/run_v2_gates.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADAPTER-04 (SC-1) | All 26 V2 gates pass green | integration | `python3 scripts/run_v2_gates.py` | ✅ (script exists; contract-test-suite gate needs fix) |
| ADAPTER-04 (SC-2) | ChannelAdapter 6 methods, BackendAdapter 9 methods | unit | `PYTHONPATH="packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/router-service/src:packages/skill-registry/src" python3 -m unittest packages/contract-test-suite/tests/test_contract_count_freeze.py` | ✅ |
| ADAPTER-04 (SC-2) | platform-contract SHA-256 baseline unchanged | unit | `PYTHONPATH="packages/contract-test-suite/src:packages/platform-contract/src" python3 -m unittest packages/contract-test-suite/tests/test_contract_freeze.py` | ✅ |
| ADAPTER-04 (SC-3) | `qqbot_channel_enabled` defaults to `False` | unit | `PYTHONPATH="packages/platform-runtime/src" python3 -m unittest packages/platform-runtime/tests/test_feature_flags.py` | ✅ |
| ADAPTER-04 (SC-4) | QQBot adapter does not import from `wecom_service` | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages/channels/qqbot/tests/test_no_wecom_import.py` | ✅ |
| ADAPTER-04 (SC-5) | `dependencies = []` in QQBot pyproject.toml | inspection | `grep "dependencies = \[\]" packages/channels/qqbot/pyproject.toml` | ✅ (manual inspection; optional test in Code Examples) |

### Sampling Rate

- **Per task commit:** `python3 scripts/run_v2_gates.py` (full suite, ~30s)
- **Per wave merge:** `python3 scripts/run_v2_gates.py` (same — all gates must stay green)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` — must be restored from git history to fix contract-test-suite gate failure (covers ADAPTER-04 SC-1)

*(No other gaps — existing test infrastructure covers all phase requirements)*

## Security Domain

> Phase 58 is a verification-only safety phase with no new user-facing functionality, authentication, or cryptography. Security enforcement is limited to verifying that existing safety measures (import isolation, feature flag gating, contract freeze) remain in place.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no auth changes |
| V3 Session Management | no | N/A — no session changes |
| V4 Access Control | yes | Feature flag default-off (`qqbot_channel_enabled=False`) prevents unauthorized channel activation |
| V5 Input Validation | no | N/A — no new inputs |
| V6 Cryptography | no | N/A — no crypto changes |

### Known Threat Patterns for Safety Verification Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental contract modification | Tampering | SHA-256 baseline hash comparison (`test_contract_freeze.py`) + runtime introspection (`test_contract_count_freeze.py`) |
| Cross-channel import contamination | Tampering | AST-based import isolation test (`test_no_wecom_import.py`) |
| Feature flag default-on regression | Elevation of Privilege | Introspection-based default-off test (`test_feature_flags.py`) |

## Project Constraints (from AGENTS.md)

- **Keep changes scoped to the active GSD phase and its plan** — Phase 58 is verification + one file restoration only.
- **Add tests before or with behavior changes** — any new safety assertion test must accompany the baseline verification.
- **Do not introduce a new service, database, queue, or runtime dependency** — `dependencies = []` invariant is a success criterion.
- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads** — the trial evidence template contains only placeholder/sanitized data.
- **V2 PRD is the active product specification; V1 is retired** — the `08-TRIAL-EVIDENCE-TEMPLATE.json` is a V2 human gate artifact, not V1 reintroduction.
- **Do not rebuild Hermes core, session storage, router, skill registry, MCP registry, or model gateway** — Phase 58 does not modify any of these.

## Sources

### Primary (HIGH confidence)
- `scripts/run_v2_gates.py` — 26 gate definitions (lines 49-246), gate execution logic (lines 249-257) [VERIFIED: codebase]
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags` dataclass with `qqbot_channel_enabled: bool = False` (line 23) [VERIFIED: codebase]
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `ChannelAdapter` Protocol (lines 208-219, 6 methods), `BackendAdapter` Protocol (lines 222-239, 9 methods) [VERIFIED: codebase]
- `packages/contract-test-suite/tests/test_contract_count_freeze.py` — frozen count assertions: ChannelAdapter(6), BackendAdapter(9), AdapterCapabilitySet(14), RouterPort(1), SkillRegistryPort(3) [VERIFIED: codebase]
- `packages/contract-test-suite/tests/test_contract_freeze.py` — SHA-256 baseline for 31 platform-contract files [VERIFIED: codebase]
- `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — 31-file SHA-256 baseline, algorithm=sha256 [VERIFIED: codebase]
- `packages/channels/qqbot/tests/test_no_wecom_import.py` — AST-based import isolation test (6 test methods) [VERIFIED: codebase]
- `packages/channels/qqbot/tests/test_feature_flag.py` — flag default-off + disabled adapter behavior tests (10 test methods) [VERIFIED: codebase]
- `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` — qqbot-package-local freeze assertions (7 test methods) [VERIFIED: codebase]
- `packages/channels/qqbot/pyproject.toml` — `dependencies = []` (line 15) [VERIFIED: codebase]
- `packages/platform-contract/src/platform_contract/enums.py` — `Channel.QQBOT = "qqbot"`, `FeedbackSource` 4 values, `FeedbackAction` 4 values [VERIFIED: codebase]
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — fixture-only adapter, imports from `channel_core` and `platform_contract`/`platform_runtime` only [VERIFIED: codebase]
- `packages/contract-test-suite/tests/test_trial_acceptance.py` — line 126 reads `08-TRIAL-EVIDENCE-TEMPLATE.json`, currently failing [VERIFIED: codebase + gate run]
- `git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` — 39-line JSON template file content [VERIFIED: git history]
- `.planning/milestones/v1.7-MILESTONE-AUDIT.md` — "24 gates pass (exit 0)", "1,547+ tests", frozen surface verification [VERIFIED: codebase]
- `.planning/milestones/v1.6-phases/36-m2-pre-implementation-safety/36-RESEARCH.md` — analog phase research (v1.6 pre-implementation safety) [VERIFIED: codebase]
- `.planning/milestones/v1.7-ROADMAP.md` — Phase 45 (M3 Pre-Implementation Safety) structure with 4 plans [VERIFIED: codebase]
- `packages/platform-runtime/tests/test_feature_flags.py` — introspection-based default-off test pattern [VERIFIED: codebase]
- `services/admin-console-api/tests/test_contract_freeze.py` — hardcoded flag-set assertion (23 flags) [VERIFIED: codebase]
- `packages/contract-test-suite/tests/test_gate_coverage.py` — gate coverage meta-test with `assertGreaterEqual(len(_gates()), 19)` [VERIFIED: codebase]
- Gate run output (2026-07-07): 25/26 gates pass, contract-test-suite fails with 1 error (FileNotFoundError for trial evidence template) [VERIFIED: exec]

### Secondary (MEDIUM confidence)
- none

### Tertiary (LOW confidence)
- none

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external packages, pure stdlib verification
- Architecture: HIGH — all safety infrastructure verified by direct codebase inspection and gate execution
- Pitfalls: HIGH — the one regression (missing template file) was reproduced and root-caused to a specific git commit

**Research date:** 2026-07-07
**Valid until:** 2026-08-07 (30 days — stable codebase, no external dependencies)
