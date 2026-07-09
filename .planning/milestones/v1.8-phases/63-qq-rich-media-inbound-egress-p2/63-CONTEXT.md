# Phase 63: QQ Rich Media Inbound + Egress (P2) - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQ Bot rich media inbound (image/voice/video/file `attachments[]`) is parsed into `AttachmentRef` records with reference-only policy; rich media egress uses two-step upload for DOCX/PDF legal document delivery with retry and evidence collection.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints:
- Reference-only policy: `raw_payload_ref`, no raw payload storage
- Two-step upload: `POST /v2/.../files` → `file_info` → `msg_type=7` for DOCX/PDF
- Retry + sanitized evidence collection on egress failures
- Reuse Phase 61 TokenManager + Phase 62 MessageTransport patterns
- `dependencies = []`; no wecom_service imports
- Do not modify frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, or channel-core modules
- Prefer extending normalization.py / sender.py rather than new channel-core modules

</decisions>

<code_context>
## Existing Code Insights

Prior: Phase 61 TokenManager, Phase 62 sender envelopes + MessageTransport. Codebase context gathered during research.

</code_context>

<specifics>
## Specific Ideas

Requirements: EGRESS-05, EGRESS-06.
Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
