# Phase 62: QQ Egress Sender — Text + Markdown + Keyboard - Research

**Researched:** 2026-07-09
**Domain:** QQ Bot OpenAPI egress (text / markdown / keyboard), passive-reply windows, output boundary
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from ROADMAP / ADAPTER-04:
- Reuse Phase 61 `TokenManager` for Authorization bearer tokens
- Keep `dependencies = []` (stdlib urllib + asyncio.to_thread)
- No `wecom_service` imports (`test_no_wecom_import.py` must pass)
- Do not modify frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, or channel-core modules
- QQ-specific behavior via `ChannelDelivery.metadata` / capability metadata only
- Output boundary: filter/rewrite/drop backend gateway/system/meta notices before user delivery
- Passive-reply windows: C2C 60min/4, group 5min/5 per `msg_id`; expiry → delivery failure + InkStatute-owned interim service notice
- Feedback card buttons: up / down / needs_fix / route_wrong
- `adapter.py` `deliver()` wires the new sender

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. Rich media (EGRESS-05/06) is Phase 63.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EGRESS-02 | Text `msg_type=0` via OpenAPI with `msg_id`+`msg_seq` dedupe, retry on transient failure, output boundary | `build_text_envelope` + `send_message` + `MessageTransport` retry map; `apply_output_policy` before content attach |
| EGRESS-03 | Markdown+keyboard feedback cards (`msg_type=2` + `keyboard`); `delivery_type=="card"` → QQ keyboard (not WeCom `template_card`) | `build_feedback_keyboard_envelope` with callback buttons `up`/`down`/`needs_fix`/`route_wrong` |
| EGRESS-04 | Passive-reply window C2C 60min/4, group 5min/5 per `msg_id`; expiry → delivery failure + interim owned notice | `PassiveReplyWindow` / `check_passive_reply_window`; `issue_code=qqbot_passive_reply_window_expired` + `build_owned_notice` |
| EGRESS-07 | Markdown replies (`msg_type=2`) for structured legal answers with output boundary | `build_markdown_envelope`; policy on markdown content |
</phase_requirements>

## Summary

Phase 62 adds `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` as the QQ-native egress layer: policy-checked envelope builders for text (`msg_type=0`), markdown (`msg_type=2`), and markdown+keyboard feedback cards (`msg_type=2` + `keyboard`), plus an injectable HTTP transport that POSTs to QQ OpenAPI with `TokenManager` bearer tokens, `msg_id`+`msg_seq` passive-reply fields, transient retry, and pre-send passive-window enforcement. `QQBotChannelAdapter.deliver()` must stop using placeholder `msg_type: "text"|"card"` stubs and route through these builders (WeCom-analog separation of concerns, without importing `wecom_service`).

Official QQ docs confirm C2C `/v2/users/{openid}/messages` and group `/v2/groups/{group_openid}/messages`, Authorization `QQBot {token}`, and server-side rejection of duplicate `msg_id`+`msg_seq`. Keyboard must nest under `keyboard.content.rows` with `action.type=1` callback buttons; markdown content is required when attaching a keyboard. Locked CONTEXT windows (C2C 60min/4, group 5min/5) match the 2026-01-10 capability update; an older paragraph on the same page still says C2C “5 times” — honor CONTEXT/REQUIREMENTS (4).

**Primary recommendation:** Implement `sender.py` with WeCom-style envelope builders + Phase-61-style `MessageTransport`/`FakeMessageTransport`/`UrllibMessageTransport`, wire `adapter.deliver()` to them, keep live POST behind injectable transport + `enabled` (default fixture path remains no network), and enforce windows/policy before any send.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Output boundary (block/rewrite/allow) | API / Backend (channel package) | channel-core library | Shared `apply_output_policy` already used by QQ adapter; must run before envelope content attach |
| QQ send envelope construction | API / Backend (`sender.py`) | — | Channel-local payload shapes; no Protocol change |
| Access token for Authorization | API / Backend (`TokenManager`) | — | Phase 61; sender calls `get_token()` only |
| HTTP POST to QQ OpenAPI | API / Backend (`MessageTransport`) | — | Stdlib urllib + `asyncio.to_thread`; injectable for tests |
| Passive-reply window tracking | API / Backend (`sender.py`) | Host/session (Phase 64+) | Per-`msg_id` count + `received_at` check before send; host later owns durable seq |
| `ChannelAdapter.deliver()` routing | API / Backend (`adapter.py`) | — | Frozen Protocol method; metadata-only QQ specifics |
| Feedback button round-trip | API / Backend (egress keyboard + existing ingress) | feedback-service (later) | Egress emits `action.data`; Phase 60 already normalizes `INTERACTION_CREATE` |
| Rich media upload | Deferred (Phase 63) | — | Out of scope |

