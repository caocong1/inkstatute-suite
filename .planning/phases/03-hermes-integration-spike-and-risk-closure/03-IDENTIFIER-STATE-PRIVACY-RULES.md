# Phase 03 Identifier, State, Privacy, and Safety Rules

**Plan:** 03-03  
**Created:** 2026-06-27T18:33:17Z  
**Scope:** Documentation-only rules for Phase 4+ mapper and feedback-service work.

## Status Tags

- `confirmed`: Repo-local platform contract, schema, fixture, or planning evidence is enough for the contract-side rule.
- `assumed`: A provisional design rule is recorded, but must be replaced by Hermes source/runtime evidence before production dependency.
- `requires Hermes source/runtime`: Hermes source, sanitized callback samples, runtime logs, or storage policy are required before implementation can claim the detail.
- `unavailable`: No usable Hermes signal is known yet; do not approximate silently.
- `blocked`: Production work must stop until evidence or an explicit fallback is selected.

## Evidence Boundary

This document follows Phase 03 decisions D-05, D-06, D-07, and D-09. The repository contains the platform contract fields and synthetic fixture patterns, but it does not contain Hermes runtime source, `response_filter`, `template_card_dispatcher`, `wecom_template_card_shim`, `pending_previews.jsonl`, `feedback.jsonl`, callback samples, long-task logs, raw payload stores, or retention policy evidence.

PRD descriptions are treated as specification evidence, not source-confirmed Hermes API evidence. Any field that depends on real callback payloads, card payloads, preview rows, long-task signals, or storage location remains `requires Hermes source/runtime`.

## Identifier and Feedback Association Rules

### D-05 Canonical Association Graph

D-05 requires one traceable feedback target per user-visible response. The contract-side graph is:

```text
AgentTurn.turn_id
  -> RouteDecision.turn_id
  -> ExecutionTrace.turn_id
  -> AgentResult.turn_id
  -> AgentResult.result_id
  -> AgentResult.feedback_target
  -> FeedbackEvent.result_id
  -> FeedbackEvent.feedback_target
  -> FeedbackEvent.raw_payload_ref
```

Hermes-side association candidates are:

```text
message_id
  -> pending_previews.jsonl row
  -> template_card_id
  -> callback_event_id
  -> feedback.jsonl row
```

The joining rule is:

| Link | Rule | Status |
|------|------|--------|
| `AgentTurn.turn_id` -> `AgentResult.turn_id` | Must match exactly for all records in the same task. | confirmed |
| `AgentResult.result_id` -> `FeedbackEvent.result_id` | Must match when Hermes feedback can be associated with a specific result. If unavailable, the feedback must still carry `turn_id`, `conversation_id`, and `feedback_target`. | confirmed |
| `AgentResult.feedback_target` -> `FeedbackEvent.feedback_target` | Must match exactly for feedback tied to a user-visible response. | confirmed |
| `message_id` -> `feedback_target` | Allowed only if Hermes source/runtime confirms the same `message_id` survives `response_filter`, `pending_previews.jsonl`, template card dispatch, callback payload, and `feedback.jsonl`. | requires Hermes source/runtime |
| `template_card_id` -> `feedback_target` | May support association, but must not replace the canonical `feedback_target` unless source/runtime shows a one-card-per-response invariant. | requires Hermes source/runtime |
| `callback_event_id` -> `feedback_id` / `idempotency_key` | Prefer as native callback identity if Hermes/WeCom exposes one. | requires Hermes source/runtime |

### Canonical Feedback Target Selection

1. If source/runtime confirms `message_id` is stable across `response_filter`, `pending_previews.jsonl`, template card dispatch, callback payload, and `feedback.jsonl`, set `AgentResult.feedback_target = FeedbackEvent.feedback_target = message_id`.
2. Otherwise, use a derived key candidate assembled only from confirmed runtime fields and mark the rule `assumed` until samples prove it. The candidate shape is `channel:conversation_or_session:message_or_result:card_or_callback`.
3. If a field in the derived key is not confirmed, do not invent a replacement. Mark the field `requires Hermes source/runtime` and keep the Phase 4 implementation blocked for that association.
4. The chosen canonical value must be stable for replay and must be written consistently to `AgentResult.feedback_target` and normalized `FeedbackEvent.feedback_target`.

### Multi-Card and Repeated Callback Handling

- Each user-visible response must have one canonical `feedback_target`.
- Multiple template cards for the same response must map back to that canonical target. Card-level identifiers such as `template_card_id` may be retained in metadata, but they are not the contract association key unless source/runtime proves a single card is the response.
- Duplicate cards, network retries, repeated button clicks, and repeated shim writes must normalize to one canonical `FeedbackEvent` per idempotency rule.
- If the same response creates multiple meaningful feedback surfaces, Phase 4 must either prove they share one response-level target or record separate `AgentResult` records. Do not merge unrelated responses under one target.
- `pending_previews.jsonl` and `feedback.jsonl` are input references for association, not contract authorities. Their field names and retention behavior remain `requires Hermes source/runtime`.

## Feedback Idempotency Rules

The normalized feedback processor must compute an `idempotency_key` using this ladder:

| Priority | Key Source | Rule | Status |
|----------|------------|------|--------|
| 1 | Native callback id | Use `callback_event_id` or equivalent native callback id if Hermes/WeCom provides one and it is stable across retries. | requires Hermes source/runtime |
| 2 | Derived callback tuple | Use `feedback_target + action + user_id + created_at_bucket` when all fields are confirmed. `created_at_bucket` should be coarse enough to collapse transport retries, but not broad enough to merge distinct user actions. | assumed |
| 3 | Payload fingerprint | Use `raw_payload_hash` only as metadata, with the raw callback payload stored by reference through `raw_payload_ref`. Do not store the full callback raw payload in contract logs. | assumed |

The selected `idempotency_key` belongs in normalized metadata until the contract schema explicitly adds a top-level field. It must not depend on unconfirmed callback fields without a `requires Hermes source/runtime` note.

## D-09 Skill Candidate and Legal Safety Rules

Route mismatch, repeated negative feedback, or unknown-task evidence may create `skill_candidate` data, but V2 records candidates only. The following rules are mandatory:

- `route_mismatch=true` feedback must set `skill_candidate.requires_human_review=true` when a candidate is detected.
- Any feedback that suggests modifying legal conclusion skills, statute references, cause-of-action judgments, jurisdiction judgments, liability conclusions, or lawyer-facing legal analysis must set `requires_human_review`.
- Feedback normalization must not auto-modify legal skills, must not call automatic skill synthesis, and must not trigger direct `skillopt-runner` edits for high-risk legal work.
- Candidate evidence must reference `feedback_id`, `turn_id`, `result_id`, `feedback_target`, or `raw_payload_ref`; it must not embed sensitive legal/customer payload text.
- If Hermes runtime has an existing skill optimization flow, the boundary between normalized feedback and that flow is `requires Hermes source/runtime` until source confirms no automatic legal modification is triggered.

## Phase 4/6 Inputs

Phase 4 mapper work can consume the confirmed contract-side graph now. Phase 4/6 implementation must still obtain Hermes source/runtime evidence for:

1. Stable propagation of `message_id` through response filter, preview storage, template card dispatch, callback payload, and feedback rows.
2. Actual `template_card_id`, `callback_event_id`, callback action, user id, and timestamp field names.
3. Whether `feedback.jsonl` already contains enough fields to populate `FeedbackEvent.result_id`, `FeedbackEvent.feedback_target`, and `raw_payload_ref`.
4. Whether existing Hermes skill optimization can be invoked only after explicit human review.
