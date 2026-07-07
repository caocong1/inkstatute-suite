# Architecture Research

**Domain:** QQ Bot platform channel production — real ingress/egress/feedback/session-continuity integrated into the existing InkStatute V2 multi-channel platform
**Researched:** 2026-07-07
**Confidence:** HIGH (sourced from codebase inspection of all referenced files, official QQ Open Platform docs at bot.q.qq.com API v2, and cross-checked against the existing WeCom reference channel implementation)

## Standard Architecture

### System Overview

The diagram below shows the **target v1.8 architecture** — the existing platform with new QQBot production components (marked `[NEW]`) integrated alongside reusable existing components (marked `[REUSE]`). The frozen 6-method `ChannelAdapter` Protocol (`packages/platform-runtime/src/platform_runtime/protocols.py:208-219`) is the integration seam between the QQBot channel and the platform runtime. No Protocol methods are added or modified.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        External Platform Layer                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐              ┌──────────────────────────┐      │
│  │  QQ Open Platform   │              │  WeCom (existing)        │      │
│  │  (webhook + OpenAPI)│              │  (callback + send API)   │      │
│  └──────────┬──────────┘              └────────────┬─────────────┘      │
├─────────────┼──────────────────────────────────────┼────────────────────┤
│             ▼                                      ▼                    │
│  ┌──────────────────────┐         ┌──────────────────────────────┐      │
│  │ QQBot Channel Adapter│         │ WeCom Channel Service        │      │
│  │ [packages/channels/  │         │ [services/wecom-service]     │      │
│  │  qqbot]              │         │  (reference channel)         │      │
│  │                      │         │                              │      │
│  │ ┌──────────────────┐ │         │ ┌──────────────────────────┐ │      │
│  │ │ Ed25519 Verifier │ │         │ │ SHA1+AES Verifier        │ │      │
│  │ │ [NEW]             │ │         │ │ [REUSE protocol.py]      │ │      │
│  │ ├──────────────────┤ │         │ ├──────────────────────────┤ │      │
│  │ │ QQ Normalizer    │ │         │ │ WeCom Normalizer         │ │      │
│  │ │ [NEW]             │ │         │ │ [REUSE normalization.py] │ │      │
│  │ ├──────────────────┤ │         │ ├──────────────────────────┤ │      │
│  │ │ QQ Egress Sender │ │         │ │ WeCom Sender             │ │      │
│  │ │ [NEW]             │ │         │ │ [REUSE sender.py]        │ │      │
│  │ ├──────────────────┤ │         │ ├──────────────────────────┤ │      │
│  │ │ Token Manager    │ │         │ │ (WeCom access_token)     │ │      │
│  │ │ [NEW]             │ │         │ │ [REUSE agent_backend.py] │ │      │
│  │ ├──────────────────┤ │         │ ├──────────────────────────┤ │      │
│  │ │ QQBotSession     │ │         │ │ WeComSessionRuntime      │ │      │
│  │ │ Runtime [NEW]     │ │         │ │ [REUSE pattern, not code]│ │      │
│  │ └──────────────────┘ │         │ └──────────────────────────┘ │      │
│  └──────────┬──────────┘         └──────────────┬───────────────┘      │
│             │                                    │                      │
│  ┌──────────┴──────────────────────────────────┴──────────────┐        │
│  │           channel-core [REUSE — shared, frozen]             │        │
│  │  output_policy · idempotency · delivery_guard ·             │        │
│  │  active_task_router · owned_notices                          │        │
│  └──────────┬─────────────────────────────────────┬───────────┘        │
├─────────────┼─────────────────────────────────────┼────────────────────┤
│             ▼                                     ▼                    │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │         ChannelAdapter Protocol (6 methods, FROZEN)          │      │
│  │  channel_id · capabilities · verify_and_ack ·                │      │
│  │  normalize_inbound · deliver · health                        │      │
│  │  [packages/platform-runtime/.../protocols.py:208-219]        │      │
│  └──────────┬──────────────────────────────────────┬───────────┘      │
│             ▼                                      ▼                   │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │              DefaultRunRuntime [REUSE — unchanged]           │      │
│  │  create_run · resume_interrupt · poll · stream · cancel      │      │
│  │  [packages/platform-runtime/.../runtime.py:26-693]           │      │
│  │  Injected: BackendAdapter · channels[] · MemoryOrchestrator  │      │
│  └──────────┬──────────────────────────────────────┬───────────┘      │
│             ▼                                      ▼                   │
│  ┌──────────────────────────┐    ┌───────────────────────────────┐    │
│  │ BackendAdapter (Hermes)  │    │ SessionResolutionPolicy       │    │
│  │ [REUSE — unchanged]      │    │ + InterruptStore [REUSE]      │    │
│  │                          │    │ + MemoryOrchestrator [REUSE]  │    │
│  └──────────────────────────┘    └───────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────┤
│                        Cross-Channel Services                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │ feedback-service │  │ conversation-    │  │ contract-test-   │    │
│  │ [REUSE]          │  │ read-view        │  │ suite [REUSE]    │    │
│  │ channel-neutral  │  │ [REUSE]          │  │ 24 V2 gates      │    │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘    │
├─────────────────────────────────────────────────────────────────────────┤
│                        Contract Layer                                    │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐        │
│  │ platform-contract│  │ JSONL Contract Event Logs            │        │
│  │ [FROZEN — no     │  │ (AgentTurn · AgentResult ·            │        │
│  │  enum additions] │  │  FeedbackEvent · ExecutionTrace)     │        │
│  └──────────────────┘  └──────────────────────────────────────┘        │
├─────────────────────────────────────────────────────────────────────────┤
│                        Operator Layer                                    │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │ QQBot Smoke-Test Toolkit [NEW]                              │        │
│  │ CLI script + fixtures + runbook (env-var credentials)       │        │
│  └────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| QQBotChannelAdapter | Implement 6-method ChannelAdapter Protocol for QQ platform: verify_and_ack, normalize_inbound, deliver, health, channel_id, capabilities | **MODIFY** (promote from fixture to real IO) | `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` |
| QQBotChannelConfig | Hold channel config with secret refs (never raw secrets), `from_env` factory | **MODIFY** (add `bot_secret_ref` for Ed25519) | `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` |
| Ed25519 Verifier | Verify QQ webhook signatures (`X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp+raw_body`); sign validation challenge (op=13) | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` |
| QQ Event Normalizer | Parse QQ gateway envelope `{id,op,s,t,d}` → `AgentTurn` / `FeedbackEvent`; strip @-bot prefix; map `INTERACTION_CREATE` → feedback | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` |
| QQ Egress Sender | Build QQ send envelopes (text `msg_type=0`, markdown+keyboard `msg_type=2`); call QQ OpenAPI with access token; handle `msg_id`+`msg_seq` dedupe | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` |
| QQ Access Token Manager | Acquire + cache + auto-refresh QQ access token (`appId`+`clientSecret` → token, 7200s TTL, 60s overlap) | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py` |
| QQBotSessionRuntime | Orchestrate session resolution, interrupt resume, active-task routing, memory recall for QQ turns — mirrors WeComSessionRuntime pattern with QQ identity rules | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py` |
| QQBotIngressRuntime | Host-callable ingress boundary: callback → turn → session runtime → outcome (mirrors WeComRuntimeIngress) | **NEW** | `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py` |
| channel-core | Channel-generic logic: output_policy, idempotency, delivery_guard, active_task_router, owned_notices | **REUSE** (frozen, no changes) | `packages/channel-core/src/channel_core/` |
| ChannelAdapter Protocol | 6-method Protocol signature contract | **FROZEN** (no changes) | `packages/platform-runtime/src/platform_runtime/protocols.py:208-219` |
| DefaultRunRuntime | Embeddable run runtime: create_run, resume_interrupt, poll, stream, cancel, approve | **REUSE** (unchanged) | `packages/platform-runtime/src/platform_runtime/runtime.py` |
| SessionResolutionPolicy + InterruptStore | Session resolution decisions, interrupt lifecycle | **REUSE** (unchanged) | `packages/platform-runtime/src/platform_runtime/session_resolver.py` |
| MemoryOrchestrator | Memory recall + retain for session continuity | **REUSE** (unchanged) | `packages/platform-runtime/src/platform_runtime/memory_orchestrator.py` |
| feedback-service | FeedbackEvent normalization, dedupe, classification, pending queue — channel-neutral | **REUSE** (unchanged, channel-neutral by design) | `services/feedback-service/src/feedback_service/` |
| conversation-read-view | Read-only views from contract logs — channel-neutral (filters by `channel` field) | **REUSE** (unchanged, already supports `Channel.QQBOT`) | `services/conversation-read-view/src/conversation_read_view/` |
| platform-contract | Event schemas, enums (Channel.QQBOT already exists), Python bindings | **FROZEN** (no enum additions needed) | `packages/platform-contract/src/platform_contract/` |
| QQBot Smoke-Test Toolkit | CLI script + fixtures + runbook for live-platform smoke test | **NEW** | `packages/channels/qqbot/scripts/smoke_test.py` + `packages/channels/qqbot/runbook/` |

## Recommended Project Structure

```
packages/channels/qqbot/
├── src/inkstatute_channels_qqbot/
│   ├── __init__.py              # Exports: adapter, config, new modules
│   ├── adapter.py               # MODIFY: promote from fixture to real IO
│   ├── config.py                # MODIFY: add bot_secret_ref
│   ├── signature.py             # NEW: Ed25519 verify + sign (validation challenge)
│   ├── normalization.py         # NEW: QQ gateway envelope → AgentTurn / FeedbackEvent
│   ├── sender.py                # NEW: QQ egress envelopes + OpenAPI calls
│   ├── token_manager.py         # NEW: access token acquire/cache/refresh
│   ├── session_runtime.py       # NEW: QQBotSessionRuntime (mirrors WeCom pattern)
│   ├── ingress_runtime.py       # NEW: QQBotIngressRuntime (callback → turn → runtime)
│   └── qq_types.py              # NEW: QQ event type constants, op codes, intent flags
├── tests/
│   ├── test_qqbot_channel_adapter.py    # EXISTING: extend with real-IO paths
│   ├── test_qqbot_channel_loop.py       # EXISTING: extend with real loop
│   ├── test_signature.py                # NEW: Ed25519 verify + challenge vectors
│   ├── test_normalization.py            # NEW: QQ event → AgentTurn / FeedbackEvent
│   ├── test_sender.py                   # NEW: egress envelope + msg_seq dedupe
│   ├── test_token_manager.py            # NEW: token lifecycle + refresh
│   ├── test_session_runtime.py          # NEW: QQ session continuity
│   ├── test_ingress_runtime.py          # NEW: callback → runtime orchestration
│   ├── test_feature_flag.py             # EXISTING: keep green
│   ├── test_no_wecom_import.py          # EXISTING: keep green (enforced)
│   ├── test_contract_freeze_not_violated.py  # EXISTING: keep green
│   └── test_smoke_toolkit.py            # NEW: toolkit dry-run (no live IO in CI)
├── fixtures/
│   ├── qqbot_channel_loop.json          # EXISTING: fixture-only loop
│   ├── qqbot_real_ingress.json          # NEW: real QQ event payload fixtures
│   ├── qqbot_real_egress.json           # NEW: real QQ send envelope fixtures
│   └── qqbot_feedback_interaction.json  # NEW: INTERACTION_CREATE fixtures
├── scripts/
│   └── smoke_test.py                    # NEW: one-click live smoke-test CLI
├── runbook/
│   └── SMOKE_TEST_RUNBOOK.md            # NEW: operator runbook
├── pyproject.toml
└── README.md
```

### Structure Rationale

- **`packages/channels/qqbot/` (not `services/`):** QQBot is a channel adapter package, not a standalone service. It implements the `ChannelAdapter` Protocol and is injected into `DefaultRunRuntime.channels[]`. WeCom is a `services/` because it owns a full service (ingress runtime, task flow, session runtime, sender, protocol). QQBot follows the same internal decomposition but as a package, consistent with the v1.6 decision to extract channel adapters into `packages/channels/`.
- **No `wecom_service` imports:** Enforced by `test_no_wecom_import.py`. All channel-generic logic comes from `channel-core`. QQ-specific logic (signature, normalization, sender, token, session) is channel-local.
- **`signature.py` separate from `normalization.py`:** Ed25519 key derivation + verify/sign is a distinct concern from event payload parsing. Separation matches the WeCom pattern where `protocol.py` (signature/parse) is separate from `normalization.py` (event mapping).
- **`session_runtime.py` + `ingress_runtime.py` as new files:** These mirror `wecom_service/session_runtime.py` and `wecom_service/ingress_runtime.py` but with QQ identity rules (composite openid conversation IDs, passive-reply window awareness). They must NOT import from `wecom_service` — they compose `platform_runtime` primitives directly.
- **`scripts/` + `runbook/` at package root:** The smoke-test toolkit is an operator deliverable, not a library module. Scripts import the adapter package; the runbook is documentation.

## Architectural Patterns

### Pattern 1: Protocol-Adapter — QQ-Specific Behavior via Metadata, Not New Methods

**What:** The frozen 6-method `ChannelAdapter` Protocol (`channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health`) is the only integration seam between the QQBot channel and the platform runtime. QQ-specific capabilities (markdown delivery, interaction ACK, Ed25519 verification, keyboard buttons) are expressed through existing method implementations using `ChannelDelivery.metadata`, `AckResponse.metadata`, and `ChannelCapabilitySet.metadata` — never by adding Protocol methods.

**When to use:** Always — this is a hard constraint enforced by `test_contract_freeze_not_violated.py`.

**Trade-offs:** The Protocol stays stable (all channels remain swappable), but QQ-specific logic is less type-safe (metadata is `JsonObject`). The trade-off is intentional: channel-specific richness lives inside the adapter, not in the shared contract.

**Example:**
```python
# QQ interaction ACK encoded in AckResponse.metadata, not a new method
async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
    payload = self._payload_from_raw(raw)
    if payload.get("op") == 13:  # validation challenge
        return AckResponse(
            accepted=True,
            status_code=200,
            metadata={
                "qq_ack_type": "validation_challenge",
                "plain_token": payload["d"]["plain_token"],
                "signature": self._sign_challenge(payload["d"]),
            },
        )
    if payload.get("t") == "INTERACTION_CREATE":
        return AckResponse(
            accepted=True,
            status_code=200,
            metadata={
                "qq_ack_type": "interaction_ack_required",
                "interaction_id": payload["d"]["id"],
                # Host must call PUT /interactions/{id} via egress
            },
        )
    # Normal message event: HTTP 200 empty body
    return AckResponse(accepted=True, status_code=200, metadata={"qq_ack_type": "webhook"})