## Project Constraints (from AGENTS.md)

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- Assistant output boundary: filter/rewrite/drop backend-originated meta/system/gateway notices before ordinary user delivery. `[VERIFIED: AGENTS.md]`
- Keep changes scoped to the active GSD phase; do not introduce new services/DBs/queues unless required. `[VERIFIED: AGENTS.md]`
- Prefer structured parsers/validators over ad hoc string parsing. `[VERIFIED: AGENTS.md]`
- `dependencies = []` for qqbot package; no `wecom_service` imports. `[VERIFIED: packages/channels/qqbot/pyproject.toml, test_no_wecom_import.py]`
- Frozen ChannelAdapter / BackendAdapter / platform-contract / channel-core must not be modified. `[VERIFIED: ROADMAP]`

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `urllib.request` + `urllib.error` | 3.11+ (env has 3.14.6) | HTTPS POST to QQ OpenAPI | Same as Phase 61 `UrllibTokenTransport`; preserves `dependencies = []` `[VERIFIED: token_manager.py]` |
| `asyncio.to_thread` | stdlib 3.11+ | Non-blocking urllib | Proven in TokenManager `[VERIFIED: token_manager.py:75]` |
| `asyncio` | stdlib | Async `send_message` / adapter `deliver` | Existing adapter is async `[VERIFIED: adapter.py]` |
| `json` | stdlib | Request/response bodies | TokenManager precedent |
| `channel_core.output_policy` | in-repo | Output boundary | Already imported by QQ adapter `[VERIFIED: adapter.py:11]` |
| `channel_core.owned_notices` | in-repo | Interim service notices on window expiry | Templates for `long_processing` / `status_running` / `failed` `[VERIFIED: owned_notices.py]` |
| Phase 61 `TokenManager` | in-repo | `Authorization: QQBot {token}` | Required by ROADMAP; `get_token()` + `invalidate()` on 401 `[VERIFIED: token_manager.py]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.IsolatedAsyncioTestCase` | stdlib | Async sender/window/retry tests | Same as `test_token_manager.py` |
| `time.monotonic` (injectable clock) | stdlib | Window expiry tests | Same clock-injection pattern as TokenManager |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib urllib + to_thread | `httpx` optional extra | Earlier research floated httpx for egress; **rejected for Phase 62** — hard constraint `dependencies = []` and Phase 61 already solved async HTTP without it `[VERIFIED: 61-RESEARCH.md, CONTEXT]` |
| WeCom `template_card` | QQ keyboard | Forbidden — QQ has no template_card; EGRESS-03 requires keyboard `[CITED: bot.q.qq.com msg-btn.html]` |
| ARK `msg_type=3` for cards | markdown+keyboard `msg_type=2` | ARK needs templates/permissions; keyboard is the documented feedback primitive and matches REQUIREMENTS |

**Installation:** none — no new packages.

**Version verification:** No third-party packages. Python `>=3.11` already required by `packages/channels/qqbot/pyproject.toml`. `[VERIFIED: pyproject.toml]`

## Package Legitimacy Audit

> Phase installs **no** external packages (`dependencies = []` preserved).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 was available; no candidate packages to audit.*

## Architecture Patterns

### System Architecture Diagram

