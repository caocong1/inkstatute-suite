# Stack Research: v1.8 QQBot Channel Production

**Domain:** QQ Bot platform ingress/egress, feedback cards, runtime session continuity, one-click smoke-test toolkit
**Researched:** 2026-07-07
**Confidence:** HIGH

## Architectural Constraints (Carried from v1.6/v1.7)

Every existing package and service declares `dependencies = []` in `pyproject.toml`. No package uses FastAPI, aiohttp, uvicorn, SQLAlchemy, or any third-party runtime library at import time. The WeCom service (`services/wecom-service`) implements signature verification, message normalization, and envelope building in **pure Python stdlib** (`hashlib`, `hmac`, `xml.etree.ElementTree`) — it does NOT use a WeCom SDK. Channel/backend adapters wrap "sanitized primitives" with `network_io: False` metadata. The AGENTS rule is explicit: *"Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it."*

**v1.8 strategy:** New runtime dependencies are added ONLY as optional extras (`[project.optional-dependencies]`), imported lazily inside method bodies, so packages remain importable with `dependencies = []` in CI and contract tests. This mirrors the existing `provider_model` adapter pattern (lazy `AsyncOpenAI` import inside `openai_runner.py:398`) and the `ollama_runner.py` pattern (lazy `urllib.request` import). The contract freeze (`packages/platform-contract/`), frozen Protocols (`ChannelAdapter` 6 methods, `BackendAdapter` 9 methods), and feature-flag-default-OFF strategy are preserved. The `channel-core` package (already extracted in v1.6) is reused as-is — no changes.

---

## QQ Bot Platform API v2 — Key Characteristics

Researched from official docs at `bot.q.qq.com/wiki/develop/api-v2/`:

| Aspect | QQ Bot API v2 | WeCom (reference) |
|--------|---------------|-------------------|
| **Payload format** | JSON (`{id, op, d, s, t}`) | XML (callback) + JSON (API) |
| **Signature algorithm** | Ed25519 (NOT in Python stdlib) | SHA1 sort + HMAC (stdlib `hashlib`/`hmac`) |
| **Auth** | AppID + AppSecret → AccessToken (7200s TTL), header `Authorization: QQBot {token}` | CorpID + secret → access_token |
| **Receive mode** | Webhook (HTTPS callback) OR WebSocket (mutually exclusive) | Webhook (HTTP callback) |
| **Message types** | 0=text, 2=markdown, 3=ark, 4=embed, 7=media | text, image, file, template_card |
| **Card format** | ARK message (`template_id` + `kv` pairs) or Keyboard (button grid) | template_card |
| **Feedback mechanism** | Keyboard callback button → `INTERACTION_CREATE` event (intents `1<<26`) | template_card button callback |
| **Interaction ACK** | POST `/interactions/{interaction_id}` | ACK body `"success"` |
| **Rich media** | Upload to `/v2/users/{openid}/files` → `file_info` → send `msg_type=7` | media_id → send `msgtype=file` |
| **Rate limits** | 60 qpm verified / 30 qpm unverified; passive reply 5×/60min (C2C), 5×/5min (group) | Per-app limits |
| **Callback URL validation** | OpCode 13: sign `event_ts + plain_token` with Ed25519 private key | Echo `echostr` after signature check |
| **API base URL** | `https://api.sgroup.qq.com` | `https://qyapi.weixin.qq.com/cgi-bin` |
| **Token endpoint** | `https://bots.qq.com/app/getAppAccessToken` (POST) | `https://qyapi.weixin.qq.com/cgi-bin/gettoken` (GET) |

### Ed25519 Signature Verification Flow (QQ Bot specific)

1. **Seed derivation**: Repeat `botSecret` string until ≥32 bytes, take first 32 bytes as Ed25519 seed.
2. **Key generation**: `ed25519.GenerateKey(seed[:32])` → public key + private key.
3. **Webhook event verification**: `ed25519.Verify(publicKey, timestamp + raw_body, signature)` where `timestamp` = `X-Signature-Timestamp` header, `signature` = hex-decoded `X-Signature-Ed25519` header.
4. **Callback URL validation** (op=13): `ed25519.Sign(privateKey, event_ts + plain_token)` → return `{"plain_token": ..., "signature": hex_signature}`.