```

### Pattern 2: Channel-Generic Core + Channel-Local Periphery

**What:** All logic that is identical across channels lives in `channel-core` (output_policy, idempotency, delivery_guard, active_task_router, owned_notices). All logic that differs per platform lives in the channel package. The QQBot adapter imports from `channel-core` but never from `wecom_service`.

**When to use:** When a new channel shares behavior with an existing channel but has platform-specific protocol details (signature scheme, payload format, send API, session identity).

**Trade-offs:** `channel-core` must stay generic enough for all channels (no WeCom-specific assumptions leaked in). The v1.6 extraction already achieved this. Risk: if QQ needs a behavior that WeCom also needs but `channel-core` doesn't have yet, it must be added to `channel-core` (not duplicated in both).

**Example:**
```python
# QQBot adapter reuses channel-core for output boundary + idempotency
from channel_core.idempotency import channel_idempotency_key
from channel_core.output_policy import apply_output_policy

# QQ-specific normalization is channel-local
def normalize_qq_event(payload: dict) -> AgentTurn:
    # ... QQ gateway envelope parsing ...
    idem_key = channel_idempotency_key(payload, channel_prefix="qqbot",
                                       stable_fields=(("message", ("id",)),))
    # ... build AgentTurn with channel="qqbot" ...
```

### Pattern 3: Session Runtime Mirror — QQBotSessionRuntime Composes platform_runtime Primitives

**What:** `WeComSessionRuntime` (`services/wecom-service/.../session_runtime.py:92-853`) is a pure orchestration seam that composes `RunRuntime`, `SessionResolutionPolicy`, `InMemoryInterruptStore`, `MemoryOrchestrator`, and `active_task_router` to handle normalized turns. `QQBotSessionRuntime` mirrors this pattern with QQ-specific identity rules (composite openid conversation IDs, passive-reply window awareness) but composes the same `platform_runtime` primitives. It does NOT subclass or import `WeComSessionRuntime`.

**When to use:** When a channel needs session continuity (interrupt resume, active-task routing, memory recall) but has different identity/session semantics from the reference channel.

**Trade-offs:** Code duplication between `WeComSessionRuntime` and `QQBotSessionRuntime` is intentional — it preserves the no-cross-channel-import constraint and allows each channel to evolve its session semantics independently. If significant shared orchestration logic emerges, it should be extracted into `channel-core` or `platform-runtime`, not shared by direct import.

**Example:**
```python
# QQBotSessionRuntime composes platform_runtime, not wecom_service
from platform_runtime import (
    InMemoryInterruptStore, MemoryOrchestrator, RunRuntime,
    SessionResolutionPolicy, SessionScope,
)
from channel_core.active_task_router import route_active_task_turn