```text
ChannelDelivery (metadata: delivery_type, scene, user_openid,
                 group_openid, msg_id, msg_seq, received_at,
                 feedback_target, reply_count)
        │
        ▼
QQBotChannelAdapter.deliver()
        │
        ├─► apply_output_policy(content)          [channel_core]
        │         │
        │         ├─ block  → DeliveryResult(accepted=False, policy_action=block)
        │         └─ allow/rewrite → visible_text
        │
        ├─► check_passive_reply_window(scene, received_at, reply_count)
        │         │
        │         └─ expired → DeliveryResult(accepted=False,
        │                issue_code=qqbot_passive_reply_window_expired,
        │                interim_notice=build_owned_notice(...))
        │
        ├─► sender.build_*_envelope(...)
        │         │
        │         ├─ text     → msg_type=0, content, msg_id, msg_seq
        │         ├─ markdown → msg_type=2, markdown.content, msg_id, msg_seq
        │         └─ card     → msg_type=2, markdown + keyboard.content.rows
        │
        └─► (optional live path) sender.send_message(envelope, scene, openids,
                    token_manager, transport)
                  │
                  ├─ TokenManager.get_token()
                  ├─ POST https://api.sgroup.qq.com/v2/users|{groups}/.../messages
                  │     Authorization: QQBot {token}
                  ├─ transient fail → retry with backoff; 401 → invalidate + once once
                  └─ terminal (304027/304026/22009/…) → SendError / accepted=False
```

### Recommended Project Structure

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── sender.py              # NEW — envelopes, window, transport, send+retry
├── token_manager.py       # REUSE — Authorization bearer
├── adapter.py             # MODIFY — deliver() routes to sender
├── normalization.py       # REUSE — inbound message_id/scene for metadata contract
└── ...

packages/channels/qqbot/tests/
├── test_sender.py         # NEW — envelopes, window, retry, keyboard shape
├── test_qqbot_channel_adapter.py  # UPDATE — expect msg_type int + keyboard
└── test_no_wecom_import.py         # UPDATE — AST-scan sender.py
```

### Pattern 1: Envelope builders (WeCom analog, QQ payloads)

**What:** Pure functions that run `apply_output_policy` then attach QQ OpenAPI fields. No network I/O.
**When to use:** Always from `adapter.deliver()` before optional send.
**Example:**

```python
# Analog structure from wecom_service/sender.py — DO NOT import wecom_service.
# QQ shapes from https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html

def build_text_envelope(*, content: str, msg_id: str, msg_seq: int = 1) -> dict:
    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        envelope.update({"msg_type": 0, "content": decision.visible_text})
    return envelope

def build_markdown_envelope(*, content: str, msg_id: str, msg_seq: int = 1) -> dict:
    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        envelope.update({
            "msg_type": 2,
            "markdown": {"content": decision.visible_text},
        })
    return envelope
