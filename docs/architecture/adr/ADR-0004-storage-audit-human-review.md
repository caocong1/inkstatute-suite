# ADR-0004: Storage, Audit, And Legal Human Review

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

InkStatute records platform contract events for replay, audit, feedback, and
read views. Legal users may send sensitive documents, facts, and work product.
The platform also records route mismatch and skill candidate signals that could
affect future legal behavior.

## Decision

Contract logs are reference-first. Raw source material is represented by
references such as `raw_payload_ref`, artifact references, hashes, or secret
reference names. Logs must not store runtime callback bodies, customer legal
payloads, runtime databases, logs, media files, or plaintext secrets by default.

High-risk legal feedback remains human-reviewed. Feedback that could modify
legal conclusions, law citations, risk judgments, jurisdiction analysis, or
legal skills may record a `skill_candidate`, but it must not auto-synthesize or
auto-apply a legal skill change.

Audit records should describe blocked, rewritten, or dropped output-policy
events without storing sensitive raw text unless a later approved retention
policy explicitly allows it.

## Consequences

The platform can build useful read views and replay evidence while preserving
privacy and legal safety defaults. Human review remains the control point for
high-risk legal evolution.

The tradeoff is that some debugging workflows require looking up external
payload references rather than reading full payloads directly from contract logs.

## Verification Notes

Privacy and boundary tests must reject committed secrets, raw payload content,
runtime databases, logs, and customer materials. Feedback tests must preserve
`requires_human_review` for high-risk legal skill candidates.

