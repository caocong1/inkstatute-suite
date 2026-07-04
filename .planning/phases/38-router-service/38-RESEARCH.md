# Phase 38 Research — Router Service

> Research document for Phase 38 (Router Service). All file paths are relative to
> `/home/sorawatcher/workspace/inkstatute-suite` unless noted. Line numbers reflect
> the repository state at Phase 37 close (2026-07-04).

---

## 1. Summary

- **`RouteDecision` already exists and is FROZEN.** The dataclass lives at
  `packages/platform-contract/src/platform_contract/events.py:206-222` and the JSON
  Schema at `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json`.
  No `packages/platform-contract/` modifications are permitted (SAFETY-06 contract freeze,
  enforced by `packages/contract-test-suite/tests/test_contract_freeze.py`).

- **`RouteMode` enum already exists with 4 values** at
  `packages/platform-contract/src/platform_contract/enums.py:164-168`:
  `MATCHED`, `SIMPLE_QA`, `SKIPPED`, `ZERO_MATCH`. The phase requirements mention
  `RouteMode.RULE` and `RouteMode.SKILL` — **these are NOT new enum values**. They are
  router-service-internal *routing strategies* that map onto the existing frozen
  `RouteMode` values. Adding `RULE`/`SKILL` to the enum would violate SAFETY-06.

- **The inline router lives in `hermes-contract-layer/mapper.py`.**
  `map_agent_end_context()` (lines 29-179) produces a `route_decision` dict
  (lines 92-117) by reverse-inferring from Hermes `agent:end` hook context.
  Route-mode logic is in `_route_mode()` (lines 230-238).

- **`RouterPort` Protocol does NOT exist yet** — only in planning docs. It must be
  created in a new `packages/router-service/` library package, following the
  `SkillRegistryPort` pattern from Phase 37.

- **`router_service_enabled` feature flag already exists** at
  `packages/platform-runtime/src/platform_runtime/feature_flags.py:20`, defaults to
  `False`. The default-off test already exists at
  `packages/platform-runtime/tests/test_feature_flags.py:19`.

- **Skill Registry from Phase 37 is the SKILL-mode data source.**
  `packages/skill-registry/src/inkstatute_skill_registry/registry.py` exposes
  `SkillRegistryPort` with `list_skills()`, `get_skill(skill_id)`, and
  `search(tag, category, name_substring)` returning `NeutralSkillDescriptor` records.

- **The router must be a library package, NOT an HTTP service.** Per
  ARCHITECTURE.md and PITFALLS.md, the standalone router is importable in-process.
  An HTTP facade is explicitly deferred to M3+.

- **Fallback policy: `None` default preserves in-process behavior.** When the
  injected router is `None`, the mapper continues inline inference exactly as today.
  When a router is injected but unavailable, it falls back to
  `RouteDecision(mode="zero_match")` so the backend handles routing internally.

- **V2 gate count is currently 10** (Phase 37 added the `skill-registry` gate).
  Phase 38 should add an 11th `router-service` gate. The gate-count assertion at
  `packages/contract-test-suite/tests/test_audit_v2_requirements.py:436` must be
  updated from 10 to 11. Note: ROADMAP.md line 75 says "all 9 V2 gates" — this is
  stale text written before Phase 37; the 38-CONTEXT.md correctly says "all 10".

- **No new runtime dependencies.** The router-service package declares
  `dependencies = []`, consistent with every existing package. Pure-Python,
  stdlib-only, `unittest`-tested.

---

## 2. Existing Inline Router

### File: `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py`

The inline router is embedded in `map_agent_end_context()`. It is NOT a separate
module — route computation is interleaved with the four-event mapping
(`agent_turn`, `route_decision`, `execution_trace`, `agent_result`).

**Entry point** (lines 29-34):
```python
def map_agent_end_context(
    context: Mapping[str, Any],
    *,
    now: datetime | str,
    seq_start: int = 0,
) -> OrderedDict[str, dict[str, Any]]:
    """Return AgentTurn, RouteDecision, ExecutionTrace, and AgentResult payloads."""
```

**Route decision construction** (lines 92-117):
```python
route_decision = {
    "route_decision_id": route_decision_id,
    "turn_id": turn_id,
    "primary_skill": primary_skill,
    "supporting_skills": _string_list(context.get("supporting_skills")),
    "gates_before": _string_list(context.get("gates_before")),
    "gates_after": _string_list(context.get("gates_after")),
    "required_tools": _string_list(context.get("required_tools")),
    "confidence": route_confidence,
    "reason": _route_reason(route_mode, matched_registered_skill),
    "mode": route_mode,
    "route_mismatch": route_mismatch,
    "created_at": timestamp,
    "industry_context": industry_context,
    "metadata": {
        "route_source": "hermes_hook_context",
        "router_output_source_status": "unavailable",
        "matched_registered_skill": matched_registered_skill,
        "raw_payload_ref": raw_payload_ref,
    },
}
if matched_registered_skill:
    route_decision["matched_rule"] = _string(
        context.get("matched_rule"),
        f"hermes_active_skill:{primary_skill}",
    )
```

