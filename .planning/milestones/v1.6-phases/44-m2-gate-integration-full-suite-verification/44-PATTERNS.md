# Phase 44 — Pattern Map

**Mapped:** 2026-07-04

## File 1: scripts/run_v2_gates.py (MODIFIED)

### Analog: Existing Gate entries (qqbot-channel from Phase 43, codex-backend from Phase 39)

```python
# Gate dataclass (line 15-19):
@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    pythonpath: tuple[str, ...] = ()

# qqbot-channel gate (lines 116-120):
Gate(
    "qqbot-channel",
    (py, "-m", "unittest", "discover", "-s", "packages/channels/qqbot/tests"),
    (qqbot_src, channel_core_src, platform_src, platform_runtime_src),
),

# codex-backend gate (lines 101-105):
Gate(
    "codex-backend",
    (py, "-m", "unittest", "discover", "-s", "packages/backends/codex/tests"),
    (codex_backend_src, platform_src, platform_runtime_src, wecom_src, channel_core_src),
),

# compileall gate (lines 146-171):
Gate(
    "compileall",
    (
        py,
        "-m",
        "compileall",
        "packages/platform-contract/src",
        "packages/contract-test-suite/src",
        # ... 14 source dirs + 3 scripts ...
        "scripts/run_v2_gates.py",
        "scripts/audit_v2_requirements.py",
        "scripts/generate_gap_evidence_reports.py",
        "scripts/generate_v2_readiness_report.py",
    ),
),
```

### Pattern to follow:
- Source path variables are defined at the top of `_gates()` (lines 51-68) as `repo_root / "packages" / ... / "src"`.
- New gates are appended to the return tuple BEFORE the `compileall` gate (compileall is always last).
- PYTHONPATH tuple includes the gate's own source dir first, then dependencies.
- For channel adapters: `(adapter_src, channel_core_src, platform_src, platform_runtime_src)`.
- For the wecom-channel gate, ALSO include `wecom_src` (services/wecom-service/src) because `test_wecom_channel_adapter.py` imports `wecom_service.protocol`.
- For compileall: append new source dir strings to the compileall command tuple.
- Gate naming convention: `<package-name>` with hyphens (e.g., `qqbot-channel`, `codex-backend`).
- New source path variables to define: `web_sse_src = repo_root / "packages" / "channels" / "web_sse" / "src"`, `wecom_channel_src = repo_root / "packages" / "channels" / "wecom" / "src"`, `sdk_ts_src = repo_root / "packages" / "platform-sdk-ts" / "src"`.

### New gates to add (3):
1. `web-sse-channel` — test path: `packages/channels/web_sse/tests`, PYTHONPATH: `(web_sse_src, channel_core_src, platform_src, contract_src, platform_runtime_src)`
2. `wecom-channel` — test path: `packages/channels/wecom/tests`, PYTHONPATH: `(wecom_channel_src, channel_core_src, platform_src, contract_src, platform_runtime_src, wecom_src)` — NOTE: `wecom_src` is required to fix the import error.
3. `platform-sdk-ts` — test path: `packages/platform-sdk-ts/tests`, PYTHONPATH: `(platform_src, contract_src, platform_runtime_src)` — the test sets its own subprocess PYTHONPATH for the generator.

### Meta-test gate to add (1):
```python
Gate(
    "gate-coverage-meta-test",
    (py, "-m", "unittest", "packages/contract-test-suite/tests/test_gate_coverage.py"),
    (contract_src, platform_src),
),
```
Insert BEFORE compileall, AFTER v2-acceptance-traceability.

### Compileall additions (4 source dirs):
```
"packages/backends/hermes/src",
"packages/solution-loader/src",
"solutions/lawfirm/src",
"solutions/demo_non_legal/src",
```

## File 2: packages/contract-test-suite/tests/test_gate_coverage.py (CREATED)

### Analog: test_audit_v2_requirements.py — test_v2_gates_includes_traceability_gate (lines 424-443)

```python
def test_v2_gates_includes_traceability_gate(self):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_v2_gates.py"), "--list"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    self.assertEqual(result.returncode, 0)
    gate_names = result.stdout.strip().split("\n")
    self.assertIn("v2-acceptance-traceability", gate_names)
    # ... more assertIn checks ...
    self.assertEqual(len(gate_names), 15)
```

### Analog: Import conventions from test_audit_v2_requirements.py (lines 14-26)

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
```

### Pattern to follow:
- `REPO_ROOT = Path(__file__).resolve().parents[3]` — contract-test-suite tests are 3 dirs below repo root.
- Import `run_v2_gates._gates` via `sys.path.insert(0, str(REPO_ROOT / "scripts"))` to get runtime inspection (no subprocess needed for gate objects).
- For directory enumeration: `(REPO_ROOT / "packages").glob("*/src")` and `(REPO_ROOT / "services").glob("*/src")`.
- For coverage check: collect all paths from gate.pythonpath tuples + compileall command args, resolve them, compare against on-disk directories.
- Use `Path.resolve()` for comparison to avoid relative/absolute mismatches.
- Test class name: `TestGateCoverage` (matches `TestAudit` pattern).

### Structure:
```python
class TestGateCoverage(unittest.TestCase):
    def _gates(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from run_v2_gates import _gates
        return _gates(REPO_ROOT)

    def _all_covered_src_paths(self):
        """Set of all src paths referenced by any gate."""
        ...

    def test_all_packages_src_covered(self):
        """Every packages/*/src directory is covered by at least one gate."""
        ...

    def test_all_services_src_covered(self):
        """Every services/*/src directory is covered by at least one gate."""
        ...

    def test_gate_count_meets_baseline(self):
        """Gate count meets the expected baseline (regression detection)."""
        ...
```

## File 3: packages/contract-test-suite/tests/test_audit_v2_requirements.py (MODIFIED)

### Analog: Current test (lines 424-443)

```python
def test_v2_gates_includes_traceability_gate(self):
    result = subprocess.run(...)
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

### Pattern to follow:
- Add 3 new `assertIn` calls: `"web-sse-channel"`, `"wecom-channel"`, `"platform-sdk-ts"`.
- Add 1 `assertIn` for the meta-test gate: `"gate-coverage-meta-test"`.
- Change `self.assertEqual(len(gate_names), 15)` → `self.assertEqual(len(gate_names), 19)`.
  - 15 existing + 3 new package gates + 1 meta-test gate = 19.

## File 4: .planning/ROADMAP.md (MODIFIED)

### Analog: Current Phase 44 SC#2

```
2. Operator can run all 9 existing V2 gates and verify they stay green with no regressions after all M2 features are merged.
```

### Pattern to follow:
- Change "all 9 existing V2 gates" → "all existing V2 gates" (avoid hardcoding count — it goes stale as phases add gates).
- Minimal edit, no structural change to the success criteria format.

## PATTERN MAPPING COMPLETE
