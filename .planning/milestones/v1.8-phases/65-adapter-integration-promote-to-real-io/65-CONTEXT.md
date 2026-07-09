# Phase 65: Adapter Integration — Promote to Real IO - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQBotChannelAdapter is promoted from fixture-only to real IO across all 6 frozen Protocol methods, with QQ-specific behavior encoded via metadata fields; `qqbot_channel_enabled` flag gates real IO; fixture path is preserved for CI when flag off; two-tier ACK is implemented; `test_no_wecom_import.py` enforced; no new channel-core modules.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- All 6 frozen ChannelAdapter Protocol methods gain real IO behind `qqbot_channel_enabled` (default OFF)
- QQ-specific behavior ONLY via ChannelDelivery.metadata, AckResponse.metadata, ChannelCapabilitySet.metadata
- Two-tier ACK: op=12 HTTP 200 for messages + PUT /interactions/{id} for button clicks (INGRESS-06)
- Fixture path preserved when flag off (CI)
- No wecom_service imports; dependencies=[]; no frozen Protocol/platform-contract/channel-core module edits
- No new channel-core modules
- Compose existing Phase 59–64 modules (signature, normalization, token, sender, session/ingress runtime)

</decisions>

<code_context>
## Existing Code Insights

Prior phases built signature, normalization, token_manager, sender, session_runtime, ingress_runtime. This phase wires them into adapter Protocol methods.

</code_context>

<specifics>
## Specific Ideas

Requirements: ADAPTER-01, ADAPTER-02, ADAPTER-03, INGRESS-06.

</specifics>

<deferred>
## Deferred Ideas

Feedback loop end-to-end and interaction recall are Phase 66. Smoke toolkit is Phase 67.

</deferred>
