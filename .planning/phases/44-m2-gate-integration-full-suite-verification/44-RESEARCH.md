# Phase 44: M2 Gate Integration & Full Suite Verification - Research

**Researched:** 2026-07-04
**Status:** Complete

## Executive Summary

Phase 44 ensures every `packages/*/src` and `services/*/src` directory is covered by a V2 gate, all existing gates stay green, and a meta-test enforces coverage going forward. Research reveals a significant gap: **3 package directories have source code and passing tests but NO gate at all**, and **4 directories are missing from the compileall gate**. The phase requires real implementation work (new gates + meta-test), not just documentation.

**Gate count progression:** 15 (current) → 18 (after adding 3 missing gates) → 19 (after adding the meta-test gate itself).

## Current Gate Structure

### Gate Runner
**File:** `scripts/run_v2_gates.py` (187 lines)

The gate runner defines a frozen `Gate` dataclass:
```python
@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    pythonpath: tuple[str, ...] = ()
```

Each gate runs `python -m unittest discover -s <test_path>` with a PYTHONPATH tailored to that gate's dependencies. The runner exits on the first failing gate (fail-fast). `--list` prints gate names; `--json-summary` prints a sanitized JSON result.

### Current 15 Gates

| # | Gate Name | Test Path | PYTHONPATH Highlights | Phase |
|---|-----------|-----------|----------------------|-------|
| 1 | platform-contract | `packages/platform-contract/tests` | platform_src | Pre-M2 |
| 2 | wecom-service | `services/wecom-service/tests` | wecom_src, channel_core_src, platform_src, contract_src, platform_runtime_src | Pre-M2 |
| 3 | hermes-contract-layer | `services/hermes-contract-layer/tests` | hermes_src, platform_src, contract_src, router_service_src, skill_registry_src | Pre-M2 |
| 4 | conversation-read-view | `services/conversation-read-view/tests` | read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src | 41 |
| 5 | skill-registry | `packages/skill-registry/tests` | skill_registry_src, platform_src, platform_runtime_src | 37 |
| 6 | router-service | `packages/router-service/tests` | router_service_src, platform_src, skill_registry_src | 38 |
| 7 | codex-backend | `packages/backends/codex/tests` | codex_backend_src, platform_src, platform_runtime_src, wecom_src, channel_core_src | 39 |
| 8 | provider-model-backend | `packages/backends/provider_model/tests` | provider_model_backend_src, platform_src, platform_runtime_src, wecom_src, channel_core_src | 40 |
| 9 | admin-console-api | `services/admin-console-api/tests` | admin_api_src, read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src | 42 |
| 10 | qqbot-channel | `packages/channels/qqbot/tests` | qqbot_src, channel_core_src, platform_src, platform_runtime_src | 43 |
| 11 | feedback-service | `services/feedback-service/tests` | feedback_src, wecom_src, channel_core_src, contract_src, platform_src, platform_runtime_src | Pre-M2 |
| 12 | phase7-privacy-boundary | `test_privacy_gates.py` + `test_thin_layer_boundaries.py` | contract_src, platform_src | Pre-M2 |
| 13 | contract-test-suite | `packages/contract-test-suite/tests` | ALL 18 source dirs | Pre-M2 |
| 14 | v2-acceptance-traceability | `scripts/audit_v2_requirements.py --check-gaps` | (none) | Pre-M2 |
| 15 | compileall | `compileall` on 14 src dirs + 3 scripts | (none) | Pre-M2 |

### M2 Gate Status (Success Criterion #1)

All 6 M2 packages/services listed in ROADMAP SC#1 already have dedicated gates:

| M2 Package | Gate Name | Phase Added | Status |
|------------|-----------|-------------|--------|
| codex | codex-backend | 39 | ✓ |
| provider_model | provider-model-backend | 40 | ✓ |
| router-service | router-service | 38 | ✓ |
| skill-registry | skill-registry | 37 | ✓ |
| admin-console-api | admin-console-api | 42 | ✓ |
| qqbot | qqbot-channel | 43 | ✓ |

**SC#1 is already satisfied.** No new M2 gates need to be created for the 6 listed packages.

## Directory Coverage Gap Analysis (Success Criterion #3)

### All `packages/*/src` Directories on Disk (14)

