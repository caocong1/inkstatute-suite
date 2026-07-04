# Phase 36 Research

**Phase:** 36
**Name:** M2 Pre-Implementation Safety
**Researched:** 2026-07-03

## Executive Summary

Phase 36 implements six cross-cutting safety measures (SAFETY-01 through SAFETY-06) that must be in place before any M2 feature code is written. All changes are additive — new tests, new flags, unified keys, fixed bypass — with zero breaking changes to the 9 V2 gates (479 tests). The measures protect the V2 gate suite and the parallel V2 human gates (Phase 5 UAT + Phase 8 lawyer trial) from M2 prototype code accidentally affecting live acceptance.

The most critical finding is that the research documents (SUMMARY.md, PITFALLS.md) contain miscounts for Protocol method counts. The actual code inspection reveals: `BackendAdapter` has **9 methods** (not 8 as stated in research), `ChannelAdapter` has **6 methods** (not 5 as stated in PITFALLS), and `AdapterCapabilitySet` has **14 fields** (matches research). The baseline values for SAFETY-02 must be captured from actual code, not from research text. Additionally, `_FORBIDDEN_FULL_TEXT_KEYS` in `store.py` contains **6 keys** in the set, plus `raw_payload` checked separately = **7 total forbidden keys**, while `privacy.py` only checks **1 key** (`raw_payload`).

## SAFETY-01: Selection Gate Bypass Fix

### Current Code

**File:** `services/wecom-service/src/wecom_service/agent_backend.py` (lines 47-51)

```python
metadata = _metadata(manifest)
production_ready = bool(metadata.get("production_ready", requested_mode == AgentBackendMode.HERMES.value))
live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value
if requested_mode != AgentBackendMode.HERMES.value and metadata.get("production_ready") is True:
    live_acceptance_allowed = True
```

**The bypass:** Lines 50-51 override the Hermes-only live acceptance constraint. If a non-Hermes manifest (Codex, provider_model) sets `metadata.production_ready: True`, the `live_acceptance_allowed` flag becomes `True`, making the prototype eligible for live WeCom turns during parallel V2 human gates.

**Existing test coverage:** `services/wecom-service/tests/test_agent_backend.py` line 30-37 tests `test_codex_future_manifest_is_contract_compatible_not_live_ready` — but only with `production_ready=False`. There is no test asserting that `production_ready=True` on a non-Hermes manifest still results in `live_acceptance_allowed=False`.

### Fix Approach

Remove lines 50-51 entirely. The correct logic is already on line 49: `live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value`. This means `live_acceptance_allowed` is `True` only when both (a) `production_ready` is truthy AND (b) the mode is Hermes. Non-Hermes modes get `False` regardless of `production_ready` metadata.

**Proposed change to `agent_backend.py`:**

```python
metadata = _metadata(manifest)
production_ready = bool(metadata.get("production_ready", requested_mode == AgentBackendMode.HERMES.value))
live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value
# Lines 50-51 removed — non-Hermes modes are never live-acceptance-eligible
```

This is a 2-line deletion. No new code, no new dependencies. The `AgentBackendSelection` dataclass and all other logic remain unchanged.

### Test Approach

**File to modify:** `services/wecom-service/tests/test_agent_backend.py`

Add a test that proves `select_agent_backend` returns `live_acceptance_allowed=False` for all non-Hermes modes (Codex, provider_model) even when `metadata.production_ready` is explicitly `True`:

```python
def test_non_hermes_manifest_with_production_ready_true_is_not_live_eligible(self) -> None:
    for mode in (AgentBackendMode.CODEX, AgentBackendMode.PROVIDER_MODEL):
        with self.subTest(mode=mode):
            manifest = self.manifest(mode, no_channel_io=True, production_ready=True)
            selection = select_agent_backend({"agent_backend": {"mode": mode.value}}, [manifest])
            self.assertEqual(selection.mode, mode.value)
            self.assertTrue(selection.contract_compatible)
            self.assertFalse(selection.live_acceptance_allowed)
```

The existing `manifest()` helper (line 43-67) already accepts `production_ready` as a parameter, so no new fixture builder is needed.

**Gate impact:** `wecom-service` gate. The existing test `test_codex_future_manifest_is_contract_compatible_not_live_ready` (line 30-37) continues to pass since it uses `production_ready=False`. The existing `test_selects_valid_hermes_manifest_for_live_acceptance` (line 15-22) continues to pass since Hermes with `production_ready=True` still gets `live_acceptance_allowed=True`.

## SAFETY-02: Contract-Count Assertion Tests

### What to Count

