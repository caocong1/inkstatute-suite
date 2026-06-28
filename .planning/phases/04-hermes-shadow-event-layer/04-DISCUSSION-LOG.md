# Phase 4: Hermes Shadow Event Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-28T01:47:53Z
**Phase:** 4-Hermes Shadow Event Layer
**Areas discussed:** Hook placement and deployment shape, Mapper scope, Writer/log contract, Replay and verification
**Mode:** Auto-selected recommended defaults from Phase 3 evidence and V2 scope.

---

## Hook Placement and Deployment Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Repo-owned hook artifact sorted after `response_filter` | Add artifact under `services/hermes-contract-layer/`, with a directory such as `response_filter_contract_result_recorder/` and manifest `name: contract_result_recorder`. | x |
| Directly modify local Hermes runtime/profile | Copy files into `/home/sorawatcher/.hermes/...` during Phase 4 implementation. | |
| Inline recording inside `response_filter` | Couple recording to the existing filter hook for strongest order guarantee. | |

**User's choice:** Auto-selected repo-owned hook artifact sorted after `response_filter`.
**Notes:** Phase 3 source evidence proves a plain `contract_result_recorder/` directory runs too early. Direct runtime mutation is not appropriate for repo implementation without explicit deployment instruction.

---

## Mapper Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Map AgentTurn, RouteDecision, ExecutionTrace, and AgentResult only | Keep feedback normalization for Phase 5/6 while preserving feedback target fields where available. | x |
| Also implement FeedbackEvent normalization | Read callback rows and normalize feedback in Phase 4. | |
| Only record AgentResult | Minimal hook output but insufficient for Phase 4 success criteria. | |

**User's choice:** Auto-selected four-event shadow mapping with honest feedback deferral.
**Notes:** This matches Phase 4 success criteria and avoids preempting feedback-service scope.

---

## Writer and Log Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Dependency-free JSONL writer with schema-valid event payloads | Append envelopes/payloads to a configured path; tests use temp files. | x |
| Database or queue-backed writer | Introduce runtime infrastructure for logs. | |
| Add top-level log fields to every event schema | Mutate payloads with `occurred_at`, `ingested_at`, and `seq` even where schemas disallow them. | |

**User's choice:** Auto-selected dependency-free JSONL writer.
**Notes:** Current schemas only expose top-level `occurred_at`, `ingested_at`, and `seq` on `ExecutionTrace`; other event payloads must stay schema-valid.

---

## Replay and Verification

| Option | Description | Selected |
|--------|-------------|----------|
| Add partial event-stream replay support where feedback is unavailable | Validate real Phase 4 event streams without fabricating feedback. | x |
| Force all hook-output fixtures into full five-event bundles | Preserve existing bundle harness at the cost of fake feedback records. | |
| Defer replay evidence to Phase 5 | Leaves Phase 4 without proof that hook output validates. | |

**User's choice:** Auto-selected partial event-stream replay support.
**Notes:** Existing full-bundle replay remains intact; Phase 4 can add explicit stream validation for AgentTurn, RouteDecision, ExecutionTrace, and AgentResult until feedback capture is in scope.

---

## the agent's Discretion

- Module names and internal helper decomposition inside `services/hermes-contract-layer/`.
- Exact JSONL envelope structure, provided payload validation and replay support are clear.
- Exact number of Phase 4 hook-output fixtures between 3 and 5, provided success/failure/simple-QA coverage is adequate.

## Deferred Ideas

- Runtime deployment into Hermes profile directories.
- Feedback-service callback normalization.
- Conversation read APIs.
- CI workflow wiring and coverage gates.
