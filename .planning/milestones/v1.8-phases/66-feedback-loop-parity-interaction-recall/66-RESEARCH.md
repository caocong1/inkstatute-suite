# Phase 66: Feedback Loop Parity + Interaction Recall - Research

**Researched:** 2026-07-09
**Domain:** QQ Bot feedback E2E (INTERACTION_CREATE → FeedbackEvent → feedback-service) + C2C `is_wakeup` interaction recall
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- End-to-end feedback: keyboard → INTERACTION_CREATE → FeedbackEvent → feedback-service
- Interaction ACK (PUT /interactions/{id}) after feedback normalization
- Dedupe: msg_id + button identity
- is_wakeup recall: 30-day windows, 1 per period
- Parity with WeCom feedback pipeline (compose patterns, no wecom_service import)
- dependencies=[]; no frozen Protocol/platform-contract/channel-core edits
- Reuse Phase 60 normalization FeedbackEvent + Phase 65 ack_interaction

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

### Deferred Ideas (OUT OF SCOPE)
Smoke toolkit is Phase 67. Live promotion remains human gate.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FEEDBACK-01 | E2E feedback: keyboard → INTERACTION_CREATE → FeedbackEvent → feedback-service dedupe/classify/queue; WeCom parity | Compose QQ FeedbackEvent dicts into existing `normalize_feedback_inputs(contract_feedback_events=…)` + `build_pending_feedback_queue`; do not import `wecom_service` |
| FEEDBACK-02 | Interaction ACK (`PUT /interactions/{id}`) after feedback normalization | Reuse Phase 65 `ack_interaction`; host/pipeline no-ops when `interaction_ack_status=="sent"`; optional deferred-ACK host path documented |
| FEEDBACK-03 | Dedupe via `msg_id` + button identity | Stamp `metadata.idempotency_key` in `normalize_interaction_event`; feedback-service collapses on that key |
| RECALL-01 | `is_wakeup` recall for over-window long-task completion (30-day periods, 1/period) | C2C-only wire field; mutual exclusion with `msg_id`/`event_id`; in-package period gate + deliver branch |
</phase_requirements>

## Summary

Phase 60 already maps `INTERACTION_CREATE` → `FeedbackEvent(source="card_button")`. Phase 62 already builds markdown+keyboard cards. Phase 65 already performs two-tier ACK (`{"op":12}` + live `PUT /interactions/{id}`). Feedback-service already dedupes/classifies/queues any contract-shaped FeedbackEvent dict via `normalize_feedback_inputs(contract_feedback_events=…)` without needing WeCom-specific normalizers. [VERIFIED: codebase]

The remaining gaps are composition and QQ-specific semantics: (1) stamp a stable `metadata.idempotency_key` of `msg_id + button identity` on interaction FeedbackEvents; (2) expose a host-callable feedback ingress path (today `QQBotRuntimeIngress` skips non-message categories); (3) prove E2E queue parity without `wecom_service` imports and without adding package dependencies; (4) implement C2C `is_wakeup` send + period accounting when passive-reply windows expire. [VERIFIED: ingress_runtime.py, queue.py, official send docs]

**Primary recommendation:** Keep `packages/channels/qqbot` as the owner of QQ-specific prepare/ACK/wakeup helpers (`dependencies=[]`). Stamp FEEDBACK-03 keys in `normalization.py`. Add a pure feedback-ingress helper that returns FeedbackEvent dicts. Compose into feedback-service only at host/test PYTHONPATH boundaries (mirror WeCom: channel normalizes → service queues). Extend `sender.py` + `adapter.deliver` for C2C `is_wakeup` with an injectable in-memory period store — no new DB/queue service.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keyboard card egress | API / Backend (`qqbot.sender` + `adapter.deliver`) | — | Already Phase 62; host supplies `delivery_type=card` |
| INTERACTION_CREATE → FeedbackEvent | API / Backend (`normalization.py`) | — | Phase 60 pure normalizer; stamp idempotency here |
| Feedback ingress (non-session) | API / Backend (`ingress` helper / host) | — | Interactions are not AgentTurns; skip session runtime |
| Dedupe / classify / pending queue | API / Backend (`feedback_service`) | — | Existing Phase 6 helpers; channel-agnostic |
| Interaction ACK PUT | API / Backend (`sender.ack_interaction`) | Host HTTP 200 op=12 | Phase 65; Phase 66 no-ops if already `sent` |
| Passive-window gate | API / Backend (`check_passive_reply_window`) | — | Phase 62; fail-closed before wakeup |
| `is_wakeup` recall send | API / Backend (`sender` + `adapter.deliver`) | Injectable period store | C2C OpenAPI only; no durable DB in this phase |
| Live smoke / credentials | Manual / Phase 67 | — | Deferred |