Three contract surfaces must be frozen for M2:

1. **`BackendAdapter` Protocol methods** — defined in `packages/platform-runtime/src/platform_runtime/protocols.py` lines 222-239
2. **`AdapterCapabilitySet` fields** — defined in `packages/platform-contract/src/platform_contract/agent_adapter.py` lines 18-33
3. **`ChannelAdapter` Protocol methods** — defined in `packages/platform-runtime/src/platform_runtime/protocols.py` lines 208-219

### Baseline Values (captured from actual code, NOT from research text)

| Contract Surface | Actual Count | Research Said | Method/Field Names |
|-----------------|-------------|---------------|-------------------|
| `BackendAdapter` methods | **9** | 8 (miscount) | `backend_id`, `capabilities`, `bootstrap_check`, `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts` |
| `AdapterCapabilitySet` fields | **14** | 14 (correct) | `hook_event_support`, `invocation_mode`, `feedback_target_support`, `session_read_support`, `artifact_return_support`, `trace_support`, `no_channel_io`, `run_invocation_modes`, `stream_event_support`, `cancel_support`, `approval_support`, `live_update_support`, `parallel_task_support`, `session_memory_support` |
| `ChannelAdapter` methods | **6** | 5 (miscount in PITFALLS) | `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health` |

**Critical note:** The research documents (SUMMARY.md line 10, PITFALLS.md line 16, line 346) contain miscounts. The baseline values above are verified by runtime introspection (`dir()` + `dataclasses.fields()`). The test must use these actual values.

### Test Approach

**File to create:** `packages/contract-test-suite/tests/test_contract_count_freeze.py`

This test uses runtime introspection to count methods/fields and asserts they match the baseline. It does NOT import the Protocol classes and count manually — it uses `inspect` / `dataclasses.fields` for robustness:

```python
import unittest
from dataclasses import fields
from platform_runtime.protocols import BackendAdapter, ChannelAdapter
from platform_contract.agent_adapter import AdapterCapabilitySet

class ContractCountFreezeTests(unittest.TestCase):
    BACKEND_ADAPTER_METHOD_COUNT = 9
    ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14
    CHANNEL_ADAPTER_METHOD_COUNT = 6

    def test_backend_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith('_')]
        self.assertEqual(len(methods), self.BACKEND_ADAPTER_METHOD_COUNT,
            f"BackendAdapter Protocol method count changed: expected {self.BACKEND_ADAPTER_METHOD_COUNT}, got {len(methods)}: {methods}")

    def test_adapter_capability_set_field_count_unchanged(self) -> None:
        field_names = [f.name for f in fields(AdapterCapabilitySet)]
        self.assertEqual(len(field_names), self.ADAPTER_CAPABILITY_SET_FIELD_COUNT,
            f"AdapterCapabilitySet field count changed: expected {self.ADAPTER_CAPABILITY_SET_FIELD_COUNT}, got {len(field_names)}: {field_names}")

    def test_channel_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith('_')]
        self.assertEqual(len(methods), self.CHANNEL_ADAPTER_METHOD_COUNT,
            f"ChannelAdapter Protocol method count changed: expected {self.CHANNEL_ADAPTER_METHOD_COUNT}, got {len(methods)}: {methods}")
```

**Gate placement:** This test goes in `packages/contract-test-suite/tests/` and is picked up by the `contract-test-suite` gate (line 100-104 in `run_v2_gates.py`). The gate's PYTHONPATH already includes `platform_src` and `platform_runtime_src` (line 103), so both `platform_contract` and `platform_runtime` imports resolve.

**Baseline storage:** The baseline values are hardcoded as class constants in the test file. This is the simplest approach — no external baseline file needed for counts. If counts change intentionally in a future phase, the constants are updated in the same PR that changes the Protocol.

## SAFETY-03: Privacy Scrub Unification

### Current State

**`store.py`** (`packages/platform-runtime/src/platform_runtime/store.py` lines 108-137):

The `_reject_forbidden_payload_storage` function checks two things:
1. `raw_payload` key (line 110-111) — raises `ContractLogPrivacyError`
2. Any key in `_FORBIDDEN_FULL_TEXT_KEYS` set (line 112-115) — raises `ContractLogPrivacyError`

The `_FORBIDDEN_FULL_TEXT_KEYS` set (lines 130-137) contains **6 keys**:
```python
_FORBIDDEN_FULL_TEXT_KEYS = {
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
}
```

Total forbidden keys at store-time: **7** (raw_payload + 6 full-text keys).

**`privacy.py`** (`services/conversation-read-view/src/conversation_read_view/privacy.py` lines 9-43):

