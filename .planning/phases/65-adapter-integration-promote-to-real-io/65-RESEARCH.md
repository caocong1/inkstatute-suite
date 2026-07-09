# Phase 65: Adapter Integration — Promote to Real IO - Research

**Researched:** 2026-07-09
**Domain:** QQBot ChannelAdapter Protocol integration — real IO behind feature flag, metadata-only QQ specifics, two-tier ACK
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion.

Key constraints:
- All 6 frozen ChannelAdapter Protocol methods gain real IO behind `qqbot_channel_enabled` (default OFF)
- QQ-specific behavior ONLY via ChannelDelivery.metadata, AckResponse.metadata, ChannelCapabilitySet.metadata
- Two-tier ACK: op=12 HTTP 200 for messages + PUT /interactions/{id} for button clicks (INGRESS-06)
- Fixture path preserved when flag off (CI)
- No wecom_service imports; dependencies=[]; no frozen Protocol/platform-contract/channel-core module edits
- No new channel-core modules
- Compose existing Phase 59–64 modules (signature, normalization, token, sender, session/ingress runtime)

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

### Deferred Ideas (OUT OF SCOPE)
Feedback loop end-to-end and interaction recall are Phase 66. Smoke toolkit is Phase 67.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADAPTER-01 | Promote QQBotChannelAdapter from fixture-only to real IO across all 6 frozen Protocol methods; QQ specifics only via metadata | Wire Phase 59–63 modules into `adapter.py`; flip `fixture_only`/`network_io` metadata when enabled+injected transport; no Protocol edits |
| ADAPTER-02 | `qqbot_channel_enabled` defaults False; fixture path when flag off; real IO gated | Keep `RuntimeFeatureFlags.qqbot_channel_enabled=False` + `QQBotChannelConfig.enabled=False`; host maps flag→config; CI loop tests stay `network_io=False` |
| ADAPTER-03 | No `wecom_service` imports; reuse channel-core as-is; no new channel-core modules | Enforce/extend `test_no_wecom_import.py`; all new helpers stay in `inkstatute_channels_qqbot` |
| INGRESS-06 | Two-tier ACK: HTTP 200 + op=12 for messages; `PUT /interactions/{id}` for button clicks | `verify_and_ack` emits op=12 body metadata; interaction path calls/records PUT `{code:0}` via sender transport |
</phase_requirements>

## Summary

Phase 65 is an **integration phase**, not a greenfield module phase. Phases 59–64 already shipped signature verification, envelope normalization, token manager, egress sender (text/markdown/keyboard/rich media), and session/ingress runtimes. `QQBotChannelAdapter` already implements all six frozen `ChannelAdapter` methods, but most paths still advertise `fixture_only=True` / `network_io=False`, and `verify_and_ack` does not yet emit the QQ webhook op=12 ACK body or perform interaction PUT ACK.

This phase promotes the adapter to production-capable IO **behind** `qqbot_channel_enabled` / `QQBotChannelConfig.enabled` (default OFF): when the flag is off or transport/token are absent, preserve the existing CI fixture path; when enabled with injected `TokenManager` + message transport, `deliver` / interaction ACK may perform real OpenAPI calls using the Phase 61–63 urllib/Fake twin pattern (`dependencies = []`). QQ-specific wire details stay in metadata fields on frozen dataclasses — never new Protocol methods.