## Project Constraints (from .cursor/rules/ + AGENTS.md)

No `.cursor/rules/` directory present in this workspace. Applicable project constraints from `AGENTS.md` / v1.8 practice:

- Do not import `wecom_service` into qqbot (`test_no_wecom_import.py`).
- Do not modify frozen ChannelAdapter Protocol, platform-contract schemas/enums, or channel-core modules.
- Keep `packages/channels/qqbot` and `services/feedback-service` at `dependencies=[]`.
- Prefer `raw_payload_ref`; never store `raw_payload` / secrets / attachment URLs in events or metadata.
- High-risk feedback (`route_wrong` / skill_candidate) stays human-reviewed (`no_auto_modify`); no auto skill synthesis.
- Do not introduce a new durable queue, database, or worker daemon unless the active plan requires it — feedback-service pending queue remains derived/rebuildable.
- Tests with behavior changes (dedupe, ordering, fixture replay).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `unittest` | 3.11+ (env 3.14.6) | Unit/integration tests | Existing qqbot + feedback-service pattern [VERIFIED: env] |
| `platform_contract.events.FeedbackEvent` | in-repo | Contract event shape | Frozen; already used by Phase 60 [VERIFIED: events.py] |
| `feedback_service.queue` | in-repo `0.1.0` | Dedupe / classify / pending queue | WeCom parity composition target [VERIFIED: queue.py] |
| `inkstatute_channels_qqbot` | in-repo `0.1.0` | Normalize, ACK, deliver, wakeup | Channel owner; `dependencies=[]` [VERIFIED: pyproject.toml] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses.asdict` (stdlib) | — | FeedbackEvent → dict for queue | Before `contract_feedback_events=` |
| `channel_core.idempotency.channel_idempotency_key` | in-repo | Generic key helper (messages) | Not for FEEDBACK-03 — use explicit msg_id+button |
| FakeMessageTransport / Fake TokenManager | in-repo | CI live-IO simulation | Wakeup + ACK tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Host PYTHONPATH composition | Add `feedback-service` to qqbot `dependencies` | Violates `dependencies=[]` |
| Import `wecom_service.normalize_wecom_feedback_callback` | Copy WeCom patterns only | Forbidden by ADAPTER-03 / no-wecom rule |
| Durable Redis/DB for wakeup periods | In-memory injectable store | New infra out of scope; host can swap later |
| Monthly active push (`PUSH-01`) | `is_wakeup` only | Explicitly deferred; quota/opt-in risk |

**Installation:** none — no new external packages.

**Version verification:** No new registry packages. Existing packages remain `dependencies=[]`. [VERIFIED: pyproject.toml ×2]

## Package Legitimacy Audit

> No new external packages are recommended for this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 available; unused because no install candidates.*

## Architecture Patterns

### System Architecture Diagram

```text
[QQ keyboard card] --deliver card--> [adapter.deliver / sender.build_feedback_keyboard_envelope]
        |
        v
[User button click] --> [Webhook INTERACTION_CREATE]
        |
        +--> [verify_and_ack] --> op=12 body + (live) PUT /interactions/{id}   # Phase 65
        |
        +--> [normalize_inbound / normalize_interaction_event]
                |  stamps metadata.idempotency_key = msg_id + button
                v
           FeedbackEvent (source=card_button)
                |
                v
        [host: dataclasses.asdict + privacy check]
                |
                v
        [feedback_service.normalize_feedback_inputs(contract_feedback_events=…)]
                |  dedupe on metadata.idempotency_key
                v
        [classify_feedback_event → build_pending_feedback_queue]