**Route mode inference** (lines 230-238):
```python
ROUTE_MODES = {"matched", "simple_qa", "skipped", "zero_match"}  # line 26

def _route_mode(context: Mapping[str, Any], primary_skill: str | None) -> str:
    explicit = _string_or_none(context.get("route_mode"))
    if explicit in ROUTE_MODES:
        return explicit
    if context.get("route_mismatch") or context.get("route_error") or context.get("zero_match"):
        return "zero_match"
    if primary_skill:
        return "matched"
    return "simple_qa"
```

**Confidence computation** (lines 241-248):
```python
def _confidence(value: Any, matched_registered_skill: bool, route_mode: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return min(1.0, max(0.0, float(value)))
    if matched_registered_skill:
        return 1.0
    if route_mode == "simple_qa":
        return 0.5
    return 0.0
```

**Route reason** (lines 251-258):
```python
def _route_reason(route_mode: str, matched_registered_skill: bool) -> str:
    if matched_registered_skill:
        return "Mapped from Hermes active skill metadata in post-filter hook context."
    if route_mode == "zero_match":
        return "Hermes route output was unavailable or unmatched in hook context."
    if route_mode == "simple_qa":
        return "No registered skill was exposed; recorded as simple question-answer path."
    return "Route decision was unavailable in Hermes hook context."
```

**Key observation:** The inline router reverse-infers from Hermes hook context
(`active_skill_name`, `route_confidence`, `matched_rule`, `route_mismatch`). It has
no concept of RULE vs SKILL strategies — it only knows the 4 frozen `RouteMode`
outcome values. The standalone router adds strategy selection (RULE/SKILL) as an
internal concern while emitting the same frozen outcome values.

---

## 3. RouteDecision Schema

### Dataclass: `packages/platform-contract/src/platform_contract/events.py:206-222`

```python
@dataclass(frozen=True, slots=True)
class RouteDecision:
    route_decision_id: str
    turn_id: str
    primary_skill: str | None
    confidence: float
    mode: RouteMode | str
    created_at: str
    supporting_skills: list[str] = field(default_factory=list)
    gates_before: list[str] = field(default_factory=list)
    gates_after: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    matched_rule: str | None = None
    reason: str | None = None
    route_mismatch: bool | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

### JSON Schema: `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json`

Required fields (lines 8-15): `route_decision_id`, `turn_id`, `primary_skill`,
`confidence`, `mode`, `created_at`.

Optional fields: `supporting_skills`, `gates_before`, `gates_after`,
`required_tools`, `matched_rule`, `reason`, `route_mismatch`,
`industry_context`, `metadata`.

The `mode` field references `common.schema.json#/$defs/route_mode` (line 65),
which is an enum of `["matched", "simple_qa", "skipped", "zero_match"]`
(`common.schema.json:190-197`).

### Re-exports

- `packages/platform-contract/src/platform_contract/__init__.py:57` (events import),
  `:122` (`__all__` entry).

### Contract freeze impact

**NONE.** The schema and dataclass are frozen by SAFETY-06. The standalone router
must produce dicts with exactly this shape. Router-service metadata (version,
strategy) fits in the existing `metadata` object — **no schema change required**
(confirmed by ARCHITECTURE.md line 53 and SUMMARY.md line 10).

---

## 4. RouteMode Enum

### File: `packages/platform-contract/src/platform_contract/enums.py:164-168`

```python
class RouteMode(StrEnum):
    MATCHED = "matched"
    SIMPLE_QA = "simple_qa"
    SKIPPED = "skipped"
    ZERO_MATCH = "zero_match"
```

### CRITICAL: RULE and SKILL are NOT RouteMode values

The phase requirements (ROUTER-02) say "configure `RouteMode.RULE` and
`RouteMode.SKILL` routing modes." This is a **naming collision in the requirements
text**, not a contract change. The frozen `RouteMode` enum has only 4 values, and
the JSON Schema `route_mode` enum (`common.schema.json:190-197`) enforces the same
4 values. Adding `RULE`/`SKILL` would:

1. Violate SAFETY-06 contract freeze (`test_contract_freeze.py` hash mismatch on
   `enums.py` and `common.schema.json`).