**Primary recommendation:** Modify only `packages/channels/qqbot` (`adapter.py` + small `sender.py` PUT helper for interaction ACK). Gate live network on `config.enabled` and injected transport/token. Encode two-tier ACK in `AckResponse.metadata` (`http_callback_ack_body={"op":12}` always on verified dispatch; `interaction_ack_*` + optional live PUT for `INTERACTION_CREATE`). Leave Phase 64 session/ingress as host-composed pure orchestration; leave feedback-service wiring and `is_wakeup` to Phase 66/67.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feature-flag gate (default OFF) | API / Backend (`QQBotChannelConfig.enabled` ← host from `RuntimeFeatureFlags.qqbot_channel_enabled`) | — | Adapter-local gate already used; do not edit frozen flags dataclass shape |
| `channel_id` / `capabilities` | API / Backend (`adapter.py`) | metadata only | Advertise QQ capabilities; flip `fixture_only`/`network_io` when live-capable |
| Signature + op=13 challenge | API / Backend (`verify_and_ack` → `signature.py`) | — | Already Phase 59; keep |
| Webhook ACK op=12 body | API / Backend (`verify_and_ack` metadata) | Host HTTP response writer | Adapter returns body in metadata; host writes HTTP 200 + JSON |
| Interaction PUT ACK | API / Backend (`verify_and_ack` / sender helper) | TokenManager + MessageTransport | Official `PUT /interactions/{id}` `{code:0}`; needs bearer token |
| Normalize inbound | API / Backend (`normalize_inbound` → `normalization.py`) | — | Already gateway-aware; adjust metadata flags only |
| Deliver text/card/file/image | API / Backend (`deliver` → `sender.py`) | TokenManager + transport | Already partially live when transport injected |
| Health | API / Backend (`health`) | optional TokenManager presence | Report enabled + injection readiness; avoid leaking tokens |
| Session continuity | Host + Phase 64 runtimes | — | Out of Protocol surface; host composes after normalize |
| Feedback-service queue / recall | Deferred Phase 66/67 | — | Out of scope |

## Project Constraints (from AGENTS.md / .cursor/rules/)

- No `.cursor/rules/` directory present — constraints from `AGENTS.md` + ROADMAP apply. `[VERIFIED: workspace listing 2026-07-09]`
- Never commit secrets, tokens, runtime DBs, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- Prefer `raw_payload_ref`; no sensitive full text in contract logs by default. `[VERIFIED: AGENTS.md]`
- Do not introduce new services/DBs/queues/runtime deps unless required. `[VERIFIED: AGENTS.md]`
- Keep changes scoped to active GSD phase. `[VERIFIED: AGENTS.md]`
- Frozen ChannelAdapter / BackendAdapter / platform-contract / channel-core must not be modified (ADAPTER-04 cross-cutting). `[VERIFIED: ROADMAP.md, REQUIREMENTS.md]`
- `packages/channels/qqbot/pyproject.toml` must keep `dependencies = []`. `[VERIFIED: pyproject.toml]`
- No `wecom_service` imports. `[VERIFIED: test_no_wecom_import.py]`

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `platform_runtime.protocols.ChannelAdapter` | in-repo (frozen 6 methods) | Protocol surface | Must not edit `[VERIFIED: protocols.py:208-219]` |
| `AckResponse` / `ChannelCapabilitySet` / `ChannelDelivery` / `DeliveryResult` / `InboundNormalized` / `ComponentHealth` / `RawInbound` | in-repo | Metadata carriers for QQ specifics | ADAPTER-01 requires metadata-only QQ behavior `[VERIFIED: protocols.py:32-95]` |
| Phase 59 `signature.py` | in-repo | Ed25519 verify + op=13 | Already wired in `verify_and_ack` |
| Phase 60 `normalization.py` | in-repo | Envelope → AgentTurn / FeedbackEvent | Already wired in `normalize_inbound` |
| Phase 61 `token_manager.py` | in-repo | Access token cache + single-flight | Required for interaction PUT + deliver |
| Phase 62/63 `sender.py` | in-repo | Envelopes + `MessageTransport` + send/upload | Extend with interaction PUT helper |
| Phase 64 session/ingress | in-repo | Host-side turn orchestration | Compose after normalize; not Protocol methods |
| `channel_core.output_policy` / `idempotency` | in-repo (read-only) | Output boundary + idem keys | Reuse as-is; no new channel-core modules |
| Python stdlib `urllib` / `asyncio` / `unittest` | 3.11+ (env 3.14.6) | HTTP twin + tests | Matches Phases 61–63; no httpx |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `FakeMessageTransport` / `FakeTokenTransport` | in-repo | CI real-IO path without network | Flag-on unit tests |
| `UrllibMessageTransport` / `UrllibTokenTransport` | in-repo | Production host injection | Live smoke (Phase 67 human gate) |
| `RuntimeFeatureFlags.qqbot_channel_enabled` | in-repo | Platform default-OFF flag | Assert default False; host maps to config |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stdlib urllib transport twin | `httpx` | **Forbidden** — `dependencies=[]`; STACK.md httpx advice superseded by Phases 61–63 `[VERIFIED: 63-RESEARCH.md]` |
| New Protocol methods for ACK body / interaction | Metadata on `AckResponse` | Locked by ADAPTER-01 / ADAPTER-04 |
| New `channel_core.qqbot_ack` module | Helpers in `sender.py` / `adapter.py` | CONTEXT forbids new channel-core modules |
| Import WeCom ACK helpers | Copy pattern only | ADAPTER-03 / `test_no_wecom_import` |
| Eager host-only PUT (adapter metadata only, never PUT) | Adapter performs PUT when live | ROADMAP SC requires PUT for button clicks in Phase 65; metadata-only alone is insufficient for “real IO” |

