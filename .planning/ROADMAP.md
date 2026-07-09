# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)
- Complete **v1.4 Long-Term Memory Productization** - Phases 26-32 shipped 2026-07-03. Productized long-term memory with Hindsight backend, singleton wiring, and contract event observability. Audit passed (20/20 requirements).
  - Archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)
- Complete **v1.5 V2 Acceptance Closure** - Phases 33-35 shipped 2026-07-03. Audited all unchecked V2 Active requirements, closed code gaps, produced acceptance readiness report. Audit passed (23/23 requirements). Autonomous closure READY; V2 acceptance BLOCKED ON HUMAN GATES (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial).
  - Archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)
- Complete **v1.6 M2 Multi-Backend & Platform Extensions** - Phases 36-44 shipped 2026-07-04. Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate coverage meta-test. Audit passed (22/22 requirements, 19/19 gates green, 969 tests).
  - Archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)
- Complete **v1.7 M3 Platform Extensions** - Phases 45-57 + 57.1 gap closure shipped 2026-07-06. Promoted adapter prototypes to production-grade, extended platform surface (MCP, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Audit passed (38/38 requirements, 24/24 gates green, 1,547+ tests).
  - Archive: [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)
- Complete **v1.8 QQBot Channel Production** - Phases 58-67 shipped 2026-07-09. Promoted QQBot from fixture-only proof to production-grade channel loop (signature, normalize, token, egress, rich media, session/ingress, adapter real IO, feedback+wakeup, smoke toolkit). Audit: gaps_found (host composition deferred; package-level 28/28 + 321 tests green). Live QQ smoke remains a human gate.
  - Archive: [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)

## Current Milestone: (awaiting next)

> v1.8 QQBot Channel Production shipped 2026-07-09. Phase directories archived to `.planning/milestones/v1.8-phases/`. See archive links above.

## Archived Milestone Detail: v1.8 QQBot Channel Production

**Goal:** Promote the QQBot channel from v1.6 fixture-only proof to a complete V2 production-grade channel loop aligned with WeCom behavior (including QQ-platform-required differences), and deliver a one-click live-platform smoke-test toolkit.

**Requirements:** `.planning/REQUIREMENTS.md` (28 requirements)

**Key context:**

- Maintain v1.7 safety strategy: contract freeze, feature flags default OFF, output boundary enforced, human gates preserved.
- `qqbot_channel_enabled` flag default-OFF; live promotion remains a human gate.
- All 24 existing V2 gates must stay green throughout (no regressions).
- Frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified (ADAPTER-04 cross-cutting safety).
- Phase numbering continues from v1.7 (next phase = 58).
- Critical path: P58 (safety) → P59 (signature) → P60 (normalization) → P61 (token) → P62 (egress sender) → P63 (rich media) → P64 (session runtime) → P65 (adapter integration) → P66 (feedback + recall) → P67 (smoke-test toolkit).

## Phases

- [x] **Phase 58: v1.8 Pre-Implementation Safety** - Verify 24 V2 gates green baseline, frozen ChannelAdapter Protocol / BackendAdapter Protocol / platform-contract enums / channel-core modules unmodified, `qqbot_channel_enabled` flag default-off, `test_no_wecom_import.py` passes, `dependencies = []` invariant holds. *(ADAPTER-04; cross-cutting safety criterion for all v1.8 phases)* — completed 2026-07-07
- [x] **Phase 59: Ed25519 Signature Verification + Validation Challenge** - `signature.py` (Ed25519 key derivation from BotSecret, verify `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + raw_body`, sign op=13 challenge `{event_ts + plain_token}`); reject unverified callbacks with HTTP 401; tests with official QQ demo vectors. *(INGRESS-01, INGRESS-02)* — completed 2026-07-07
- [x] **Phase 60: QQ Event Normalization** - `normalization.py` (parse gateway envelope `{op, t, d}` → typed event categories; C2C/GROUP_AT_MESSAGE_CREATE → `AgentTurn` with @-bot prefix stripped and scene-aware `conversation_id`; INTERACTION_CREATE → `FeedbackEvent` with `source="card_button"` frozen enum); fixture files + tests. *(INGRESS-03, INGRESS-04, INGRESS-05)* (completed 2026-07-07)
- [x] **Phase 61: Access Token Manager** - `token_manager.py` (appId + clientSecret → `POST /getAppAccessToken`, 7200s TTL cache, auto-refresh 60s before expiry, single-flight via `asyncio.Lock`); tests for lifecycle, concurrent refresh, error handling. *(EGRESS-01)* (completed 2026-07-09)
- [x] **Phase 62: QQ Egress Sender — Text + Markdown + Keyboard** - `sender.py` (text `msg_type=0` with `msg_id`+`msg_seq` dedupe + retry; markdown+keyboard `msg_type=2` with callback buttons up/down/needs_fix/route_wrong; markdown `msg_type=2` for structured legal answers; passive-reply window tracking C2C 60min/4 + group 5min/5 with window-expiry delivery failure + interim service notice; output boundary enforcement); `adapter.py` `deliver()` modification. *(EGRESS-02, EGRESS-03, EGRESS-04, EGRESS-07)* (completed 2026-07-09)
- [x] **Phase 63: QQ Rich Media Inbound + Egress (P2)** - Parse `attachments[]` (image/voice/video/file) → `AttachmentRef` with reference-only policy (`raw_payload_ref`, no raw payload storage); two-step upload (`POST /v2/.../files` → `file_info` → `msg_type=7`) for DOCX/PDF legal document delivery with retry + evidence collection. *(EGRESS-05, EGRESS-06)* (completed 2026-07-09)
- [x] **Phase 64: QQBotSessionRuntime + QQBotIngressRuntime** - `session_runtime.py` (orchestrate continuous conversation via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator`, composing `platform_runtime` primitives directly, no `wecom_service` import); `ingress_runtime.py` (callback → turn → session runtime); scene-aware conversation identity `qqbot:{scene}:{scene_id}:{user_openid}`; interrupt resume across user replies; memory recall (pre-turn recall + post-turn retention) with fail-open degradation. *(SESS-01, SESS-02, SESS-03)* (completed 2026-07-09)
- [x] **Phase 65: Adapter Integration — Promote to Real IO** - `adapter.py` full modification (all 6 frozen Protocol methods gain real IO behind `qqbot_channel_enabled` flag; QQ-specific behavior via `ChannelDelivery.metadata`, `AckResponse.metadata`, `ChannelCapabilitySet.metadata`; two-tier ACK: op=12 HTTP 200 for messages + `PUT /interactions/{id}` for button clicks); fixture path preserved for CI when flag off; `test_no_wecom_import.py` enforced; no new channel-core modules. *(ADAPTER-01, ADAPTER-02, ADAPTER-03, INGRESS-06)* (completed 2026-07-09)
- [x] **Phase 66: Feedback Loop Parity + Interaction Recall** - End-to-end feedback wiring (keyboard card dispatch → user button click → INTERACTION_CREATE → FeedbackEvent normalization → feedback-service dedupe/classify/queue); interaction ACK after feedback normalization; feedback dedupe via `msg_id` + button identity; `is_wakeup` interaction recall for over-window long-task completion (windowed 30-day periods, 1 per period); parity with WeCom feedback pipeline. *(FEEDBACK-01, FEEDBACK-02, FEEDBACK-03, RECALL-01)* (completed 2026-07-09)
- [x] **Phase 67: One-Click Smoke-Test Toolkit** - `scripts/smoke_test.py` (CLI: validate signature, send text + markdown+keyboard, simulate callback, collect sanitized evidence via env-var credential injection); `--dry-run` mode for CI (fixture credentials, no live platform); `runbook/SMOKE_TEST_RUNBOOK.md` (credential setup, env-var injection, command sequence, expected outputs, evidence format); sanitized evidence output (no tokens, no raw payloads, no attachment URLs). Live run remains a human gate. *(SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04)* (completed 2026-07-09)

**Cross-cutting safety (ADAPTER-04):** All 24 existing V2 gates must remain green throughout v1.8; frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified. This is a success criterion in every v1.8 phase.

## Phase Details

### Phase 58: v1.8 Pre-Implementation Safety

**Goal:** Operator can verify that all cross-cutting v1.8 safety measures (24 V2 gates green baseline, frozen ChannelAdapter Protocol / BackendAdapter Protocol / platform-contract enums / channel-core modules unmodified, `qqbot_channel_enabled` flag default-off, `test_no_wecom_import.py` passes, `dependencies = []` invariant holds) are in place before any v1.8 feature code.
**Depends on:** v1.7 completion (Phase 57.1)
**Requirements:** ADAPTER-04
**Success Criteria** (what must be TRUE):

1. All 24 existing V2 gates pass green (1,547+ tests) with no regressions on the v1.8 baseline branch.
2. Contract-count assertion test confirms no frozen Protocol modified (`ChannelAdapter` 6 methods, `BackendAdapter` 9 methods) and `packages/platform-contract/` baseline hash unchanged from v1.7.
3. `qqbot_channel_enabled` feature flag defaults to `False` in `RuntimeFeatureFlags`.
4. `test_no_wecom_import.py` passes — QQBot adapter does not import from `wecom_service`.
5. `dependencies = []` invariant holds — no new runtime dependencies added to QQBot channel package.

**Plans:** 1 plan

Plans:

- [ ] 58-01-PLAN.md — Restore deleted trial evidence template from git history + create consolidated v1.8 safety baseline test + verify all 26 V2 gates green

### Phase 59: Ed25519 Signature Verification + Validation Challenge

**Goal:** QQ Bot webhook callback signatures are verified using Ed25519 (BotSecret-derived keypair, `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + raw_body`), rejecting unverified callbacks with HTTP 401; callback URL validation handshake (op=13) is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`.
**Depends on:** Phase 58
**Requirements:** INGRESS-01, INGRESS-02
**Success Criteria** (what must be TRUE):

1. `signature.py` derives Ed25519 keypair from BotSecret and verifies `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + raw_body`.
2. Unverified callbacks are rejected with HTTP 401.
3. op=13 validation challenge is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`.
4. Tests pass with official QQ demo vectors for signature verification and validation challenge.

**Plans:** 2 plans

Plans:

- [ ] 59-01-PLAN.md — Vendored RFC 8032 Ed25519 module + signature.py (derive_keypair, verify_callback_signature, handle_validation_challenge) + known-answer tests with official QQ demo vectors
- [ ] 59-02-PLAN.md — Config bot_secret_ref + adapter verify_and_ack integration (401 rejection, op=13 challenge handling) + import isolation coverage

### Phase 60: QQ Event Normalization

**Goal:** QQ Bot gateway envelope `{op, t, d}` is parsed into typed event categories (C2C message, GROUP_AT_MESSAGE_CREATE, INTERACTION_CREATE, validation challenge) with correct dispatch; C2C/group @-bot messages normalize into `AgentTurn` with @-bot prefix stripped and scene-aware `conversation_id`; INTERACTION_CREATE normalizes into `FeedbackEvent` with `source="card_button"` frozen enum.
**Depends on:** Phase 59
**Requirements:** INGRESS-03, INGRESS-04, INGRESS-05
**Success Criteria** (what must be TRUE):

1. `normalization.py` parses gateway envelope `{op, t, d}` into typed event categories with correct dispatch.
2. C2C/GROUP_AT_MESSAGE_CREATE events normalize into `AgentTurn` with @-bot prefix stripped and scene-aware `conversation_id` (`qqbot:{scene}:{scene_id}:{user_openid}`).
3. INTERACTION_CREATE events normalize into `FeedbackEvent` with `source="card_button"` (frozen enum) and `action` mapped from button data.
4. No new `FeedbackSource` enum values added.
5. Fixture files and tests cover all event categories.

### Phase 61: Access Token Manager

**Goal:** QQ Bot access token is acquired via `appId + clientSecret → POST /getAppAccessToken`, cached with 7200s TTL, auto-refreshed 60s before expiry, and single-flight under concurrent refresh via `asyncio.Lock`.
**Depends on:** Phase 60
**Requirements:** EGRESS-01
**Plans:** 2/2 plans complete

Plans:

- [x] 61-01-PLAN.md — Create token_manager.py (transport injection + TokenManager cache/refresh) and lifecycle/import-safety tests
- [x] 61-02-PLAN.md — Concurrent single-flight + error-handling tests; wecom import isolation; safety suite green

**Success Criteria** (what must be TRUE):

1. `token_manager.py` acquires access token via `POST /getAppAccessToken` using appId + clientSecret.
2. Token is cached with 7200s TTL and auto-refreshed 60s before expiry.
3. Concurrent refresh is single-flight via `asyncio.Lock` (no duplicate token requests).
4. Tests cover lifecycle, concurrent refresh, and error handling.

### Phase 62: QQ Egress Sender — Text + Markdown + Keyboard

**Goal:** QQ Bot text messages (`msg_type=0`) are delivered with `msg_id`+`msg_seq` dedupe and retry; markdown+keyboard feedback cards (`msg_type=2`) are delivered with callback buttons; markdown replies (`msg_type=2`) are delivered for structured legal answers; passive-reply time window is tracked with window-expiry delivery failure + interim service notice; output boundary is enforced.
**Depends on:** Phase 61
**Requirements:** EGRESS-02, EGRESS-03, EGRESS-04, EGRESS-07
**Success Criteria** (what must be TRUE):

1. `sender.py` delivers text messages (`msg_type=0`) with `msg_id`+`msg_seq` passive-reply dedupe and retry on transient failure.
2. `sender.py` delivers markdown+keyboard feedback cards (`msg_type=2` + `keyboard`) with callback buttons up/down/needs_fix/route_wrong, mapping `delivery_type=="card"` to QQ keyboard payload.
3. `sender.py` delivers markdown replies (`msg_type=2`) for structured legal answers with output boundary enforcement.
4. Passive-reply time window (C2C 60min/4, group 5min/5 per `msg_id`) is tracked; window expiry surfaces as delivery failure with interim InkStatute-owned service notice.
5. `adapter.py` `deliver()` is modified to use the new sender.
6. Output boundary enforcement prevents backend gateway/system notices from leaking to users.

**Plans:** 3/3 plans complete

Plans:

- [x] 62-01-PLAN.md — Envelope builders for text/markdown/keyboard + output policy tests
- [x] 62-02-PLAN.md — Passive-reply window gate + MessageTransport send/retry
- [x] 62-03-PLAN.md — adapter.deliver() wiring + fixture/wecom-isolation test updates

### Phase 63: QQ Rich Media Inbound + Egress (P2)

**Goal:** QQ Bot rich media inbound (image/voice/video/file `attachments[]`) is parsed into `AttachmentRef` records with reference-only policy; rich media egress uses two-step upload for DOCX/PDF legal document delivery with retry and evidence collection.
**Depends on:** Phase 62
**Requirements:** EGRESS-05, EGRESS-06
**Success Criteria** (what must be TRUE):

1. `attachments[]` (image/voice/video/file) are parsed into `AttachmentRef` records with reference-only policy (`raw_payload_ref`, no raw payload storage).
2. Two-step upload (`POST /v2/.../files` → `file_info` → `msg_type=7`) is implemented for DOCX/PDF legal document delivery.
3. Retry and evidence collection are implemented for rich media egress failures.

**Plans:** 3/3 plans complete

Plans:

- [x] 63-01-PLAN.md — Inbound attachments[] → AttachmentRef (reference-only qqbot-media://) + fixtures/tests
- [x] 63-02-PLAN.md — Two-step upload + msg_type=7 media envelope + retry 304082/304083 + sanitized evidence
- [x] 63-03-PLAN.md — adapter.deliver file/image wiring + capabilities flags + ADAPTER-04 safety gates

### Phase 64: QQBotSessionRuntime + QQBotIngressRuntime

**Goal:** QQBotSessionRuntime orchestrates continuous conversation for QQ users via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator` (composing `platform_runtime` primitives directly, no `wecom_service` import); QQBotIngressRuntime wires callback → turn → session runtime; scene-aware conversation identity partitions sessions; interrupt resume and memory recall work with fail-open degradation.
**Depends on:** Phase 63
**Requirements:** SESS-01, SESS-02, SESS-03
**Success Criteria** (what must be TRUE):

1. `session_runtime.py` orchestrates continuous conversation via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator`, composing `platform_runtime` primitives directly (no `wecom_service` import).
2. `ingress_runtime.py` wires callback → turn → session runtime.
3. Scene-aware conversation identity `qqbot:{scene}:{scene_id}:{user_openid}` partitions sessions by channel + scene (no C2C/group cross-scene collision).
4. Interrupt resume preserves skill clarification questions across user replies.
5. Memory recall (pre-turn recall + post-turn retention) is wired via `MemoryOrchestrator` with fail-open graceful degradation.

**Plans:** 3/3 plans complete

Plans:

- [x] 64-01-PLAN.md — QQBotSessionRuntime core: create_run/resume_interrupt, scene isolation, no wecom import
- [x] 64-02-PLAN.md — QQBotRuntimeIngress callback→turn→session + public exports + skip non-message
- [x] 64-03-PLAN.md — MemoryOrchestrator fail-open recall + finalize_memory retention (SESS-03)

### Phase 65: Adapter Integration — Promote to Real IO

**Goal:** QQBotChannelAdapter is promoted from fixture-only to real IO across all 6 frozen Protocol methods, with QQ-specific behavior encoded via metadata fields; `qqbot_channel_enabled` flag gates real IO; fixture path is preserved for CI when flag off; two-tier ACK is implemented; `test_no_wecom_import.py` is enforced; no new channel-core modules.
**Depends on:** Phase 64
**Requirements:** ADAPTER-01, ADAPTER-02, ADAPTER-03, INGRESS-06
**Success Criteria** (what must be TRUE):

1. `adapter.py` all 6 frozen Protocol methods gain real IO behind `qqbot_channel_enabled` flag.
2. QQ-specific behavior is encoded via `ChannelDelivery.metadata`, `AckResponse.metadata`, `ChannelCapabilitySet.metadata` (no Protocol methods added or modified).
3. Two-tier ACK: op=12 HTTP 200 for message events + `PUT /interactions/{id}` for button-click events.
4. Fixture path is preserved for CI when flag is off.
5. `test_no_wecom_import.py` is enforced (QQBot adapter does not import from `wecom_service`).
6. No new channel-core modules are created.

**Plans:** 3/3 plans complete

Plans:

- [x] 65-01-PLAN.md — Wave 0 + sender put_json/ack_interaction + verify_and_ack two-tier ACK (INGRESS-06)
- [x] 65-02-PLAN.md — Honest live metadata across 6 Protocol methods + flag default-OFF CI fixture path (ADAPTER-01/02)
- [x] 65-03-PLAN.md — no-wecom / freeze / deps=[] / privacy metadata safety gates (ADAPTER-03 + ADAPTER-04)

### Phase 66: Feedback Loop Parity + Interaction Recall

**Goal:** QQ Bot feedback loop is wired end-to-end (keyboard card dispatch → user button click → INTERACTION_CREATE → FeedbackEvent normalization → feedback-service dedupe/classify/queue); interaction ACK is sent after feedback normalization; feedback dedupe uses `msg_id` + button identity; `is_wakeup` interaction recall is supported for over-window long-task completion.
**Depends on:** Phase 65
**Requirements:** FEEDBACK-01, FEEDBACK-02, FEEDBACK-03, RECALL-01
**Success Criteria** (what must be TRUE):

1. End-to-end feedback wiring: keyboard card dispatch → user button click → INTERACTION_CREATE → FeedbackEvent normalization → feedback-service dedupe/classify/queue.
2. Interaction ACK (`PUT /interactions/{id}`) is sent after feedback normalization.
3. Feedback dedupe uses `msg_id` + button identity, preventing duplicate `FeedbackEvent` records.
4. `is_wakeup` interaction recall is supported for over-window long-task completion (windowed: 30-day periods, 1 per period).
5. Parity with WeCom feedback pipeline is achieved.

**Plans:** 3/3 plans complete

Plans:

- [x] 66-01-PLAN.md — FEEDBACK-03 idempotency stamp + feedback_ingress helper + Wave 0 RED tests
- [x] 66-02-PLAN.md — FEEDBACK-01 queue parity + FEEDBACK-02 ACK no-op-if-sent
- [x] 66-03-PLAN.md — RECALL-01 C2C is_wakeup period gate + ADAPTER-04 safety gates

### Phase 67: One-Click Smoke-Test Toolkit

**Goal:** One-click smoke-test CLI validates signature verification, sends text + markdown+keyboard, simulates callback, and collects sanitized evidence via env-var credential injection; `--dry-run` mode runs without live platform for CI; operator runbook documents the full process; evidence output is sanitized.
**Depends on:** Phase 66
**Requirements:** SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04
**Success Criteria** (what must be TRUE):

1. `scripts/smoke_test.py` CLI validates signature, sends text + markdown+keyboard, simulates callback, and collects sanitized evidence via env-var credential injection.
2. `--dry-run` mode runs without live QQ Bot platform connection (CI-able), validating envelope structure, signature logic, and evidence format with fixture credentials.
3. `runbook/SMOKE_TEST_RUNBOOK.md` documents credential setup, env-var injection, command sequence, expected outputs, and evidence collection format.
4. Evidence output is sanitized (no tokens, no raw user payloads, no attachment URLs).
5. Live run remains a human gate (not an autonomous deliverable).

**Plans:** 3/3 plans complete

Plans:

- [x] 67-01-PLAN.md — Wave 0 smoke tests + dry-run CLI (signature, text+keyboard, callback Fake path)
- [x] 67-02-PLAN.md — Sanitized evidence schema + operator SMOKE_TEST_RUNBOOK
- [x] 67-03-PLAN.md — Live env fail-closed path + ADAPTER-04 / qqbot-channel regression

## Completed Milestones

<details>
<summary>✅ v1.7 M3 Platform Extensions (Phases 45-57.1) — SHIPPED 2026-07-06</summary>

- [x] Phase 45: M3 Pre-Implementation Safety (4/4 plans) — completed 2026-07-06
- [x] Phase 46: Streaming Events (A1) (1/1 plan) — completed 2026-07-06
- [x] Phase 47: Artifact Return (A2) (3/3 plans) — completed 2026-07-06
- [x] Phase 48: Multi-Provider Runners (A3) (3/3 plans) — completed 2026-07-06
- [x] Phase 49: Session Memory Wiring (A4) (3/3 plans) — completed 2026-07-06
- [x] Phase 50: MCP Connector Registry (B1) (3/3 plans) — completed 2026-07-06
- [x] Phase 51: RBAC (C1) (3/3 plans) — completed 2026-07-06
- [x] Phase 52: Skill Registry Write (B2) (2/2 plans) — completed 2026-07-06
- [x] Phase 53: Hybrid Routing (B3) (2/2 plans) — completed 2026-07-06
- [x] Phase 54: Model Provider Gateway (B4) (3/3 plans) — completed 2026-07-06
- [x] Phase 55: Multi-Agent Runtime Adapter (B5) (1/1 plan) — completed 2026-07-06
- [x] Phase 56: Multi-Tenant Isolation (C2) (2/2 plans) — completed 2026-07-06
- [x] Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4) (1/1 plan) — completed 2026-07-06
- [x] Phase 57.1: Gap Closure — TenantGuard wiring (1/1 plan) — completed 2026-07-07

</details>

<details>
<summary>✅ v1.6 M2 Multi-Backend & Platform Extensions (Phases 36-44) — SHIPPED 2026-07-04</summary>

- [x] Phase 36: M2 Pre-Implementation Safety
- [x] Phase 37: Skill Registry Read
- [x] Phase 38: Router Service
- [x] Phase 39: Codex Adapter Prototype
- [x] Phase 40: Provider Model Adapter Prototype
- [x] Phase 41: Conversation Read-View Completion
- [x] Phase 42: Admin Console API
- [x] Phase 43: QQBot Channel loop
- [x] Phase 44: M2 Gate Integration & Full Suite Verification

**Full archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.5 V2 Acceptance Closure (Phases 33-35) — SHIPPED 2026-07-03</summary>

- [x] Phase 33: V2 Requirement Audit & Traceability Infrastructure
- [x] Phase 34: V2 Code Gap Closure
- [x] Phase 35: V2 Acceptance Readiness Report & Traceability Update

**Full archive:** [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)

</details>

## Backlog

No active backlog. v1.8 QQBot Channel Production roadmap defined (Phases 58-67).

---
*Last updated: 2026-07-07 after v1.8 QQBot Channel Production roadmap creation*