```

### Pattern 2: Transport injection (TokenManager twin)

**What:** `MessageTransport` Protocol + `FakeMessageTransport` + `UrllibMessageTransport` (lazy urllib inside method + `asyncio.to_thread`).
**When to use:** All live OpenAPI POSTs; tests never touch network.

```python
class MessageTransport(Protocol):
    async def post_message(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...
```

### Pattern 3: Passive-reply window gate

**What:** Pure check before send using scene limits from locked CONTEXT.
**When to use:** Every passive reply (`msg_id` present).

| Scene | Max age | Max replies per `msg_id` |
|-------|---------|--------------------------|
| `c2c` | 60 minutes | 4 |
| `group` | 5 minutes | 5 |

On fail: `accepted=False`, `metadata.issue_code = "qqbot_passive_reply_window_expired"`, `metadata.interim_notice = build_owned_notice("long_processing", seed=msg_id)` (or `status_running`). Do **not** silently drop. Do **not** implement `is_wakeup` here (RECALL-01 / later phase).

### Anti-Patterns to Avoid

- **Copying WeCom `template_card`:** QQ returns parameter errors; breaks feedback loop. `[CITED: PITFALLS.md Pitfall 4]`
- **`keyboard.rows` without `content` wrapper:** Official schema is `keyboard.content.rows`. `[CITED: bot.q.qq.com/wiki/.../msg-btn.html]`
- **Keyboard-only message:** Docs require markdown content when mounting buttons. `[CITED: msg-btn.html]`
- **Logging Authorization / access_token:** Token must never enter `DeliveryResult.metadata` or errors. `[CITED: PITFALLS.md Pitfall 6]`
- **Conflating ACK 3s with passive-reply window:** `ack_deadline_ms=3000` is webhook ACK only. `[VERIFIED: adapter.py capabilities]`
- **Importing `wecom_service` for “parity”:** Analog only; AST test will fail. `[VERIFIED: test_no_wecom_import.py]`
- **Modifying frozen protocols/schemas:** Encode QQ fields in `ChannelDelivery.metadata` only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Output boundary regexes | Custom QQ filter | `channel_core.output_policy.apply_output_policy` | Shared, tested, already wired in adapter |
| User-facing interim copy | Ad hoc Chinese strings | `channel_core.owned_notices.build_owned_notice` | Seeded, privacy-safe templates |
| Async HTTPS client | New httpx/aiohttp dep | `Urllib*Transport` + `asyncio.to_thread` | `dependencies = []` invariant |
| Token cache/refresh | Second token client | Phase 61 `TokenManager` | Single-flight + 60s margin already proven |
| Feedback action vocabulary | New button ids | Canonical `{up, down, needs_fix, route_wrong}` | Matches Phase 60 normalization |

**Key insight:** Phase 62 is payload + window + window discipline — not a new policy engine or HTTP stack.

## Common Pitfalls

### Pitfall 1: Ignoring passive-reply window (silent 304027)
**What goes wrong:** Long legal tasks exceed group 5min; API returns `304027 MSG_EXPIRE`; user sees nothing.
**Why it happens:** WeCom has no hard reply deadline.
**How to avoid:** Pre-check window; fail with `qqbot_passive_reply_window_expired` + interim owned notice.
**Warning signs:** No window unit test; production logs show 304027 swallowed.

### Pitfall 2: WeCom template_card for QQ cards
**What goes wrong:** 400 / feedback loop broken.
**How to avoid:** `delivery_type=="card"` → `msg_type=2` + keyboard; assert no `template_card` key in tests.

### Pitfall 3: Wrong keyboard nesting / action type
**What goes wrong:** Buttons never fire `INTERACTION_CREATE`, or API rejects payload (`304037`–`304040`).
**How to avoid:** Use `keyboard: {"content": {"rows": [...]}}`, `action.type=1`, `action.data` in canonical set, `permission.type=2` (everyone) for C2C/group feedback unless product requires otherwise.
**Warning signs:** Envelope has top-level `rows`; `action.type=2` (command) instead of callback.

### Pitfall 4: Duplicate `msg_id`+`msg_seq`
**What goes wrong:** Second send with same pair fails (platform dedupe).
**How to avoid:** Default `msg_seq=1`; accept caller-supplied seq from metadata; document that host/session increments for multi-part replies. Sender may optionally track in-memory seq for a single process, but durable seq is Phase 64 concern — for Phase 62, require `msg_seq` in metadata (default 1) and do not reuse the same pair on retry of a *successful* send (retries of the same attempt may reuse the same seq only if the first attempt had no confirmed success — prefer idempotent retry of the same body).

### Pitfall 5: Token / secret leakage in SendError or DeliveryResult
**What goes wrong:** Bearer token lands in CI artifacts.
**How to avoid:** Sanitize errors like `TokenError`; never put token in metadata; redact Authorization in any debug fields.

### Pitfall 6: Breaking existing fixture tests
**What goes wrong:** `test_qqbot_channel_adapter` / channel loop expect old `msg_type: "text"|"card"` strings.
**How to avoid:** Update assertions to integer `msg_type` and keyboard presence; keep `fixture_only` / `network_io=False` defaults when no transport injected.

### Pitfall 7: C2C reply-count doc conflict
**What goes wrong:** Implementing 5 C2C replies when CONTEXT locks 4 (post–`is_wakeup` adjustment).
**How to avoid:** Use **4** for C2C per CONTEXT/REQUIREMENTS/2026-01-10 update note; treat older “5次” paragraph as stale. `[CITED: send.html 2026/01/10 update vs older 单聊 bullet]`

## Code Examples

### Text send body (C2C)

```json
{
  "content": "根据《民法典》……",
  "msg_type": 0,
  "msg_id": "inbound-message-id",
  "msg_seq": 1
}
```

Source: [QQ send message API](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html)

### Markdown + keyboard feedback card

```python
# Keyboard shape from official msg-btn docs (content.rows nesting).
FEEDBACK_ACTIONS = ("up", "down", "needs_fix", "route_wrong")
LABELS = {
    "up": "有帮助",
    "down": "需改进",
    "needs_fix": "需要修正",
    "route_wrong": "路由错误",
}

def build_feedback_keyboard_envelope(
    *, title: str, feedback_target: str, msg_id: str, msg_seq: int = 1
) -> dict:
    decision = apply_output_policy(title)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action == "block":
        return envelope
    visible = decision.visible_text or "请评价本次回复"
    buttons = []
    for action in FEEDBACK_ACTIONS:
        buttons.append({
            "id": action,
            "render_data": {
                "label": LABELS[action],
                "visited_label": LABELS[action],
                "style": 1,
            },
            "action": {
                "type": 1,  # callback → INTERACTION_CREATE
                "permission": {"type": 2},  # everyone
                "data": action,
                "unsupport_tips": "请升级 QQ 后重试",
            },
        })
    envelope.update({
        "msg_type": 2,
        "markdown": {"content": visible},
        "keyboard": {"content": {"rows": [{"buttons": buttons}]}},
        # feedback_target is InkStatute correlation — keep in policy/audit metadata,
        # not as a WeCom template_card field. Optionally embed in markdown footer.
        "inkstatute": {"feedback_target": feedback_target},
    })
    return envelope
```

**Planner note:** Strip non-API keys (`policy`, `inkstatute`) before POST — keep them only on the DeliveryResult envelope copy for tests/audit. Production body sent to QQ must contain only documented fields.

### Endpoints + auth

| Scene | Method | URL |
|-------|--------|-----|
| C2C | POST | `https://api.sgroup.qq.com/v2/users/{user_openid}/messages` |
| Group | POST | `https://api.sgroup.qq.com/v2/groups/{group_openid}/messages` |

Header: `Authorization: QQBot {access_token}`, `Content-Type: application/json`.
`[CITED: bot.q.qq.com api-use.html + send.html; 61-RESEARCH.md]`

### Retry classification (prescriptive for Phase 62)

| Condition | Class | Action |
|-----------|-------|--------|
| HTTP 429, 500, 504; URLError/timeout; body codes in `504000–504999`; `11242`/`11252`/`11263` (retry-once system) | Transient | Retry with bounded backoff (e.g. 3 attempts, exponential 0.05–0.5s injectable) |
| HTTP 401 | Auth | `token_manager.invalidate()`; refresh once; if still 401 → terminal |
| `304027` MSG_EXPIRE, `304026` MSG_ID, `22009` msg limit, `50006` empty, `304003` URL | Terminal | No retry; map to delivery failure |
| Duplicate msg_id+msg_seq failure | Terminal (idempotent) | Treat as non-retryable for a *new* attempt; same-attempt retry OK only if prior attempt unconfirmed |

`[CITED: bot.q.qq.com/wiki/develop/api-v2/openapi/error/error.html]` — exact duplicate-pair error code not uniquely documented; tests should assert FakeTransport records one successful body per seq.

### Metadata contract for `ChannelDelivery` (no Protocol change)

| Key | Required for | Notes |
|-----|--------------|-------|
| `delivery_type` | routing | `text` (default), `markdown`, `card` (aliases: `message_type`/`kind`) |
| `scene` | window + URL | `c2c` \| `group` (from inbound `AgentTurn.metadata.scene`) |
| `user_openid` | C2C URL | Inbound author openid |
| `group_openid` | group URL | Inbound `group_openid` |
| `msg_id` | passive reply | Prefer inbound `message_id`; alias `msg_id` |
| `msg_seq` | dedupe | int, default `1` |
| `received_at` | window | ISO-8601 from inbound `received_at` |
| `reply_count` | window | Prior successful replies for this `msg_id` (0-based before this send); default `0` |
| `feedback_target` | card | Or `delivery.result.feedback_target` |
| `idempotency_key` | outbound audit | Optional; separate from platform msg_seq |

### `adapter.deliver()` wiring (prescriptive)

1. Resolve `delivery_type` / text like WeCom helpers (`_delivery_type`, `_delivery_text`) — copy pattern into qqbot adapter, do not import wecom.
2. Resolve `msg_id` from `metadata.msg_id` or `metadata.message_id`.
3. Run window check when `msg_id` present.
4. Build envelope via sender builders.
5. If `policy.action == "block"` or channel disabled → `accepted=False`.
6. If `self._transport` is set and `enabled` → `send_message(...)`; else keep `network_io=False` fixture path with envelope in metadata (CI-safe default).
7. Return `DeliveryResult` with `envelope`, `policy_*`, `issue_code` (if any), never tokens.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixture `msg_type: "text"/"card"` strings | Integer `msg_type` 0/2 + keyboard | Phase 62 | Matches OpenAPI |
| Envelope-only WeCom channel package | QQ adds optional live POST via transport | Phase 62 | Still default-OFF / injectable |
| C2C passive 5 replies | C2C 4 replies after wakeup feature | 2026-01-10 | Align with CONTEXT (4) |
| Active push unrestricted | Active push heavily limited / historically disabled | 2025–2026 docs | Phase 62 stays on passive `msg_id` replies; wakeup deferred |

**Deprecated/outdated:**
- Treating QQ cards as WeCom `template_card`
- Assuming no passive-reply deadline
- Adding `httpx` for this phase under `dependencies = []`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Stripping `policy`/`inkstatute` keys before POST is required and safe | Code Examples | If host expects those keys on the wire, API may reject — keep dual envelope (audit vs wire) |
| A2 | `permission.type=2` (everyone) is acceptable for feedback buttons in C2C/group | Code Examples | May need specify_user_ids for C2C-only clickers — adjust if product requires |
| A3 | In-memory / metadata `reply_count` from caller is sufficient for Phase 62 (durable tracker in Phase 64) | Pattern 3 | Under-count could allow over-limit sends until platform rejects |
| A4 | Group markdown sends include top-level `content=""` companion alongside `markdown.content` (Q1 resolved) | Open Questions (RESOLVED) | Empty companion satisfies group API required-`content` row without duplicating visible text |
| A5 | Interim notice on window expiry is returned in `DeliveryResult.metadata` for the host to surface; Phase 62 does not require a successful active/wakeup send | EGRESS-04 | If product expects an immediate user-visible QQ message on expiry, need active/wakeup path (out of scope / limited) |

## Open Questions (RESOLVED)

1. **Group `content` required vs markdown-only** — **RESOLVED: `content=""`**
   - What we know: Group request table lists `content` as required; markdown uses `markdown.content`. `[CITED: send.html]`
   - Resolution (Plan 01): `build_markdown_envelope` sets top-level `content=""` (empty string) alongside `markdown.content` so the group required-`content` field is present without a second visible body. Wire-shape unit tests lock this companion field.

2. **Where durable `msg_seq` / `reply_count` live** — **RESOLVED: metadata / process-local only (no durable store)**
   - What we know: Platform dedupes on pair; CONTEXT requires tracking.
   - Resolution (Plan 02 / A3): Phase 62 accepts `reply_count` (and related window inputs) via caller metadata and optional process-local A3 tracker keyed by `msg_id`. No durable store in this phase; Phase 64 session runtime owns durable tracking.

3. **Exact error body for duplicate `msg_id`+`msg_seq`** — **RESOLVED: terminal `304026`**
   - What we know: Docs say duplicate send fails; `304026` is MSG_ID error.
   - Resolution (Plan 02): Treat QQ body/code `304026` (with `304027` / `22009` / `50006` / `304003`) as terminal — no retry; cover with FakeMessageTransport.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | qqbot package | ✓ | 3.14.6 | — |
| `asyncio.to_thread` | Urllib transports | ✓ | stdlib | — |
| Network to `api.sgroup.qq.com` | Live send | N/A in CI | — | FakeMessageTransport (required for tests) |
| QQ app credentials | Live send | Host-injected | — | Fixture path when `enabled=False` / no transport |

**Missing dependencies with no fallback:** none for planned CI path.

**Missing dependencies with fallback:** live QQ network — FakeMessageTransport.

Step 2.6: external tools beyond stdlib Python are not required for implementation/tests.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib) + `IsolatedAsyncioTestCase` |
| Config file | `packages/channels/qqbot/pyproject.toml` |
| Quick run command | `python3 -m unittest packages.channels.qqbot.tests.test_sender -v` |
| Full suite command | `python3 -m unittest discover -s packages/channels/qqbot/tests -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EGRESS-02 | Text envelope `msg_type==0` + msg_id/msg_seq; retry on transient | unit | `python3 -m unittest packages.channels.qqbot.tests.test_sender -v` | ❌ Wave 0 |
| EGRESS-02 | Output policy blocks gateway/system notices on text | unit | same + adapter delivery test | ⚠️ partial (adapter exists; update for new shapes) |
| EGRESS-03 | Card → keyboard with four callback actions; no template_card | unit | `test_sender` keyboard assertions | ❌ Wave 0 |
| EGRESS-04 | C2C/group window expiry → issue_code + interim_notice | unit | `test_sender` window tests | ❌ Wave 0 |
| EGRESS-07 | Markdown envelope `msg_type==2` + policy on content | unit | `test_sender` markdown tests | ❌ Wave 0 |
| ADAPTER | `deliver()` uses sender builders | unit | `test_qqbot_channel_adapter` update | ✅ update |
| Safety | `sender.py` no wecom import; `dependencies = []` | unit | `test_no_wecom_import` + safety baseline | ✅ extend |

### Sampling Rate

- **Per task commit:** `python3 -m unittest packages.channels.qqbot.tests.test_sender -v`
- **Per wave merge:** full qqbot discover suite
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/channels/qqbot/tests/test_sender.py` — envelopes, keyboard shape, window, retry, policy
- [ ] Extend `test_no_wecom_import.py` for `sender.py`
- [ ] Update `test_qqbot_channel_adapter.py` / `test_qqbot_channel_loop.py` for integer `msg_type` + keyboard

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `TokenManager` + `Authorization: QQBot …`; never log token |
| V3 Session Management | no | N/A for this phase |
| V4 Access Control | partial | Channel `enabled` default-OFF; feedback button permission field |
| V5 Input Validation | yes | Structured metadata reads; policy on outbound text/markdown |
| V6 Cryptography | no new | Ed25519 already Phase 59; no new crypto in sender |