**Installation:** None — no new packages.

**Version verification:** No PyPI packages added. In-repo imports verified via `PYTHONPATH=… python3 -c "from platform_runtime.protocols import ChannelAdapter"`. `[VERIFIED: shell 2026-07-09]`

## Package Legitimacy Audit

> No external packages are installed in this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck available (0.6.1) but unused — zero registry dependencies.*

## Architecture Patterns

### System Architecture Diagram

```text
QQ webhook POST (raw body + Ed25519 headers)
        │
        ▼
Host builds RawInbound (payload_ref + metadata.request_body/signatures)
        │
        ▼
QQBotChannelAdapter.verify_and_ack
        ├─ enabled=False → AckResponse 503 (fixture/CI refuse)
        ├─ signature fail → 401
        ├─ op=13 → validation_challenge_response in metadata
        └─ verified dispatch:
              ├─ always: metadata.http_callback_ack_body = {"op": 12}
              └─ INTERACTION_CREATE:
                    ├─ metadata.interaction_ack_required=True + interaction_id
                    └─ if enabled + token + transport: PUT /interactions/{id} {"code":0}
        │
        ▼
Host HTTP response: status_code + optional JSON body from metadata
        │
        ▼
QQBotChannelAdapter.normalize_inbound → AgentTurn | FeedbackEvent
        │
        ▼
Host (optional Phase 64): QQBotRuntimeIngress / QQBotSessionRuntime
        │
        ▼
QQBotChannelAdapter.deliver(ChannelDelivery)
        ├─ output_policy + passive window
        ├─ build envelope (text/markdown/card/media)
        └─ if enabled + token + transport: send_message / send_rich_media
```

### Recommended Project Structure

```text
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── adapter.py              # MODIFY — promote all 6 methods; two-tier ACK metadata + live gates
├── sender.py               # MODIFY — add ack_interaction() + transport PUT support
├── signature.py            # reuse
├── normalization.py        # reuse (interaction_id already in FeedbackEvent.metadata)
├── token_manager.py        # reuse
├── session_runtime.py      # reuse (host compose; no Protocol change)
├── ingress_runtime.py      # reuse (host compose; no Protocol change)
└── config.py               # reuse (enabled default False)

packages/channels/qqbot/tests/
├── test_adapter_real_io.py           # NEW — flag-on Fake transport paths for 6 methods
├── test_adapter_two_tier_ack.py      # NEW — op=12 + interaction PUT metadata/calls
├── test_qqbot_channel_loop.py        # KEEP green — fixture path network_io=False
├── test_feature_flag.py              # KEEP / extend default-OFF
├── test_no_wecom_import.py           # KEEP / ensure still covers adapter+sender
└── test_contract_freeze_not_violated.py  # KEEP
```

### Pattern 1: Metadata-only QQ wire details (ADAPTER-01)

**What:** Encode QQ-specific ACK/capability/delivery fields exclusively in `.metadata` dicts on frozen Protocol dataclasses.
**When to use:** Always — never extend Protocol.
**Example:**