class QQBotSessionRuntime:
    def __init__(self, *, runtime: RunRuntime,
                 interrupt_store: InMemoryInterruptStore | None = None,
                 policy: SessionResolutionPolicy | None = None,
                 memory_orchestrator: MemoryOrchestrator | None = None,
                 ...):
        # Same injection pattern as WeComSessionRuntime
        self.runtime = runtime
        self.interrupt_store = interrupt_store
        # ...

    async def handle_turn(self, *, turn, scope: SessionScope, run_request, ...):
        # QQ identity: conversation_id = user_openid (C2C) or
        #              group_openid + member_openid (group)
        # Same interrupt/active-task/memory flow as WeCom
        ...
```

## Data Flow

### Request Flow — QQBot Inbound (Message → Agent Turn → Run → Reply)

```
[QQ Platform Webhook]
    │  POST {id, op:0, s, t:"C2C_MESSAGE_CREATE", d:{id, author.user_openid, content, timestamp}}
    ▼
[Host Web Server] → [RawInbound(channel_id="qqbot", payload_ref, raw_body_bytes)]
    ▼
[QQBotChannelAdapter.verify_and_ack]
    │  1. Ed25519 verify(timestamp + raw_body, X-Signature-Ed25519)
    │  2. If op==13: return validation challenge response
    │  3. Else: return AckResponse(accepted=True, status=200)
    ▼
