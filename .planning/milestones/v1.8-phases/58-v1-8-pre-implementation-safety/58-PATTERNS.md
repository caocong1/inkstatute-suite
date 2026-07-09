# Phase 58: v1.8 Pre-Implementation Safety - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 2
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` | config | file-I/O | `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` | role-match |
| `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` | test | request-response | `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` | exact |

## Pattern Assignments

### `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` (config, file-I/O)

**Analog:** `packages/contract-test-suite/fixtures/contract_freeze_baseline.json`

This is a **file restoration**, not a new file creation. The exact content is recoverable from git history (`git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`). The file is a 39-line JSON template consumed by `packages/contract-test-suite/tests/test_trial_acceptance.py` line 126.

**Consumer pattern** — `packages/contract-test-suite/tests/test_trial_acceptance.py` (lines 15-18, 125-136):
```python
REPO_ROOT = Path(__file__).resolve().parents[3]
TRIAL_EVIDENCE_TEMPLATE = (
    REPO_ROOT / ".planning" / "phases" / "08-lawyer-trial-acceptance" / "08-TRIAL-EVIDENCE-TEMPLATE.json"
)

# ...

def test_evidence_template_placeholder_rows_do_not_pass_live_acceptance(self) -> None:
    template = json.loads(TRIAL_EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))

    report = evaluate_trial_acceptance(
        template["trial_tasks"],
        readiness_gates_passed=bool(template["readiness_gates"]["local_v2_gates_passed"]),
        repair_plan_ref=template["repair_plan_ref"],
    )

    self.assertEqual(report.status, "blocked")
    self.assertEqual(report.live_task_count, 1)
    self.assertIn("readiness_gates_missing", _issue_codes(report))
```

**File content to restore** (verified from `git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`):
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

**Restoration command:**
```bash
git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json \
  > .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json
```

**Note:** The directory `.planning/phases/08-lawyer-trial-acceptance/` must be recreated (it was deleted by commit `3b12f52` during v1.7→v1.8 milestone cleanup).

---

### `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` (test, request-response)

**Analog:** `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py`

This is an **optional** consolidated test that gathers all 5 Phase 58 success criteria into a single verification artifact. The existing scattered tests already cover all criteria; this file is a convenience for operator visibility.

**Imports pattern** — from `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` (lines 18-25):
```python
from __future__ import annotations

import unittest
from dataclasses import fields

from platform_contract.enums import Channel, FeedbackSource
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import ChannelAdapter
```

The new file adds `BackendAdapter` to the protocol import and `Path` from `pathlib` for the pyproject.toml check:
```python
from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path

from platform_contract.enums import Channel, FeedbackSource
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter
```

**Core pattern — runtime introspection for Protocol method counts** — from `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` (lines 31-42):
```python
def test_channel_adapter_method_count_is_6(self) -> None:
    methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
    self.assertEqual(len(methods), 6)
    expected = {
        "channel_id",
        "capabilities",
        "verify_and_ack",
        "normalize_inbound",
        "deliver",
        "health",
    }
    self.assertEqual(set(methods), expected)
```

**Core pattern — feature flag default-off assertion** — from `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` (lines 53-55):
```python
def test_qqbot_channel_enabled_defaults_false(self) -> None:
    flags = RuntimeFeatureFlags()
    self.assertIs(flags.qqbot_channel_enabled, False)
```

**Core pattern — enum value introspection** — from `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` (lines 44-51):
```python
def test_feedback_source_has_exactly_4_values(self) -> None:
    values = [v.value for v in FeedbackSource]
    self.assertEqual(len(values), 4)
    expected = {"card_button", "text_command", "web_form", "admin_annotation"}
    self.assertEqual(set(values), expected)

def test_channel_enum_includes_qqbot(self) -> None:
    self.assertEqual(Channel.QQBOT.value, "qqbot")
```

**Core pattern — file content assertion for dependencies invariant** — novel to this file, but follows the `Path(__file__).resolve().parents[N]` convention from `test_no_wecom_import.py` (line 13):
```python
def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    self.assertIn("dependencies = []", content)
```

**Test class structure** — from `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` (lines 28-29, 91-92):
```python
class ContractFreezeNotViolatedTests(unittest.TestCase):
    """Assert frozen contract surfaces are unchanged after Phase 43."""

    # ... test methods ...

if __name__ == "__main__":
    unittest.main()
