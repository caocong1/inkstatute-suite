# Phase 5: WeCom Shadow Loop Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28T03:05:00Z
**Phase:** 5-WeCom Shadow Loop Validation
**Areas discussed:** Live deployment boundary, Evidence shape, Feedback normalization depth, Identifier and callback association, Privacy and safety gates
**Mode:** `--auto` — all gray areas selected; recommended defaults chosen without user prompts.

---

## Live Deployment Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Opt-in validation only | Document or script live hook deployment behind an explicit, reversible step; repo tests never mutate Hermes runtime. | ✓ |
| Direct runtime mutation | Copy/symlink into `/home/sorawatcher/.hermes` during phase execution. | |
| Fixture-only | Avoid live deployment entirely and validate only synthetic streams. | |

**User's choice:** Auto-selected: Opt-in validation only.
**Notes:** Matches AGENTS.md and Phase 4 boundary: live Hermes behavior must be preserved, and repo tests must not mutate runtime state.

---

## Evidence Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Live evidence plus fixture fallback | Produce fixture-backed checks and a clearly separated live WeCom evidence/runbook path; mark live blockers honestly. | ✓ |
| Live evidence only | Block all work until a live lawyer channel run is available. | |
| Synthetic evidence as acceptance | Treat fixtures as sufficient for Phase 5 live validation. | |

**User's choice:** Auto-selected: Live evidence plus fixture fallback.
**Notes:** Phase 5 must not claim live success from synthetic data, but planning can still deliver useful validators and runbooks when runtime access is unavailable.

---

## Feedback Normalization Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal validation normalizer | Convert sanitized `feedback.jsonl` and `pending_previews.jsonl` samples into schema-valid `FeedbackEvent` evidence. | ✓ |
| Full feedback-service | Implement production APIs, broad classification, dedupe, and pending queues now. | |
| No feedback normalization | Only verify AgentResult logs and leave FeedbackEvent proof to Phase 6. | |

**User's choice:** Auto-selected: Minimal validation normalizer.
**Notes:** This satisfies the Phase 5 loop proof while leaving Phase 6 responsible for the full feedback-service API and queue surface.

---

## Identifier and Callback Association

| Option | Description | Selected |
|--------|-------------|----------|
| Source-confirmed `message_id` chain | Use `message_id` as `feedback_target` only when response preview, card callback, and feedback row evidence line up. | ✓ |
| Always trust `message_id` | Assume mapper output is enough even without callback evidence. | |
| Generate a new feedback target | Create a V2-only target independent of Hermes card data. | |

**User's choice:** Auto-selected: Source-confirmed `message_id` chain.
**Notes:** Phase 3 identified message stability as a runtime gate. Phase 5 must prove it or record a blocker.

---

## Privacy and Safety Gates

| Option | Description | Selected |
|--------|-------------|----------|
| Reference-first sanitized evidence | Use `raw_payload_ref`, sanitized samples, temporary logs, and human-review skill candidates. | ✓ |
| Store full callback/task bodies for debugging | Keep full raw payloads in repo artifacts to simplify replay. | |
| Auto-forward skill candidates | Let route-mismatch feedback update skill flows automatically. | |

**User's choice:** Auto-selected: Reference-first sanitized evidence.
**Notes:** Keeps legal/customer material out of contract logs and preserves the V2 no-auto-modify safety rule.

---

## the agent's Discretion

- Exact names for Phase 5 validation fixtures, scripts, and evidence documents.
- Whether minimal feedback normalization lives as test support, a small module under `services/feedback-service/`, or contract-test-suite helper code, as long as Phase 6 boundaries are preserved.
- How to structure live validation blockers when WeCom runtime access is unavailable.

## Deferred Ideas

- Full feedback-service API, pending queue export, and production classification workflow.
- Conversation-read-view APIs.
- CI workflow enforcement and coverage gates.
- Five-workday lawyer trial acceptance metrics.