Over-window long task completion (C2C):
[adapter.deliver] --passive window fail--> issue_code=qqbot_passive_reply_window_expired
        |
        +-- if metadata.is_wakeup / allow_wakeup + C2C -->
              [check_wakeup_quota] --ok--> [build_*_envelope with is_wakeup=true, NO msg_id/event_id]
                    --> send_message POST /v2/users/{openid}/messages
              --exhausted/group--> delivery failure + interim notice (no active push)
```

### Recommended Project Structure

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── normalization.py      # MODIFY — stamp FEEDBACK-03 idempotency_key on interaction FeedbackEvent
├── feedback_ingress.py   # ADD — pure handle_feedback_callback → FeedbackEvent + dict evidence
├── adapter.py            # MODIFY — deliver() wakeup branch; optional deferred ACK helper
├── sender.py             # MODIFY — wakeup envelope builders + period gate + strip_for_wire rules
├── ingress_runtime.py    # OPTIONAL thin re-export / host docs only (keep message path unchanged)
└── ...

services/feedback-service/
├── src/feedback_service/queue.py   # REUSE — contract_feedback_events path (no wecom import)
└── tests/test_qqbot_feedback_parity.py  # ADD — QQ dicts dedupe/classify/queue

packages/channels/qqbot/tests/
├── test_feedback_pipeline.py       # ADD — normalize → dict → feedback_service (PYTHONPATH)
├── test_feedback_idempotency.py    # ADD — msg_id+button dedupe key
├── test_wakeup_recall.py           # ADD — periods, mutual exclusion, group fail-closed
└── test_no_wecom_import.py         # KEEP green
```

### Pattern 1: WeCom-parity composition (no wecom import)

**What:** Channel produces a FeedbackEvent-shaped dict with `metadata.idempotency_key` already set; feedback-service treats it as `contract_feedback_events`.
**When to use:** Always for QQ button feedback.
**Example:**

```python
# Source: services/feedback-service/src/feedback_service/queue.py (contract_feedback_events path)
from dataclasses import asdict
from feedback_service.queue import normalize_feedback_inputs, build_pending_feedback_queue

event_dict = asdict(feedback_event)  # SkillCandidate nested → dict
# Ensure no raw_payload keys (feedback_service raises)
canonical = normalize_feedback_inputs(contract_feedback_events=[event_dict])
queue = build_pending_feedback_queue(canonical)
```

### Pattern 2: FEEDBACK-03 idempotency key

**What:** Stable key `"{msg_id}:{button_identity}"` stored in `FeedbackEvent.metadata["idempotency_key"]` so `dedupe_feedback_events` collapses retries/re-clicks.
**When to use:** Inside `normalize_interaction_event` (single source of truth).
**Example:**

```python
# Source: in-repo recommendation aligned with FEEDBACK-03 + queue._idempotency_key
msg_id = _optional_string(resolved.get("message_id")) or interaction_id
button_identity = (
    _optional_string(resolved.get("button_id"))
    or _optional_string(resolved.get("button_data"))
    or action
)
idempotency_key = f"{msg_id}:{button_identity}"
metadata["idempotency_key"] = idempotency_key
metadata["dedupe_strategy"] = "msg_id + button_identity"
metadata["msg_id"] = msg_id
```

### Pattern 3: ACK after normalize (FEEDBACK-02)

**What:** Logical pipeline is normalize → queue → ensure interaction ACK complete. Phase 65 already PUTs eagerly in `verify_and_ack` when live. [VERIFIED: adapter.py]
**When to use:** Host orchestration.
**Recommended behavior:**
1. Default: keep Phase 65 eager ACK (clears QQ client loading state quickly). After normalize+queue, **no-op** if `AckResponse.metadata["interaction_ack_status"] == "sent"`.
2. Optional host mode: if ACK was `pending_host` / `skipped_fixture`, call `ack_interaction` after successful normalize (never after failed signature).
3. Do not double-PUT without treating QQ `code==3` duplicate as non-fatal (already Phase 65).

