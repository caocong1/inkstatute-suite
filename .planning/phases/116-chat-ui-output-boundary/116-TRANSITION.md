---
phase: 116-chat-ui-output-boundary
next_phase: 117-legal-guardrails
carry_forward:
  - ChatController is ready for guardrail integration (Phase 117)
  - Approval card UI is ready for guardrail enforcement
  - Output boundary is in place — guardrails will add additional filtering
  - Session database schema supports approval records
---

# Phase 116 Transition: Chat UI → Guardrails

## What Phase 116 Delivered

- Single chat UI implementation under `lib/chat/`
- Output boundary filtering all non-assistant noise
- Approval cards (allow/reject, no batch, unknown kinds denied)
- Clarification cards (`[CLARIFY:]` parsing, follow-up as new prompt)
- Citation badges (verified/retrieved/unverified) + human-review badges
- Error mapping (engineNotStarted, rateLimited, authFailed, timeout)
- Local SQLite session store with CRUD, grouping, deletion, export
- Full app shell with navigation drawer and chat view

## What Phase 117 (Legal Guardrails) Needs

Phase 117 builds the non-bypassable legal guardrails on top of the chat UI:

1. **Preset prompt segments** — Legal guardrail prompts injected into DSH system prompt
2. **App-side enforcement** — Additional output filtering beyond the output boundary:
   - Citation audit enforcement (verified/retrieved/unverified must be present)
   - `[HUMAN_REVIEW:]` markers must be preserved and visually distinct
   - High-risk legal conclusions must not be auto-finalized
3. **Approval enforcement** — The approval card path must be the only way to approve tool execution; no bypass
4. **Negative regression tests** — Guardrail bypass attempts must fail

## Carry-Forward Notes

- `ChatController` (lib/chat/chat_controller.dart) is the integration point for guardrail enforcement
- `OutputBoundary` (lib/chat/output_boundary.dart) is the base filter; guardrails add additional layers
- `ApprovalCardWidget` already enforces no-batch-approval; guardrails add policy enforcement
- `SessionDatabase` schema has `approvals` table ready for guardrail audit records
- `TextParser` already extracts `[CLARIFY:]` and `[HUMAN_REVIEW:]` markers; guardrails enforce their presence

## Architecture Decisions for Phase 117

- Guardrails are **non-bypassable**: both preset prompt segments AND app-side enforcement must be present
- Negative regression tests: removing either layer must cause test failure
- The approval path is the **only** way to approve tool execution
- Citation audit is enforced at the app layer, not just the prompt layer
