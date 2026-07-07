# Requirements: 墨律 InkStatute v1.8 QQBot Channel Production

**Defined:** 2026-07-07
**Core Value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. v1.8 extends the platform with a production-grade QQBot channel aligned with WeCom behavior, including QQ-platform-required differences.

## v1.8 Requirements

Requirements for QQBot Channel Production milestone. Each maps to roadmap phases (numbering continues from v1.7, next = 58).

### Ingress — Signature & Validation

- [ ] **INGRESS-01**: QQ Bot webhook callback signature is verified using Ed25519 (BotSecret-derived keypair, `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + raw_body`), rejecting unverified callbacks with HTTP 401.
- [ ] **INGRESS-02**: QQ Bot callback URL validation handshake (op=13) is handled by signing `{event_ts + plain_token}` with the Ed25519 private key and returning `{plain_token, signature}`, enabling webhook URL registration.
- [ ] **INGRESS-03**: QQ Bot gateway envelope `{op, t, d}` is parsed into typed event categories (C2C message, GROUP_AT_MESSAGE_CREATE, INTERACTION_CREATE, validation challenge) with correct dispatch before normal event processing.

### Ingress — Event Normalization

- [ ] **INGRESS-04**: QQ Bot C2C and group @-bot message events are normalized into `AgentTurn` records with @-bot prefix stripped, scene-aware composite `conversation_id` (`qqbot:{scene}:{scene_id}:{user_openid}`), and platform contract channel metadata.
- [ ] **INGRESS-05**: QQ Bot `INTERACTION_CREATE` events are normalized into `FeedbackEvent` records with `source="card_button"` (frozen enum), `action` mapped from button `data.resolved.button_data` (up/down/needs_fix/route_wrong), and no new `FeedbackSource` enum values added.
- [ ] **INGRESS-06**: QQ Bot webhook ACK uses two-tier strategy: HTTP 200 with op=12 envelope for message events, plus `PUT /interactions/{id}` for button-click events (without which the QQ client hangs in loading state).

### Egress — Token & Delivery

- [ ] **EGRESS-01**: QQ Bot access token is acquired via `appId + clientSecret → POST /getAppAccessToken`, cached with 7200s TTL, auto-refreshed 60s before expiry, and single-flight under concurrent refresh via `asyncio.Lock`.
- [ ] **EGRESS-02**: QQ Bot text messages (`msg_type=0`) are delivered via OpenAPI with `msg_id` + `msg_seq` passive-reply dedupe, retry on transient failure, and output boundary enforcement (no backend gateway/system notices leak to users).
- [ ] **EGRESS-03**: QQ Bot markdown + keyboard feedback cards (`msg_type=2` + `keyboard` with callback buttons up/down/needs_fix/route_wrong) are delivered, mapping `delivery_type=="card"` to QQ keyboard payload (not WeCom `template_card`).
- [ ] **EGRESS-04**: QQ Bot passive-reply time window (C2C 60min/4 replies, group 5min/5 replies per `msg_id`) is tracked; window expiry surfaces as a delivery failure with an interim InkStatute-owned service notice (not a silent drop).

### Egress — Rich Media (P2)

- [ ] **EGRESS-05**: QQ Bot rich media inbound (image/voice/video/file `attachments[]`) is parsed into `AttachmentRef` records with reference-only policy (no raw payload storage, URL stored as `raw_payload_ref`).
- [ ] **EGRESS-06**: QQ Bot rich media egress uses two-step upload (`POST /v2/.../files` → `file_info` → `msg_type=7`) for DOCX/PDF legal document delivery, with retry and evidence collection.

### Egress — Markdown Replies (P2)

- [ ] **EGRESS-07**: QQ Bot markdown replies (`msg_type=2`) are delivered for structured legal answers, leveraging QQ's native markdown support (which WeCom lacks), with output boundary enforcement on markdown content.

### Session Continuity