### Pattern 4: C2C `is_wakeup` recall (RECALL-01)

**What:** When passive window fails and host requests wakeup, send C2C message with `is_wakeup=true` and **without** `msg_id` / `event_id`. [CITED: bot.q.qq.com send.html]
**When to use:** Over-window long-task completion for C2C only.
**Example:**

```python
# Source: https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html
envelope = {
    "msg_type": 0,
    "content": visible_text,
    "is_wakeup": True,
    # intentionally omit msg_id / event_id / msg_seq
}
# POST /v2/users/{openid}/messages
```

Period model (official): four windows after user-initiated dialogue — same calendar day, 1–3 days, 3–7 days, 7–30 days; **1 message per period**; periods recompute when the user messages again on a later day. [CITED: send.html]

### Anti-Patterns to Avoid

- **Importing `wecom_service`:** Breaks ADAPTER-03 / `test_no_wecom_import.py`.
- **Adding pyproject dependencies:** Violates `dependencies=[]`.
- **Sending `is_wakeup` with `msg_id` or `event_id`:** Official mutual exclusion; platform rejects or misclassifies. [CITED: send.html]
- **Group `is_wakeup`:** Group send API has no `is_wakeup` field in official docs — fail closed. [CITED: send.html]
- **Using monthly active push for recall:** PUSH-01 deferred; burns quota / opt-in. [CITED: FEATURES.md anti-feature]
- **Editing frozen Protocol / platform-contract / channel-core:** ADAPTER-04.
- **Auto-modifying skills from `route_wrong`:** Keep `no_auto_modify` / human review.
- **Storing raw payloads or tokens in FeedbackEvent / DeliveryResult metadata.**
- **Routing INTERACTION through `QQBotSessionRuntime` as an AgentTurn:** Wrong event type; keep feedback path separate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feedback dedupe/classify/queue | Custom QQ queue service | `feedback_service.queue` | Already schema-aware, privacy-checked, pending-queue derived |
| Interaction ACK HTTP | Ad hoc urllib in adapter | `sender.ack_interaction` | Charset validation, QQ code handling, Fake transport |
| FeedbackEvent schema | New fields/enums | Existing `FeedbackEvent` + metadata | Frozen contract |
| Output filtering on wakeup text | Skip policy | `apply_output_policy` / existing builders | Same legal boundary as passive replies |
| Period math ad hoc strings | Magic timestamps only | Explicit period enum + injectable clock/store | Testable; host can persist later |

**Key insight:** Parity means **compose the same feedback-service APIs**, not share WeCom modules. QQ owns key stamping + wakeup wire shape; feedback-service stays channel-agnostic.

## Common Pitfalls

### Pitfall 1: Missing `message_id` on INTERACTION fixtures
**What goes wrong:** Dedupe key falls back to `interaction_id`; retries of the *same* platform event collapse, but distinct clicks on the same card button may not share a key if `message_id` absent.
**Why it happens:** Current fixture `qqbot_interaction_create.json` has no `resolved.message_id`. [VERIFIED: fixture]
**How to avoid:** Prefer `resolved.message_id`; fallback to interaction_id; extend fixtures with `message_id` for FEEDBACK-03 tests; document host should correlate card `feedback_target` when available.
**Warning signs:** Duplicate pending queue rows for repeated clicks on one card.

### Pitfall 2: Double ACK / ACK-before-normalize debate
**What goes wrong:** Re-implementing PUT in Phase 66 causes duplicate ACK noise or regresses Phase 65 tests.
**Why it happens:** CONTEXT says “ACK after normalize”; Phase 65 already ACKs in `verify_and_ack`.
**How to avoid:** No-op when `interaction_ack_status=="sent"`; only PUT when pending/failed-retry policy says so.
**Warning signs:** New PUT calls in normalize path; flaky `code==3` handling.

### Pitfall 3: `is_wakeup` + `msg_id` together
**What goes wrong:** Send fails or counts against wrong quota.
**Why it happens:** Passive builders always set `msg_id` via `_base_envelope`.
**How to avoid:** Dedicated wakeup builders that omit passive fields; assert mutual exclusion in unit tests; `strip_for_wire` must not re-add them.
**Warning signs:** Wire body contains both `is_wakeup` and `msg_id`.

