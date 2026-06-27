# Phase 03: Hermes Integration Spike and Risk Closure - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` | utility/doc | batch | `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md` | exact |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` | utility/doc | transform | `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md` | exact |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` | utility/doc | request-response | `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md` | exact |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` | utility/doc | event-driven | `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md` | exact |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/route_error_contract_fixture.json` | test fixture | request-response | `packages/platform-contract/fixtures/legal_wecom_contract_review.json` | role-match |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/long_task_failure_contract_fixture.json` | test fixture | event-driven | `packages/platform-contract/fixtures/legal_wecom_contract_review.json` | role-match |
| `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/repeated_feedback_clicks_contract_fixture.json` | test fixture | event-driven | `packages/platform-contract/fixtures/legal_wecom_contract_review.json` | role-match |
| `packages/contract-test-suite/fixtures/phase3_non_happy_path_*.json` | test fixture | request-response/event-driven | `packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json` and `packages/platform-contract/fixtures/non_legal_engineering_task.json` | role-match |
| `packages/contract-test-suite/tests/test_phase3_non_happy_paths.py` | test | batch | `packages/contract-test-suite/tests/test_composability.py` and `packages/contract-test-suite/tests/test_fixture_replay.py` | exact |

## Pattern Assignments

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` (utility/doc, batch)

**Analog:** `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md`

**Evidence-led inventory pattern** (lines 1-20):
```markdown
# Phase 3: Hermes Integration Spike and Risk Closure - Research

**Researched:** 2026-06-28
**Domain:** Hermes lawfirm hook/WeCom/feedback integration risk spike
**Confidence:** MEDIUM - repository-local evidence is HIGH; Hermes runtime/source-dependent claims remain LOW until Hermes source or runtime artifacts are mounted.
```

**Copy pattern:** Start with date/domain/confidence, then list every source class checked: hook files, `HOOK.yaml`, `handler.py`, `response_filter`, template-card dispatcher, callback shim, `feedback.jsonl`, `pending_previews.jsonl`, sessions/task logs. Mark each `present`, `absent`, or `requires external Hermes source/runtime`.

**Hermes absence pattern** (from required context, lines 9-14):
```markdown
The current repository does not contain the Hermes runtime source. Phase 3 must therefore be planned as an evidence-first spike using the available PRD, GSD state, contract schemas, contract-test-suite, and synthetic fixtures.
```

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` (utility/doc, transform)

**Analog:** `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md`

**Decision status pattern** (lines 25-57):
```markdown
- Hermes source absence is a first-class evidence gap. Source-dependent decisions must be recorded as `confirmed`, `assumed`, or `requires Hermes source`.
- Hook order decision must resolve whether `contract_result_recorder` can run after `response_filter`; if not confirmed, Phase 4 must block or use an adjacent/inside-`response_filter` fallback.
- Raw payload and privacy decisions block Phase 4; contract logs must prefer `raw_payload_ref` and avoid sensitive full text by default.
```

**Core table pattern** (lines 154-170):
```markdown
| Evidence | Finding | Confidence |
|----------|---------|------------|
| PRD states Hermes hooks use `HOOK.yaml` plus `handler.py`, with existing `agent:end` and `gateway:startup` events; `agent:end` context includes `response/platform/user_id/chat_id/session_id/active_skill_name`, and hooks can write back to context. | This is the only available description of Hermes hook API in this repo. | MEDIUM |
```

**Copy pattern:** Use one row per PRD section 13 risk: hook order, AgentTurn input source, message ID stability, long-task states, response/filter-card association, repeated callback idempotency, raw payload storage/redaction, route mismatch skillopt safety. Include `Source Checked`, `Status`, `Decision`, `Fallback`, and `Phase 4 Impact`.

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` (utility/doc, request-response)

**Analog:** `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md`

**Scope and fallback pattern** (lines 25-38):
```markdown
### D-03 Hook order decision must resolve the `response_filter` dependency.
- Phase 3 must decide whether `contract_result_recorder` can run after `response_filter`.
- If ordering cannot be confirmed, plans must document the fallback: either record inside/adjacent to `response_filter` or make Phase 4 block until Hermes hook ordering evidence exists.

