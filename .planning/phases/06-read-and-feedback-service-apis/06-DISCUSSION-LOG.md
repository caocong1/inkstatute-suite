# Phase 6: Read and Feedback Service APIs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-28T07:12:00Z
**Phase:** 6-read-and-feedback-service-apis
**Mode:** auto
**Areas discussed:** read model authority, API surface, task identity, feedback queue behavior, privacy and ordering

---

## Read Model Authority

| Option | Description | Selected |
|--------|-------------|----------|
| Contract logs primary | Build read views from V2 contract event logs; any cache is derived and rebuildable. | yes |
| Hermes sessions primary | Use Hermes sessions.db as the read API source. | |
| New authoritative DB | Create a new conversation/task database. | |

**Auto choice:** Contract logs primary.
**Notes:** Matches PRD and AGENTS.md. Hermes sessions are fallback-only and must be explicitly labeled Hermes-specific.

---

## API Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Pure handlers first | Implement dependency-light route handlers callable by tests; optional stdlib wrapper later. | yes |
| Web framework now | Add a runtime HTTP framework immediately. | |
| CLI-only views | Provide no GET-shaped route surface. | |

**Auto choice:** Pure handlers first.
**Notes:** Keeps dependency footprint aligned with existing packages while still supporting the required GET semantics.

---

## Task Identity

| Option | Description | Selected |
|--------|-------------|----------|
| `metadata.task_id` then `turn_id` | Prefer explicit task id when present; otherwise treat `turn_id` as canonical task id. | yes |
| Add top-level `task_id` schema field | Change platform schemas for read-view convenience. | |
| Use `trace_id` as task id | Collapse task and execution trace identity. | |

**Auto choice:** `metadata.task_id` then `turn_id`.
**Notes:** Avoids schema churn and preserves lookup by task id plus `trace_id`.

---

## Feedback Queue Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Derived pending queue | Produce pending queue items from normalized `FeedbackEvent` records and compatibility inputs. | yes |
| Durable queue service | Add persistent queue infrastructure in Phase 6. | |
| Skillopt integration | Feed route mismatch directly into automatic skill modification. | |

**Auto choice:** Derived pending queue.
**Notes:** Route mismatch must remain human-reviewed with `skill_candidate` evidence and `no_auto_modify` metadata.

---

## Privacy and Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Reference-first, ordered replay | Use `raw_payload_ref`, reject raw payloads, and sort/group by envelope timestamps and sequence. | yes |
| Store full payloads for coverage | Preserve raw callback/legal text in read views for completeness. | |
| Ignore ordering gaps | Assume logs arrive in perfect order. | |

**Auto choice:** Reference-first, ordered replay.
**Notes:** Matches contract-log privacy baseline and PRD ordering risks.

---

## the agent's Discretion

- Exact module names and dataclass names inside `services/conversation-read-view/`.
- Whether to include a stdlib HTTP wrapper after pure handlers.
- Exact fixture names, as long as they distinguish contract-log, feedback-input, and API-response evidence.

## Deferred Ideas

- Admin console UI.
- Durable production queue service.
- Database-backed materialized views.
- CI workflow gates.
- Trial acceptance reporting.