### Pitfall 4: Treating wakeup as group-capable
**What goes wrong:** Group over-window tasks silently “succeed” in code but fail on API.
**Why it happens:** FEATURES.md discusses recall generally; official `is_wakeup` is documented on C2C send only.
**How to avoid:** Gate `scene=="c2c"`; group → `issue_code=qqbot_wakeup_unsupported_scene` + interim notice.
**Warning signs:** Group wakeup tests posting `is_wakeup`.

### Pitfall 5: Importing feedback-service into qqbot runtime as a hard package dep
**What goes wrong:** Breaks `dependencies=[]` or couples channel package to service package in setuptools.
**Why it happens:** Desire for a single `ingest()` function inside qqbot.
**How to avoid:** Pure prepare helpers in qqbot; composition in tests/host via PYTHONPATH (same monorepo pattern as conversation-read-view).
**Warning signs:** `feedback-service` appears in qqbot `pyproject.toml`.

### Pitfall 6: Privacy regression in asdict
**What goes wrong:** Nested structures accidentally include forbidden keys.
**Why it happens:** `asdict` is deep and faithful.
**How to avoid:** Rely on `normalize_feedback_inputs` `_privacy_checked_clone`; unit-test that `raw_payload` raises.
**Warning signs:** ValueError at queue boundary in CI.

## Code Examples

### Stamp interaction idempotency (FEEDBACK-03)

```python
# Source: packages/channels/qqbot/.../normalization.py (extend normalize_interaction_event)
msg_id = _optional_string(resolved.get("message_id")) or interaction_id
button_identity = (
    _optional_string(button_id)
    or button_data
    or action
)
fields_map["feedback_target"] = msg_id
fields_map["metadata"]["idempotency_key"] = f"{msg_id}:{button_identity}"
fields_map["metadata"]["dedupe_strategy"] = "msg_id + button_identity"
```

### Feedback ingress helper (FEEDBACK-01)

```python
# Source: recommended feedback_ingress.py — pure, no network
from dataclasses import asdict
from .normalization import QQBotEventCategory, normalize_interaction_event, parse_envelope

def handle_feedback_callback(callback: Mapping[str, Any], *, received_at: str, payload_ref: str | None = None) -> dict[str, Any]:
    event = parse_envelope(callback)
    if event.category != QQBotEventCategory.INTERACTION:
        return {"status": "skipped", "category": event.category.value}
    feedback = normalize_interaction_event(event, created_at=received_at, payload_ref=payload_ref)
    return {
        "status": "normalized",
        "feedback_event": feedback,
        "feedback_dict": asdict(feedback),
        "idempotency_key": feedback.metadata.get("idempotency_key"),
    }
```

### Wakeup period gate (RECALL-01)

```python
# Source: recommended sender.py — injectable store + clock
# Periods relative to last user message time T0:
#   P0: same UTC calendar day as T0
#   P1: (T0+1d) .. (T0+3d]
#   P2: (T0+3d) .. (T0+7d]
#   P3: (T0+7d) .. (T0+30d]
# One send per (user_openid, period_id); reset period basis when user sends a new message on a later day.
```

Exact boundary inclusivity should be locked in tests against the official wording (“当天、1 - 3 天、3 - 7 天、7 - 30 天”). Prefer half-open intervals in code and document the choice in SUMMARY. [ASSUMED: half-open day boundaries in UTC are acceptable for CI; live calendar TZ may be CST — flag for Phase 67]

### Deliver branch sketch