| # | Directory | Dedicated Gate | compileall | contract-test-suite PYTHONPATH | Covered? |
|---|-----------|---------------|------------|-------------------------------|----------|
| 1 | packages/backends/codex/src | codex-backend | ✓ | ✓ | ✓ |
| 2 | packages/backends/hermes/src | — | ✗ | ✓ | ⚠ partial |
| 3 | packages/backends/provider_model/src | provider-model-backend | ✓ | ✓ | ✓ |
| 4 | packages/channel-core/src | — (indirect via qqbot/wecom/codex) | ✓ | ✓ | ✓ |
| 5 | packages/channels/qqbot/src | qqbot-channel | ✓ | ✓ | ✓ |
| 6 | **packages/channels/web_sse/src** | **—** | **✗** | **✗** | **✗ UNCOVERED** |
| 7 | **packages/channels/wecom/src** | **—** | **✗** | **✗** | **✗ UNCOVERED** |
| 8 | packages/contract-test-suite/src | contract-test-suite | ✓ | ✓ | ✓ |
| 9 | packages/platform-contract/src | platform-contract | ✓ | ✓ | ✓ |
| 10 | packages/platform-runtime/src | — (indirect) | ✓ | ✓ | ✓ |
| 11 | **packages/platform-sdk-ts/src** | **—** | **✗** | **✗** | **✗ UNCOVERED** |
| 12 | packages/router-service/src | router-service | ✓ | ✓ | ✓ |
| 13 | packages/skill-registry/src | skill-registry | ✓ | ✓ | ✓ |
| 14 | packages/solution-loader/src | — | ✗ | ✓ | ⚠ partial |

### All `services/*/src` Directories on Disk (5)

| # | Directory | Dedicated Gate | compileall | contract-test-suite PYTHONPATH | Covered? |
|---|-----------|---------------|------------|-------------------------------|----------|
| 1 | services/admin-console-api/src | admin-console-api | ✓ | ✓ | ✓ |
| 2 | services/conversation-read-view/src | conversation-read-view | ✓ | ✓ | ✓ |
| 3 | services/feedback-service/src | feedback-service | ✓ | ✓ | ✓ |
| 4 | services/hermes-contract-layer/src | hermes-contract-layer | ✓ | ✓ | ✓ |
| 5 | services/wecom-service/src | wecom-service | ✓ | ✓ | ✓ |

### Uncovered Directories (3 — require new gates)

**1. `packages/channels/web_sse/src`** — WebSSE channel adapter
- Source: `inkstatute_channels_web_sse/` (adapter.py, config.py, sse.py)
- Tests: `packages/channels/web_sse/tests/test_web_sse_channel.py` — **27 tests, ALL PASS**
- PYTHONPATH needed: `packages/channels/web_sse/src`, `packages/channel-core/src`, `packages/platform-contract/src`, `packages/contract-test-suite/src`, `packages/platform-runtime/src`
- Fixture: `packages/channels/web_sse/fixtures/multichannel_web_sse.json`

**2. `packages/channels/wecom/src`** — WeCom channel adapter (package, distinct from `services/wecom-service/`)
- Source: `inkstatute_channels_wecom/` (adapter.py, config.py)
- Tests: `packages/channels/wecom/tests/test_wecom_channel_adapter.py` — **1 test, currently ERRORS** (imports `wecom_service.protocol` but `services/wecom-service/src` not on PYTHONPATH)
- PYTHONPATH needed: `packages/channels/wecom/src`, `packages/channel-core/src`, `packages/platform-contract/src`, `packages/contract-test-suite/src`, `packages/platform-runtime/src`, `services/wecom-service/src`
- Fix: add `services/wecom-service/src` to PYTHONPATH so the test imports resolve

**3. `packages/platform-sdk-ts/src`** — TypeScript SDK + Python generator
- Source: `index.ts` (TypeScript — compileall does NOT apply) + generator script `packages/platform-sdk-ts/scripts/generate_sdk.py`
- Tests: `packages/platform-sdk-ts/tests/test_sdk_generation.py` — **9 tests, ALL PASS**
- PYTHONPATH needed: `packages/platform-sdk-ts/src` (for test discovery), `apps/platform_api/src`, `packages/platform-contract/src` (set inside the test via subprocess env)
- Note: compileall cannot validate `.ts` files. Coverage = running the Python test suite that validates the generator + generated output.

### Partially Covered Directories (2 — missing from compileall only)

**4. `packages/backends/hermes/src`** — Hermes backend
- In contract-test-suite PYTHONPATH ✓
- Missing from compileall ✗
- Has tests: `packages/backends/hermes/tests/` — no dedicated gate (tested via contract-test-suite)

**5. `packages/solution-loader/src`** — Solution loader
- In contract-test-suite PYTHONPATH ✓
- Missing from compileall ✗
- Has tests: `packages/solution-loader/tests/` — no dedicated gate

### Out-of-Scope Directories