[QQBotChannelAdapter.normalize_inbound]
    │  1. Parse gateway envelope {op, t, d}
    │  2. Map t → message vs feedback
    │  3. Strip @-bot prefix from content (group mode)
    │  4. Build AgentTurn(channel="qqbot", conversation_id=composite_openid,
    │     user_id=user_openid, content=stripped_text)
    │  5. channel_core.idempotency.channel_idempotency_key(prefix="qqbot")
    ▼
[QQBotIngressRuntime.handle_callback]
    │  1. Build SessionScope(tenant_id, workspace_id, channel_id="qqbot",
    │     user_id, bot_instance_id, conversation_id=composite_openid)
    │  2. Build RunRequest(turn, solution, tenant/workspace/bot, session_id)
    ▼
[QQBotSessionRuntime.handle_turn]
    │  1. Check idempotency (duplicate answer → ignore)
    │  2. Check pending interrupt (expired? → resolve; active? → resume)
    │  3. Check active task (route_active_task_turn via channel_core)
    │  4. Else: continue/start session
    │  5. Memory recall (MemoryOrchestrator.recall_and_assemble)
    ▼
[DefaultRunRuntime.create_run]
    │  1. Attach context bundle (memory + context assembly)
    │  2. BackendAdapter.submit_run → Hermes
    │  3. Record contract log (AgentTurn, RunEvent)
    │  4. Record clarification interrupt if needs_clarification
    ▼
[BackendAdapter (Hermes)] → [AgentResult]
    ▼
[DefaultRunRuntime] → [Run(status=succeeded/partial/failed)]
    ▼
[QQBotChannelAdapter.deliver]
    │  1. channel_core.output_policy.apply_output_policy(content)
    │     → block / rewrite / allow
    │  2. Build QQ send envelope (msg_type=0 text or msg_type=2 markdown+keyboard)
    │  3. Set msg_id (from inbound d.id) + msg_seq for passive-reply dedupe
    │  4. Token Manager → access_token
    │  5. POST /v2/users/{openid}/messages (C2C) or /v2/groups/{group_openid}/messages
    │  6. Return DeliveryResult(accepted, delivered_at, idempotency_key)
    ▼
[QQ Platform] → [User sees reply in QQ]
```

### Request Flow — QQBot Feedback (Button Click → FeedbackEvent → Dedupe)

```
[QQ Platform Webhook]
    │  POST {id, op:0, t:"INTERACTION_CREATE", d:{id, data.resolved.button_data,
    │      data.resolved.message_id, user_openid, group_openid}}
    ▼
[QQBotChannelAdapter.verify_and_ack]
    │  Ed25519 verify → AckResponse(metadata={"qq_ack_type": "interaction_ack_required",
    │     "interaction_id": d.id})
    ▼
[Host] → PUT /interactions/{interaction_id} via Token Manager (interaction ACK)
    ▼
[QQBotChannelAdapter.normalize_inbound]
    │  1. Detect t=="INTERACTION_CREATE"
    │  2. Map button_data → action (up/down/needs_fix/route_wrong)
    │  3. feedback_target ← data.resolved.message_id
    │  4. Build FeedbackEvent(source="card_button", event_type=rating/correction/route_mismatch,
    │     status="pending", action=action, feedback_target=target)
    │  5. channel_core.idempotency.channel_idempotency_key(prefix="qqbot",
    │     stable_fields=(("callback", ("id",)),))
    ▼
[feedback-service] (channel-neutral, REUSE)
    │  1. dedupe_feedback_events (by idempotency_key)
    │  2. classify_feedback_event
    │  3. build_pending_feedback_queue
    │  4. If route_wrong: SkillCandidate(detected=True, requires_human_review=True)
    ▼
[JSONL Contract Log] → feedback_event record
    ▼
[conversation-read-view] → feedback visible in read-only views (filtered by channel="qqbot")
```

### State Management

```
[QQBotSessionRuntime]
    │
    ├── InMemoryInterruptStore [REUSE]
    │     └── pending interrupts per SessionScope (waiting_for_user)
    │
    ├── SessionResolutionPolicy [REUSE]
    │     └── decide: resume_interrupt / active_task_follow_up / continue / start_new
    │
    ├── MemoryOrchestrator [REUSE]
    │     └── recall_and_assemble → context bundle for RunRequest
    │     └── retain after run completion (user_turn + agent_reply)
    │
    ├── Active Task Router [REUSE channel_core]
    │     └── route_active_task_turn → status/cancel/update/parallel
    │
    └── Token Manager [NEW]
          └── cached access_token + expiry → auto-refresh at 60s before expiry
