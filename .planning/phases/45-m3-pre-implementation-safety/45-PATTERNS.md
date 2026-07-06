# Phase 45: M3 Pre-Implementation Safety - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 5 (4 modified + 1 documentation artifact)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | model (frozen dataclass) | config (default-off flags) | itself — v1.6 M2 flag additions (Phase 36) | exact (self-modification) |
| `packages/platform-runtime/tests/test_feature_flags.py` | test | unit (assertion) | itself — existing v1.6 default-off + introspection tests | exact (self-extension) |
| `packages/contract-test-suite/tests/test_contract_count_freeze.py` | test | unit (runtime introspection) | itself — existing BackendAdapter/ChannelAdapter count freeze | exact (self-extension) |
| `services/admin-console-api/tests/test_contract_freeze.py` | test | unit (set equality) | itself — existing 12-flag hardcoded set assertion | exact (self-modification) |
| V2 human gate isolation documentation (VERIFICATION.md / SUMMARY.md) | documentation | file-I/O (markdown) | `.planning/milestones/v1.6-phases/36-m2-pre-implementation-safety/36-SUMMARY.md` | role-match |

## Pattern Assignments

### `packages/platform-runtime/src/platform_runtime/feature_flags.py` (model, config)

**Analog:** itself — the existing 12-flag v1.6 dataclass. Phase 36 (M2 safety) added 6 flags using this exact pattern.

**Current structure** (lines 1-38 — full file):
```python
"""Default-off feature flags for Phase 10 runtime lanes."""

from __future__ import annotations

from dataclasses import dataclass, fields


class RuntimeFeatureDisabledError(RuntimeError):
    """Raised when a runtime lane is used without explicit opt-in."""


@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False
    context_assembly_enabled: bool = False
    router_service_enabled: bool = False
    skill_registry_enabled: bool = False
    admin_api_enabled: bool = False
    qqbot_channel_enabled: bool = False
    codex_backend_enabled: bool = False
    provider_model_backend_enabled: bool = False

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")


__all__ = [
    "RuntimeFeatureDisabledError",
    "RuntimeFeatureFlags",
]
```

**Core pattern — add 9 fields after line 25 (`provider_model_backend_enabled`), all `= False`:**
```python
    # M3 flags (9) — all default OFF, gated by require_enabled
    session_memory_enabled: bool = False
    mcp_registry_enabled: bool = False
    model_gateway_enabled: bool = False
    multi_agent_enabled: bool = False
    skill_registry_write_enabled: bool = False
    hybrid_routing_enabled: bool = False
    web_sse_channel_enabled: bool = False
    rbac_enabled: bool = False
    multi_tenant_enabled: bool = False
```

**Critical:** The `require_enabled` method (lines 27-32) uses `dataclasses.fields(self)` introspection — it automatically recognizes new flags with NO code change. Do NOT modify `require_enabled`. The `__all__` export list (lines 35-38) stays unchanged (it exports the class, not individual flags).

**Error handling pattern:** `RuntimeFeatureDisabledError(RuntimeError)` (line 8-9) — already defined, no change needed. Two error messages: `"unknown runtime feature flag: {flag_name}"` (unknown flag) and `"runtime feature flag disabled: {flag_name}"` (flag exists but is False).

---

### `packages/platform-runtime/tests/test_feature_flags.py` (test, unit)

**Analog:** itself — existing v1.6 default-off + introspection tests (lines 1-58).

**Current structure** (lines 1-58 — full file):
```python
from __future__ import annotations

import unittest
from dataclasses import fields

from platform_runtime import RuntimeFeatureDisabledError, RuntimeFeatureFlags


class RuntimeFeatureFlagsTests(unittest.TestCase):
    def test_all_runtime_lanes_default_to_false(self) -> None:
        flags = RuntimeFeatureFlags()
        # ... 12 assertFalse assertions (lines 13-24)

    def test_all_m2_flags_default_to_false_via_introspection(self) -> None:
        default_flags = RuntimeFeatureFlags()
        for field in fields(RuntimeFeatureFlags):
            with self.subTest(flag=field.name):
                self.assertFalse(getattr(default_flags, field.name))

    def test_explicit_opt_in_satisfies_require_enabled(self) -> None:
        flags = RuntimeFeatureFlags(run_runtime_enabled=True)
        flags.require_enabled("run_runtime_enabled")

    def test_disabled_flag_raises_package_error(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: run_runtime_enabled",
        ):
            flags.require_enabled("run_runtime_enabled")

    def test_unknown_flag_raises_deterministic_error(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "unknown runtime feature flag: missing_lane",
        ):
            flags.require_enabled("missing_lane")
```