```python
# Source: adapter.deliver extension
if msg_id is not None:
    window = check_passive_reply_window(...)
    if not window.ok:
        if metadata.get("is_wakeup") or metadata.get("allow_wakeup"):
            return await self._deliver_wakeup(...)  # C2C only; strips msg_id
        return DeliveryResult(accepted=False, metadata={..., "issue_code": window.issue_code, ...})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixture-only feedback normalize | Real INTERACTION_CREATE → FeedbackEvent | Phase 60 | INGRESS-05 done |
| No interaction ACK | Two-tier ACK + `ack_interaction` | Phase 65 | INGRESS-06 done |
| Feedback-service WeCom-only mental model | Channel-agnostic `contract_feedback_events` | Phase 6 | FEEDBACK-01 composes here |
| Passive-only egress | + C2C `is_wakeup` recall | Phase 66 (this) | RECALL-01 |
| Active push for over-window | Avoid; use wakeup / fail closed | 2025–2026 QQ policy | PUSH-01 deferred |

**Deprecated/outdated:**
- “Store last msg_id to send is_wakeup” from FEATURES.md — contradicted by official mutual exclusion with `msg_id`/`event_id`. [CITED: send.html] [ASSUMED: FEATURES.md note is stale]
- Implementing monthly active push in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Half-open UTC day boundaries for wakeup periods are acceptable for CI; live TZ may differ | Pattern 4 / Pitfalls | Period edge tests may need CST calendar alignment in Phase 67 |
| A2 | Keeping Phase 65 eager ACK + post-normalize no-op satisfies FEEDBACK-02 “after normalization” | Pattern 3 | Product may insist PUT only after queue success — then add deferred-ACK config |
| A3 | `msg_id` in FEEDBACK-03 means card/`resolved.message_id` (feedback target), not interaction event id | Pattern 2 | If platform retries reuse interaction id only, fallback key still works |
| A4 | Group scenes have no `is_wakeup`; fail closed is correct | Pattern 4 | If QQ later adds group wakeup, extend sender |
| A5 | qqbot must not declare feedback-service in pyproject; PYTHONPATH composition is enough | Don't Hand-Roll | Host packaging may need an explicit optional extra later |
| A6 | In-memory wakeup period store is sufficient for Phase 66 (no durable DB) | Standard Stack | Multi-process hosts need host-provided store implementing same Protocol |

## Open Questions

1. **Strict ACK ordering vs eager ACK** — RESOLVED (planner 2026-07-09)
   - Resolution: Keep Phase 65 eager PUT; after normalize, **no-op if `interaction_ack_status=="sent"`**; only call `ack_interaction` when `pending_host` / retryable failed. Do not withhold ACK until queue write. Implemented in Plan 02 `ensure_interaction_ack`.

2. **Wakeup period timezone** — RESOLVED (planner 2026-07-09)
   - Resolution: Injectable timezone defaulting to `Asia/Shanghai` for period calendar-day labels; unit tests use fixed clock. Half-open P0–P3 intervals documented in Plan 03 / SUMMARY. Live TZ confirmation remains Phase 67 optional.

3. **Where E2E composition module lives** — RESOLVED (planner 2026-07-09)
   - Resolution: No new service — `feedback_ingress.py` in qqbot + host/test PYTHONPATH composition into `feedback_service.normalize_feedback_inputs(contract_feedback_events=…)`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | qqbot + feedback-service | ✓ | 3.14.6 | — |
| unittest | tests | ✓ | stdlib | — |
| feedback-service (src on PYTHONPATH) | FEEDBACK-01 parity tests | ✓ | 0.1.0 in-repo | — |
| platform-contract / channel-core | normalize + freeze gates | ✓ | in-repo | — |
| Network api.sgroup.qq.com | Live wakeup/ACK | host-dependent | — | FakeMessageTransport |
| QQ credentials | Live | not in repo | — | Fixtures / Phase 67 |
| New pip packages | — | N/A | — | **Do not add** |

**Missing dependencies with no fallback:** none for CI path.

**Missing dependencies with fallback:** live QQ network → Fake transports.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib; asyncio where needed) |
| Config file | `packages/channels/qqbot/pyproject.toml`, `services/feedback-service/pyproject.toml` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest packages.channels.qqbot.tests.test_feedback_pipeline packages.channels.qqbot.tests.test_wakeup_recall -v` |
| Full suite command | Same PYTHONPATH + `python3 -m unittest discover -s packages/channels/qqbot/tests -v` and `python3 -m unittest discover -s services/feedback-service/tests -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEEDBACK-01 | Keyboard→INTERACTION→FeedbackEvent→queue | unit/integration | `… test_feedback_pipeline` | ❌ Wave 0 |
| FEEDBACK-02 | ACK complete after normalize (no-op if sent) | unit | `… test_adapter_two_tier_ack` + new pipeline assert | ✅ extend |
| FEEDBACK-03 | Dedupe on msg_id+button | unit | `… test_feedback_idempotency` + feedback-service parity | ❌ Wave 0 |
| RECALL-01 | C2C is_wakeup periods 1/period; mutual exclusion | unit | `… test_wakeup_recall` | ❌ Wave 0 |
| ADAPTER-03/04 | no wecom; freeze; deps=[] | unit | `test_no_wecom_import` / `test_contract_freeze_not_violated` / `test_v1_8_safety_baseline` | ✅ |

### Sampling Rate

- **Per task commit:** quick run (feedback pipeline + wakeup)
- **Per wave merge:** full qqbot + feedback-service suites
- **Phase gate:** full suites green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/channels/qqbot/tests/test_feedback_pipeline.py` — FEEDBACK-01/02
- [ ] `packages/channels/qqbot/tests/test_feedback_idempotency.py` — FEEDBACK-03
- [ ] `packages/channels/qqbot/tests/test_wakeup_recall.py` — RECALL-01
- [ ] `services/feedback-service/tests/test_qqbot_feedback_parity.py` — contract_feedback_events dedupe/classify
- [ ] Extend `packages/channels/qqbot/fixtures/qqbot_interaction_create.json` with `resolved.message_id`
- [ ] Framework install: none

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (egress token) | Existing TokenManager bearer; no new auth |
| V3 Session Management | no | Feedback path is not session runtime |
| V4 Access Control | yes | Openid path validation in sender; no cross-tenant keys in events |
| V5 Input Validation | yes | Structured envelope parse; button_data allowlist via existing action map; interaction_id charset |
| V6 Cryptography | no new | Ed25519 verify already Phase 59; do not hand-roll |