```python
# Source: platform_runtime.protocols AckResponse + official op=12
return AckResponse(
    accepted=True,
    status_code=200,
    idempotency_key=idem_key,
    metadata={
        "channel_id": self._config.channel_id,
        "signature_status": "verified",
        "http_callback_ack_body": {"op": 12},
        "ack_tier": "webhook_op12",
        "fixture_only": not live,
        "network_io": False,  # webhook reply is host-local; PUT may flip separately
        # interaction only:
        # "ack_tier": "webhook_op12+interaction_put",
        # "interaction_ack_required": True,
        # "interaction_id": interaction_id,
        # "interaction_ack_body": {"code": 0},
        # "interaction_ack_status": "sent"|"pending_host"|"skipped_fixture",
    },
)
```

### Pattern 2: Live-capable gate (ADAPTER-02)

**What:** Real network only when **all** of: `config.enabled`, injected `token_manager`, injected `transport`.
**When to use:** `deliver`, interaction PUT, optional health probe.
**Example:**

```python
def _live_io_ready(self) -> bool:
    return bool(
        self._config.enabled
        and self._token_manager is not None
        and self._transport is not None
    )
```

Host mapping (document in README; do not hard-couple adapter to `RuntimeFeatureFlags`):

```python
flags = RuntimeFeatureFlags()  # qqbot_channel_enabled defaults False
config = QQBotChannelConfig(enabled=flags.qqbot_channel_enabled, ...)
```

### Pattern 3: Two-tier ACK (INGRESS-06)

**What:**
1. **Tier 1 (all webhook events after verify):** HTTP 200 + response body `{"op": 12}` (HTTP Callback ACK). `[CITED: bot.q.qq.com event-emit.html OpCode 12]`
2. **Tier 2 (`INTERACTION_CREATE` only):** `PUT https://api.sgroup.qq.com/interactions/{interaction_id}` with `Authorization: QQBot {token}` and JSON `{"code": 0}`. `[CITED: bot.q.qq.com msg-btn.html]`

**When to use:** Inside `verify_and_ack` after signature success; detect interaction via gateway envelope `t == "INTERACTION_CREATE"` or `parse_envelope(...).category == INTERACTION`.

**interaction_id source:** Prefer `d.id`, fall back to top-level envelope `id` (already how `normalize_interaction_event` resolves `interaction_id`). `[VERIFIED: normalization.py:374]`

**Phase 66 note:** Feedback-service end-to-end may re-emphasize ACK-after-normalize timing. Phase 65 still implements the PUT mechanism + metadata. Prefer ACK in `verify_and_ack` (stops client loading ASAP). Duplicate PUT may return QQ code 3 (重复操作) — treat as non-fatal in evidence.

### Pattern 4: Transport PUT extension (sender.py)

**What:** Extend qqbot-local transport to support PUT without new deps.
**When to use:** Interaction ACK only.

```python
# Recommended: add optional method on Fake/Urllib transports
async def put_json(
    self, *, url: str, authorization: str, body: dict[str, Any]
) -> dict[str, Any]:
    ...

async def ack_interaction(
    *,
    interaction_id: str,
    token_manager: TokenManager,
    transport: Any,
    code: int = 0,
) -> dict[str, Any]:
    # validate interaction_id with same charset discipline as openids
    token = await token_manager.get_token()
    url = f"https://api.sgroup.qq.com/interactions/{interaction_id}"
    return await transport.put_json(
        url=url,
        authorization=f"QQBot {token}",
        body={"code": code},
    )
```

Do **not** put this in `channel-core`. Do **not** add httpx.

### Anti-Patterns to Avoid

- **Editing frozen Protocol / platform-contract / channel-core:** Violates ADAPTER-04.
- **Hardcoding `network_io=True` when flag off:** Breaks Phase 43 loop CI fixture.
- **Performing PUT when `enabled=False`:** Violates ADAPTER-02.
- **Logging Authorization / access_token / raw button payloads:** Privacy violation.
- **Importing `wecom_service`:** ADAPTER-03.
- **Treating op=12 as a new Protocol status field:** Keep in metadata / HTTP body.
- **Calling Phase 64 ingress from inside adapter Protocol methods:** Keep adapter Protocol-pure; host composes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 verify / op=13 | New crypto | `signature.py` | Already Phase 59 |
| Envelope → AgentTurn/FeedbackEvent | Ad hoc JSON | `normalization.py` | Already Phase 60 |
| Access token | New cache | `TokenManager` | Already Phase 61 |
| Message send / media | New HTTP client | `sender.send_message` / `send_rich_media` | Already Phase 62/63 |
| Output boundary | Custom filters | `channel_core.output_policy` | Shared invariant |
| Session resume | Inside adapter | Phase 64 runtimes (host) | Not a Protocol method |
| Feedback queue | Inside adapter | Phase 66 | Deferred |