The `scrub_contract_payload` function only checks for `FORBIDDEN_RAW_PAYLOAD_KEY = "raw_payload"` (line 9). It does NOT check any of the 6 full-text keys. This means:
- Store-time: 7 keys are rejected (raw_payload + 6 full-text keys)
- Read-time: only 1 key is rejected (raw_payload)
- **Gap:** The 6 full-text keys pass read-time scrubbing. If they somehow get into contract logs (e.g., through a code path that bypasses the store), they would be exposed in API responses.

### Unified Keys

Create a shared forbidden keys set that both `store.py` and `privacy.py` reference. The unified set should include:

1. The existing 6 full-text keys from `store.py`
2. `raw_payload` (currently checked separately in both files)
3. **4 new backend field names** that M2 backends may produce:
   - `prompt_content` — provider_model adapter may include prompt text
   - `completion_text` — provider_model adapter may include completion text
   - `function_call_result` — Codex adapter may include function call output
   - `tool_output` — Codex/provider_model may include tool execution output

**Total unified forbidden keys: 11** (raw_payload + 6 existing full-text + 4 new backend fields)

### Implementation Approach

**Option A (preferred): Shared module in platform-runtime**

Create a new module `packages/platform-runtime/src/platform_runtime/privacy_keys.py`:

```python
"""Unified forbidden full-text keys for contract log privacy."""

from __future__ import annotations

FORBIDDEN_RAW_PAYLOAD_KEY = "raw_payload"

FORBIDDEN_FULL_TEXT_KEYS = frozenset({
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
    "prompt_content",
    "completion_text",
    "function_call_result",
    "tool_output",
})

ALL_FORBIDDEN_KEYS = frozenset({FORBIDDEN_RAW_PAYLOAD_KEY}) | FORBIDDEN_FULL_TEXT_KEYS
```

Then update `store.py` to import from this module:
```python
from .privacy_keys import ALL_FORBIDDEN_KEYS, FORBIDDEN_RAW_PAYLOAD_KEY
```
And simplify `_reject_forbidden_payload_storage` to check `ALL_FORBIDDEN_KEYS` in a single pass.

Update `privacy.py` in conversation-read-view to import the shared keys. Since conversation-read-view already has `platform_runtime_src` in its PYTHONPATH (line 82 of `run_v2_gates.py`), it can import from `platform_runtime.privacy_keys`:

```python
from platform_runtime.privacy_keys import ALL_FORBIDDEN_KEYS, FORBIDDEN_RAW_PAYLOAD_KEY
```

Update `scrub_contract_payload` to check all forbidden keys, not just `raw_payload`.

**Option B (minimal change): Duplicate the set in both files**

Less DRY but avoids cross-package import. Not recommended — the whole point is unification.

### Scrub Application Paths

**Current API response paths in `api.py`** (`services/conversation-read-view/src/conversation_read_view/api.py`):

| Route | Line | Applies `scrub_contract_payload`? |
|-------|------|----------------------------------|
| `/conversations/{id}` | 18-23 | NO — uses `_with_contract_metadata` only |
| `/tasks/{id}` | 25-32 | NO — uses `_with_contract_metadata` only |
| `/feedback` | 34-56 | YES — line 48: `[scrub_contract_payload(item) for item in ...]` |

**Note:** `read_model.py` line 52 applies `scrub_contract_payload` to each record event during `from_records`, so the read model data is scrubbed at load time. However, defense-in-depth requires every API response path to scrub independently.

**Fix:** Update `_with_contract_metadata` (line 93-98) to apply `scrub_contract_payload` before adding metadata:

```python
def _with_contract_metadata(body: dict[str, Any]) -> dict[str, Any]:
    scrubbed = scrub_contract_payload(body)
    response = dict(scrubbed) if isinstance(scrubbed, dict) else {"data": scrubbed}
    metadata = dict(response.get("metadata", {})) if isinstance(response.get("metadata"), Mapping) else {}
    metadata["derived_from_contract_log"] = True
    response["metadata"] = metadata
    return response
```

This ensures all three response paths (`/conversations/`, `/tasks/`, `/feedback`) apply scrubbing.

### Test Approach

**File to create/modify:** `services/conversation-read-view/tests/test_privacy_unification.py` (new) and existing `packages/contract-test-suite/tests/test_privacy_gates.py` (extend)