### Known Threat Patterns for QQ feedback + wakeup

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate button callbacks inflate queue | Tampering / DoS | FEEDBACK-03 idempotency_key + feedback-service dedupe |
| Raw legal payload in feedback logs | Information disclosure | `raw_payload_ref` only; privacy clone raises on `raw_payload` |
| Token/Authorization in DeliveryResult metadata | Information disclosure | Existing sanitized metadata rules; assert in tests |
| Wakeup spam beyond quota | Elevation / abuse | Period store 1/period; fail closed when exhausted |
| Path injection via openid/interaction_id | Tampering | Existing `_require_openid` charset checks |
| Auto skill modify from route_wrong | Tampering | `no_auto_modify` + human review flags |

## Sources

### Primary (HIGH confidence)

- [VERIFIED: codebase] `packages/channels/qqbot/src/inkstatute_channels_qqbot/{normalization,adapter,sender,ingress_runtime}.py`
- [VERIFIED: codebase] `services/feedback-service/src/feedback_service/{queue,classification,wecom_normalizer}.py`
- [CITED: https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html] — `is_wakeup` mutual exclusion, C2C periods, group API fields
- [VERIFIED: `.planning/REQUIREMENTS.md` / `ROADMAP.md`] — FEEDBACK-01..03, RECALL-01
- [VERIFIED: Phase 65 RESEARCH/VALIDATION] — ACK timing resolution, deps=[], no wecom

### Secondary (MEDIUM confidence)

- [CITED: `.planning/research/FEATURES.md`] — wakeup feature intent; active-push anti-feature (partially stale on msg_id storage)
- Community adapter notes on `is_wakeup` suppressing passive fields (cross-check with official docs only)

### Tertiary (LOW confidence)

- Exact calendar TZ for “当天” period boundaries — needs Phase 67 live confirmation [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — reuse in-repo packages; no new deps
- Architecture: HIGH — composition path verified against feedback-service + Phase 60/65 code
- Pitfalls: HIGH — ACK ordering, wakeup mutual exclusion, group limitation cited from official docs; TZ boundary MEDIUM

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days; QQ OpenAPI send docs dated 2026-01-10 / 2026-06-22)