2. Break the `route_decision.schema.json` `$ref` to `route_mode`.
3. Break all 10 existing V2 gates that validate `RouteDecision` events.

### Resolution: RouterStrategy enum (router-service-internal)

The router-service package should define its own **internal** `RouterStrategy`
enum (NOT exported from `platform-contract`):

```python
# packages/router-service/src/inkstatute_router_service/strategies.py
class RouterStrategy(StrEnum):
    RULE = "rule"    # keyword/regex rule-based intent classification
    SKILL = "skill"  # stateless Skill Registry lookup
```

The strategy determines *how* the router computes a decision, but the resulting
`RouteDecision.mode` is always one of the 4 frozen `RouteMode` values:

| Strategy | Typical `RouteDecision.mode` outcome |
|----------|--------------------------------------|
| RULE     | `matched` (rule hit), `simple_qa` (no rule hit), `zero_match` (mismatch) |
| SKILL    | `matched` (skill found), `zero_match` (no skill found) |

The `metadata.router_strategy` field records which strategy produced the decision,
fitting in the existing `metadata` object without schema changes.

---

## 5. RouterPort Protocol

### Status: DOES NOT EXIST — must be created

`RouterPort` appears only in planning docs (ROADMAP.md, PITFALLS.md, SUMMARY.md).
No Python Protocol exists in the codebase.

### Design (from PITFALLS.md lines 111-116 and ARCHITECTURE.md lines 144-148)

The `RouterPort` Protocol should live in the new router-service package and follow
the `SkillRegistryPort` pattern (`packages/skill-registry/src/inkstatute_skill_registry/registry.py:16-28`):

```python
# packages/router-service/src/inkstatute_router_service/port.py
from __future__ import annotations
from typing import Any, Mapping, Protocol

from platform_contract import RouteDecision


class RouterPort(Protocol):
    """Standalone router protocol — produces normalized RouteDecision records.

    Implementations must be stateless and side-effect free.  When the router is
    unavailable or raises, the caller falls back to inline inference.
    """

    def decide(self, context: Mapping[str, Any]) -> RouteDecision: ...
```

### Injection point

Per PITFALLS.md line 112, the mapper (or runtime) accepts an optional
`router: RouterPort | None = None`. When `None`, routing stays in-process (inline
inference, as today). When provided, `decide()` is called and its output is used
as the `RouteDecision`.

### Fallback contract

Per PITFALLS.md line 136: if the router raises or is unavailable, fall back to
`RouteDecision(mode="zero_match")` and let the backend handle routing internally.
This preserves the current behavior where Hermes routes internally.

---

## 6. Skill Registry Integration

### Phase 37 output: `packages/skill-registry/`

**Registry class:** `packages/skill-registry/src/inkstatute_skill_registry/registry.py`

```python
class SkillRegistryPort(Protocol):  # lines 16-28
    def list_skills(self) -> list[NeutralSkillDescriptor]: ...
    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...
    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]: ...
```

**`NeutralSkillDescriptor`** (`packages/platform-contract/src/platform_contract/events.py:105-112`):
```python
@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

### SKILL routing mode — stateless lookup

The SKILL strategy performs **stateless** skill lookup (no caching, no mutation):

1. **Intent classification:** Extract keywords from the incoming message
   (`context["message"]`).
2. **Skill search:** Call `registry.search(name_substring=<keyword>)` or
   `registry.search(category=<intent>)` to find matching skills.
3. **Decision:** If exactly one skill matches → `mode="matched"`,
   `primary_skill=<skill_id>`, `confidence` based on match strength. If no match →
   `mode="zero_match"`. If multiple matches → pick highest-confidence or
   `mode="simple_qa"` with `supporting_skills` populated.

### Skill metadata shape (from lawfirm manifest)

`solutions/lawfirm/manifest.json:12-41` defines skills with:
- `name` (e.g. `case_qa`, `contract_draft`)
- `description`
- `intent` (e.g. `factual_qa`, `drafting`, `analysis`, `review`)
- `required_tools`
- `risk_level`

The skill-registry mapper (`packages/skill-registry/src/inkstatute_skill_registry/mapper.py:17-45`)
converts these to `NeutralSkillDescriptor` with `metadata.intent` and
`metadata.risk_level`. The SKILL router can use `registry.search(category=<intent>)`
to match on the `intent` field.

### Dependency wiring

The router-service package depends on `skill-registry` (optional) and
`platform-contract`. The `SkillRegistryPort` is injected into the router at
construction time, keeping the router stateless and testable with fakes.

---

## 7. Feature Flag Integration

### File: `packages/platform-runtime/src/platform_runtime/feature_flags.py:20`

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False
    context_assembly_enabled: bool = False
    router_service_enabled: bool = False   # line 20 — already added in Phase 36
    skill_registry_enabled: bool = False
    admin_api_enabled: bool = False
    qqbot_channel_enabled: bool = False
    codex_backend_enabled: bool = False
    provider_model_backend_enabled: bool = False
```

