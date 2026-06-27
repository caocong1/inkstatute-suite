# Phase 03 Hook and AgentTurn Decisions

**Plan:** 03-02  
**Created:** 2026-06-27T18:40:29Z  
**Scope:** Decision record for D-03 hook ordering and D-04 AgentTurn input strategy. This document is a Phase 3 spike artifact only and does not implement production hook code.

## Hook Ordering

**Decision ID:** D-03  
**Evidence basis:** `03-HOOK-ORDER-EVIDENCE.md`  
**Decision:** `BLOCKING_VERIFICATION_GAP`

`03-HOOK-ORDER-EVIDENCE.md` records `EVIDENCE_OUTCOME: blocking_gap` and `HOOK_ORDER_DECISION: BLOCKING_VERIFICATION_GAP`. Therefore Plan 03-02 cannot state a confirmed yes/no answer for whether `contract_result_recorder` can run after `response_filter` on `agent:end`.

The only locally available Hermes hook references are specification/planning references. No repo-local Hermes source/runtime evidence proves hook loader ordering, `HOOK.yaml` registration order, `handler.py` execution order, or whether `response_filter` context mutations are visible to a later same-event hook.

### Non-Decision

This plan does not approve a separate Phase 4 `contract_result_recorder` hook after `response_filter`.

This plan also does not reject the design permanently. It blocks the claim until Hermes source/runtime evidence or a sanitized tested probe exists.

### Fallback Options

Future Phase 4 planning must choose one of these before production implementation:

| Option | When Valid | Tradeoff |
|--------|------------|----------|
| record inside `response_filter` | Valid if Phase 4 accepts tighter coupling to the existing filtering hook and can preserve Hermes outbound behavior. | Strong ordering guarantee, but more coupling to existing response filtering. |
| record adjacent to `response_filter` | Valid if Hermes source shows a stable adjacent extension point with deterministic ordering and filtered context visibility. | Lower coupling than inline recording, but still requires source/runtime proof. |
| keep Phase 4 blocked until hook loader/order evidence exists | Required when neither source/runtime evidence nor sanitized probe evidence is available. | Safest privacy posture; delays production shadow recording. |

### Phase 4 Block Condition

Phase 4 must not implement a separate `contract_result_recorder` hook that depends on running after `response_filter` until `03-HOOK-ORDER-EVIDENCE.md` is replaced or amended with `EVIDENCE_OUTCOME: source_confirmed` or `EVIDENCE_OUTCOME: sanitized_probe_tested` and a concrete `HOOK_ORDER_DECISION` of `can_run_after_response_filter` or `cannot_run_after_response_filter`.

## AgentTurn Input Strategy

**Decision ID:** D-04  
**Preferred closure:** mount Hermes source/runtime and identify a stable inbound hook or session source for complete AgentTurn input.  
**Fallback while source is absent:** infer what is possible from `agent:end` context and preserve missing original input by reference only through `metadata.raw_payload_ref`.

The V2 PRD describes `agent:end` and `gateway:startup` as existing Hermes hook events and states that no `agent:start` event is currently exposed. In this repo that remains specification evidence, not source/runtime proof. `gateway:startup` may initialize gateway behavior, but it does not by itself provide per-turn inbound content.

### Reverse-Inference Boundary

When no inbound hook or stable source is confirmed, Phase 4 may only claim AgentTurn fields at the confidence levels below.

| AgentTurn Field | Fallback Source | Status | Limit |
|-----------------|-----------------|--------|-------|
| `turn_id` | Derived from available result/session identifiers at `agent:end` | requires Hermes source/runtime | Must be stable and deterministic; cannot be invented if source IDs are missing. |
| `conversation_id` | `session_id`, `chat_id`, or channel conversation field if present in `agent:end` context | requires Hermes source/runtime | Needs source confirmation of which field is canonical. |
| `channel` | Platform/gateway context at `agent:end` | requires Hermes source/runtime | PRD implies WeCom is the V2 acceptance channel, but runtime context field names are unconfirmed. |
| `user_id` | `user_id` in `agent:end` context if present | requires Hermes source/runtime | Must not use display names or raw account payloads as a substitute. |
| `message_type` | Inbound message metadata from session/context if retained | requires Hermes source/runtime | If absent, do not approximate from reply type. |
| `content` | Original user input from session/context if retained | requires Hermes source/runtime | May be incomplete when reverse-inferred after processing; use reference-only preservation for unavailable raw input. |
| `attachments` | Session/context attachment references if retained | requires Hermes source/runtime | Do not embed raw documents; only attachment references or artifact refs are allowed. |
| `output_constraints` | Session/context parsed constraints if retained | requires Hermes source/runtime | Do not infer constraints from final response formatting alone. |
| `received_at` | Inbound timestamp from session/context or gateway record if retained | requires Hermes source/runtime | Do not replace with `agent:end` time except as explicitly labeled derived metadata. |
| `industry_context` | Contract-layer classification or retained profile metadata | requires Hermes source/runtime | Legal-specific values belong here, not in platform top-level fields. |
| `metadata.raw_payload_ref` | Runtime-owned reference to inbound payload or session record | required when raw input is not embedded | Reference must not expose raw legal text, customer data, callback bodies, secrets, runtime DB rows, or logs in contract events. |

### Reference-Only Raw Input Policy

If the original inbound payload cannot be reconstructed safely, Phase 4 should set `metadata.raw_payload_ref` to a runtime-owned reference namespace and omit raw content rather than copying sensitive legal text into contract logs.

Allowed examples are reference-shaped values such as `hermes://session/{id}/turn/{id}` or another Phase 4 source-confirmed namespace. The namespace, retention owner, and redaction path remain `requires Hermes source/runtime` until mounted evidence exists.

### Phase 4 Gate

Before production implementation can claim AgentTurn content coverage, Phase 4 must provide:

1. Hermes source/runtime evidence for an inbound hook or stable session/context fields.
2. A mapping from Hermes fields to `turn_id`, `conversation_id`, `channel`, `user_id`, `message_type`, `content`, `attachments`, `output_constraints`, `received_at`, `industry_context`, and `metadata.raw_payload_ref`.
3. Privacy proof that raw legal/customer payloads remain referenced, minimized, or redacted rather than embedded in contract logs.
4. A documented fallback for any field that remains unavailable.

Until then, AgentTurn reverse inference from `agent:end` is a limited fallback, not complete input coverage.