**`solutions/*/src`** (2 dirs: `solutions/lawfirm/src`, `solutions/demo_non_legal/src`)
- NOT under `packages/` or `services/` — ROADMAP SC#3 scope is `packages/*/src` and `services/*/src` only
- Currently in contract-test-suite PYTHONPATH but missing from compileall
- Decision: add to compileall for syntax validation (low cost), but meta-test scope excludes them per SC#3 wording

**`apps/*/src`** (2 dirs: `apps/platform_api/src`, `apps/web_chat/src`)
- NOT under `packages/` or `services/` — out of SC#3 scope
- Have tests (`apps/platform_api/tests`, `apps/web_chat/tests`) — not in any gate
- Decision: out of scope for Phase 44 (not mentioned in ROADMAP)

## Test Directories Without Dedicated Gates (7)

| Test Directory | Test Count | Has Source Dir | In Some Gate? |
|---------------|-----------|----------------|---------------|
| packages/backends/hermes/tests | (exists) | packages/backends/hermes/src | contract-test-suite PYTHONPATH only |
| packages/channel-core/tests | (exists) | packages/channel-core/src | compileall + indirect |
| packages/channels/web_sse/tests | 27 | packages/channels/web_sse/src | **NONE** |
| packages/channels/wecom/tests | 1 (errors) | packages/channels/wecom/src | **NONE** |
| packages/platform-runtime/tests | (exists) | packages/platform-runtime/src | compileall + indirect |
| packages/platform-sdk-ts/tests | 9 | packages/platform-sdk-ts/src | **NONE** |
| packages/solution-loader/tests | (exists) | packages/solution-loader/src | contract-test-suite PYTHONPATH only |

**37 tests (27 + 1 + 9) run entirely outside the gate suite.** This is the core gap Phase 44 closes.

## Existing Gate-List Test

**File:** `packages/contract-test-suite/tests/test_audit_v2_requirements.py` (lines 424-443)

```python
def test_v2_gates_includes_traceability_gate(self):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_v2_gates.py"), "--list"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    self.assertEqual(result.returncode, 0)
    gate_names = result.stdout.strip().split("\n")
    self.assertIn("v2-acceptance-traceability", gate_names)
    self.assertIn("skill-registry", gate_names)
    self.assertIn("router-service", gate_names)
    self.assertIn("codex-backend", gate_names)
    self.assertIn("provider-model-backend", gate_names)
    self.assertIn("admin-console-api", gate_names)
    self.assertIn("qqbot-channel", gate_names)
    self.assertEqual(len(gate_names), 15)
```

**Must be updated** when new gates are added: assert count becomes 18 (or 19 with meta-test gate), and add `web-sse-channel`, `wecom-channel`, `platform-sdk-ts` to the assertIn checks.

## ROADMAP Documentation Discrepancy

ROADMAP SC#2 states "all 9 existing V2 gates" but there are 15. The ROADMAP was written before Phases 39-43 added gates. The "9 existing gates" refers to the pre-M2 baseline. After Phase 44, the count will be 18-19.

**Action:** Update ROADMAP SC#2 wording from "9 existing" to "all existing" (or "15 pre-M2 + M2 gates") to avoid staleness. Do NOT change the success criterion's intent.

## Meta-Test Design

### Coverage Definition

A `packages/*/src` or `services/*/src` directory is "covered by a gate" if ANY of:
1. It appears in a dedicated gate's PYTHONPATH tuple (the gate exercises code from that directory), OR
2. It appears in the compileall gate's path list (syntax validation), OR
3. It has a dedicated gate whose test path is `<directory>/tests` (direct test coverage)

### Implementation Approach: Runtime Inspection (Recommended)

Import the `_gates()` function from `run_v2_gates.py` and inspect the returned `Gate` objects. This is more robust than static parsing (no regex fragility) and stays in sync with the gate runner automatically.

```python
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_v2_gates import _gates

gates = _gates(REPO_ROOT)
```

### Test Structure

```python
class TestGateDirectoryCoverage(unittest.TestCase):
    def _all_covered_paths(self):
        """Return set of all src paths referenced by any gate."""
        gates = _gates(REPO_ROOT)
        covered = set()
        for gate in gates:
            for p in gate.pythonpath:
                covered.add(Path(p).resolve())
            # Also parse compileall command for path args
            if "compileall" in gate.command:
                for arg in gate.command:
                    if arg.endswith("/src") or arg.endswith("scripts/run_v2_gates.py"):
                        covered.add((REPO_ROOT / arg).resolve())
        return covered

    def test_all_packages_src_covered(self):
        """Every packages/*/src directory is covered by at least one gate."""
        on_disk = {p.resolve() for p in (REPO_ROOT / "packages").glob("*/src")}
        covered = self._all_covered_paths()
        uncovered = on_disk - covered
        self.assertEqual(uncovered, set(), f"Uncovered packages/*/src: {uncovered}")

    def test_all_services_src_covered(self):
        """Every services/*/src directory is covered by at least one gate."""
        on_disk = {p.resolve() for p in (REPO_ROOT / "services").glob("*/src")}
        covered = self._all_covered_paths()
        uncovered = on_disk - covered
        self.assertEqual(uncovered, set(), f"Uncovered services/*/src: {uncovered}")

    def test_gate_count(self):
        """Gate count matches expected (regression detection)."""
        gates = _gates(REPO_ROOT)
        self.assertGreaterEqual(len(gates), 15)
```