**Key insight:** Phase 65 is wiring + ACK completion + metadata honesty, not reimplementation.

## Common Pitfalls

### Pitfall 1: Breaking fixture CI loop
**What goes wrong:** Default adapter starts advertising `network_io=True` or performing PUT without Fake transport.
**Why it happens:** Flipping metadata globally instead of gating on `_live_io_ready()`.
**How to avoid:** Default config remains `enabled=False`; `test_qqbot_channel_loop.py` must stay green with `network_io=False`.
**Warning signs:** Loop test failures on `test_no_network_io_in_loop`.

### Pitfall 2: op=12 body format ambiguity
**What goes wrong:** Host returns empty 200 while QQ expects Callback ACK opcode body (or vice versa).
**Why it happens:** FEATURES.md says “HTTP 200 empty”; STACK.md / community adapters use `{"op": 12}`; official docs define opcode 12 as webhook Reply. `[CITED: event-emit.html]` `[ASSUMED: body {"op":12} is the correct Reply payload]`
**How to avoid:** Always put `http_callback_ack_body={"op": 12}` in metadata; document host must write that JSON on 200 for dispatch events. op=13 challenge remains the signed `{plain_token, signature}` body (already implemented).
**Warning signs:** Webhook registration works (op=13) but events retry / drop.

### Pitfall 3: Wrong interaction_id
**What goes wrong:** PUT uses message id / button_id instead of interaction event id → client hangs.
**Why it happens:** Confusing `d.id` (interaction) with `data.resolved.message_id`.
**How to avoid:** Reuse normalization’s `interaction_id` resolution; unit-test with fixture `INTERACTION_CREATE`.
**Warning signs:** Fake transport PUT URL path ≠ fixture interaction id.

### Pitfall 4: MessageTransport POST-only
**What goes wrong:** Interaction ACK cannot call PUT on existing Protocol.
**Why it happens:** `MessageTransport` currently only defines `post_message`. `[VERIFIED: sender.py:281-291]`
**How to avoid:** Add `put_json` to Fake/Urllib transports + duck-typed helper; keep POST path unchanged.
**Warning signs:** AttributeError in flag-on interaction tests.

### Pitfall 5: Double-meaning of “enabled”
**What goes wrong:** Tests enable `QQBotChannelConfig` but forget platform flag assertions (or vice versa).
**Why it happens:** Two knobs: `RuntimeFeatureFlags.qqbot_channel_enabled` and `QQBotChannelConfig.enabled`.
**How to avoid:** Keep both default False; adapter gates on config; tests assert both; README states host mapping.
**Warning signs:** ADAPTER-02 review finds only one default-OFF check.

### Pitfall 6: Premature feedback-service coupling
**What goes wrong:** Phase 65 imports feedback-service or auto-queues FeedbackEvent.
**Why it happens:** INTERACTION_CREATE normalize already produces FeedbackEvent.
**How to avoid:** Stop at normalize + ACK; Phase 66 owns queue/dedupe/parity.
**Warning signs:** New imports outside qqbot/channel_core/platform_*.

## Code Examples

### Detect interaction for tier-2 ACK

```python
# Source: normalization.parse_envelope + official INTERACTION_CREATE
from .normalization import QQBotEventCategory, parse_envelope

payload = self._payload_from_raw(raw)
if _is_gateway_envelope(payload):
    event = parse_envelope(payload)
    if event.category == QQBotEventCategory.INTERACTION:
        interaction_id = (
            _optional_string(event.data.get("id"))
            or event.event_id
        )
```

### capabilities metadata when live-capable