### Existing test coverage

`packages/platform-runtime/tests/test_feature_flags.py:19`:
```python
self.assertFalse(flags.router_service_enabled)
```

And `test_all_m2_flags_default_to_false_via_introspection` (lines 26-31) asserts
ALL flags default to `False` via `dataclasses.fields` introspection — this
automatically covers `router_service_enabled`.

### How the flag is checked

Following the skill-registry API pattern (`packages/skill-registry/src/inkstatute_skill_registry/api.py:46-47`):
```python
if flags is not None:
    flags.require_enabled("router_service_enabled")
```

The router-service should accept an optional `flags: RuntimeFeatureFlags | None`
parameter. When `flags` is provided and `router_service_enabled` is `False`,
`require_enabled()` raises `RuntimeFeatureDisabledError`. When `flags` is `None`
(the default for library imports), the flag is not enforced — the caller decides.

**No changes to `feature_flags.py` are needed.** The flag already exists and is
tested. Phase 38 only adds *consumption* of the flag in the router-service.

---

## 8. Fallback Policy

### None default — in-process fallback

The core design principle (PITFALLS.md lines 111-116, ARCHITECTURE.md line 55):

> `map_agent_end_context` can delegate route computation to the router-service
> library while keeping the same output schema. No gate test changes if the JSONL
> event shape is unchanged.

**When `router=None` (default):** The mapper uses inline inference exactly as
today (`_route_mode()`, `_confidence()`, `_route_reason()`). All 10 V2 gates stay
green because behavior is unchanged.

**When `router=<RouterPort impl>` is injected:** The mapper calls
`router.decide(context)` and uses the returned `RouteDecision` (converted to dict)
as the `route_decision` event. The inline inference is bypassed.

### Router unavailable fallback

Per PITFALLS.md line 136:

> `RouterPort` implementations must have a configurable timeout (default: 500ms)
> and a fallback policy: if the router service is unavailable, fall back to
> `RouteDecision(mode="zero_match")` and let the backend handle routing internally.

The mapper should wrap the `router.decide()` call in a try/except. On any
exception, it falls back to inline inference (NOT a synthetic zero_match — inline
inference preserves the existing Hermes-derived decision, which is more accurate
than a blanket zero_match). This is safer than PITFALLS.md's suggestion because it
preserves all existing behavior on failure.

```python
# Pseudocode for mapper integration
if router is not None:
    try:
        decision = router.decide(context)
        route_decision = _route_decision_to_dict(decision, ...)
    except Exception:
        route_decision = _inline_route_decision(context, ...)  # existing logic
else:
    route_decision = _inline_route_decision(context, ...)  # existing logic
```

---

## 9. Intent Classification

### RULE strategy — keyword/regex

The RULE strategy classifies intent via keyword/regex matching against the
incoming message. This mirrors the existing Hermes `scripts/router.py` approach
(referenced in PITFALLS.md line 99) but as a pure function.

**Pattern source:** Skill descriptors from the Skill Registry carry
`metadata.intent` (e.g. `factual_qa`, `drafting`, `analysis`, `review`) and
`description` text. The RULE router builds a keyword→intent map from registry
descriptors and matches incoming message text.

**Example classification logic:**
```python
INTENT_KEYWORDS = {
    "factual_qa": ["什么", "是否", "如何", "请问", "查询", "what", "is", "how"],
    "drafting": ["起草", "草拟", "撰写", "draft", "write", "generate"],
    "analysis": ["分析", "总结", "归纳", "analyze", "summarize"],
    "review": ["审查", "审核", "检查", "review", "check", "compliance"],
}
```

When a keyword matches, the router looks up the skill with that intent via
`registry.search(category=<intent>)` and produces a `matched` decision.

### SKILL strategy — stateless skill lookup

The SKILL strategy skips keyword classification and directly searches the Skill
Registry by name substring or skill_id. This is useful when the caller already
knows the target skill (e.g., from a UI selection or a previous turn's
`active_skill_name`).

### Both strategies are stateless

No caching, no session state, no mutation of the registry. Each `decide()` call
is independent. This satisfies ROUTER-02's "stateless skill lookup" requirement
and the PITFALLS.md warning against extracting `active_task_router.py` (which must
remain in-process in wecom-service — PITFALLS.md line 134).

---

## 10. API Design

### RouterPort Protocol