### Known Threat Patterns for QQ egress

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token leakage in logs/metadata | Information Disclosure | Sanitized `SendError`; no token in DeliveryResult |
| Backend gateway notice leak to lawyers | Information Disclosure | `apply_output_policy` before attach |
| Forged feedback button data | Tampering | Inbound signature already Phase 59; egress only emits canonical actions |
| Over-window silent failure | Denial of Service / spoofed availability | Explicit window failure + owned notice |
| SSRF via custom URL | Tampering | Hardcode `api.sgroup.qq.com` base in UrllibMessageTransport |

## WeCom Analog Map (import-forbidden)

| WeCom (inspiration only) | QQ Phase 62 |
|--------------------------|-------------|
| `wecom_service/sender.py` builders | `inkstatute_channels_qqbot/sender.py` |
| `msgtype: text` | `msg_type: 0` |
| `msgtype: template_card` | `msg_type: 2` + `keyboard` |
| (no markdown) | `msg_type: 2` markdown |
| `apply_output_policy` via wecom shim | Direct `channel_core.output_policy` |
| Adapter `deliver()` routes by `delivery_type` | Same routing pattern in qqbot adapter |
| No live HTTP in wecom channel package | Optional injectable POST (QQ-specific need) |

## Sources

### Primary (HIGH confidence)