```python
live = self._live_io_ready()
return ChannelCapabilitySet(
    supports_text=True,
    supports_files=True,
    supports_cards=True,
    supports_images=True,
    supports_voice=False,
    supports_streaming=False,
    ack_deadline_ms=3000,
    idempotency_strategy="qqbot_callback_metadata",
    metadata={
        "enabled": self._config.enabled,
        "fixture_only": not live,
        "network_io": live,
        "ack_strategy": "op12_plus_interaction_put",
        "secret_refs_configured": {...},
    },
)
```

### health without token leak

```python
live = self._live_io_ready()
return ComponentHealth(
    ok=self._config.enabled,
    component_id="qqbot-channel",
    checked_at=_now(),
    detail="qqbot channel enabled" if self._config.enabled else "qqbot channel disabled",
    metadata={
        "fixture_only": not live,
        "network_io": False,  # health itself performs no OpenAPI call by default
        "token_manager_present": self._token_manager is not None,
        "transport_present": self._transport is not None,
        "live_io_ready": live,
        "secret_refs_configured": {...},
    },
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixture-only adapter metadata | Flag-gated live metadata + injectable IO | Phase 65 | ADAPTER-01/02 |
| verify_and_ack: signature only | + op=12 body metadata + interaction PUT | Phase 65 | INGRESS-06 |
| deliver live only if transport injected | Same, plus honest capabilities/health flags | Phase 62–65 | Consistent gate |
| Milestone STACK suggested httpx | Stdlib urllib twin | Phases 61–63 | `dependencies=[]` |

**Deprecated/outdated:**
- Adding `httpx` to qqbot package for ACK/send — superseded.
- Empty-body-only webhook ACK without documenting op=12 Reply payload — prefer `{"op":12}` metadata.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Webhook dispatch ACK response body should be `{"op": 12}` (not empty body) | Pattern 3 / Pitfall 2 | Host may need empty body; keep body in metadata so host can choose, but tests assert key present |
| A2 | Interaction PUT in `verify_and_ack` (eager) is acceptable vs only-after-normalize (Phase 66) | Pattern 3 | If product insists ACK-after-feedback only, Phase 65 emits metadata + helper; host/Phase 66 calls PUT |
| A3 | Extending `MessageTransport` with `put_json` in sender.py is allowed (qqbot-local, not channel-core) | Pattern 4 | Alternative: separate InteractionTransport Protocol in same package |
| A4 | Host maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` outside adapter | Pattern 2 | If a host forgets mapping, “platform flag on” won’t enable adapter — document clearly |
| A5 | `health()` should not call `get_token()` by default (presence-only) | Code Examples | If operators want live token probe, add explicit opt-in metadata flag later |

## Open Questions

1. **Should interaction PUT be mandatory inside `verify_and_ack` when live, or metadata+helper only?**
   - What we know: INGRESS-06 and ROADMAP SC require PUT for button clicks; Phase 66 also mentions ACK after feedback normalize.
   - What's unclear: Exact timing relative to feedback-service.
   - Recommendation: Implement helper + call it from `verify_and_ack` when `_live_io_ready()`; always emit metadata; Phase 66 can no-op if `interaction_ack_status=="sent"`.

2. **Exact HTTP body for non-interaction webhook ACK**
   - What we know: Opcode 12 is HTTP Callback ACK Reply. `[CITED: event-emit.html]`
   - What's unclear: Whether some deployments accept empty 200.
   - Recommendation: Standardize on `{"op": 12}` in metadata; Phase 67 smoke confirms live.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | qqbot package | ✓ | 3.14.6 | — |
| unittest | tests | ✓ | stdlib | — |
| pytest | optional runner | ✓ | 9.1.1 | unittest discovery |
| Network to api.sgroup.qq.com | Live PUT/send | host-dependent | — | FakeMessageTransport in CI |
| QQ app credentials | Live IO | not in repo | — | Fixture path / Fake transports |
| httpx / botpy | — | N/A | — | **Do not use** |

**Missing dependencies with no fallback:** none for CI path.

**Missing dependencies with fallback:** live QQ credentials → Fake transports + flag OFF.