```python
# packages/router-service/src/inkstatute_router_service/port.py
from __future__ import annotations
from typing import Any, Mapping, Protocol
from platform_contract import RouteDecision


class RouterPort(Protocol):
    def decide(self, context: Mapping[str, Any]) -> RouteDecision: ...
```

### RouterService implementation

```python
# packages/router-service/src/inkstatute_router_service/service.py
from __future__ import annotations
from typing import Any, Mapping
from platform_contract import RouteDecision, RouteMode
from inkstatute_skill_registry import SkillRegistryPort


class RouterService:
    """Standalone router producing normalized RouteDecision records.

    Stateless: each decide() call is independent.  Two strategies:
    - RULE: keyword/regex intent classification → skill lookup
    - SKILL: direct skill lookup from Skill Registry
    """

    def __init__(
        self,
        skill_registry: SkillRegistryPort | None = None,
        strategy: RouterStrategy = RouterStrategy.RULE,
    ) -> None:
        self._registry = skill_registry
        self._strategy = strategy

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        if self._strategy == RouterStrategy.SKILL:
            return self._decide_skill(context)
        return self._decide_rule(context)
```

### RouteDecision production

The `decide()` method returns a `RouteDecision` dataclass (frozen). The mapper
converts it to a dict for JSONL serialization. The dict shape must match the
inline implementation's `route_decision` dict (mapper.py lines 92-117) exactly:

```python
{
    "route_decision_id": str,
    "turn_id": str,
    "primary_skill": str | None,
    "supporting_skills": list[str],
    "gates_before": list[str],
    "gates_after": list[str],
    "required_tools": list[str],
    "confidence": float,
    "reason": str | None,
    "mode": str,  # one of: matched, simple_qa, skipped, zero_match
    "route_mismatch": bool | None,
    "created_at": str,
    "industry_context": dict,
    "metadata": dict,  # includes router_strategy, router_service_version
    "matched_rule": str | None,  # only when matched
}
```

### Mapper integration signature

```python
def map_agent_end_context(
    context: Mapping[str, Any],
    *,
    now: datetime | str,
    seq_start: int = 0,
    router: RouterPort | None = None,  # NEW optional parameter
) -> OrderedDict[str, dict[str, Any]]:
```

The `router` parameter defaults to `None`, preserving all existing call sites and
test behavior.

---

## 11. Implementation Plan Guidance

### ROUTER-01: Injectable standalone router library

**Files to create:**
- `packages/router-service/pyproject.toml` — package definition (model on
  `packages/skill-registry/pyproject.toml`, `dependencies = []`,
  `default_off_flag = "router_service_enabled"`)
- `packages/router-service/src/inkstatute_router_service/__init__.py` — re-exports
- `packages/router-service/src/inkstatute_router_service/port.py` — `RouterPort` Protocol
- `packages/router-service/src/inkstatute_router_service/service.py` — `RouterService` class
- `packages/router-service/src/inkstatute_router_service/strategies.py` — `RouterStrategy` enum
- `packages/router-service/tests/test_port.py` — Protocol conformance tests
- `packages/router-service/tests/test_service.py` — router decision tests

**Files to modify:**
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` — add
  optional `router: RouterPort | None = None` parameter to
  `map_agent_end_context()`. When provided, call `router.decide(context)` and use
  its output. When `None` or on exception, fall back to existing inline inference.
- `scripts/run_v2_gates.py` — add `router-service` gate (line ~89, after
  `skill-registry` gate), add `router_service_src` to PYTHONPATH entries, add
  `packages/router-service/src` to `compileall` gate (line ~124). Add
  `router_service_src` to `contract-test-suite` gate PYTHONPATH (line 109).
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py:436` — update
  gate count assertion from 10 to 11.

**Key constraint:** The `route_decision` dict shape must be byte-for-byte
compatible with the inline implementation. The `metadata` object gains
`router_strategy` and `router_service_version` keys but loses nothing.

### ROUTER-02: RULE and SKILL routing modes

**Files to create:**
- `packages/router-service/src/inkstatute_router_service/strategies.py` —
  `RouterStrategy(StrEnum)` with `RULE = "rule"` and `SKILL = "skill"`.
- `packages/router-service/src/inkstatute_router_service/classifier.py` —
  keyword/regex intent classification functions (pure functions, stdlib `re`).
- `packages/router-service/tests/test_classifier.py` — intent classification tests
- `packages/router-service/tests/test_skill_routing.py` — SKILL mode tests with
  fake `SkillRegistryPort`

**Integration with Skill Registry:**
- `RouterService.__init__` accepts `skill_registry: SkillRegistryPort | None`.
- SKILL strategy calls `registry.search()` / `registry.get_skill()`.
- RULE strategy uses `classifier.classify_intent(message)` then
  `registry.search(category=<intent>)`.