```

### Key Data Flows

1. **Inbound identity mapping:** QQ has no platform-side session/thread. Conversation identity is derived: C2C → `conversation_id = user_openid`; Group → `conversation_id = f"{group_openid}:{member_openid}"`. This composite ID flows into `SessionScope.conversation_id`, which drives interrupt scoping, memory recall, and active-task routing. The `SessionScope.channel_id` is always `"qqbot"` (from `Channel.QQBOT` enum, already exists in `platform-contract/enums.py:35`).

2. **Passive-reply window awareness:** QQ passive replies are time-boxed (C2C: 60 min / 4 replies per `msg_id`; Group: 5 min / 5 replies per `msg_id`). The inbound `msg_id` (from `d.id`) must be stored and passed to egress as `msg_id` + incrementing `msg_seq`. Window expiry surfaces as a `DeliveryResult` with `accepted=False` and a QQ-specific reason — not a silent drop. This is a QQ-specific data flow that has no WeCom equivalent (WeCom has a 48h service window, not per-message reply limits).

3. **Contract log channel tagging:** All contract events (`AgentTurn`, `AgentResult`, `FeedbackEvent`, `ExecutionTrace`) already carry a `channel` field. `Channel.QQBOT = "qqbot"` exists in the frozen enum (`platform-contract/enums.py:35`). No new enum values are needed. `conversation-read-view` already filters by channel — QQBot events appear automatically once they are written to the JSONL contract log. No read-view changes required.

4. **Feedback source parity:** QQ `INTERACTION_CREATE` maps to `FeedbackSource.CARD_BUTTON = "card_button"` — the same enum value WeCom uses. No new `FeedbackSource` enum value is added (frozen contract). The `feedback-service` normalizer (`wecom_normalizer.py`) is WeCom-specific by name but the dedupe/classification/queue logic (`queue.py`, `classification.py`) is channel-neutral. QQ feedback events flow through the same `dedupe_feedback_events` + `classify_feedback_event` + `build_pending_feedback_queue` pipeline.

5. **Output boundary reuse:** `channel_core.output_policy.apply_output_policy` is called inside `QQBotChannelAdapter.deliver()` before building the QQ send envelope — identical to how the fixture adapter already calls it (`adapter.py:107`). Block/rewrite/allow decisions apply to QQ text and markdown content. No new policy code.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 QQ users (trial) | Single-process async, in-memory interrupt store, in-memory token cache. All QQBot components in one package. Smoke-test toolkit validates the loop. No changes to platform-runtime or channel-core. |
| 100-10k QQ users | Swap `InMemoryInterruptStore` for a persistent store (same Protocol, injection point already exists in `DefaultRunRuntime.__init__`). Token manager adds a file/Redis cache for multi-process token sharing. QQBot adapter remains single-package; horizontal scaling is at the host/web-server layer, not the adapter. |
| 10k+ QQ users | QQ webhook events may need a queue (the adapter is synchronous ACK → async process). The `verify_and_ack` → `normalize_inbound` → `session_runtime` pipeline can be split: ACK immediately, enqueue `RawInbound` for async processing. This is a host-layer concern, not an adapter change — the adapter methods stay the same. Token manager must handle QQ rate limits (token endpoint may rate-limit). |

### Scaling Priorities

1. **First bottleneck: Token manager under concurrent egress.** All QQ OpenAPI calls (text send, markdown+keyboard send, interaction ACK, file upload) require the same access token. Under concurrent delivery, token refresh must be single-flight (one refresh, many waiters). Implement with an `asyncio.Lock` around the refresh path from the start.
2. **Second bottleneck: Passive-reply window expiry for long tasks.** Hermes legal tasks can exceed the 5-60 min QQ passive window. The `QQBotSessionRuntime` must detect window expiry and either (a) use `is_wakeup` interaction recall (v1.x feature, deferred) or (b) record a `delivery_guard` failure with a clear reason. Do not silently drop.

## Anti-Patterns

### Anti-Pattern 1: Importing from wecom_service in the QQBot Adapter

**What people do:** Copy `WeComSessionRuntime` or `WeComRuntimeIngress` logic by importing from `wecom_service`, or share a base class across channels via `wecom_service`.

**Why it's wrong:** `test_no_wecom_import.py` explicitly enforces that the QQBot adapter source contains no `wecom_service` string. WeCom is the reference channel, not a shared library. Cross-channel imports create a coupling that makes channels non-independent and violates the v1.6 architectural decision.

**Do this instead:** Mirror the pattern in channel-local code. Share only through `channel-core` (for channel-generic logic) and `platform-runtime` (for runtime primitives). If significant shared session orchestration logic emerges, extract it into `channel-core` as a new module — not into `wecom_service`.

### Anti-Pattern 2: Adding ChannelAdapter Protocol Methods for QQ-Specific Capabilities

**What people do:** Add `send_markdown()`, `ack_interaction()`, or `verify_webhook_challenge()` as new methods on the `ChannelAdapter` Protocol to express QQ-specific behavior cleanly.

**Why it's wrong:** The 6-method Protocol is frozen (`test_contract_freeze_not_violated.py`). Adding methods breaks every channel implementation, the contract freeze, and the 24 V2 gates. The Protocol is the stable integration seam — its power comes from being minimal and frozen.

**Do this instead:** Encode QQ-specific behavior inside existing method implementations using metadata fields: `ChannelDelivery.metadata["delivery_type"] = "markdown_keyboard"`, `AckResponse.metadata["qq_ack_type"] = "interaction_ack_required"`, `ChannelCapabilitySet.metadata["supports_markdown"] = True`. The host reads metadata to decide post-adapter actions (e.g., calling the interaction ACK endpoint).

### Anti-Pattern 3: Storing QQ Attachment URLs or Raw Media in Contract Logs

**What people do:** Store the QQ attachment `url` (time-limited, may contain PII from contract screenshots) or media bytes in the JSONL contract log for "replay purposes."

**Why it's wrong:** V2 privacy rule: contract logs prefer `raw_payload_ref` and must not store sensitive full text by default (`AGENTS.md`). QQ attachment URLs expire and may carry user legal documents. Storing them leaks content after expiry and violates privacy baselines.

**Do this instead:** Store only `attachment_id` (hash of URL), `kind`, `content_type`, and a `qqbot-media://` reference URI. Mirror WeCom's `source_status: "media_reference_only"` pattern (`normalization.py:147-149`). Never store the raw URL or bytes.

### Anti-Pattern 4: Conflating QQ WebSocket Resume with Conversation Session Continuity

**What people do:** Use QQ WebSocket op6 Resume (connection-level event replay after reconnect) as the mechanism for conversation session continuity (interrupt resume, memory recall).

**Why it's wrong:** WebSocket Resume is a transport reliability concern (replay missed events after a dropped connection). Conversation session continuity is a semantic concern (resume an interrupted agent turn, recall memory for a continuing conversation). Conflating them couples session state to transport and produces broken interrupt/resume semantics.

**Do this instead:** Use `platform_runtime` session/memory layer (`RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator`, `InMemoryInterruptStore`) for conversation continuity — same as WeCom. Treat WebSocket Resume (if ever implemented) purely as a transport concern that feeds events into the same `normalize_inbound` → `session_runtime` pipeline.

### Anti-Pattern 5: Auto-Active-Push for Task Completion

**What people do:** When a long legal task finishes, automatically push the answer to the QQ user/group via active push.

**Why it's wrong:** QQ active push is quota-capped (4/month per user/group), was disabled Apr 2025–Jun 2026, and group active push requires group-owner opt-in. Blind auto-push burns the monthly quota and can fail silently if the user disabled active messages (`C2C_MSG_REJECT`).