Step 2.6: external live QQ not required for phase execution; CI uses fakes.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib; asyncio.run / IsolatedAsyncioTestCase as existing) |
| Config file | `packages/channels/qqbot/pyproject.toml` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_adapter_two_tier_ack packages.channels.qqbot.tests.test_adapter_real_io packages.channels.qqbot.tests.test_feature_flag -v` |
| Full suite command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADAPTER-01 | All 6 methods work; live metadata when ready | unit | `… test_adapter_real_io` | ❌ Wave 0 |
| ADAPTER-02 | Flag/config default OFF; fixture path no network | unit | `… test_feature_flag` + `test_qqbot_channel_loop` | ✅ extend |
| ADAPTER-03 | No wecom import; no new channel-core modules | unit | `… test_no_wecom_import` + freeze tests | ✅ |
| INGRESS-06 | op=12 metadata; interaction PUT with Fake | unit | `… test_adapter_two_tier_ack` | ❌ Wave 0 |
| ADAPTER-04 | Protocol still 6 methods; deps=[] | unit | `… test_contract_freeze_not_violated` + `test_v1_8_safety_baseline` | ✅ |

### Sampling Rate

- **Per task commit:** quick run command
- **Per wave merge:** full qqbot suite
- **Phase gate:** full qqbot suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/channels/qqbot/tests/test_adapter_two_tier_ack.py` — covers INGRESS-06
- [ ] `packages/channels/qqbot/tests/test_adapter_real_io.py` — covers ADAPTER-01 flag-on Fake paths for capabilities/verify/normalize/deliver/health
- [ ] Extend assertions in `test_feature_flag.py` / loop tests so flag-off path remains `network_io=False`
- [ ] Extend `FakeMessageTransport` tests for `put_json` once added

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Ed25519 callback verify; TokenManager bearer for PUT/send; never log token |
| V3 Session Management | no | N/A at adapter Protocol layer |
| V4 Access Control | partial | Host allowlist api.sgroup.qq.com; openid/interaction_id charset validation |
| V5 Input Validation | yes | Structured envelope parse; reject missing signatures with 401 |
| V6 Cryptography | no new | Reuse Phase 59 Ed25519 only |

### Known Threat Patterns for adapter real IO

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed webhook | Spoofing | Existing Ed25519 verify; 401 on failure |
| Token leak in Ack/Delivery metadata | Information Disclosure | Never put Authorization/access_token in metadata; sanitize errors |
| Interaction id injection in URL path | Tampering | Validate id charset before path interpolate (mirror `_OPENID_RE`) |
| Accidental live calls in CI | Elevation / Abuse | Default flag OFF; require explicit transport injection |
| Raw legal / button payload retention | Information Disclosure | Keep refs only; fixture_only path unchanged |
| wecom_service coupling | — | AST import ban |

## Sources

### Primary (HIGH confidence)

- [Official QQ event opcodes](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html) — op=12 HTTP Callback ACK, op=13 validation
- [Official QQ message buttons / interaction ACK](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/trans/msg-btn.html) — `PUT /interactions/{interaction_id}` `{code:0..5}`
- `packages/platform-runtime/src/platform_runtime/protocols.py` — frozen ChannelAdapter + metadata dataclasses
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — current 6-method implementation
- Phases 59–64 RESEARCH/code — signature, normalization, token, sender, session/ingress
- `.planning/REQUIREMENTS.md` / `ROADMAP.md` — ADAPTER-01/02/03, INGRESS-06 success criteria

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` — two-tier ACK product note (empty-body vs op=12 tension → A1)
- `.planning/research/STACK.md` / `SUMMARY.md` — Phase 65 wiring intent; httpx superseded
- Community Hermes qqbot adapter — confirms PUT `/interactions/{id}` with `{"code": 0}`

### Tertiary (LOW confidence)

- Whether empty HTTP 200 without `{"op":12}` is accepted by all QQ webhook deployments — validate in Phase 67

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; reuse verified Phases 59–63
- Architecture: HIGH — Protocol + official ACK docs + existing adapter seams
- Pitfalls: HIGH — fixture CI + transport PUT gap + flag dual-knob verified in-repo

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days; QQ docs stable, integration-focused)