### Recommended Location

**File:** `packages/contract-test-suite/tests/test_gate_coverage.py`

This is a contract-test-suite concern (meta-level: testing the test infrastructure) and the contract-test-suite gate already has all source dirs on PYTHONPATH.

### Registration as a Gate

Add a new gate entry in `run_v2_gates.py`:
```python
Gate(
    "gate-coverage-meta-test",
    (py, "-m", "unittest", "packages/contract-test-suite/tests/test_gate_coverage.py"),
    (contract_src, platform_src),
),
```

This makes the meta-test a first-class gate — if any directory becomes uncovered, the gate suite fails.

## CI Integration

**File:** `.github/workflows/v2-contract-gates.yml`

The workflow runs `python scripts/run_v2_gates.py`. New gates added to `_gates()` are automatically picked up by CI — no workflow change needed.

## Validation Architecture

### How Gates Validate
- **UnitTest gates:** `python -m unittest discover -s <path>` — exit code 0 = pass, non-zero = fail
- **compileall gate:** `python -m compileall <paths>` — validates all `.py` files compile (syntax check)
- **Traceability gate:** `python scripts/audit_v2_requirements.py --check-gaps` — exits 0 if no requirement gaps
- **Meta-test gate (new):** `python -m unittest test_gate_coverage.py` — asserts directory coverage + gate count

### Regression Safety
- All 15 existing gates must stay green after changes
- The meta-test itself becomes a gate (gate #19) — future uncovered directories automatically fail CI
- Gate count assertion in `test_v2_gates_includes_traceability_gate` must be updated to match

### Feedback Sampling
- After each task: run `python scripts/run_v2_gates.py` (full suite, ~30s)
- Before verification: full suite must be green
- Max feedback latency: ~30 seconds (gate suite is fast — all unittest, no heavy integration)

## Implementation Tasks (Researcher Recommendation)

### Task 1: Add 3 missing gates to `run_v2_gates.py`
Add `web-sse-channel`, `wecom-channel`, `platform-sdk-ts` gates with correct PYTHONPATH.
Fix the wecom-channel PYTHONPATH to include `services/wecom-service/src` (currently errors).

### Task 2: Add 4 missing directories to compileall gate
Add: `packages/backends/hermes/src`, `packages/solution-loader/src`, `solutions/lawfirm/src`, `solutions/demo_non_legal/src`
(Compileall = syntax validation for all Python source, even if no dedicated gate.)

### Task 3: Create meta-test `test_gate_coverage.py`
Assert every `packages/*/src` and `services/*/src` is covered by at least one gate.
Assert gate count >= expected (regression detection).

### Task 4: Register meta-test as a gate
Add `gate-coverage-meta-test` entry to `run_v2_gates.py`.

### Task 5: Update existing gate-list test
Update `test_v2_gates_includes_traceability_gate`: count 15 → 18 (or 19), add new gate names to assertIn.

### Task 6: Update ROADMAP SC#2 wording
Change "9 existing V2 gates" → "all existing V2 gates" (avoid stale count).

### Task 7: Run full gate suite and verify all green
`python scripts/run_v2_gates.py` — all 18-19 gates pass.

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `scripts/run_v2_gates.py` | Modify | Add 3 gates + 4 compileall dirs + meta-test gate |
| `packages/contract-test-suite/tests/test_gate_coverage.py` | Create | Meta-test for directory coverage |
| `packages/contract-test-suite/tests/test_audit_v2_requirements.py` | Modify | Update gate count assertion |
| `.planning/ROADMAP.md` | Modify | Update SC#2 wording (9 → all) |

## Success Criteria Verification

| SC | Status Before Phase 44 | Status After Phase 44 |
|----|----------------------|----------------------|
| #1 (M2 gates exist) | ✅ Already satisfied | ✅ Confirmed |
| #2 (existing gates green) | ✅ 15 gates green | ✅ 18-19 gates green |
| #3 (meta-test for coverage) | ❌ Not implemented | ✅ Meta-test gate enforces coverage |

## RESEARCH COMPLETE
