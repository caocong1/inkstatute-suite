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
- **v1.8 QQBot Channel Production** - Phases 58-67 (planning). Promote the QQBot channel from v1.6 fixture-only proof to a complete V2 production-grade channel loop aligned with WeCom behavior (including QQ-platform-required differences), and deliver a one-click live-platform smoke-test toolkit. 28 requirements, 10 phases.

## Phases

<details>
<summary>🔵 v1.8 QQBot Channel Production (Phases 58-67) — PLANNING</summary>

- [ ] Phase 58: v1.8 Pre-Implementation Safety — verify 24 V2 gates green baseline, frozen ChannelAdapter Protocol / BackendAdapter Protocol / platform-contract enums / channel-core modules unmodified, `qqbot_channel_enabled` flag default-off, `test_no_wecom_import.py` passes, `dependencies = []` invariant holds. *(ADAPTER-04; cross-cutting safety criterion for all v1.8 phases)*
- [ ] Phase 59: Ed25519 Signature Verification + Validation Challenge — `signature.py` (Ed25519 key derivation from BotSecret, verify `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + raw_body`, sign op=13 challenge `{event_ts + plain_token}`); reject unverified callbacks with HTTP 401; tests with official QQ demo vectors. *(INGRESS-01, INGRESS-02)*
- [ ] Phase 60: QQ Event Normalization — `normalization.py` (parse gateway envelope `{op, t, d}` → typed event categories; C2C/GROUP_AT_MESSAGE_CREATE → `AgentTurn` with @-bot prefix stripped and scene-aware `conversation_id`; INTERACTION_CREATE → `FeedbackEvent` with `source="card_button"` frozen enum); fixture files + tests. *(INGRESS-03, INGRESS-04, INGRESS-05)*
- [ ] Phase 61: Access Token Manager — `token_manager.py` (appId + clientSecret → `POST /getAppAccessToken`, 7200s TTL cache, auto-refresh 60s before expiry, single-flight via `asyncio.Lock`); tests for lifecycle, concurrent refresh, error handling. *(EGRESS-01)*
- [ ] Phase 62: QQ Egress Sender — Text + Markdown + Keyboard — `sender.py` (text `msg_type=0` with `msg_id`+`msg_seq` dedupe + retry; markdown+keyboard `msg_type=2` with callback buttons up/down/needs_fix/route_wrong; markdown `msg_type=2` for structured legal answers; passive-reply window tracking C2C 60min/4 + group 5min/5 with window-expiry delivery failure + interim service notice; output boundary enforcement); `adapter.py` `deliver()` modification. *(EGRESS-02, EGRESS-03, EGRESS-04, EGRESS-07)*
- [ ] Phase 63: QQ Rich Media Inbound + Egress (P2) — parse `attachments[]` (image/voice/video/file) → `AttachmentRef` with reference-only policy (`raw_payload_ref`, no raw payload storage); two-step upload (`POST /v2/.../files` → `file_info` → `msg_type=7`) for DOCX/PDF legal document delivery with retry + evidence collection. *(EGRESS-05, EGRESS-06)*
- [ ] Phase 64: QQBotSessionRuntime + QQBotIngressRuntime — `session_runtime.py` (orchestrate continuous conversation via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator`, composing `platform_runtime` primitives directly, no `wecom_service` import); `ingress_runtime.py` (callback → turn → session runtime); scene-aware conversation identity `qqbot:{scene}:{scene_id}:{user_openid}`; interrupt resume across user replies; memory recall (pre-turn recall + post-turn retention) with fail-open degradation. *(SESS-01, SESS-02, SESS-03)*
- [ ] Phase 65: Adapter Integration — Promote to Real IO — `adapter.py` full modification (all 6 frozen Protocol methods gain real IO behind `qqbot_channel_enabled` flag; QQ-specific behavior via `ChannelDelivery.metadata`, `AckResponse.metadata`, `ChannelCapabilitySet.metadata`; two-tier ACK: op=12 HTTP 200 for messages + `PUT /interactions/{id}` for button clicks); fixture path preserved for CI when flag off; `test_no_wecom_import.py` enforced; no new channel-core modules. *(ADAPTER-01, ADAPTER-02, ADAPTER-03, INGRESS-06)*
- [ ] Phase 66: Feedback Loop Parity + Interaction Recall — end-to-end feedback wiring (keyboard card dispatch → user button click → INTERACTION_CREATE → FeedbackEvent normalization → feedback-service dedupe/classify/queue); interaction ACK after feedback normalization; feedback dedupe via `msg_id` + button identity; `is_wakeup` interaction recall for over-window long-task completion (windowed 30-day periods, 1 per period); parity with WeCom feedback pipeline. *(FEEDBACK-01, FEEDBACK-02, FEEDBACK-03, RECALL-01)*
- [ ] Phase 67: One-Click Smoke-Test Toolkit — `scripts/smoke_test.py` (CLI: validate signature, send text + markdown+keyboard, simulate callback, collect sanitized evidence via env-var credential injection); `--dry-run` mode for CI (fixture credentials, no live platform); `runbook/SMOKE_TEST_RUNBOOK.md` (credential setup, env-var injection, command sequence, expected outputs, evidence format); sanitized evidence output (no tokens, no raw payloads, no attachment URLs). Live run remains a human gate. *(SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04)*

**Cross-cutting safety (ADAPTER-04):** All 24 existing V2 gates must remain green throughout v1.8; frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified. This is a success criterion in every v1.8 phase.

</details>

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
- [x] Phase 43: QQBot Channel Loop
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