### D-04 AgentTurn input strategy must be explicit.
- Preferred outcome: identify a stable inbound hook/source for AgentTurn.
- Fallback outcome: document `agent:end` reverse-inference limits, including which AgentTurn fields may be incomplete and how `raw_payload_ref` should preserve reference-only access.
```

**Copy pattern:** Split into `Hook Ordering`, `AgentTurn Input Strategy`, `Confirmed Evidence`, `Assumptions`, `Fallback`, and `Phase 4 Gate`. Do not present PRD prose as source-confirmed Hermes API.

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` (utility/doc, event-driven)

**Analog:** `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-RESEARCH.md`

**Identifier relationship pattern** (lines 187-196):
```markdown
| Evidence | Finding | Confidence |
|----------|---------|------------|
| Platform schemas and fixtures already support `AgentResult.feedback_target` and `FeedbackEvent.feedback_target`, and relationship replay checks them. | Contract-side association field exists and is tested on synthetic fixtures. | HIGH |
```

**State enum source pattern** (`packages/platform-contract/src/platform_contract/enums.py` lines 6-14):
```python
class AsyncTaskState(StrEnum):
    """Locked async task states for platform-visible task progress."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**Privacy pattern** (`packages/platform-contract/fixtures/README.md` lines 22-25):
```markdown
Legal-specific sample details must stay inside extension containers such as
`industry_context` or `metadata`. Raw legal payloads and sensitive personal data
must be represented only by references, such as `raw_payload_ref` or artifact
URIs.
```

**Copy pattern:** Keep platform states exact. For each Hermes signal, mark `confirmed`, `derived`, `unavailable`, or `requires Hermes source/runtime`. Use `feedback_target = message_id` only if the card/callback chain confirms stability; otherwise document a derived stable key.

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/route_error_contract_fixture.json` (test fixture, request-response)

**Analog:** `packages/platform-contract/fixtures/legal_wecom_contract_review.json`

**Fixture envelope pattern** (lines 1-5):
```json
{
  "fixture_id": "legal-wecom-contract-review-001",
  "description": "Synthetic WeCom lawfirm contract review turn with a track changes artifact and feedback relationship.",
  "events": {
```

**Route mismatch fields pattern** (lines 47-68 and 150-171):
```json
"route_decision": {
  "route_decision_id": "route-lawfirm-001",
  "turn_id": "turn-lawfirm-001",
  "primary_skill": "lawfirm.contract_review",
  "confidence": 0.92,
  "mode": "matched",
  "route_mismatch": false,
  "created_at": "2026-06-27T10:00:03Z"
},
"feedback_event": {
  "event_type": "format_issue",
  "action": "needs_fix",
  "route_mismatch": false,
  "related_route_decision": "route-lawfirm-001",
  "feedback_target": "feedback-target-lawfirm-001",
  "raw_payload_ref": "fixture://raw/lawfirm-feedback-001"
}
```