Tests to write:
1. **Unified keys test:** Assert `_FORBIDDEN_FULL_TEXT_KEYS` in `store.py` and the forbidden keys in `privacy.py` are the same set (import both and compare).
2. **New backend field rejection at store-time:** Assert `InMemoryContractLogStore.append` raises `ContractLogPrivacyError` for events containing `prompt_content`, `completion_text`, `function_call_result`, `tool_output`.
3. **New backend field rejection at read-time:** Assert `scrub_contract_payload` raises `ValueError` for payloads containing the new field names.
4. **Every API response path is scrubbed:** Assert `/conversations/{id}`, `/tasks/{id}`, and `/feedback` responses do not contain any forbidden keys when the underlying read model data contains them.

**Gate impact:** `conversation-read-view` gate and `contract-test-suite` gate. Both already have the necessary PYTHONPATH entries.

## SAFETY-04: M2 Feature Flags

### Existing Pattern

**File:** `packages/platform-runtime/src/platform_runtime/feature_flags.py` (lines 12-26)

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False
    context_assembly_enabled: bool = False

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")
```

All 6 existing flags default to `False`. The `require_enabled` method provides a runtime gate: calling code must check the flag before using the feature. The `dataclass(frozen=True, slots=True)` pattern ensures flags are immutable after construction.

**Existing test:** `packages/platform-runtime/tests/test_feature_flags.py` — `test_all_runtime_lanes_default_to_false` (line 9-16) asserts all 6 flags are `False` on default construction.

### New M2 Feature Flags

Add 6 new flags for M2 features, all defaulting to `False`:

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    # Existing V2 flags
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False
    context_assembly_enabled: bool = False
    # M2 feature flags (all default-OFF)
    router_service_enabled: bool = False
    skill_registry_enabled: bool = False
    admin_api_enabled: bool = False
    qqbot_channel_enabled: bool = False
    codex_backend_enabled: bool = False
    provider_model_backend_enabled: bool = False
```

The `require_enabled` method and `RuntimeFeatureDisabledError` need no changes — they already use `dataclasses.fields` for introspection, so new flags are automatically recognized.

### Test Approach

**File to modify:** `packages/platform-runtime/tests/test_feature_flags.py`

Update `test_all_runtime_lanes_default_to_false` to include the 6 new M2 flags:

```python
def test_all_runtime_lanes_default_to_false(self) -> None:
    flags = RuntimeFeatureFlags()

    # V2 flags
    self.assertFalse(flags.run_runtime_enabled)
    self.assertFalse(flags.streaming_lane_enabled)
    self.assertFalse(flags.channel_delivery_enabled)
    self.assertFalse(flags.approval_lane_enabled)
    self.assertFalse(flags.contract_log_enabled)
    self.assertFalse(flags.context_assembly_enabled)
    # M2 flags
    self.assertFalse(flags.router_service_enabled)
    self.assertFalse(flags.skill_registry_enabled)
    self.assertFalse(flags.admin_api_enabled)
    self.assertFalse(flags.qqbot_channel_enabled)
    self.assertFalse(flags.codex_backend_enabled)
    self.assertFalse(flags.provider_model_backend_enabled)
```

Add a test that uses `dataclasses.fields` to assert ALL flags default to `False` (catches future additions that forget to default-OFF):

```python
def test_all_flags_default_to_false_via_introspection(self) -> None:
    from dataclasses import fields
    flags = RuntimeFeatureFlags()
    for field in fields(RuntimeFeatureFlags):
        with self.subTest(flag=field.name):
            self.assertFalse(getattr(flags, field.name),
                f"feature flag {field.name} must default to False")
```

This introspection-based test is more robust — it automatically covers any new flags added in future phases.

**Gate impact:** `platform-runtime` gate (not explicitly in `run_v2_gates.py` but covered by `contract-test-suite` gate which includes `platform_runtime_src` in PYTHONPATH). The existing tests with `RuntimeFeatureFlags(run_runtime_enabled=True)` etc. continue to work since the new flags are optional with defaults.

## SAFETY-05: Generic Output Boundary Rules

### Existing Rules

**File:** `packages/platform-runtime/src/platform_runtime/output_boundary.py` (lines 82-108)

Three rule categories, all Hermes-specific:

**`_HARD_BLOCK_RULES`** (lines 82-91) — blocks the text entirely:
- `secret_like`: credential patterns (token, key, secret)
- `internal_path`: filesystem paths (`/path/to`, `C:\path`)
- `debug_trace`: `admin_notice`, `stack trace`, `traceback`, `delivery debug`, `runtime detail`

**`_OPERATOR_COMMAND_RULES`** (lines 93-98) — blocks slash commands:
- `operator_command`: `/command` patterns