- [QQ send message](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html) — endpoints, msg_type, msg_id/msg_seq, passive windows, 2026-01-10 C2C 4-reply update
- [QQ message buttons](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/trans/msg-btn.html) — keyboard.content.rows, action.type=1 callback
- [QQ markdown](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/markdown.html) — `markdown.content`
- [QQ OpenAPI errors](https://bot.q.qq.com/wiki/develop/api-v2/openapi/error/error.html) — 304026/304027/22009/429/504xxx
- Phase 61 `token_manager.py` + `61-RESEARCH.md` — transport injection + Authorization header
- `channel_core/output_policy.py`, `owned_notices.py` — boundary + interim notices
- `wecom_service/sender.py`, `inkstatute_channels_wecom/adapter.py` — structural analogs only
- `.planning/REQUIREMENTS.md`, `ROADMAP.md`, `62-CONTEXT.md`, `research/PITFALLS.md`, `research/STACK.md`

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — milestone architecture and pitfall framing (pre-phase; verify against live docs above)

### Tertiary (LOW confidence)

- Exact wire error code for duplicate msg_seq — documented behaviorally, not as a unique code in error table

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked stdlib + existing TokenManager/channel_core
- Architecture: HIGH — WeCom builder split + Phase 61 transport proven in-repo; QQ payloads from official docs
- Pitfalls: HIGH — PITFALLS.md + official window/keyboard/error docs cross-checked
- C2C reply count: MEDIUM — CONTEXT locks 4; older doc paragraph still says 5

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (QQ Bot API docs move frequently)