**Imports pattern** (lines 1-6):
```python
from __future__ import annotations
import unittest
from dataclasses import fields
from platform_runtime import RuntimeFeatureDisabledError, RuntimeFeatureFlags
```
Note: imports from `platform_runtime` (the package `__init__`), not `platform_runtime.feature_flags` directly. Keep this import style.

**Core pattern — add a new `M3FeatureFlagDefaultTests` class after the existing class (after line 55):**
```python
class M3FeatureFlagDefaultTests(unittest.TestCase):
    """Verify all 9 M3 feature flags default to False and require_enabled gates them."""

    M3_FLAGS = (
        "session_memory_enabled",
        "mcp_registry_enabled",
        "model_gateway_enabled",
        "multi_agent_enabled",
        "skill_registry_write_enabled",
        "hybrid_routing_enabled",
        "web_sse_channel_enabled",
        "rbac_enabled",
        "multi_tenant_enabled",
    )

    def test_all_m3_flags_default_false(self) -> None:
        flags = RuntimeFeatureFlags()
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                self.assertIs(getattr(flags, flag_name), False)

    def test_all_m3_flags_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                with self.assertRaises(RuntimeFeatureDisabledError):
                    flags.require_enabled(flag_name)

    def test_all_m3_flags_require_enabled_passes_when_true(self) -> None:
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                kwargs = {flag_name: True}
                flags = RuntimeFeatureFlags(**kwargs)
                flags.require_enabled(flag_name)

    def test_all_m3_flags_field_exists(self) -> None:
        field_names = {f.name for f in fields(RuntimeFeatureFlags)}
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                self.assertIn(flag_name, field_names)
```

**Also rename** the existing introspection test (line 26) from `test_all_m2_flags_default_to_false_via_introspection` to a version-agnostic name like `test_all_flags_default_to_false_via_introspection`. This test already iterates ALL fields via `dataclasses.fields()`, so it automatically covers the 9 new M3 flags — no logic change needed, just the rename. The explicit per-flag `test_all_runtime_lanes_default_to_false` (lines 10-24) can optionally be extended with 9 more `assertFalse` assertions, but the introspection test already covers this.

**Testing pattern:** Uses `self.subTest(flag=flag_name)` for per-flag isolation. Uses `self.assertIs(..., False)` (identity check, not just falsy) for default-off assertions. Uses `self.assertRaises(RuntimeFeatureDisabledError)` for the disabled-lane gate.

---

### `packages/contract-test-suite/tests/test_contract_count_freeze.py` (test, unit — runtime introspection)

**Analog:** itself — existing BackendAdapter(9) + ChannelAdapter(6) + AdapterCapabilitySet(14) count freeze (lines 1-59).

**Current structure** (lines 1-59 — full file):
```python
"""Contract-count freeze tests (SAFETY-02).

Freezes the method/field counts of the three core contract surfaces at the
v1.5 baseline so that any accidental addition or removal during M2 is caught
by the contract-test-suite gate.

The baseline values are verified by runtime introspection, not by manual
counting from research documents (which contained miscounts).
"""

from __future__ import annotations

import unittest
from dataclasses import fields

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_runtime.protocols import BackendAdapter, ChannelAdapter


class ContractCountFreezeTests(unittest.TestCase):
    """Assert contract surface counts remain frozen at the v1.5 baseline."""

    BACKEND_ADAPTER_METHOD_COUNT = 9
    ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14
    CHANNEL_ADAPTER_METHOD_COUNT = 6

    def test_backend_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.BACKEND_ADAPTER_METHOD_COUNT,
            f"BackendAdapter Protocol method count changed: "
            f"expected {self.BACKEND_ADAPTER_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )

    def test_adapter_capability_set_field_count_unchanged(self) -> None:
        field_names = [f.name for f in fields(AdapterCapabilitySet)]
        self.assertEqual(
            len(field_names),
            self.ADAPTER_CAPABILITY_SET_FIELD_COUNT,
            f"AdapterCapabilitySet field count changed: "
            f"expected {self.ADAPTER_CAPABILITY_SET_FIELD_COUNT}, "
            f"got {len(field_names)}: {field_names}",
        )

    def test_channel_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.CHANNEL_ADAPTER_METHOD_COUNT,
            f"ChannelAdapter Protocol method count changed: "
            f"expected {self.CHANNEL_ADAPTER_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )
```