**`_REWRITE_RULES`** (lines 100-108) — replaces with owned service notice:
- `backend_lifecycle`: `restart`, `reconnect`, `disconnect`, `shutting down`, `self-update`
- `tool_progress`: `tool progress`, `internal retrieval`, `memory sync`, `tool call`
- `approval_request`: `dangerous command`, `approval required`, `requires approval`
- `debug_trace`: `debug`, `diagnostic`

### New Generic Patterns

Add backend-agnostic patterns that catch the *class* of noise from any provider/model backend, not specific backend strings:

**Add to `_HARD_BLOCK_RULES`:**

```python
("provider_leak", r"\b(?:model|provider|api[_-]?key|quota|rate[_-]?limit|token[_-]?usage)\b"),
("api_error", r"\b(?:api key invalid|quota exceeded|rate limit retry|context window exceeded|insufficient quota)\b"),
("function_trace", r"\b(?:function call|tool output|token usage report|function_call_result)\b"),
```

**Add to `_REWRITE_RULES`:**

```python
("rate_limit_notice", r"\b(?:rate[_ ]?limit(?:ed|ing)?|too many requests|retrying(?: after)? \d+)\b"),
("context_window", r"\b(?:context (?:window|length) (?:exceeded|limit)|maximum context|token limit)\b"),
```

These patterns are generic — they catch "model", "provider", "api_key", "quota", "rate_limit", "token_usage" as concepts, not "glm-5.2" or "ollama-cloud" as specific names. They do not introduce any backend-specific string.

**Important:** The `test_runtime_source_does_not_embed_concrete_leak_examples` test (line 90-96 of `test_output_boundary.py`) asserts that `output_boundary.py` source code does not contain "Hermes", "WeCom", "lawfirm", "gateway", ".hermes". The new patterns must also not contain any concrete backend names. The patterns above use only generic terms.

### Test Approach

**File to modify:** `packages/platform-runtime/tests/test_output_boundary.py`

Add fixture-based tests with noise samples from generic provider/model backends:

```python
def test_blocks_provider_model_name_leakage(self) -> None:
    samples = [
        "The model glm-5.2 generated a response",
        "Provider: ollama-cloud, API key: sk-xxx",
        "Token usage: 1500 tokens consumed",
        "Quota exceeded for this request",
    ]
    boundary = DefaultAssistantOutputBoundary()
    for sample in samples:
        with self.subTest(sample=sample):
            decision = boundary.apply("ordinary_user", text=sample)
            self.assertEqual(decision.action, BoundaryAction.BLOCK)

def test_rewrites_rate_limit_and_context_window_notices(self) -> None:
    samples = [
        "Rate limit exceeded, retrying after 30 seconds",
        "Context window exceeded, please reduce input length",
        "Too many requests, please wait",
    ]
    boundary = DefaultAssistantOutputBoundary()
    for sample in samples:
        with self.subTest(sample=sample):
            decision = boundary.apply("ordinary_user", text=sample)
            self.assertEqual(decision.action, BoundaryAction.REWRITE)
            self.assertNotIn("rate", decision.visible_text.lower())
            self.assertNotIn("context", decision.visible_text.lower())

def test_blocks_function_call_traces(self) -> None:
    samples = [
        "Function call: web_search(query='legal precedent')",
        "Tool output: {\"result\": \"...\"}",
        "Token usage report: input=500, output=1000",
    ]
    boundary = DefaultAssistantOutputBoundary()
    for sample in samples:
        with self.subTest(sample=sample):
            decision = boundary.apply("ordinary_user", text=sample)
            self.assertEqual(decision.action, BoundaryAction.BLOCK)

def test_legal_business_text_still_allowed_with_new_rules(self) -> None:
    """Ensure new rules don't false-positive on legal business text."""
    samples = [
        "The supplier must cure the breach within 30 days.",
        "Under the contract, the buyer may terminate for material breach.",
        "The model clause requires notice before termination.",
    ]
    boundary = DefaultAssistantOutputBoundary()
    for sample in samples:
        with self.subTest(sample=sample):
            decision = boundary.apply("ordinary_user", text=sample)
            self.assertEqual(decision.action, BoundaryAction.ALLOW)
```

**Caution:** The word "model" appears in legal text ("the model clause"). The `provider_leak` regex `\bmodel\b` would false-positive on this. Consider making the pattern more specific: `\b(?:model[:\s]|provider[:\s]|api[_-]?key|quota|rate[_-]?limit|token[_-]?usage)\b` — requiring a colon or space after "model" to match "model: glm-5.2" but not "model clause". The test `test_legal_business_text_still_allowed_with_new_rules` catches this regression.