**Do this instead:** Use passive reply within the window first. For over-window completion, use `is_wakeup` interaction recall (windowed, 1/period — deferred to v1.x). If neither is available, record a `delivery_guard` failure with a clear reason. Never auto-active-push without an explicit user-initiated prior event.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| QQ Open Platform (webhook ingress) | Host web server receives POST callbacks; raw body bytes + `X-Signature-Ed25519` + `X-Signature-Timestamp` headers passed to `QQBotChannelAdapter.verify_and_ack` as `RawInbound.metadata["raw_body"]` + signature headers | Ed25519 verification over `timestamp + raw_body` (byte-concatenated). Must read raw body before JSON parse. Bot Secret → 32-byte seed (repeat-to-fill) → Ed25519 keypair. |
| QQ Open Platform (OpenAPI egress) | `QQBotChannelAdapter.deliver` calls QQ OpenAPI via `sender.py` using access token from `token_manager.py`. All calls use `Authorization: QQBot {ACCESS_TOKEN}` header. | Token: `POST https://bots.qq.com/app/getAppAccessToken` with `{appId, clientSecret}`. TTL 7200s, refresh at 60s before expiry. Single-flight refresh under concurrency. |
| QQ Open Platform (interaction ACK) | Host reads `AckResponse.metadata["qq_ack_type"] == "interaction_ack_required"` and calls `PUT /interactions/{interaction_id}` with `{code: 0}` via `sender.py` + token manager | Required for `INTERACTION_CREATE` events or the QQ client stays in loading state. Depends on access token (egress auth). This is a feedback→egress dependency unique to QQ. |
| Hermes (agent backend) | **No change.** `DefaultRunRuntime` calls `BackendAdapter.submit_run` → Hermes. QQBot turns reach Hermes through the same `RunRequest` path as WeCom turns. | `AgentTurn.channel = "qqbot"` is the only differentiator. Hermes does not know about QQBot — it receives a neutral `AgentTurn`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| QQBot Adapter ↔ channel-core | Direct Python import (`from channel_core.output_policy import apply_output_policy`) | channel-core is frozen. QQBot imports only the 5 existing modules: output_policy, idempotency, delivery_guard, active_task_router, owned_notices. No new channel-core modules needed for v1.8 MVP. |
| QQBot Adapter ↔ platform-runtime | Protocol-based (`ChannelAdapter` Protocol implemented by adapter; `RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator` injected into `QQBotSessionRuntime`) | The adapter is injected into `DefaultRunRuntime.channels[]`. `QQBotSessionRuntime` composes `platform_runtime` primitives directly (not through the adapter). |
| QQBot Adapter ↔ wecom_service | **No communication.** Enforced by `test_no_wecom_import.py`. | QQBot must not import, subclass, or reference `wecom_service`. Shared logic goes through `channel-core` or `platform-runtime`. |
| QQBot Adapter ↔ feedback-service | `FeedbackEvent` dataclass (from `platform_contract.events`) passed to feedback-service functions | feedback-service is channel-neutral (`dedupe_feedback_events`, `classify_feedback_event`, `build_pending_feedback_queue` accept `FeedbackEvent`-shaped dicts). No WeCom-specific coupling in the dedupe/classification/queue path. The `wecom_normalizer.py` module is WeCom-specific but is NOT used by QQBot — QQBot builds `FeedbackEvent` in its own `normalization.py`. |
| QQBot Adapter ↔ conversation-read-view | Indirect — via JSONL contract log records | `conversation-read-view` reads contract event JSONL files. QQBot events are written to the same log format with `channel="qqbot"`. The read-view already supports `Channel.QQBOT` filtering. No read-view changes needed. |
| QQBot Adapter ↔ platform-contract | `AgentTurn`, `FeedbackEvent`, `AttachmentRef`, `SkillCandidate` dataclasses; `Channel.QQBOT`, `FeedbackSource.CARD_BUTTON`, `FeedbackAction` enums | All needed enum values already exist in the frozen contract. No additions. `Channel.QQBOT = "qqbot"` (line 35), `FeedbackSource.CARD_BUTTON = "card_button"` (line 133), `FeedbackAction.{UP,DOWN,NEEDS_FIX,ROUTE_WRONG}` (lines 151-154). |
| QQBot Adapter ↔ feature flags | `RuntimeFeatureFlags.qqbot_channel_enabled` (default `False`) | Already exists (`feature_flags.py:23`). All real-IO paths must be gated behind this flag. When disabled, `verify_and_ack` returns 503 and `deliver` returns `accepted=False` (existing fixture behavior). |

## New vs Reuse vs Modified — Summary

### NEW Components (7 modules + toolkit)