**Copy pattern:** Change route error fixture to `mode: "zero_match"` or `mode: "simple_qa"`, set `route_mismatch: true` on result/feedback, include `skill_candidate` only as recorded candidate data, and keep raw route/callback payloads as `fixture://` refs.

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/long_task_failure_contract_fixture.json` (test fixture, event-driven)

**Analog:** `packages/platform-contract/fixtures/legal_wecom_contract_review.json`

**Execution trace and error slots pattern** (lines 70-114):
```json
"execution_trace": {
  "trace_id": "trace-lawfirm-001",
  "turn_id": "turn-lawfirm-001",
  "started_at": "2026-06-27T10:00:04Z",
  "ended_at": "2026-06-27T10:01:30Z",
  "active_skill_name": "lawfirm.contract_review",
  "matched_registered_skill": true,
  "seq": 1,
  "steps": [
    {
      "name": "classify_request",
      "state": "succeeded"
    }
  ],
  "errors": []
}
```

**Result status pattern** (lines 115-149):
```json
"agent_result": {
  "result_id": "result-lawfirm-001",
  "turn_id": "turn-lawfirm-001",
  "status": "success",
  "reply_type": "file",
  "feedback_target": "feedback-target-lawfirm-001",
  "metadata": {
    "trace_id": "trace-lawfirm-001",
    "route_decision_id": "route-lawfirm-001"
  }
}
```

**Copy pattern:** For a failure fixture, use `steps[].state: "queued"`, `"running"`, then `"failed"` where relevant, `agent_result.status: "failed"`, `reply_type: "status_update"` or `"text"`, and an `error`/`errors` object with category from `ErrorCategory` (`contract_error`, `runtime_error`, `channel_error`).

### `.planning/phases/03-hermes-integration-spike-and-risk-closure/fixtures/repeated_feedback_clicks_contract_fixture.json` (test fixture, event-driven)

**Analog:** `packages/platform-contract/fixtures/legal_wecom_contract_review.json`

**Feedback association pattern** (lines 142-171):
```json
"feedback_target": "feedback-target-lawfirm-001",
"feedback_event": {
  "feedback_id": "feedback-lawfirm-001",
  "turn_id": "turn-lawfirm-001",
  "result_id": "result-lawfirm-001",
  "conversation_id": "conv-lawfirm-demo-001",
  "user_id": "user-lawfirm-demo-001",
  "source": "card_button",
  "action": "needs_fix",
  "related_route_decision": "route-lawfirm-001",
  "feedback_target": "feedback-target-lawfirm-001",
  "status": "pending",
  "raw_payload_ref": "fixture://raw/lawfirm-feedback-001"
}
```

**Copy pattern:** Preserve one traceable `feedback_target` per response. For repeated click examples, represent dedupe evidence in `metadata` or a separate phase decision table; if using a single bundle, model the canonical accepted event and document duplicate callback rows by `raw_payload_ref`, not by embedding raw callback payload.

### `packages/contract-test-suite/fixtures/phase3_non_happy_path_*.json` (test fixture, request-response/event-driven)

**Analog:** `packages/platform-contract/fixtures/non_legal_engineering_task.json`

**Non-legal industry-neutral fixture pattern** (lines 5-29):
```json
"agent_turn": {
  "turn_id": "turn-engineering-001",
  "conversation_id": "conv-engineering-demo-001",
  "channel": "web",
  "user_id": "user-engineering-demo-001",
  "message_type": "text",
  "content": "Summarize this deployment checklist into a short engineering handoff.",
  "industry_context": {
    "domain": "engineering",
    "system": "deployment",
    "task_type": "handoff_summary"
  },
  "metadata": {
    "profile": "engineering-demo",
    "raw_payload_ref": "fixture://raw/engineering-turn-001"
  }
}
```

**Simple/zero-match route pattern** (lines 30-43):
```json
"route_decision": {
  "route_decision_id": "route-engineering-001",
  "turn_id": "turn-engineering-001",
  "primary_skill": null,
  "supporting_skills": [],
  "confidence": 0.61,
  "matched_rule": "simple_markdown_summary",
  "mode": "simple_qa",
  "route_mismatch": false,
  "created_at": "2026-06-27T11:00:02Z"
}
```

**Copy pattern:** Add at least one Phase 3 non-legal fixture using `industry_context.domain` outside `lawfirm`. Do not add legal-only top-level fields; keep sensitive/source payloads under `metadata.raw_payload_ref` or artifact/source refs.

### `packages/contract-test-suite/tests/test_phase3_non_happy_paths.py` (test, batch)

**Analog:** `packages/contract-test-suite/tests/test_composability.py`

**Imports and setup pattern** (lines 1-17 and 28-32):
```python
from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT, PLATFORM_FIXTURE_ROOT
from contract_test_suite.schema_validation import (
    ContractValidationError,
    FORBIDDEN_TOP_LEVEL_FIELDS,
    load_schemas,
    validate_event_bundle,
)

class ComposabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixtures = load_non_legal_composability_fixtures()
```

**Validation and relationship pattern** (lines 34-41):
```python
def test_non_legal_fixtures_validate_and_preserve_relationships(self) -> None:
    for fixture_path, fixture in self.fixtures:
        with self.subTest(fixture=fixture["fixture_id"]):
            validate_event_bundle(fixture, self.schemas)
            report = assert_relationship_integrity([fixture_path], schemas=self.schemas)

            self.assertEqual(report.broken_relationship_count, 0)
            self.assertEqual(report.breakage_rate, 0.0)
```

**Negative relationship pattern** (`packages/contract-test-suite/tests/test_fixture_replay.py` lines 74-123):
```python
def test_relationship_breaks_fail_with_fixture_name_expected_and_actual(self) -> None:
    cases = (
        (
            "feedback_target",
            ("events", "feedback_event", "feedback_target"),
            "feedback-target-broken",
            r"feedback_event.feedback_target.*expected='feedback-target-lawfirm-001'.*actual='feedback-target-broken'",
        ),
    )

    for relationship, path, replacement, expected_message in cases:
        with self.subTest(relationship=relationship):
            fixture = copy.deepcopy(self.fixtures[0])
            self._set_path(fixture, path, replacement)

            with self.assertRaisesRegex(
                AssertionError,
                rf"legal-wecom-contract-review-001.*{relationship}.*{expected_message}",
            ):
                self._assert_single_fixture_integrity(fixture)