**Imports pattern** (lines 11-17):
```python
from __future__ import annotations
import unittest
from dataclasses import fields
from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_runtime.protocols import BackendAdapter, ChannelAdapter
```

**Core pattern — extend with RouterPort and SkillRegistryPort:**

Add imports (after line 17):
```python
from inkstatute_router_service.port import RouterPort
from inkstatute_skill_registry.registry import SkillRegistryPort
```

These imports resolve because the `contract-test-suite` gate PYTHONPATH (line 158 of `scripts/run_v2_gates.py`) already includes `router_service_src` and `skill_registry_src`:
```python
Gate(
    "contract-test-suite",
    (py, "-m", "unittest", "discover", "-s", "packages/contract-test-suite/tests"),
    (contract_src, platform_src, platform_runtime_src, wecom_src, hermes_src,
     hermes_backend_src, read_view_src, feedback_src, solution_loader_src,
     lawfirm_solution_src, demo_non_legal_solution_src, skill_registry_src,
     router_service_src, codex_backend_src, provider_model_backend_src,
     admin_api_src, channel_core_src, qqbot_src),
),
```

Add class constants (after line 25):
```python
    ROUTER_PORT_METHOD_COUNT = 1
    SKILL_REGISTRY_PORT_METHOD_COUNT = 3
```

Add two test methods (after line 55, before `if __name__`):
```python
    def test_router_port_method_count_unchanged(self) -> None:
        methods = [m for m in dir(RouterPort) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.ROUTER_PORT_METHOD_COUNT,
            f"RouterPort Protocol method count changed: "
            f"expected {self.ROUTER_PORT_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )

    def test_skill_registry_port_method_count_unchanged(self) -> None:
        methods = [m for m in dir(SkillRegistryPort) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.SKILL_REGISTRY_PORT_METHOD_COUNT,
            f"SkillRegistryPort Protocol method count changed: "
            f"expected {self.SKILL_REGISTRY_PORT_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )
```

**Verified baseline values** (from runtime introspection of actual Protocol definitions):

| Protocol | File | Methods | Count |
|----------|------|---------|-------|
| `RouterPort` | `packages/router-service/src/inkstatute_router_service/port.py` lines 15-29 | `decide` | 1 |
| `SkillRegistryPort` | `packages/skill-registry/src/inkstatute_skill_registry/registry.py` lines 16-28 | `list_skills`, `get_skill`, `search` | 3 |

**RouterPort definition** (port.py lines 15-29):
```python
class RouterPort(Protocol):
    """Protocol for injectable router implementations."""

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        """Produce a normalized ``RouteDecision`` from *context*."""
        ...
```

**SkillRegistryPort definition** (registry.py lines 16-28):
```python
class SkillRegistryPort(Protocol):
    """Read-only Skill Registry protocol — no write methods."""

    def list_skills(self) -> list[NeutralSkillDescriptor]: ...

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]: ...
```

**Testing pattern:** Uses `dir(Protocol)` filtered by `not m.startswith("_")` for method counting (runtime introspection — robust against ordering, catches add/remove). Uses hardcoded class constants for baseline values. Error message includes both expected and actual count plus the full method list for debugging.

---

### `services/admin-console-api/tests/test_contract_freeze.py` (test, unit — set equality)

**Analog:** itself — existing 12-flag hardcoded set assertion (lines 45-61).