Python stdlib does NOT include Ed25519. This is the one mandatory new dependency.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `cryptography` (pyca/cryptography) | 49.0.0 (Jun 2026) | Ed25519 signature verification for QQ Bot webhook callbacks + callback URL validation signing | The official QQ Bot docs specify Ed25519 for webhook signature verification (`X-Signature-Ed25519` + `X-Signature-Timestamp` headers). Python stdlib has NO Ed25519 support. `cryptography` is the de facto Python crypto standard (7.7K GitHub stars, Apache-2.0/BSD-3-Clause, Python 3.9+, production-stable). Provides `Ed25519PrivateKey.from_private_bytes(seed)` and `Ed25519PublicKey.verify(signature, data)`. Already a transitive dependency of `httpx` (via `openai` SDK used in `provider_model` adapter), so likely already installed in dev environments. |
| `httpx` | 0.28.1 (latest stable) | Async HTTP client for QQ Bot OpenAPI calls (AccessToken acquisition, message send, rich media upload, interaction ACK) | QQ Bot API v2 is a REST API over HTTPS. `httpx` provides native `asyncio` support (`AsyncClient`), connection pooling, timeout control, and JSON response handling. Already a transitive dependency of the `openai` Python SDK (used in `provider_model` adapter's `openai_runner.py`), so it's already in the dependency tree. BSD-3-Clause license. The existing `ollama_runner.py` uses stdlib `urllib.request` for sync HTTP, but QQ Bot's async API surface (token refresh, retry, concurrent sends) benefits from `httpx`'s async client. |
| Python stdlib `json` + `asyncio` | 3.11+ (CI floor) | QQ Bot payload parsing (JSON, not XML), async runtime, idempotency keys | QQ Bot uses JSON payloads (`{id, op, d, s, t}`), unlike WeCom's XML callbacks. `json` from stdlib is sufficient — no `jsonschema` runtime dependency needed (schemas are validated in contract-test-suite, not at runtime). `asyncio` is the native async primitive already used throughout the platform. `hashlib` (already used in `channel_core/idempotency.py`) handles idempotency key generation. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `channel_core.idempotency.channel_idempotency_key` | internal (existing) | Channel-generic idempotency key derivation from callback metadata | Already imported by the fixture-only QQBot adapter (`adapter.py:10`). Reuse as-is for production — QQ Bot message IDs (`msg_id` in event data) map to the `message` stable field. No changes needed. |
| `channel_core.output_policy.apply_output_policy` | internal (existing) | Assistant output boundary enforcement — blocks backend gateway/system notices | Already imported by the fixture-only QQBot adapter (`adapter.py:11`). Reuse as-is for production egress. QQ Bot text/ark/keyboard envelopes all pass through `apply_output_policy()` before delivery. No changes needed. |
| `channel_core.delivery_guard.assess_delivery_completion` | internal (existing) | Delivery-completion guardrails for live task flows | Reuse for QQBot egress when file delivery is requested. Already channel-generic. No changes needed. |
| Python stdlib `argparse` + `os.environ` | 3.11+ (CI floor) | Smoke-test CLI toolkit — credential injection via env vars, one-click execution | The smoke-test toolkit is a CLI script (`scripts/qqbot_smoke_test.py` or similar). `argparse` handles CLI flags, `os.environ` reads `INKSTATUTE_QQBOT_APP_ID_REF` / `INKSTATUTE_QQBOT_APP_SECRET_REF` / `INKSTATUTE_QQBOT_TOKEN_SECRET_REF`. No new CLI framework needed. |
| Python stdlib `hashlib` + `hmac` | 3.11+ (CI floor) | Idempotency key generation, constant-time comparison | `hashlib.sha256` already used in `channel_core/idempotency.py:digest_short()`. `hmac.compare_digest` for constant-time signature comparison (same pattern as `wecom_service/protocol.py:27`). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` + `unittest.mock` | Unit tests for QQBot adapter with mocked HTTP responses | Tests mock `httpx.AsyncClient` and `cryptography` Ed25519 operations. The existing `test_qqbot_channel_adapter.py` and `test_qqbot_channel_loop.py` already test the fixture-only adapter — extend with production-path tests that inject fake HTTP transports (same pattern as `ollama_runner.py`'s `OllamaTransport` Protocol). |
| `pytest-asyncio` | Async test support | Already used across the platform for `async def` test functions. |
| QQ Bot sandbox environment | Live smoke-test target | QQ Bot provides a sandbox mode where message sends bypass rate limits. The smoke-test toolkit targets the sandbox endpoint. Live platform run remains a human gate. |

---

## Installation

```bash
# Core (optional extras — packages remain importable with dependencies = [])
# In packages/channels/qqbot/pyproject.toml:
# [project.optional-dependencies]
# runtime = [
#   "cryptography>=44,<50",
#   "httpx>=0.27,<0.29",
# ]

# Install for development / smoke-test
pip install -e "packages/channels/qqbot[runtime]"

# The package itself stays dependencies = [] — lazy imports inside method bodies
```

```bash
# Smoke-test toolkit only (standalone script, no package install needed)
pip install cryptography>=44 httpx>=0.27
python scripts/qqbot_smoke_test.py --help
```

---

## Integration Points with Existing Architecture

### 1. QQBot Adapter (`packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`)

The existing `QQBotChannelAdapter` class already implements all 6 frozen `ChannelAdapter` Protocol methods:
- `channel_id()` → returns `"qqbot"`
- `capabilities()` → returns `ChannelCapabilitySet(supports_text=True, supports_cards=True, ...)`
- `verify_and_ack(raw: RawInbound)` → currently returns fixture ACK
- `normalize_inbound(raw: RawInbound)` → currently parses fixture payload
- `deliver(delivery: ChannelDelivery)` → currently appends to `self.deliveries` list
- `health()` → currently returns fixture health

**v1.8 production upgrade:** The adapter class signature and Protocol interface do NOT change. Internal method bodies gain real platform behavior:
- `verify_and_ack()`: Add Ed25519 signature verification (`cryptography` lazy import) + op=13 callback URL validation handling. The `QQBotChannelConfig` already carries `app_id_ref`, `app_secret_ref`, `token_secret_ref` — these resolve to runtime secrets for Ed25519 seed derivation.
- `normalize_inbound()`: Parse real QQ Bot JSON payloads (`{id, op, d, s, t}`) instead of fixture payloads. Map `op=0` dispatch events to `AgentTurn` (C2C_MESSAGE_CREATE / GROUP_AT_MESSAGE_CREATE) or `FeedbackEvent` (INTERACTION_CREATE). The existing `_is_feedback_payload()` and `_feedback_from_payload()` logic already handles the feedback-vs-message branching — extend with real QQ Bot event type detection.
- `deliver()`: Build real QQ Bot send envelopes (text `msg_type=0`, ark `msg_type=3`, keyboard buttons for feedback) and POST via `httpx` lazy import. The existing `_build_text_envelope()` and `_build_card_envelope()` are extended to produce QQ Bot API-compatible JSON. `apply_output_policy()` is already called — output boundary enforcement is preserved.
- `health()`: Add real AccessToken validation (check token expiry, verify app_id/app_secret configured).

### 2. Channel-Core (`packages/channel-core/`) — NO CHANGES

`channel_core.idempotency.channel_idempotency_key()` already handles QQ Bot message IDs via the `stable_fields` parameter: `("message", ("message_id", "msg_id", "MsgId"))`. QQ Bot events carry `msg_id` in `d.id` or `d.message_id` — these map to existing aliases. No new stable fields needed.

`channel_core.output_policy.apply_output_policy()` is channel-generic. QQ Bot text/ark/keyboard content all pass through it. No changes needed.

### 3. Runtime Session Continuity — New `QQBotSessionRuntime`

The WeCom service has `WeComSessionRuntime` (`session_runtime.py`) and `WeComRuntimeIngress` (`ingress_runtime.py`) that wrap the channel-generic `RunRuntime` Protocol with WeCom-specific scope/metadata. QQBot needs an equivalent:

- **`QQBotRuntimeIngress`**: Wraps `RunRuntime`, constructs `AgentTurn` from QQ Bot normalized inbound, builds `SessionScope` with `channel_id="qqbot"`, delegates to `RunRuntime.create_run()` or `RunRuntime.resume_interrupt()`. Same pattern as `WeComRuntimeIngress.handle_callback()`.
- **`QQBotSessionRuntime`**: Wraps `RunRuntime` + `SessionResolutionPolicy` + `MemoryOrchestrator` for interrupt resume, memory recall, and active-task routing. Same pattern as `WeComSessionRuntime.handle_turn()`.
- **No new runtime dependency**: These classes use the same `RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator`, `InMemoryInterruptStore` that WeCom uses. The only difference is channel-specific metadata (`channel_id="qqbot"`, QQ Bot `openid` as `user_id`, QQ Bot `conversation_id` from event data).

### 4. Smoke-Test Toolkit — New CLI Script

A standalone Python script (`scripts/qqbot_smoke_test.py`) that:
1. Reads credentials from env vars (`INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_APP_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`).
2. Acquires AccessToken via `httpx` POST to `https://bots.qq.com/app/getAppAccessToken`.
3. Sends a test text message to a configured `openid` via `/v2/users/{openid}/messages`.
4. Verifies Ed25519 signature verification logic by generating a test signature and validating it.
5. Checks health endpoint (adapter `health()` method).
6. Collects evidence (timestamps, response codes, signature validation results) into a structured JSON report.
7. Prints a pass/fail summary.

Uses `argparse` for CLI flags, `httpx` (lazy import) for HTTP, `cryptography` (lazy import) for Ed25519. No new framework.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `cryptography` 49.0.0 for Ed25519 | `pynacl` (PyNaCl) 1.6.2 | If the project already uses PyNaCl elsewhere or prefers libsodium bindings. PyNaCl's `SigningKey(seed)` and `VerifyKey.verify()` are equally capable. However, `cryptography` is more widely adopted, has no C extension build requirements on most platforms (manylinux wheels), and is already a transitive dependency of `httpx`/`openai`. |
| `cryptography` 49.0.0 for Ed25519 | `ed25519` package (pure Python) | Never — the `ed25519` PyPI package is unmaintained (last release 2018) and has known side-channel concerns. |
| `cryptography` 49.0.0 for Ed25519 | Implement Ed25519 in pure Python stdlib | Never — Ed25519 is a complex elliptic curve algorithm. A hand-rolled implementation would be a security risk and maintenance burden. Use a vetted crypto library. |
| `httpx` 0.28.1 for async HTTP | `aiohttp` 3.10+ | If the project already uses `aiohttp` as its primary async HTTP client. However, the project uses `httpx` transitively via `openai` SDK, and `httpx` has a simpler API surface. `aiohttp` adds a separate dependency tree. |
| `httpx` 0.28.1 for async HTTP | stdlib `urllib.request` (sync) | If only sync HTTP is needed and async is not required. The `ollama_runner.py` uses this pattern. However, QQ Bot's token refresh + concurrent send + retry patterns benefit from async. For the smoke-test CLI (sync), `urllib.request` could work, but using `httpx` for both adapter and CLI keeps the dependency surface unified. |
| Direct API implementation (no SDK) | `qq-botpy` (botpy) v1.2.1 | If the project wants a WebSocket-based event loop framework with built-in reconnection, heartbeat, and event dispatch. However, `botpy` is a **framework** (`bot.Client` subclass with `on_at_message_create` handlers), not a lightweight API client. It doesn't fit the webhook callback model that aligns with WeCom. Last updated March 2024 (2+ years stale). The codebase pattern (WeCom reference) is to implement protocol primitives directly. See "What NOT to Use" below. |
| Webhook receive mode | WebSocket receive mode | If the deployment environment cannot expose a public HTTPS endpoint. WebSocket mode connects outbound to QQ's gateway. However, webhook mode aligns with WeCom's callback pattern, is simpler to test, and supports the same `verify_and_ack → normalize_inbound` flow. WebSocket and webhook are mutually exclusive on QQ's side — choose webhook for parity with WeCom. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `qq-botpy` (botpy) v1.2.1 | **Stale**: Last release March 2024 (2+ years old, no updates). **Wrong abstraction**: It's a WebSocket framework (`bot.Client` subclass with `on_at_message_create` event handlers), not a lightweight API client. It doesn't fit the webhook callback model that aligns with WeCom's `verify_and_ack → normalize_inbound` flow. **Framework lock-in**: Adopting `botpy` means inheriting its event loop, reconnection logic, and heartbeat management — the platform already has `RunRuntime` and `WeComSessionRuntime` patterns for this. **Breaking the `dependencies = []` invariant**: `botpy` has its own dependencies (`aiohttp`, `loguru`, etc.) that would need to be optional extras, adding complexity. | Implement QQ Bot protocol primitives (Ed25519 verification, JSON payload parsing, HTTP API calls) directly in the adapter, mirroring the WeCom service pattern. Use `cryptography` for Ed25519 and `httpx` for HTTP. |
| `qq-bot` (old SDK) v0.8.5 | **Deprecated**: Official docs state "原机器人的老版本qq-bot仍然可以使用，但新接口的支持上会逐渐暂停" (old version still works but new API support will gradually stop). Uses old `Token(appid, token)` auth, not the current `AppID + AppSecret → AccessToken` flow. | Direct API implementation with `httpx` + `cryptography`. |
| `aiohttp` | Adds a separate async HTTP dependency tree when `httpx` is already a transitive dependency of `openai` SDK. The project has zero `aiohttp` usage today. | `httpx` 0.28.1 — already in the transitive dependency tree, simpler API, supports both sync and async. |
| `pynacl` (PyNaCl) | While capable of Ed25519, it adds a separate crypto library when `cryptography` is already a transitive dependency of `httpx`. Two crypto libraries is unnecessary. | `cryptography` 49.0.0 — standard Python crypto library, already in the dependency tree. |
| `loguru` or other logging frameworks | `botpy` depends on `loguru`, but the platform uses stdlib `logging` everywhere. Adding `loguru` for one channel adapter is inconsistent. | Python stdlib `logging` — already used across all services and packages. |
| New database / queue / service | AGENTS rule: "Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it." QQ Bot production features are implemented within the existing `packages/channels/qqbot` package and a smoke-test script. | Reuse existing `RunRuntime`, `InMemoryInterruptStore`, `MemoryOrchestrator`, `channel_core` utilities. |
| ChannelAdapter Protocol modification | The Protocol is FROZEN (6 methods: `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health`). The `test_contract_freeze_not_violated.py` test enforces this at runtime. | Implement all QQ Bot production behavior within the existing 6-method interface. Internal method bodies change; the Protocol surface does not. |
| `channel-core` changes | Already extracted in v1.6 as channel-generic logic. `channel_idempotency_key()`, `apply_output_policy()`, `delivery_guard` are all channel-neutral. | Reuse as-is. QQ Bot message IDs and feedback actions map to existing field aliases. |
| `platform-contract` changes | Contract is frozen. `Channel.QQBOT == "qqbot"` already exists. `FeedbackSource.CARD_BUTTON == "card_button"` already exists and is used by the fixture adapter. | No new enum values, no new event schemas. QQ Bot feedback maps to existing `FeedbackSource.CARD_BUTTON`. |
| Hermes core changes | AGENTS rule: "Do not rebuild Hermes core, session storage, router, skill registry, MCP registry, or model gateway." | QQ Bot channel is an InkStatute-owned channel adapter, not a Hermes modification. |
| `websockets` library | WebSocket receive mode is an alternative to webhook, but webhook mode aligns with WeCom's callback pattern and the existing `verify_and_ack → normalize_inbound` Protocol flow. WebSocket and webhook are mutually exclusive on QQ's side. | Webhook (HTTP callback) mode — simpler, testable, aligns with WeCom. If WebSocket mode is needed later, it would be a separate milestone. |

---

## Stack Patterns by Variant

**If webhook receive mode (recommended for v1.8):**
- Use `cryptography` for Ed25519 signature verification of `X-Signature-Ed25519` + `X-Signature-Timestamp` headers
- Use `httpx.AsyncClient` for outbound API calls (token, send, upload, interaction ACK)
- Parse JSON payload `{id, op, d, s, t}` with stdlib `json`
- Handle op=13 (callback URL validation) by signing `event_ts + plain_token` and returning `{"plain_token", "signature"}`
- Handle op=0 (dispatch) by routing to `normalize_inbound()` based on event type `t`
- Handle op=12 (HTTP callback ACK) by returning `{"op": 12}` response body
- Because webhook mode is HTTPS callback-based, it maps directly to the existing `verify_and_ack → normalize_inbound` Protocol flow

**If WebSocket receive mode (deferred, not v1.8):**
- Use `websockets` library (would be a new optional dependency)
- Connect to QQ Bot gateway WSS endpoint
- Implement OpCode 2 (Identify), OpCode 1 (Heartbeat), OpCode 6 (Resume) handling
- Map gateway events to the same `normalize_inbound()` flow
- Because WebSocket requires persistent connection management, it adds complexity beyond the webhook model
- Not recommended for v1.8 — webhook mode provides parity with WeCom and is simpler to test

**If smoke-test toolkit (one-click):**
- Use `httpx` (sync `Client` is fine for CLI) for AccessToken + test message send
- Use `cryptography` for signature verification self-test (generate key pair from test secret, sign, verify)
- Use `argparse` for CLI flags (`--openid`, `--message`, `--verbose`)
- Read credentials from env vars: `INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_APP_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`
- Output structured JSON evidence report to stdout and a file
- Exit code 0 = pass, 1 = fail

**If runtime session continuity (QQBotSessionRuntime):**
- Reuse `RunRuntime` Protocol (create_run, resume_interrupt, poll, stream, cancel, approve)
- Reuse `SessionResolutionPolicy` for interrupt resume vs. new session decisions
- Reuse `MemoryOrchestrator` for memory recall (Hindsight integration)
- Reuse `InMemoryInterruptStore` for pending clarification interrupts
- Build `SessionScope` with `channel_id="qqbot"`, `user_id=<openid>`, `conversation_id=<from event data>`
- No new runtime dependency — all building blocks exist from v1.2/v1.4

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `cryptography>=44,<50` | Python 3.11+ | `cryptography` 44.0.0+ supports Python 3.9+. Ed25519 support added in v2.6 (2019). v49.0.0 (Jun 2026) is the latest stable. Pin `<50` to avoid major version breaking changes. The lower bound `>=44` ensures Ed25519 key derivation from raw bytes is stable. |
| `httpx>=0.27,<0.29` | Python 3.11+, `cryptography` (transitive) | `httpx` 0.28.1 is the latest stable. 0.28.x introduced zstd support and deprecated some APIs. Pin `<0.29` to avoid breaking changes. `httpx` depends on `httpcore`, `certifi`, `idna`, `anyio` — all lightweight. |
| `httpx` 0.28.1 | `openai` SDK 2.x (already used in `provider_model`) | `httpx` is a direct dependency of `openai` SDK. Installing `httpx` for QQBot does not add a new top-level dependency to the environment — it's already present. |
| `cryptography` 49.0.0 | `httpx` 0.28.1 (transitive via `openai`) | `cryptography` is a transitive dependency of `httpx` via `openai` SDK's SSL/TLS stack. Already installed in dev environments that have `openai` installed. |
| `cryptography` Ed25519 | QQ Bot Ed25519 seed derivation | QQ Bot's seed derivation (`repeat botSecret until ≥32 bytes, take first 32`) produces a 32-byte seed. `cryptography`'s `Ed25519PrivateKey.from_private_bytes(seed)` accepts exactly 32 bytes. The public key is derived via `private_key.public_key()`. This matches the QQ Bot Go reference implementation. |
| `channel_core` (existing) | `inkstatute-channels-qqbot` (existing) | The QQBot adapter already imports `channel_core.idempotency.channel_idempotency_key` and `channel_core.output_policy.apply_output_policy`. No version change needed — `channel-core` is at v0.1.0 with `dependencies = []`. |
| `platform_contract` (frozen) | `inkstatute-channels-qqbot` (existing) | The adapter imports `AgentTurn`, `FeedbackEvent`, `SkillCandidate` from `platform_contract.events` and `Channel.QQBOT` from `platform_contract.enums`. No contract changes needed. |
| `platform_runtime` (existing) | `QQBotSessionRuntime` (new) | `RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator`, `InMemoryInterruptStore` are existing Protocol interfaces. `QQBotSessionRuntime` consumes them — no `platform_runtime` changes needed. |

---

## QQ Bot Message Type → ChannelDelivery Mapping

| QQ Bot `msg_type` | ChannelDelivery `delivery_type` | Envelope Builder | Notes |
|-------------------|--------------------------------|------------------|-------|
| 0 (text) | `"text"` | `_build_text_envelope()` → `{"content": ..., "msg_type": 0}` | Primary egress for agent replies. `apply_output_policy()` enforced before content. |
| 2 (markdown) | `"markdown"` | `_build_markdown_envelope()` → `{"markdown": {"content": ...}, "msg_type": 2}` | Optional — QQ Bot supports markdown in C2C and group. Use for formatted legal output. |
| 3 (ark) | `"card"` | `_build_ark_envelope()` → `{"ark": {"template_id": 23/24/37, "kv": [...]}, "msg_type": 3}` | ARK templates 23 (link+text list), 24 (text+thumbnail), 37 (large image) are available by default. Used for rich feedback cards. |
| 7 (media) | `"file"` / `"image"` | `_build_media_envelope()` → upload to `/v2/users/{openid}/files` → `{"media": {"file_info": ...}, "msg_type": 7}` | Two-step: upload (POST `/files`) → send (POST `/messages` with `file_info`). `file_type`: 1=image, 2=video, 3=voice, 4=file. |
| keyboard (buttons) | `"card"` with `card_type="feedback"` | `_build_keyboard_envelope()` → `{"keyboard": {"content": {"rows": [{"buttons": [...]}]}}, "msg_type": 2}` | Keyboard is sent as part of a markdown or text message. Buttons with `action.type=1` (callback) trigger `INTERACTION_CREATE` events. Maps to existing `FeedbackSource.CARD_BUTTON`. |

### QQ Bot Event Type → InboundNormalized Mapping

| QQ Bot Event `t` | OpCode | InboundNormalized | Notes |
|------------------|--------|-------------------|-------|
| `C2C_MESSAGE_CREATE` | 0 | `message=AgentTurn(channel="qqbot")` | User sends DM to bot. `d.content` = text, `d.author.openid` = user_id. |
| `GROUP_AT_MESSAGE_CREATE` | 0 | `message=AgentTurn(channel="qqbot")` | User @-mentions bot in group. `d.content` = text (without @mention prefix), `d.author.openid` = user_id, `d.group_openid` = conversation_id. |
| `INTERACTION_CREATE` | 0 | `feedback=FeedbackEvent(source="card_button")` | User clicks callback button. `d.data.resolved.button_data` = action, `d.data.resolved.button_id` = button ID. Maps to existing `_feedback_action()` logic. |
| `FRIEND_ADD` / `FRIEND_DEL` | 0 | (metadata only, no AgentTurn) | Bot friend add/remove events. Can be logged but don't produce turns. |
| `GROUP_ADD` / `GROUP_DEL` | 0 | (metadata only, no AgentTurn) | Bot added/removed from group. Can be logged but don't produce turns. |
| (op=13) | 13 | (callback URL validation, not a turn) | Sign `event_ts + plain_token` and return `{"plain_token", "signature"}`. Handled in `verify_and_ack()`. |

---

## Sources

- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html` — Ed25519 signature verification flow, seed derivation, header fields (`X-Signature-Ed25519`, `X-Signature-Timestamp`). Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html` — Webhook vs WebSocket modes, OpCode table (0/1/2/6/7/9/10/11/12/13), payload structure `{id, op, d, s, t}`, callback URL validation flow. Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html` — AccessToken acquisition (POST `https://bots.qq.com/app/getAppAccessToken`), auth header format `Authorization: QQBot {token}`, 7200s TTL, API base URL `https://api.sgroup.qq.com`. Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html` — Send message endpoints (C2C `/v2/users/{openid}/messages`, group `/v2/groups/{group_openid}/messages`), `msg_type` values (0/2/3/4/7), rate limits (60 qpm verified, passive reply windows). Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/ark.html` — ARK message format (`template_id` + `kv` pairs), default templates 23/24/37, kv structure for array-type variables. Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/rich-media.html` — Rich media upload flow (POST `/v2/users/{openid}/files` → `file_info` → send with `msg_type=7`), `file_type` values (1=image, 2=video, 3=voice, 4=file). Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/trans/msg-btn.html` — Keyboard button configuration (`action.type`: 0=link, 1=callback, 2=command), `INTERACTION_CREATE` event (intents `1<<26`), interaction ACK via `/interactions/{interaction_id}`, event fields (`data.resolved.button_data`, `data.resolved.button_id`). Verified 2026-07-07.
- `bot.q.qq.com/wiki/develop/pythonsdk/` — Official Python SDK (`qq-botpy` / `botpy`), install via `pip install qq-botpy`, Python 3.8+. Confirmed this is a WebSocket framework, not a lightweight API client. Verified 2026-07-07.
- `github.com/tencent-connect/botpy` — Official SDK repo (877 stars, MIT, 228 commits). Latest release v1.2.1 (March 2024), last push September 2024. Confirmed stale — 2+ years without update. Verified 2026-07-07.
- `pypi.org/project/qq-botpy/` — PyPI package page. Latest version v1.2.1 (March 22, 2024). Status: 4 - Beta. Verified 2026-07-07.
- `pypi.org/project/cryptography/` — Latest version 49.0.0 (June 12, 2026). Apache-2.0/BSD-3-Clause. Python 3.9+. Ed25519 support since v2.6. Verified 2026-07-07.
- `pypi.org/project/httpx/` — Latest version 0.28.1. BSD-3-Clause. Python 3.8+. Async client support. Verified 2026-07-07.
- `cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/` — `Ed25519PrivateKey.from_private_bytes(data)`, `Ed25519PublicKey.verify(signature, data)`, `Ed25519PrivateKey.sign(data)`. Verified 2026-07-07.
- Existing codebase: `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — Current fixture-only adapter (323 lines), 6-method Protocol implementation, imports from `channel_core` and `platform_contract`. Read 2026-07-07.
- Existing codebase: `packages/channel-core/src/channel_core/idempotency.py` — `channel_idempotency_key()` with stable fields `("message", ("message_id", "msg_id", "MsgId"))`. Read 2026-07-07.
- Existing codebase: `services/wecom-service/src/wecom_service/protocol.py` — WeCom signature verification pattern (`hashlib.sha1` + `hmac.compare_digest`), `parse_callback_envelope()`, `ack_response()`. Read 2026-07-07.
- Existing codebase: `services/wecom-service/src/wecom_service/ingress_runtime.py` — `WeComRuntimeIngress` pattern wrapping `RunRuntime` with channel-specific scope/metadata. Read 2026-07-07.
- Existing codebase: `services/wecom-service/src/wecom_service/session_runtime.py` — `WeComSessionRuntime` pattern with interrupt resume, memory recall, active-task routing. Read 2026-07-07.
- Existing codebase: `packages/platform-runtime/src/platform_runtime/protocols.py` — Frozen `ChannelAdapter` Protocol (6 methods, line 208-219), `RawInbound`, `AckResponse`, `InboundNormalized`, `ChannelDelivery`, `DeliveryResult`, `ChannelCapabilitySet`, `ComponentHealth` dataclasses. Read 2026-07-07.
- Existing codebase: `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py` — Lazy `urllib.request` import pattern, `OllamaTransport` Protocol for test injection. Read 2026-07-07.
- Existing codebase: `.planning/milestones/v1.7-research/STACK.md` — v1.7 stack research pattern (optional extras, lazy imports, `dependencies = []` invariant). Read 2026-07-07.

---
*Stack research for: v1.8 QQBot Channel Production — real QQ Bot platform ingress/egress, feedback cards, runtime session continuity, one-click smoke-test toolkit*
*Researched: 2026-07-07*