```

**Copy pattern:** Load explicit Phase 3 fixture paths. For each, run `validate_event_bundle()` and `assert_relationship_integrity()`. Add focused assertions for route error (`route_mismatch` and candidate recorded), long-task failure (`failed` step/status and error category), repeated feedback (`feedback_target`, idempotency metadata or documented duplicate ref), and non-legal coverage.

## Shared Patterns

### Contract Test Runner
**Source:** `packages/contract-test-suite/README.md` lines 5-14 and `packages/contract-test-suite/scripts/run_contract_tests.py` lines 11-23
**Apply to:** Any fixture/test change
```bash
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
```

```python
suite = unittest.defaultTestLoader.discover(str(package_root / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
return 0 if result.wasSuccessful() else 1
```

### Fixture Loading Roots
**Source:** `packages/contract-test-suite/src/contract_test_suite/paths.py` lines 8-13
**Apply to:** Tests that load platform or contract-test-suite fixtures
```python
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]
PLATFORM_CONTRACT_ROOT = REPO_ROOT / "packages" / "platform-contract"
PLATFORM_SCHEMA_ROOT = PLATFORM_CONTRACT_ROOT / "src" / "platform_contract" / "schemas"
PLATFORM_FIXTURE_ROOT = PLATFORM_CONTRACT_ROOT / "fixtures"
LOCAL_FIXTURE_ROOT = PACKAGE_ROOT / "fixtures"
```

### Schema Validation
**Source:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` lines 19-39 and 96-114
**Apply to:** All Phase 3 reusable JSON fixtures
```python
EVENT_SCHEMA_BY_KEY = {
    "agent_turn": "agent_turn",
    "route_decision": "route_decision",
    "execution_trace": "execution_trace",
    "agent_result": "agent_result",
    "feedback_event": "feedback_event",
}

FORBIDDEN_TOP_LEVEL_FIELDS = {
    "case_type",
    "jurisdiction",
    "statute",
    "cause_of_action",
    "liability",
    "client_name",
    "id_number",
    "phone",
    "bank_account",
    "address",
    "raw_payload",
}
```

```python
def validate_event_bundle(
    fixture: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    loaded_schemas = schemas if schemas is not None else load_schemas()
    fixture_id = _fixture_id(fixture)
    events = fixture.get("events")
    if not isinstance(events, dict):
        raise ContractValidationError(f"{fixture_id}: events must be object")

    extra_events = sorted(set(events) - set(EVENT_SCHEMA_BY_KEY))
    if extra_events:
        raise ContractValidationError(f"{fixture_id}.{extra_events[0]}: unknown event key")

    for event_key in EVENT_SCHEMA_BY_KEY:
        if event_key not in events:
            raise ContractValidationError(f"{fixture_id}.{event_key}: missing event")
        validate_event(event_key, events[event_key], loaded_schemas, fixture_id=fixture_id)
```

### Relationship Integrity
**Source:** `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` lines 115-147 and 180-228
**Apply to:** Route error, long-task failure, repeated feedback, and non-legal fixtures
```python
turn_id = agent_turn["turn_id"]
for event_key in ("route_decision", "execution_trace", "agent_result", "feedback_event"):
    checks.append(("turn_id", f"{event_key}.turn_id", turn_id, events[event_key]["turn_id"]))

checks.extend(
    [
        (
            "feedback_result_id",
            "feedback_event.result_id",
            agent_result["result_id"],
            feedback_event["result_id"],
        ),
        (
            "feedback_target",
            "feedback_event.feedback_target",
            agent_result["feedback_target"],
            feedback_event["feedback_target"],
        ),
    ]
)
```

```python
if isinstance(result_metadata, dict) and "trace_id" in result_metadata:
    checks.append(
        (
            "trace_id",
            "agent_result.metadata.trace_id",
            execution_trace["trace_id"],
            result_metadata["trace_id"],
        )
    )

artifacts_written = set(execution_trace.get("artifacts_written", []))
result_artifact_ids: set[Any] = set()
for index, artifact in enumerate(agent_result.get("artifacts", [])):
    artifact_id = artifact.get("artifact_id")
    result_artifact_ids.add(artifact_id)
    checks.append(
        (
            "artifact_id",
            f"agent_result.artifacts[{index}].artifact_id",
            artifact_id,
            artifacts_written,
        )
    )
```

### Privacy Boundary
**Source:** `packages/platform-contract/fixtures/README.md` lines 3-5 and 22-25
**Apply to:** All docs, fixtures, and tests
```markdown
These fixtures are synthetic, non-sensitive examples for checking the Phase 1
platform contract package. They demonstrate event relationships only; they are
not production logs, legal documents, customer records, or Hermes runtime data.
```

```markdown
Legal-specific sample details must stay inside extension containers such as
`industry_context` or `metadata`. Raw legal payloads and sensitive personal data
must be represented only by references, such as `raw_payload_ref` or artifact
URIs.
```

### Exact Enum Values
**Source:** `packages/platform-contract/src/platform_contract/enums.py` lines 6-22, 57-62, 96-125, 128-132
**Apply to:** State mapping docs and non-happy-path fixtures
```python
class AsyncTaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ErrorCategory(StrEnum):
    CONTRACT_ERROR = "contract_error"
    RUNTIME_ERROR = "runtime_error"
    CHANNEL_ERROR = "channel_error"
```

```python
class AgentResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"
```

## No Analog Found

No Phase 3 expected file is completely without an analog. The main limitation is that production Hermes hook source, WeCom callback payload samples, `feedback.jsonl`, and long-task runtime logs are absent from this repository, so all Hermes-source-dependent patterns must be documented as `requires Hermes source/runtime`.

## Metadata

**Analog search scope:** `.planning/phases/03-hermes-integration-spike-and-risk-closure`, `.planning/phases/01-platform-contract-foundation`, `.planning/phases/02-contract-test-suite-foundation`, `packages/platform-contract`, `packages/contract-test-suite`, `docs/requirements/V2-PRD.md`
**Files scanned:** 30+
**Pattern extraction date:** 2026-06-28