**Current structure** (lines 1-75 — full file):
```python
"""Contract freeze verification tests (SAFETY-02, SAFETY-06).

Verifies that Phase 42 did not modify any contract freeze protected
files: ``packages/platform-contract/``, ``packages/platform-runtime/
protocols.py``, and ``packages/platform-runtime/src/platform_runtime/
feature_flags.py``.
"""

from __future__ import annotations

import unittest
from dataclasses import fields

import platform_contract
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter


class ContractFreezeTests(unittest.TestCase):
    """Assert the contract freeze protected surfaces are unchanged."""

    def test_admin_api_enabled_already_exists_in_feature_flags(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertTrue(hasattr(flags, "admin_api_enabled"))

    def test_admin_api_enabled_defaults_false(self) -> None:
        self.assertIs(RuntimeFeatureFlags().admin_api_enabled, False)

    def test_feature_flags_has_all_m2_flags(self) -> None:
        flag_names = {f.name for f in fields(RuntimeFeatureFlags)}
        self.assertIn("admin_api_enabled", flag_names)
        self.assertIn("router_service_enabled", flag_names)
        self.assertIn("skill_registry_enabled", flag_names)
        self.assertIn("qqbot_channel_enabled", flag_names)
        self.assertIn("codex_backend_enabled", flag_names)
        self.assertIn("provider_model_backend_enabled", flag_names)

    def test_no_new_fields_added_to_feature_flags(self) -> None:
        flag_names = {f.name for f in fields(RuntimeFeatureFlags)}
        expected_flags = {
            "run_runtime_enabled",
            "streaming_lane_enabled",
            "channel_delivery_enabled",
            "approval_lane_enabled",
            "contract_log_enabled",
            "context_assembly_enabled",
            "router_service_enabled",
            "skill_registry_enabled",
            "admin_api_enabled",
            "qqbot_channel_enabled",
            "codex_backend_enabled",
            "provider_model_backend_enabled",
        }
        self.assertEqual(flag_names, expected_flags)

    def test_protocols_py_not_modified_by_phase42(self) -> None:
        self.assertTrue(hasattr(BackendAdapter, "__protocol_attrs__") or BackendAdapter is not None)
        self.assertTrue(hasattr(ChannelAdapter, "__protocol_attrs__") or ChannelAdapter is not None)

    def test_platform_contract_importable(self) -> None:
        self.assertIsNotNone(platform_contract)
```

**Imports pattern** (lines 16-23):
```python
from __future__ import annotations
import unittest
from dataclasses import fields
import platform_contract
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter
```
Note: this file imports from `platform_runtime.feature_flags` (direct module), unlike `test_feature_flags.py` which imports from `platform_runtime` (package `__init__`). Keep each file's existing import style.

**Core pattern — update `test_no_new_fields_added_to_feature_flags` (lines 45-61) to include all 21 flags:**
```python
    def test_no_new_fields_added_to_feature_flags(self) -> None:
        flag_names = {f.name for f in fields(RuntimeFeatureFlags)}
        expected_flags = {
            # V2 flags (6)
            "run_runtime_enabled",
            "streaming_lane_enabled",
            "channel_delivery_enabled",
            "approval_lane_enabled",
            "contract_log_enabled",
            "context_assembly_enabled",
            # M2 flags (6)
            "router_service_enabled",
            "skill_registry_enabled",
            "admin_api_enabled",
            "qqbot_channel_enabled",
            "codex_backend_enabled",
            "provider_model_backend_enabled",
            # M3 flags (9)
            "session_memory_enabled",
            "mcp_registry_enabled",
            "model_gateway_enabled",
            "multi_agent_enabled",
            "skill_registry_write_enabled",
            "hybrid_routing_enabled",
            "web_sse_channel_enabled",
            "rbac_enabled",
            "multi_tenant_enabled",
        }
        self.assertEqual(flag_names, expected_flags)
```

**Critical:** This test WILL FAIL if not updated in the same PR that adds the 9 M3 flags — `flag_names` will have 21 entries while `expected_flags` has 12. The `assertEqual(flag_names, expected_flags)` is a set equality check that catches both unexpected additions AND missing flags.

**Testing pattern:** Uses `{f.name for f in fields(RuntimeFeatureFlags)}` to get the actual flag set, then `assertEqual` against a hardcoded expected set. The test name `test_no_new_fields_added_to_feature_flags` is Phase-42-specific — consider updating the docstring to reflect the M3 baseline (21 flags).

---

### V2 human gate isolation documentation (documentation, file-I/O)

**Analog:** `.planning/milestones/v1.6-phases/36-m2-pre-implementation-safety/36-SUMMARY.md` — the M2 safety phase summary that documented V2 human gate isolation.

**This is a documentation artifact produced during execute (VERIFICATION.md or SUMMARY.md), not a code file.** It is not planned as a separate code file — it is written during the phase execute step.

**Content pattern** (from RESEARCH.md Example 5):
1. All 9 M3 feature flags default to `False`, so no M3 lane is active during V2 human gate execution.
2. The contract freeze (SHA-256 baseline + method-count freeze) ensures no V2 contract surface is modified.
3. The 19 V2 gates pass green, confirming no regression in the V2 baseline.
4. Human gate evidence remains carried forward (`.planning/STATE.md` lines 56-59) — Phase 45 does not mark them complete.