- When `skill_registry is None`, both strategies fall back to `zero_match`.

**Normalized RouteDecision records:**
- `primary_skill` = `skill_id` from `NeutralSkillDescriptor` (e.g.
  `lawfirm/contract_draft`)
- `required_tools` = `descriptor.required_tool_refs`
- `confidence` = match strength (1.0 for exact skill_id, 0.7 for single keyword
  match, 0.5 for ambiguous, 0.0 for no match)
- `mode` = `matched` (skill found), `zero_match` (no skill), `simple_qa` (no
  registry configured)

---

## 12. Test Strategy

### New package tests: `packages/router-service/tests/`

**`test_port.py`:**
- `test_router_service_satisfies_router_port_protocol` — `RouterService` is a
  structural subtype of `RouterPort`.
- `test_router_port_is_protocol` — `RouterPort` is a `typing.Protocol`.

**`test_service.py`:**
- `test_decide_rule_strategy_matched` — keyword match → `mode="matched"`,
  `primary_skill` set, `confidence > 0`.
- `test_decide_rule_strategy_zero_match` — no keyword match → `mode="zero_match"`,
  `primary_skill=None`, `confidence=0.0`.
- `test_decide_skill_strategy_matched` — `get_skill()` returns descriptor →
  `mode="matched"`.
- `test_decide_skill_strategy_not_found` — `get_skill()` returns `None` →
  `mode="zero_match"`.
- `test_decide_no_registry_falls_back_to_zero_match` — `skill_registry=None` →
  `mode="zero_match"` (or `simple_qa`).
- `test_decide_is_stateless` — two consecutive `decide()` calls with same context
  produce equal results; registry is not mutated.
- `test_route_decision_shape_matches_schema` — validate via
  `contract_test_suite.schema_validation.validate_event("route_decision", ...)`.
- `test_route_decision_mode_is_frozen_value` — `mode` is always one of
  `matched`, `simple_qa`, `skipped`, `zero_match`.
- `test_metadata_includes_router_strategy` — `metadata["router_strategy"]` is set.
- `test_router_service_enabled_defaults_false` — feature flag default-off
  consumption test.

**`test_classifier.py`:**
- `test_classify_intent_factual_qa` — question keywords → `factual_qa`.
- `test_classify_intent_drafting` — drafting keywords → `drafting`.
- `test_classify_intent_no_match` — unrecognized text → `None`.
- `test_classify_intent_empty_message` — empty/None → `None`.

**`test_skill_routing.py`:**
- `test_skill_lookup_by_id` — `get_skill("lawfirm/case_qa")` → matched.
- `test_skill_lookup_by_intent` — `search(category="drafting")` → matched.
- `test_skill_lookup_ambiguous` — multiple matches → supporting_skills populated.
- `test_skill_lookup_registry_not_configured` — `None` registry → zero_match.

### Modified mapper tests: `services/hermes-contract-layer/tests/test_mapper.py`

Add tests proving injection and fallback:
- `test_map_with_router_none_uses_inline_inference` — `router=None` produces
  identical results to current behavior (regression guard).
- `test_map_with_router_injected_uses_router_output` — inject a fake `RouterPort`,
  verify `route_decision` reflects the router's output, not inline inference.
- `test_map_with_router_exception_falls_back_to_inline` — inject a router that
  raises, verify mapper falls back to inline inference without crashing.
- `test_map_with_router_preserves_jsonl_shape` — validate all 4 events via
  `validate_event()` when router is injected.

### Gate count assertion update

`packages/contract-test-suite/tests/test_audit_v2_requirements.py:436`:
```python
# Before:
self.assertEqual(len(gate_names), 10)
# After:
self.assertEqual(len(gate_names), 11)
```

Also add `self.assertIn("router-service", gate_names)` (line ~435).

---

## 13. V2 Gate Integration

### Current state: 10 gates

`scripts/run_v2_gates.py:64-135` defines 10 gates:
1. `platform-contract`
2. `wecom-service`
3. `hermes-contract-layer`
4. `conversation-read-view`
5. `skill-registry` (added in Phase 37)
6. `feedback-service`
7. `phase7-privacy-boundary`
8. `contract-test-suite`
9. `v2-acceptance-traceability`
10. `compileall`

### Phase 38 adds an 11th gate: `router-service`

Insert after the `skill-registry` gate (line 89):
```python
Gate(
    "router-service",
    (py, "-m", "unittest", "discover", "-s", "packages/router-service/tests"),
    (router_service_src, platform_src, platform_runtime_src, skill_registry_src),
),
```