```

**Full reference implementation** (from RESEARCH.md lines 288-331, verified against analog patterns):
```python
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


if __name__ == "__main__":
    unittest.main()
```

## Shared Patterns

### Runtime Introspection for Protocol Freeze Verification
**Source:** `packages/contract-test-suite/tests/test_contract_count_freeze.py` lines 31-39
**Apply to:** `test_v1_8_safety_baseline.py` (SC-2 assertions)
```python
methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
self.assertEqual(
    len(methods),
    self.BACKEND_ADAPTER_METHOD_COUNT,
    f"BackendAdapter Protocol method count changed: "
    f"expected {self.BACKEND_ADAPTER_METHOD_COUNT}, "
    f"got {len(methods)}: {methods}",
)
```
**Convention:** Use `dir()` + filter `_` prefix for Protocol methods. Use `dataclasses.fields()` for dataclass field counts. Never parse source text.

### AST-Based Import Isolation Verification
**Source:** `packages/channels/qqbot/tests/test_no_wecom_import.py` lines 16-27
**Apply to:** No new file needed — existing `test_no_wecom_import.py` already covers SC-4. The consolidated test does NOT duplicate this check (AST scanning is package-internal, not a cross-cutting concern).
```python
def _imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules
```

### SHA-256 Baseline File Comparison
**Source:** `packages/contract-test-suite/tests/test_contract_freeze.py` lines 32-46
**Apply to:** No new file needed — existing `test_contract_freeze.py` already covers SC-2 SHA-256 baseline. The consolidated test uses runtime introspection instead (complementary, not duplicative).
```python
def test_schema_files_match_baseline_hash(self) -> None:
    baseline = self._load_baseline()
    for rel_path, expected_hash in baseline["files"].items():
        with self.subTest(file=rel_path):
            file_path = REPO_ROOT / rel_path
            self.assertTrue(file_path.exists(), ...)
            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            self.assertEqual(actual_hash, expected_hash, ...)
```

### Feature Flag Default-Off Assertion
**Source:** `packages/channels/qqbot/tests/test_feature_flag.py` lines 67-69
**Apply to:** `test_v1_8_safety_baseline.py` (SC-3 assertion)
```python
def test_qqbot_channel_enabled_defaults_to_false(self) -> None:
    flags = RuntimeFeatureFlags()
    self.assertIs(flags.qqbot_channel_enabled, False)
```
**Convention:** Use `assertIs(..., False)` not `assertFalse(...)` — the flag must be literally `False`, not just falsy.

### unittest TestCase Structure
**Source:** All analog test files
**Apply to:** `test_v1_8_safety_baseline.py`
```python
from __future__ import annotations

import unittest

class XyzTests(unittest.TestCase):
    """Docstring describing what is verified."""

    def test_something(self) -> None:
        ...

if __name__ == "__main__":
    unittest.main()
```
**Convention:** `from __future__ import annotations` first. Type hints on all test methods (`-> None`). Descriptive class docstring. `unittest.main()` guard at bottom.

### Path Resolution Convention
**Source:** `packages/channels/qqbot/tests/test_no_wecom_import.py` line 13, `packages/contract-test-suite/tests/test_contract_freeze.py` lines 20-22
**Apply to:** `test_v1_8_safety_baseline.py` (pyproject.toml check)
```python
# Package-local (from test file to package root):
PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src" / "inkstatute_channels_qqbot"

# Repo-root (from test file to repo root):
REPO_ROOT = Path(__file__).resolve().parents[3]
```
**Convention:** Use `Path(__file__).resolve().parents[N]` for deterministic path resolution. `parents[1]` = package root (for pyproject.toml), `parents[3]` = repo root.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All files have analogs |

## Metadata

**Analog search scope:**
- `packages/channels/qqbot/tests/` — 4 test files scanned
- `packages/contract-test-suite/tests/` — 3 test files scanned
- `packages/contract-test-suite/fixtures/` — 1 JSON fixture scanned
- `packages/platform-runtime/src/platform_runtime/` — 2 source files scanned
- `packages/channels/qqbot/` — 1 pyproject.toml scanned
- `scripts/` — 1 gate runner scanned
- `.planning/` — JSON artifacts checked
- Git history (`3b12f52^`) — deleted template file recovered

**Files scanned:** 12
**Pattern extraction date:** 2026-07-07