| Component | Location | Why New |
|-----------|----------|---------|
| Ed25519 Verifier | `packages/channels/qqbot/.../signature.py` | QQ uses Ed25519 (not WeCom's SHA1+AES). Completely different crypto primitive. |
| QQ Event Normalizer | `packages/channels/qqbot/.../normalization.py` | QQ gateway envelope `{op,t,d}` is a different payload shape from WeCom's flat XML/JSON callback. QQ event types (`C2C_MESSAGE_CREATE`, `GROUP_AT_MESSAGE_CREATE`, `INTERACTION_CREATE`) have no WeCom equivalent. |
| QQ Egress Sender | `packages/channels/qqbot/.../sender.py` | QQ send API (`msg_type=0/2`, `msg_id`+`msg_seq`, keyboard structure) is different from WeCom's `msgtype`+`text.content` envelope. |
| Token Manager | `packages/channels/qqbot/.../token_manager.py` | QQ access token (appId+clientSecret → token, 7200s TTL) is a different auth flow from WeCom's access_token (corpid+secret). |
| QQBotSessionRuntime | `packages/channels/qqbot/.../session_runtime.py` | QQ identity rules (composite openid conversation IDs, passive-reply window awareness) differ from WeCom's chat_id/thread_id + 48h window. Must not import WeComSessionRuntime. |
| QQBotIngressRuntime | `packages/channels/qqbot/.../ingress_runtime.py` | Callback → turn → session runtime orchestration with QQ-specific scope building. Mirrors WeComRuntimeIngress pattern but with QQ identity. |
| Smoke-Test Toolkit | `packages/channels/qqbot/scripts/` + `runbook/` | No existing one-click toolkit for any channel. New operator deliverable. |

### MODIFIED Components (2 files)

| Component | Location | What Changes |
|-----------|----------|--------------|
| QQBotChannelAdapter | `packages/channels/qqbot/.../adapter.py` | Promote from fixture-only (no network IO) to real IO: `verify_and_ack` calls Ed25519 verifier; `normalize_inbound` calls QQ normalizer; `deliver` calls QQ sender + token manager; `health` checks token validity. All behind `qqbot_channel_enabled` flag. Fixture path preserved for CI when flag is off. |
| QQBotChannelConfig | `packages/channels/qqbot/.../config.py` | Add `bot_secret_ref` field (for Ed25519 key derivation). Add `from_env` entries for `INKSTATUTE_QQBOT_BOT_SECRET_REF`. Existing `app_id_ref`/`app_secret_ref`/`token_secret_ref` already present. |

### REUSED Components (unchanged)

| Component | Location | Reuse Mechanism |
|-----------|----------|-----------------|
| channel-core (5 modules) | `packages/channel-core/src/channel_core/` | Direct import: `output_policy`, `idempotency`, `delivery_guard`, `active_task_router`, `owned_notices` |
| ChannelAdapter Protocol | `packages/platform-runtime/.../protocols.py:208-219` | Implemented by QQBotChannelAdapter (6 methods, frozen) |
| DefaultRunRuntime | `packages/platform-runtime/.../runtime.py` | QQBot adapter injected into `channels[]`; `QQBotSessionRuntime` calls `create_run`/`resume_interrupt` |
| SessionResolutionPolicy + InterruptStore | `packages/platform-runtime/.../session_resolver.py` | Injected into `QQBotSessionRuntime` (same as WeComSessionRuntime) |
| MemoryOrchestrator | `packages/platform-runtime/.../memory_orchestrator.py` | Injected into `QQBotSessionRuntime` for recall + retain |
| feedback-service (dedupe/classify/queue) | `services/feedback-service/src/feedback_service/` | Channel-neutral functions accept `FeedbackEvent`-shaped dicts from QQ normalizer |
| conversation-read-view | `services/conversation-read-view/src/conversation_read_view/` | Reads JSONL contract logs; QQBot events with `channel="qqbot"` appear automatically |
| platform-contract (enums + events) | `packages/platform-contract/src/platform_contract/` | `Channel.QQBOT`, `FeedbackSource.CARD_BUTTON`, `FeedbackAction.*` all already exist |
| RuntimeFeatureFlags.qqbot_channel_enabled | `packages/platform-runtime/.../feature_flags.py:23` | Already exists, default `False` |

### FROZEN (must not change)

| Component | Location | Constraint |
|-----------|----------|------------|
| ChannelAdapter Protocol (6 methods) | `protocols.py:208-219` | `test_contract_freeze_not_violated.py` |
| BackendAdapter Protocol (9 methods) | `protocols.py:222-239` | Not touched by QQBot work |
| platform-contract enums | `enums.py` | No new enum values needed |
| platform-contract event schemas | `events.py` | No schema changes needed |
| channel-core modules | `channel_core/` | No new modules needed for MVP |
| Hermes core | (external) | Not rebuilt, called via BackendAdapter |

## Suggested Build Order

The build order respects dependencies identified in the FEATURES.md dependency graph and the codebase's existing test-first convention. Each phase produces testable, gate-green increments. No phase modifies the frozen Protocol, platform-contract, or Hermes core.

### Phase 1: Ed25519 Signature Verification + Validation Challenge

**Why first:** Every other ingress feature depends on being able to verify QQ callbacks. The validation challenge (op=13) is required to register the webhook URL at all. This is the foundation — without it, no QQ events arrive.

**Builds:**
- `signature.py`: Ed25519 key derivation (Bot Secret → 32-byte seed → keypair), `verify(timestamp + raw_body, signature)`, `sign(event_ts + plain_token)` for op=13.
- Tests with official QQ demo vectors.
- Modify `config.py`: add `bot_secret_ref`.

**Depends on:** `QQBotChannelConfig` (exists, needs `bot_secret_ref` addition).
**Does NOT depend on:** Any other new component.

### Phase 2: QQ Event Normalization (Inbound)

**Why second:** Once callbacks can be verified, the next step is parsing QQ gateway envelopes into platform contract events. This is pure data transformation with no network IO — testable with fixtures.

**Builds:**
- `normalization.py`: Parse `{op, t, d}` envelope; map `C2C_MESSAGE_CREATE` + `GROUP_AT_MESSAGE_CREATE` → `AgentTurn`; map `INTERACTION_CREATE` → `FeedbackEvent`; strip @-bot prefix; build composite openid `conversation_id`.
- `qq_types.py`: Event type constants, op codes.
- Fixture files: `qqbot_real_ingress.json`, `qqbot_feedback_interaction.json`.
- Tests: normalization correctness, @-bot stripping, identity mapping, feedback action aliases.

**Depends on:** Phase 1 (signature verification for real callback handling, though normalization itself is pure).
**Does NOT depend on:** Token manager, sender, session runtime.

### Phase 3: Access Token Manager

**Why third:** All egress (text send, markdown+keyboard send, interaction ACK) requires a valid access token. This is the shared dependency for the entire egress surface. Building it before egress allows egress tests to mock the token.

**Builds:**
- `token_manager.py`: Acquire token (`POST getAppAccessToken`), cache with expiry, auto-refresh at 60s before expiry, single-flight refresh (`asyncio.Lock`).
- Tests: token lifecycle, refresh timing, concurrent refresh single-flight, error handling.

**Depends on:** `QQBotChannelConfig` (`app_id_ref`, `app_secret_ref` — already exist).
**Does NOT depend on:** Sender, normalization, session runtime.

### Phase 4: QQ Egress Sender (Text + Markdown + Keyboard)

**Why fourth:** With token management in place, the sender can make real OpenAPI calls. Text egress is the simplest; markdown+keyboard is the feedback card carrier. Both are needed before the feedback loop can dispatch cards.

**Builds:**
- `sender.py`: `build_text_envelope` (msg_type=0), `build_markdown_keyboard_envelope` (msg_type=2 + keyboard with callback buttons), `send_message` (POST to QQ OpenAPI with token), `msg_id`+`msg_seq` passive-reply dedupe, retry on transient failure.
- Modify `adapter.py`: `deliver()` calls sender + `apply_output_policy` (already called in fixture, now with real IO).
- Tests: envelope structure, msg_seq increment, output policy enforcement, retry behavior, window-expiry failure.

**Depends on:** Phase 3 (token manager), `channel_core.output_policy` (exists), `channel_core.delivery_guard` (exists).
**Does NOT depend on:** Session runtime, ingress runtime.

### Phase 5: QQBotSessionRuntime + QQBotIngressRuntime

**Why fifth:** Session continuity composes the runtime primitives around the normalized turns. It depends on normalization (Phase 2) to produce `AgentTurn`/`FeedbackEvent` and on the adapter (Phases 1+4) for ACK/delivery. This is the orchestration layer that ties ingress to the platform runtime.

**Builds:**
- `session_runtime.py`: `QQBotSessionRuntime` mirroring `WeComSessionRuntime` pattern — compose `RunRuntime`, `SessionResolutionPolicy`, `InMemoryInterruptStore`, `MemoryOrchestrator`, `active_task_router`. QQ identity rules: composite openid `conversation_id`, passive-reply window awareness.
- `ingress_runtime.py`: `QQBotIngressRuntime` — callback → `AgentTurn` → `SessionScope` → `RunRequest` → `QQBotSessionRuntime.handle_turn`.
- Tests: session continuity (continue/start/resume/active-task), interrupt resume, memory recall, idempotency, no `wecom_service` import.

**Depends on:** Phase 2 (normalization), `platform_runtime` primitives (exist), `channel_core.active_task_router` (exists).
**Does NOT depend on:** Sender (session runtime produces outcomes, not deliveries — delivery is a separate host concern).

### Phase 6: Adapter Integration — Promote to Real IO

**Why sixth:** Wire all new modules into `QQBotChannelAdapter`. The adapter becomes the single entry point that the host and `DefaultRunRuntime` use. Fixture path preserved for CI (when `qqbot_channel_enabled=False`).

**Builds:**
- Modify `adapter.py`: `verify_and_ack` → Ed25519 verify + op=13 challenge + interaction ACK metadata; `normalize_inbound` → QQ normalizer; `deliver` → QQ sender + output policy; `health` → token validity + config check.
- Update `capabilities()`: `supports_cards=True` (already), add `metadata["supports_markdown"]=True`, `metadata["network_io"]=True` (when enabled), remove `fixture_only=True` when enabled.
- Tests: full real-IO loop (mocked OpenAPI), fixture loop still passes, feature flag gating, contract freeze preservation.

**Depends on:** Phases 1-5 (all new modules).
**Does NOT depend on:** Smoke-test toolkit.

### Phase 7: Feedback Loop Parity (Interaction ACK + FeedbackEvent Pipeline)

**Why seventh:** The feedback loop requires egress (keyboard card dispatch — Phase 4) and ingress (INTERACTION_CREATE normalization — Phase 2) plus the interaction ACK (egress — Phase 4). This phase wires the complete feedback loop end-to-end and validates parity with WeCom's feedback-service pipeline.

**Builds:**
- Wire `INTERACTION_CREATE` → `normalize_inbound` → `FeedbackEvent` → `feedback-service` dedupe/classify/queue.
- Wire interaction ACK: host reads `AckResponse.metadata["qq_ack_type"]` → calls `PUT /interactions/{id}` via sender + token manager.
- Tests: feedback loop end-to-end, dedupe via `channel_core.idempotency`, `FeedbackSource.CARD_BUTTON` parity, `SkillCandidate` human-review-only for `route_wrong`.

**Depends on:** Phases 2, 4, 6.
**Does NOT depend on:** Session runtime (feedback normalization is independent of session continuity).

### Phase 8: One-Click Smoke-Test Toolkit

**Why last:** The toolkit exercises the entire real loop (ingress + egress + feedback) against the live QQ sandbox. It depends on all production features being implemented. Live run remains a human gate, but the toolkit ships in this milestone.

**Builds:**
- `scripts/smoke_test.py`: CLI that (1) validates webhook signature with demo vector, (2) sends a text message to a configured openid, (3) sends a markdown+keyboard feedback card, (4) simulates a callback button click, (5) collects evidence into a sanitized JSON artifact. Credentials via env vars only.
- `runbook/SMOKE_TEST_RUNBOOK.md`: Step-by-step operator guide.
- Tests: dry-run mode (no live IO in CI), credential injection via env, evidence format validation, no secrets in output.

**Depends on:** Phases 1-7 (all production features).

### Build Order Dependency Graph

```
Phase 1 (Ed25519 signature)
    │
    ├──> Phase 2 (Normalization)
    │       │
    │       └──> Phase 5 (Session Runtime + Ingress Runtime)
    │               │
    │               └──> Phase 6 (Adapter Integration)
    │                       │
    │                       └──> Phase 7 (Feedback Loop Parity)
    │                               │
    │                               └──> Phase 8 (Smoke-Test Toolkit)
    │
    └──> Phase 3 (Token Manager)
            │
            └──> Phase 4 (Egress Sender)
                    │
                    └──> Phase 6 (Adapter Integration)
                    │
                    └──> Phase 7 (Feedback Loop Parity)
```

Phases 1+3 can be built in parallel (no interdependency). Phases 2+4 can be built in parallel after their respective deps (Phase 2 after Phase 1; Phase 4 after Phase 3). Phase 5 requires Phase 2. Phase 6 requires Phases 1-5. Phase 7 requires Phases 2+4+6. Phase 8 requires Phases 1-7.

## Sources

- Codebase inspection: `packages/channels/qqbot/` (adapter.py, config.py, tests, fixtures)
- Codebase inspection: `packages/channel-core/` (output_policy.py, idempotency.py, delivery_guard.py, active_task_router.py, owned_notices.py)
- Codebase inspection: `services/wecom-service/` (session_runtime.py, ingress_runtime.py, normalization.py, sender.py, protocol.py, task_flow.py, agent_backend.py, memory_integration.py)
- Codebase inspection: `packages/platform-runtime/` (protocols.py, runtime.py, session_resolver.py, feature_flags.py, memory_orchestrator.py)
- Codebase inspection: `packages/platform-contract/` (enums.py, events.py)
- Codebase inspection: `services/feedback-service/` (__init__.py, wecom_normalizer.py, queue.py, classification.py)
- Codebase inspection: `services/conversation-read-view/` (read_model.py)
- `.planning/PROJECT.md` — milestone context, requirements, key decisions
- `.planning/research/FEATURES.md` — feature landscape, dependencies, MVP definition
- `.planning/research/PITFALLS.md` — critical pitfalls (signature, validation, session, privacy)
- `AGENTS.md` — project safety rules, coding rules, architecture constraints
- QQ Open Platform official docs: bot.q.qq.com API v2 (Ed25519 verification, access token, message types, interaction callbacks, keyboard buttons)

---
*Architecture research for: QQ Bot platform channel production (v1.8)*
*Researched: 2026-07-07*