Where `router_service_src = repo_root / "packages" / "router-service" / "src"`
(added near line 62).

### compileall update (line 121-133)

Add `"packages/router-service/src"` to the `compileall` command tuple.

### contract-test-suite PYTHONPATH update (line 109)

Add `router_service_src` to the PYTHONPATH tuple so contract tests can import
the router-service package if needed.

### Stale text note

ROADMAP.md line 75 says "all 9 V2 gates staying green" — this was written before
Phase 37 added the 10th gate. The 38-CONTEXT.md correctly says "all 10 V2 gates."
After Phase 38, the count is 11. The success criterion should be interpreted as
"all V2 gates staying green" regardless of the stale number.

---

## 14. Risk Assessment

### Risk 1: JSONL shape drift (HIGH impact, MEDIUM likelihood)

**What:** The standalone router produces a `RouteDecision` dict with different
field ordering, missing optional fields, or extra fields that fail schema
validation (`additionalProperties: false` in the JSON Schema).

**Mitigation:** The router returns a `RouteDecision` dataclass (frozen, from
`platform-contract`), which guarantees field completeness. The mapper converts
it to dict using the same field set as the inline implementation. Add a
`test_route_decision_shape_matches_schema` test that validates via
`contract_test_suite.schema_validation.validate_event`.

### Risk 2: SAFETY-06 contract freeze violation (HIGH impact, LOW likelihood)

**What:** Someone adds `RULE`/`SKILL` to the `RouteMode` enum or modifies
`route_decision.schema.json`, triggering `test_contract_freeze.py` hash mismatch.

**Mitigation:** `RouterStrategy` is a separate enum in the router-service package,
NOT in `platform-contract`. Document this clearly. The freeze test
(`test_contract_freeze.py`) runs in the `contract-test-suite` gate and will fail
fast if violated.

### Risk 3: Breaking existing mapper tests (HIGH impact, LOW likelihood)

**What:** Adding the `router` parameter to `map_agent_end_context()` changes the
signature, breaking existing call sites.

**Mitigation:** The parameter is keyword-only with `None` default. All existing
call sites (`test_mapper.py`, `test_hook.py`, `test_writer.py`) call
`map_agent_end_context(context, now=...)` without the new parameter, so they are
unaffected. Run all 10 gates with `router=None` to confirm zero regression.

### Risk 4: Router-service gate PYTHONPATH gap (MEDIUM impact, MEDIUM likelihood)

**What:** The new `router-service` gate is added to `run_v2_gates.py` but its
PYTHONPATH is missing `skill_registry_src`, causing `ImportError` when the
router imports `inkstatute_skill_registry`.

**Mitigation:** Include `skill_registry_src` in the router-service gate's
PYTHONPATH tuple. Follow the exact pattern of the `skill-registry` gate (line 88).
The `compileall` gate must also include `packages/router-service/src`.

### Risk 5: Circular import (MEDIUM impact, LOW likelihood)

**What:** `router-service` imports `platform-contract` and `skill-registry`;
`hermes-contract-layer` imports `router-service`. If `router-service` imports
`hermes-contract-layer`, a circular dependency forms.

**Mitigation:** `router-service` must NOT import `hermes-contract-layer`. The
dependency graph is one-directional:
`hermes-contract-layer → router-service → {platform-contract, skill-registry}`.

### Risk 6: Gate count assertion mismatch (LOW impact, HIGH likelihood)

**What:** Forgetting to update `test_audit_v2_requirements.py:436` from 10 to 11
causes the `contract-test-suite` gate to fail.

**Mitigation:** This is a known mechanical step (Phase 37 hit the same issue —
see 37-SUMMARY.md deviation 1). Add it to the plan task list explicitly.

---

## 15. Validation Architecture

### Per-task verification map

| Task | Verification | Gate | Command |
|------|--------------|------|---------|
| Create `packages/router-service/` package | `compileall` compiles `packages/router-service/src` | `compileall` | `python -m compileall packages/router-service/src` |
| `RouterPort` Protocol defined | `test_port.py` passes | `router-service` | `python -m unittest discover -s packages/router-service/tests` |
| `RouterService.decide()` produces valid `RouteDecision` | `test_service.py` validates via `validate_event` | `router-service` | same as above |
| RULE strategy intent classification | `test_classifier.py` passes | `router-service` | same as above |
| SKILL strategy stateless lookup | `test_skill_routing.py` passes | `router-service` | same as above |
| Mapper accepts `router=None` (no regression) | `test_mapper.py` all existing tests pass | `hermes-contract-layer` | `python -m unittest discover -s services/hermes-contract-layer/tests` |
| Mapper accepts injected router | New mapper tests pass | `hermes-contract-layer` | same as above |
| `router_service_enabled` defaults `False` | `test_feature_flags.py` passes | (covered by `contract-test-suite` PYTHONPATH) | `python -m unittest packages/platform-runtime/tests/test_feature_flags.py` |
| Gate count = 11 | `test_v2_gates_includes_traceability_gate` passes | `contract-test-suite` | `python -m unittest packages/contract-test-suite/tests/test_audit_v2_requirements.py` |
| SAFETY-06 contract freeze preserved | `test_contract_freeze.py` passes | `contract-test-suite` | `python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py` |
| All gates green | Full V2 gate suite | all | `python scripts/run_v2_gates.py` |