**Reference:** `.planning/STATE.md` lines 56-59 carry forward the V2 human gates (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial). Phase 45 documents non-contamination, does not execute live gates.

## Shared Patterns

### Pattern A: Default-OFF Feature Flag Declaration

All new flags follow the exact same declaration pattern — `field_name: bool = False` in the `@dataclass(frozen=True, slots=True)` `RuntimeFeatureFlags` class. No factory, no env-var binding, no default-True. The `require_enabled` method uses `dataclasses.fields()` introspection and needs NO modification when flags are added.

**Applied to:** `feature_flags.py` (add 9 fields)

### Pattern B: Introspection-Based Default-Off Test

The `test_all_*_flags_default_to_false_via_introspection` pattern iterates `fields(RuntimeFeatureFlags)` with `self.subTest(flag=field.name)` and asserts `self.assertFalse(getattr(default_flags, field.name))`. This automatically covers new flags. Per-flag explicit tests use `self.assertIs(getattr(flags, flag_name), False)` (identity check).

**Applied to:** `test_feature_flags.py` (rename existing + add M3-specific class)

### Pattern C: Runtime Introspection Contract-Count Freeze

`dir(Protocol)` filtered by `not m.startswith("_")` counts public methods. `dataclasses.fields(DataClass)` counts fields. Hardcoded class constants hold baseline counts. `assertEqual` with a descriptive f-string message showing expected vs actual + full list.

**Applied to:** `test_contract_count_freeze.py` (add RouterPort + SkillRegistryPort)

### Pattern D: Hardcoded Flag-Set Equality Assertion

`{f.name for f in fields(RuntimeFeatureFlags)}` builds the actual set; `assertEqual(actual, expected_hardcoded_set)` catches both additions and removals. Must be updated in lockstep with flag additions.

**Applied to:** `services/admin-console-api/tests/test_contract_freeze.py` (update 12 → 21)

### Pattern E: Gate Suite as Single Entry Point (UNCHANGED)

`scripts/run_v2_gates.py` defines 19 `Gate` dataclasses. Phase 45 adds NO new gates. The `contract-test-suite` gate (line 156-158) already has the PYTHONPATH entries (`router_service_src`, `skill_registry_src`) needed for the new `RouterPort`/`SkillRegistryPort` imports in `test_contract_count_freeze.py`. The `test_v2_gates_includes_traceability_gate` test hardcodes `len(gate_names) == 19` — do not break this.

**Applied to:** verification step (run `python scripts/run_v2_gates.py` → 19/19 green)

## Unchanged Files (Must Continue Passing)

| File | Why Unchanged | Gate |
|------|---------------|------|
| `packages/contract-test-suite/tests/test_contract_freeze.py` | SHA-256 baseline hash test for 31 files — no `packages/platform-contract/` file is modified in Phase 45 | contract-test-suite |
| `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` | 31 file hashes (26 schema + 4 Python binding + 1 protocols.py) — must NOT be regenerated | contract-test-suite |
| `scripts/run_v2_gates.py` | 19 gate definitions — no new gates added | (is the runner) |
| `.github/workflows/v2-contract-gates.yml` | CI workflow calls `run_v2_gates.py` — no change needed | CI |

## Don't Hand-Roll

| Problem | Use Instead | Why |
|---------|-------------|-----|
| Counting Protocol methods manually | `dir(Protocol)` filtered by `not m.startswith("_")` | v1.6 research docs had miscounts (said 8 for BackendAdapter, actual is 9). Runtime introspection is authoritative. |
| Detecting file modifications | SHA-256 hash comparison in `test_contract_freeze.py` | Already implemented with 31-file baseline. Do not reimplement. |
| Flag default enforcement | `dataclasses.fields()` introspection in `test_all_flags_default_to_false_via_introspection` | Catches future flags that forget to default-OFF automatically. Already proven in v1.6. |
| Gate coverage verification | `test_gate_coverage.py` meta-test | Already asserts every `packages/*/src` and `services/*/src` is covered. Do not reimplement. |
| Gate count enforcement | `test_audit_v2_requirements.py` hardcodes `len(gate_names) == 19` | Do not add gates — this test enforces the 19-gate baseline. |