**Gate impact:** `platform-runtime` gate (via `contract-test-suite` gate). The existing `test_runtime_source_does_not_embed_concrete_leak_examples` test (line 90-96) continues to pass since no concrete backend names are added.

## SAFETY-06: Contract Freeze Baseline Hash

### Files to Hash

The contract freeze must cover all schema files and Python binding files that define the platform contract surface:

**Schema files (26 files):**
`packages/platform-contract/src/platform_contract/schemas/*.schema.json`

These are the JSON Schema definitions for all contract events. Any modification changes the contract surface.

**Python binding files (4 files):**
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — `AgentBackendMode`, `AdapterCapabilitySet`, `AgentBackendManifest`, `validate_agent_backend_manifest`
- `packages/platform-contract/src/platform_contract/enums.py` — all StrEnum definitions
- `packages/platform-contract/src/platform_contract/events.py` — all event dataclasses
- `packages/platform-contract/src/platform_contract/__init__.py` — public API surface

**Protocol definitions (1 file):**
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `BackendAdapter`, `ChannelAdapter`, `SolutionLoader`, `RunRuntime` Protocols and all supporting dataclasses

Total: **31 files** to hash.

### Baseline Storage

**File to create:** `packages/contract-test-suite/fixtures/contract_freeze_baseline.json`

This location is inside the contract-test-suite package, so it's automatically available to tests via the `LOCAL_FIXTURE_ROOT` path constant (`packages/contract-test-suite/fixtures/`). The baseline is a JSON object mapping relative file paths to SHA-256 hashes:

```json
{
  "generated_at": "2026-07-03T00:00:00Z",
  "algorithm": "sha256",
  "files": {
    "packages/platform-contract/src/platform_contract/schemas/agent_adapter_manifest.schema.json": "7791575e7fa9df0a...",
    "packages/platform-contract/src/platform_contract/schemas/agent_result.schema.json": "45cd6d465698538e...",
    "...": "...",
    "packages/platform-contract/src/platform_contract/agent_adapter.py": "<sha256>",
    "packages/platform-contract/src/platform_contract/enums.py": "<sha256>",
    "packages/platform-contract/src/platform_contract/events.py": "<sha256>",
    "packages/platform-contract/src/platform_contract/__init__.py": "<sha256>",
    "packages/platform-runtime/src/platform_runtime/protocols.py": "<sha256>"
  }
}
```

**Baseline generation script:** A one-time script (can be run manually or as part of the phase) generates the baseline:

```python
import hashlib, json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FILES_TO_HASH = [
    *sorted((REPO_ROOT / "packages/platform-contract/src/platform_contract/schemas").glob("*.schema.json")),
    REPO_ROOT / "packages/platform-contract/src/platform_contract/agent_adapter.py",
    REPO_ROOT / "packages/platform-contract/src/platform_contract/enums.py",
    REPO_ROOT / "packages/platform-contract/src/platform_contract/events.py",
    REPO_ROOT / "packages/platform-contract/src/platform_contract/__init__.py",
    REPO_ROOT / "packages/platform-runtime/src/platform_runtime/protocols.py",
]

baseline = {"algorithm": "sha256", "files": {}}
for path in FILES_TO_HASH:
    rel = str(path.relative_to(REPO_ROOT))
    baseline["files"][rel] = hashlib.sha256(path.read_bytes()).hexdigest()
```

### Comparison Approach

**File to create:** `packages/contract-test-suite/tests/test_contract_freeze.py`

```python
import hashlib
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "contract_freeze_baseline.json"

class ContractFreezeTests(unittest.TestCase):
    def test_schema_files_match_baseline_hash(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        for rel_path, expected_hash in baseline["files"].items():
            path = REPO_ROOT / rel_path
            with self.subTest(file=rel_path):
                self.assertTrue(path.exists(), f"contract file missing: {rel_path}")
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual_hash, expected_hash,
                    f"contract file modified from v1.5 baseline: {rel_path}")

    def test_no_new_schema_files_added_without_baseline(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        schema_root = REPO_ROOT / "packages/platform-contract/src/platform_contract/schemas"
        current_files = {str(p.relative_to(REPO_ROOT)) for p in schema_root.glob("*.schema.json")}
        baseline_files = set(baseline["files"].keys())
        new_files = current_files - baseline_files
        self.assertFalse(new_files,
            f"new schema files detected without baseline: {new_files}")
```

The test checks two directions:
1. **No existing file modified** — each file's current hash matches the baseline
2. **No new file added** — no schema files exist that aren't in the baseline