### Full gate suite command

```bash
python scripts/run_v2_gates.py
```

Expected: 11/11 gates green (10 existing + 1 new `router-service`).

### Contract freeze verification

```bash
python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py
```

This must pass with ZERO modifications to `packages/platform-contract/`. The
baseline file is at
`packages/contract-test-suite/fixtures/contract_freeze_baseline.json`.

---

## Appendix A: Package Structure (proposed)

```
packages/router-service/
├── pyproject.toml
├── README.md
├── src/
│   └── inkstatute_router_service/
│       ├── __init__.py          # re-exports
│       ├── port.py              # RouterPort Protocol
│       ├── service.py           # RouterService class
│       ├── strategies.py        # RouterStrategy enum (RULE, SKILL)
│       └── classifier.py        # keyword/regex intent classification
└── tests/
    ├── test_port.py             # Protocol conformance
    ├── test_service.py          # RouterService.decide() tests
    ├── test_classifier.py       # intent classification tests
    └── test_skill_routing.py    # SKILL mode + Skill Registry integration
```

### pyproject.toml (model on skill-registry)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-router-service"
version = "0.1.0"
description = "Standalone router library producing normalized RouteDecision records."
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.inkstatute]
subsystem = "router-service"
default_off_flag = "router_service_enabled"
```

### __init__.py

```python
"""inkstatute-router-service: standalone router library.

Re-exports the RouterPort Protocol, RouterService implementation,
and RouterStrategy enum.
"""
from .port import RouterPort
from .service import RouterService
from .strategies import RouterStrategy

__all__ = [
    "RouterPort",
    "RouterService",
    "RouterStrategy",
]
```

---

## Appendix B: Key File Reference

| Component | File | Lines |
|-----------|------|-------|
| Inline router | `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | 29-179 (entry), 92-117 (route_decision), 230-238 (_route_mode) |
| RouteDecision dataclass | `packages/platform-contract/src/platform_contract/events.py` | 206-222 |
| RouteDecision JSON Schema | `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json` | 1-80 |
| RouteMode enum | `packages/platform-contract/src/platform_contract/enums.py` | 164-168 |
| route_mode schema enum | `packages/platform-contract/src/platform_contract/schemas/common.schema.json` | 190-197 |
| Feature flag | `packages/platform-runtime/src/platform_runtime/feature_flags.py` | 20 |
| Feature flag test | `packages/platform-runtime/tests/test_feature_flags.py` | 19, 26-31 |
| SkillRegistryPort | `packages/skill-registry/src/inkstatute_skill_registry/registry.py` | 16-28 |
| SkillRegistry class | `packages/skill-registry/src/inkstatute_skill_registry/registry.py` | 31-78 |
| Skill mapper | `packages/skill-registry/src/inkstatute_skill_registry/mapper.py` | 17-64 |
| Skill API (flag pattern) | `packages/skill-registry/src/inkstatute_skill_registry/api.py` | 34-47 |
| NeutralSkillDescriptor | `packages/platform-contract/src/platform_contract/events.py` | 105-112 |
| V2 gate runner | `scripts/run_v2_gates.py` | 49-135 |
| Gate count assertion | `packages/contract-test-suite/tests/test_audit_v2_requirements.py` | 424-436 |
| Contract freeze test | `packages/contract-test-suite/tests/test_contract_freeze.py` | 1-62 |
| Mapper tests | `services/hermes-contract-layer/tests/test_mapper.py` | 1-79+ |
| Lawfirm manifest (skills) | `solutions/lawfirm/manifest.json` | 12-41 |
| Skill-registry pyproject (template) | `packages/skill-registry/pyproject.toml` | 1-17 |
| RouterPort design (PITFALLS) | `.planning/research/PITFALLS.md` | 96-139, 482-496 |
| Router architecture | `.planning/research/ARCHITECTURE.md` | 45-55, 142-148 |
| Router research summary | `.planning/research/SUMMARY.md` | 16, 49, 65, 74 |