- [ ] **SESS-01**: QQBotSessionRuntime orchestrates continuous conversation for QQ users via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator`, composing `platform_runtime` primitives directly (no `wecom_service` import).
- [ ] **SESS-02**: QQ Bot interrupt resume preserves skill clarification questions across user replies, with scene-aware conversation identity partitioning sessions by channel + scene (no C2C/group cross-scene collision).
- [ ] **SESS-03**: QQ Bot memory recall (pre-turn recall + post-turn retention) is wired via `MemoryOrchestrator` with fail-open graceful degradation, matching WeCom session runtime behavior.

### Feedback Loop Parity

- [ ] **FEEDBACK-01**: QQ Bot feedback loop is wired end-to-end: keyboard card dispatch (egress) → user button click → `INTERACTION_CREATE` (ingress) → `FeedbackEvent` normalization → feedback-service dedupe/classify/queue, achieving parity with WeCom feedback pipeline.
- [ ] **FEEDBACK-02**: QQ Bot interaction ACK (`PUT /interactions/{id}`) is sent after feedback normalization, completing the two-tier ACK for button-click events.
- [ ] **FEEDBACK-03**: QQ Bot feedback dedupe uses `msg_id` + button identity, preventing duplicate `FeedbackEvent` records from repeated clicks or platform retries.

### Session Recall (P2)

- [ ] **RECALL-01**: QQ Bot `is_wakeup` interaction recall is supported for over-window long-task completion (windowed: 30-day periods, 1 per period), allowing the bot to notify users when a long task finishes after the passive-reply window expires.

### Adapter Integration & Safety

- [ ] **ADAPTER-01**: QQBotChannelAdapter is promoted from fixture-only to real IO across all 6 frozen Protocol methods, with QQ-specific behavior encoded via `ChannelDelivery.metadata`, `AckResponse.metadata`, `ChannelCapabilitySet.metadata` (no Protocol methods added or modified).
- [ ] **ADAPTER-02**: QQBot channel feature flag (`qqbot_channel_enabled`) defaults to `False`; fixture path is preserved for CI when flag is off; real IO is gated behind the flag.
- [ ] **ADAPTER-03**: QQBot adapter does not import from `wecom_service` (enforced by `test_no_wecom_import.py`); channel-core modules are reused as-is (no new channel-core modules).
- [ ] **ADAPTER-04**: All 24 existing V2 gates remain green throughout v1.8; frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules are not modified.

### Smoke-Test Toolkit

- [ ] **SMOKE-01**: One-click smoke-test CLI (`scripts/smoke_test.py`) validates signature verification, sends text + markdown+keyboard, simulates callback, and collects sanitized evidence — all via env-var credential injection (no secrets in code or output).
- [ ] **SMOKE-02**: Smoke-test `--dry-run` mode runs without live QQ Bot platform connection (CI-able), validating envelope structure, signature logic, and evidence format with fixture credentials.
- [ ] **SMOKE-03**: Smoke-test operator runbook (`runbook/SMOKE_TEST_RUNBOOK.md`) documents credential setup, env-var injection, command sequence, expected outputs, and evidence collection format — enabling an operator to run the live smoke test without deep platform knowledge.
- [ ] **SMOKE-04**: Smoke-test evidence output is sanitized (no tokens, no raw user payloads, no attachment URLs); evidence is structured for archival in `.planning/` after live run.

## v2 Requirements (Deferred)

### WebSocket Ingress Mode

- **WS-01**: QQ Bot WebSocket ingress mode (stateful, Resume/op6, heartbeat/identify/reconnect) as an alternative to webhook mode.
- **WS-02**: WebSocket Resume (op=6) with durable `s` sequence persistence for event continuity across reconnects.

### Guild & Channel Management

- **GUILD-01**: QQ Bot guild/channel management APIs (roles, permissions, sub-channels, forums, audio stage).
- **GUILD-02**: Group role-aware routing (owner/admin/member privileges influencing routing decisions).

### Advanced Push

- **PUSH-01**: QQ Bot active push beyond `is_wakeup` (monthly quota-managed broadcasts with user opt-in).
- **PUSH-02**: QQ-built-in voice ASR passthrough for voice message inbound.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Modifying frozen ChannelAdapter Protocol (6 methods) | Protocol is frozen; QQ-specific behavior expressed via metadata fields. Modifying breaks all existing channels. |
| Modifying frozen platform-contract enums/schemas | `Channel.QQBOT`, `FeedbackSource.CARD_BUTTON`, `FeedbackAction.*` already exist; no new enum values needed. |
| Importing from `wecom_service` into QQBot adapter | Enforced by `test_no_wecom_import.py`; channels must be independent. WeCom is a reference pattern, not a shared codebase. |
| Adding `qq-botpy` (botpy) SDK | Stale (last release March 2024), WebSocket-framework mismatch with webhook model, breaks `dependencies = []` pattern. Direct protocol implementation preferred. |
| Adding new database, queue, or service | Reuse existing `RunRuntime`, `InMemoryInterruptStore`, `MemoryOrchestrator`, feedback-service, conversation-read-view. No new infrastructure. |
| Rebuilding Hermes core / channel-core / router / skill registry | V2 calls Hermes as agent backend; channel-core already extracted in v1.6. Not in scope. |
| Live QQ Bot platform connection as autonomous milestone deliverable | Live run is a human gate (symmetric with WeCom Phase 5). Toolkit + dry-run ship in milestone; live evidence is operator-driven. |
| Storing QQ attachment URLs or raw user payloads in contract logs | AGENTS.md safety rule: contract logs prefer references (`raw_payload_ref`); no sensitive full text by default. |
| Auto-synthesizing or auto-modifying legal skill candidates | V2 records `skill_candidate` for human review only; high-risk legal feedback remains human-reviewed. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGRESS-01 | 59 | Pending |
| INGRESS-02 | 59 | Pending |
| INGRESS-03 | 60 | Pending |
| INGRESS-04 | 60 | Pending |
| INGRESS-05 | 60 | Pending |
| INGRESS-06 | 65 | Pending |
| EGRESS-01 | 61 | Pending |
| EGRESS-02 | 62 | Pending |
| EGRESS-03 | 62 | Pending |
| EGRESS-04 | 62 | Pending |
| EGRESS-05 | 63 | Pending |
| EGRESS-06 | 63 | Pending |
| EGRESS-07 | 62 | Pending |
| SESS-01 | 64 | Pending |
| SESS-02 | 64 | Pending |
| SESS-03 | 64 | Pending |
| FEEDBACK-01 | 66 | Pending |
| FEEDBACK-02 | 66 | Pending |
| FEEDBACK-03 | 66 | Pending |
| RECALL-01 | 66 | Pending |
| ADAPTER-01 | 65 | Pending |
| ADAPTER-02 | 65 | Pending |
| ADAPTER-03 | 65 | Pending |
| ADAPTER-04 | 58 | Pending |
| SMOKE-01 | 67 | Pending |
| SMOKE-02 | 67 | Pending |
| SMOKE-03 | 67 | Pending |
| SMOKE-04 | 67 | Pending |

**Coverage:**
- v1.8 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-07-07*
*Last updated: 2026-07-07 after v1.8 roadmap creation (28/28 requirements mapped to Phases 58-67)*