**Gate impact:** `contract-test-suite` gate (line 100-104 of `run_v2_gates.py`). The baseline fixture is in `packages/contract-test-suite/fixtures/` which is within the package. The test uses `REPO_ROOT` to resolve file paths, which is already a pattern used by `test_thin_layer_boundaries.py` (line 15: `from contract_test_suite.paths import ... REPO_ROOT`).

**When to update the baseline:** The baseline should only be updated when a phase explicitly modifies the contract surface (e.g., adding a new enum value for a new channel). The update must be a deliberate, documented action in the phase plan, not an accidental side effect. The test failure message clearly states "contract file modified from v1.5 baseline" to prompt review.

## Validation Architecture

### How the 6 Safety Measures Work Together

The 6 measures form a layered defense:

1. **SAFETY-01 (selection gate)** — prevents prototype backends from serving live turns (runtime-level gate)
2. **SAFETY-02 (contract-count freeze)** — prevents Protocol/capability drift that would break V2 gates (contract-level gate)
3. **SAFETY-03 (privacy scrub unification)** — prevents sensitive legal content from leaking through store or read paths (data-level gate)
4. **SAFETY-04 (feature flags)** — prevents M2 services from being implicitly ON (configuration-level gate)
5. **SAFETY-05 (output boundary)** — prevents backend noise from reaching users (output-level gate)
6. **SAFETY-06 (contract freeze hash)** — prevents schema/binding modifications during V2 human gates (file-level gate)

### Gate Impact Summary

| Safety Measure | Files Modified | Tests Added/Modified | Gate(s) Affected |
|---------------|---------------|---------------------|------------------|
| SAFETY-01 | `agent_backend.py` (2 lines deleted) | `test_agent_backend.py` (1 test added) | `wecom-service` |
| SAFETY-02 | None (test-only) | `test_contract_count_freeze.py` (new, 3 tests) | `contract-test-suite` |
| SAFETY-03 | `store.py`, `privacy.py`, `api.py`, new `privacy_keys.py` | `test_privacy_unification.py` (new), `test_privacy_gates.py` (extended) | `conversation-read-view`, `contract-test-suite` |
| SAFETY-04 | `feature_flags.py` (6 fields added) | `test_feature_flags.py` (2 tests added/modified) | `platform-runtime` (via `contract-test-suite`) |
| SAFETY-05 | `output_boundary.py` (rules added) | `test_output_boundary.py` (4 tests added) | `platform-runtime` (via `contract-test-suite`) |
| SAFETY-06 | New baseline JSON fixture | `test_contract_freeze.py` (new, 2 tests) | `contract-test-suite` |

### All 9 V2 Gates Must Stay Green

The phase verification must run `python scripts/run_v2_gates.py` and confirm all 9 gates pass:
1. `platform-contract`
2. `wecom-service`
3. `hermes-contract-layer`
4. `conversation-read-view`
5. `feedback-service`
6. `phase7-privacy-boundary`
7. `contract-test-suite`
8. `v2-acceptance-traceability`
9. `compileall`

The `compileall` gate (line 110-127) compiles all source files including `platform-runtime/src` — the new `privacy_keys.py` module must be syntactically valid.

## Risk Assessment

### Risk 1: New output boundary regex false-positives on legal text

**What could go wrong:** The `provider_leak` pattern `\bmodel\b` matches "model clause" in legal text, blocking legitimate legal analysis from reaching the lawyer.

**Mitigation:** Make the pattern more specific — require a colon, space, or hyphen after "model" to match "model: glm-5.2" but not "model clause". Add the `test_legal_business_text_still_allowed_with_new_rules` test that specifically checks legal text samples are still ALLOWed. Run the full `platform-runtime` test suite to catch any existing test fixtures that contain the word "model".

### Risk 2: Privacy scrub unification breaking existing read-view tests

**What could go wrong:** Extending `scrub_contract_payload` to check all 11 forbidden keys (instead of just `raw_payload`) may cause existing test fixtures that contain `case_facts` or `document_text` to fail at read-time, even though they currently pass.

**Mitigation:** Before extending `scrub_contract_payload`, audit existing fixtures in `packages/contract-test-suite/fixtures/` and `packages/platform-contract/fixtures/` for any of the 6 existing full-text keys. If any are found, they are already passing store-time checks (which reject these keys), so they should not appear in valid contract logs. The read-time extension is defense-in-depth. Run the full `conversation-read-view` and `contract-test-suite` gates after the change.

### Risk 3: Contract-count baseline mismatch with research text

**What could go wrong:** A developer reads SUMMARY.md ("8 methods") and uses 8 as the baseline, but the actual code has 9 methods. The test would fail immediately.

**Mitigation:** This research document explicitly states the actual counts (9, 14, 6) verified by runtime introspection. The test uses these values. The research text miscounts are documented here to prevent confusion.

### Risk 4: Feature flag additions breaking existing RuntimeFeatureFlags consumers

**What could go wrong:** Adding 6 new fields to `RuntimeFeatureFlags` changes the dataclass shape. Existing code that constructs `RuntimeFeatureFlags` with keyword arguments (e.g., `RuntimeFeatureFlags(run_runtime_enabled=True)`) continues to work since new fields have defaults. But any code that introspects field count or iterates fields might behave differently.

**Mitigation:** The `require_enabled` method already uses `dataclasses.fields` for introspection, so it automatically handles new flags. The `test_all_flags_default_to_false_via_introspection` test uses the same pattern. No existing code iterates fields in a way that would break. Run all gates to verify.

### Risk 5: Contract freeze baseline becoming stale

**What could go wrong:** A legitimate contract change in a later M2 phase (e.g., adding `Channel.QQBOT` to `enums.py`) causes the freeze test to fail, blocking development.

**Mitigation:** The freeze test failure is intentional — it forces a deliberate review and baseline update. The phase that modifies the contract must update the baseline JSON in the same PR. The test message clearly states "contract file modified from v1.5 baseline" to guide the developer. This is a feature, not a bug — it prevents accidental contract drift.

## Sources

- `services/wecom-service/src/wecom_service/agent_backend.py` — selection gate bypass (lines 47-51), `select_agent_backend` function (lines 23-58)
- `services/wecom-service/tests/test_agent_backend.py` — existing test patterns, `manifest()` helper (lines 43-67)
- `packages/platform-runtime/src/platform_runtime/store.py` — `_FORBIDDEN_FULL_TEXT_KEYS` (lines 130-137), `_reject_forbidden_payload_storage` (lines 108-115)
- `services/conversation-read-view/src/conversation_read_view/privacy.py` — `scrub_contract_payload` (lines 32-43), `FORBIDDEN_RAW_PAYLOAD_KEY` (line 9)
- `services/conversation-read-view/src/conversation_read_view/api.py` — response paths (lines 11-58), `_with_contract_metadata` (lines 93-98), scrub applied only to `/feedback` (line 48)
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — `scrub_contract_payload` applied at load time (line 52)
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — `_HARD_BLOCK_RULES` (lines 82-91), `_REWRITE_RULES` (lines 100-108), `_OPERATOR_COMMAND_RULES` (lines 93-98)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags` (lines 12-26), `require_enabled` (lines 21-26)
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `BackendAdapter` Protocol (lines 222-239, 9 methods), `ChannelAdapter` Protocol (lines 208-219, 6 methods)
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — `AdapterCapabilitySet` (lines 18-33, 14 fields), `AgentBackendMode` enum (lines 12-15)
- `packages/platform-contract/src/platform_contract/schemas/` — 26 `*.schema.json` files
- `packages/platform-runtime/tests/test_feature_flags.py` — existing default-OFF test pattern (lines 9-16)
- `packages/platform-runtime/tests/test_output_boundary.py` — existing boundary test patterns, source scan test (lines 90-96)
- `packages/contract-test-suite/tests/test_agent_adapter_contract.py` — contract test patterns (lines 23-89)
- `packages/contract-test-suite/tests/test_privacy_gates.py` — privacy gate test patterns (lines 14-51)
- `packages/contract-test-suite/tests/test_thin_layer_boundaries.py` — boundary check patterns, REPO_ROOT usage (line 15)
- `packages/contract-test-suite/src/contract_test_suite/paths.py` — `REPO_ROOT`, `PLATFORM_SCHEMA_ROOT` path constants (lines 8-12)
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` — schema loading patterns, `FORBIDDEN_TOP_LEVEL_FIELDS` (lines 47-59)
- `scripts/run_v2_gates.py` — 9 gate definitions (lines 63-128), PYTHONPATH per gate (lines 51-61)
- `.planning/research/SUMMARY.md` — Key Findings (lines 8-25), Watch Out For (lines 96-109), Pre-Implementation Phase (lines 113-123)
- `.planning/research/PITFALLS.md` — selection gate bypass (lines 34-50), output boundary (lines 54-70), privacy gap (lines 506-522), feature flags (lines 482-500), contract drift (lines 13-30)
- Runtime introspection: `BackendAdapter` has 9 methods, `ChannelAdapter` has 6 methods, `AdapterCapabilitySet` has 14 fields (verified 2026-07-03)
