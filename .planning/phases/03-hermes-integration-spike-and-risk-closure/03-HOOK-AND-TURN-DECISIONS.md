# Phase 03 Hook and AgentTurn Decisions

**Plan:** 03-02  
**Updated:** 2026-06-28T09:15:50+08:00  
**Scope:** Decision record for D-03 hook ordering and D-04 AgentTurn input strategy. This document is a Phase 3 spike artifact only and does not implement production hook code.

## Hook Ordering

**Decision ID:** D-03  
**Evidence basis:** `03-HOOK-ORDER-EVIDENCE.md`  
**Decision:** `can_run_after_response_filter`

Hermes source confirms that `contract_result_recorder` can run after `response_filter` on `agent:end` when the recorder hook directory sorts lexicographically after `response_filter`. The hook manifest name is not the ordering key; the directory name is.

The required source rule is:

1. `HookRegistry.discover_and_load()` scans `HERMES_HOME/hooks` with `sorted(HOOKS_DIR.iterdir())`.
2. Each matching `HOOK.yaml` event appends that hook's `handle` function to the event handler list.
3. `emit("agent:end", context)` calls the handlers in registered order and passes one mutable `context` dict.
4. The lawfirm `response_filter` hook sets `context["message_id"]` and `context["response"]`; a later same-event hook can read those fields.

### Implementation Boundary

A recorder directory named exactly `contract_result_recorder` would run before `response_filter` because `contract_result_recorder` sorts before `response_filter`. Phase 4 must use an after-filter directory name, such as `response_filter_contract_result_recorder` or `zz_contract_result_recorder`, while keeping the manifest name `contract_result_recorder`.

Phase 4 must also account for the gateway emission shape: `agent:end` receives `{**hook_ctx, "response": (response or "")[:500]}` from `gateway/run.py`. That means the recorder can observe the hook context response and the `message_id` written by `response_filter`, but it must not claim complete outbound response capture from this hook alone until a full-response source is confirmed.

### Fallback Options

Future Phase 4 planning may still choose one of these if the sorted-directory constraint is undesirable in deployment:

| Option | When Valid | Tradeoff |
|--------|------------|----------|
| record inside `response_filter` | Valid if Phase 4 accepts tighter coupling to the existing filtering hook and can preserve Hermes outbound behavior. | Strong ordering guarantee, but more coupling to existing response filtering. |
| record adjacent to `response_filter` | Valid if implemented as a source-confirmed adjacent extension point or a hook directory sorted after `response_filter`. | Lower coupling than inline recording, but the naming/order rule must be enforced. |
| keep Phase 4 blocked until hook loader/order evidence exists | Required only for deployments that do not match the source-confirmed loader behavior. | Safest privacy posture; delays production shadow recording. |

### Phase 4 Gate

Phase 4 may start separate recorder implementation when it explicitly encodes the after-filter directory-order rule and tests that the recorder observes `context["message_id"]` after `response_filter`.

Phase 4 remains blocked for any claim that requires:

- a canonical `contract_result_recorder/` directory to run after `response_filter`
- full untruncated outbound response capture from the current `agent:end` context
- raw legal/customer payload storage in contract logs

## AgentTurn Input Strategy

**Decision ID:** D-04  
**Preferred closure:** use the source-confirmed `agent:start` hook for available inbound turn metadata, then use runtime-owned references for any full input payload or attachment material not present in hook context.  
**Fallback while full source fields are absent:** use `agent:end` reverse inference only for stable identifiers that are already present and preserve missing original input by reference through `metadata.raw_payload_ref`.

Hermes source confirms `agent:start`, `agent:step`, and `agent:end` events in `gateway/hooks.py`; `gateway/run.py` emits `agent:start` before `_run_agent(...)` with platform, user, chat, thread, chat type, session id, and `message_text[:500]`. `gateway:startup` exists for gateway lifecycle hooks, but it does not provide per-turn inbound content.

### Field-Level Strategy

| AgentTurn Field | Preferred Source | Status | Limit |
|-----------------|------------------|--------|-------|
| `turn_id` | Derived by Phase 4 from source-confirmed session/message identifiers or a contract-layer deterministic id. | requires Hermes source/runtime | No native `turn_id` is present in `agent:start`; the derivation rule must be stable and replayable. |
| `conversation_id` | `session_id` from `agent:start` / `agent:end`; `chat_id` may be retained as channel metadata. | source_confirmed | Phase 4 must choose whether contract `conversation_id` is Hermes `session_id` or channel `chat_id`; do not use both interchangeably. |
| `channel` | `platform` from `agent:start` / `agent:end`. | source_confirmed | Value should be normalized to the contract vocabulary in Phase 4. |
| `user_id` | `user_id` from `agent:start` / `agent:end`. | source_confirmed | Must not substitute display names or raw account payloads. |
| `message_type` | Not present in `agent:start` hook context. | requires Hermes source/runtime | Do not infer from final response type. |
| `content` | `message` from `agent:start`, capped at 500 characters by gateway source. | source_confirmed_partial | Full inbound content requires a session/raw payload source or `raw_payload_ref`; do not embed sensitive full legal text by default. |
| `attachments` | No attachment list is present in the source-confirmed hook context. | requires Hermes source/runtime | Use attachment references only after a source field is confirmed. |
| `output_constraints` | No parsed output constraint field is present in the source-confirmed hook context. | unavailable | Do not infer constraints from final answer formatting alone. |
| `received_at` | Not present in `agent:start` hook context. | requires Hermes source/runtime | If needed, source a gateway event timestamp rather than substituting `agent:end` time. |
| `industry_context` | Contract-layer classification or source-confirmed profile metadata. | requires Hermes source/runtime | Legal/profile-specific values belong here, not in platform top-level fields. |
| `metadata.raw_payload_ref` | Runtime-owned reference to inbound payload, session record, attachment store, or sanitized callback source. | required when raw/full input is not embedded | Reference must not expose raw legal text, customer data, callback bodies, secrets, runtime DB rows, or logs in contract events. |

### Reverse-Inference Boundary

`agent:end` reverse inference is now a limited fallback rather than the preferred AgentTurn source. It may help join result-side records to an existing turn using `session_id`, `platform`, `user_id`, `chat_id`, and the capped `message`, but it is not sufficient for full input coverage, attachments, received timestamp, or raw payload storage policy.

### Reference-Only Raw Input Policy

If the original inbound payload cannot be reconstructed safely, Phase 4 should set `metadata.raw_payload_ref` to a runtime-owned reference namespace and omit raw content rather than copying sensitive legal text into contract logs.

Allowed examples are reference-shaped values such as `hermes://session/{id}/turn/{id}` or another Phase 4 source-confirmed namespace. The namespace, retention owner, and redaction path remain `requires Hermes source/runtime` until mounted evidence exists.

### Phase 4 Gate

Before production implementation can claim AgentTurn content coverage, Phase 4 must provide:

1. A deterministic `turn_id` derivation rule from source-confirmed fields.
2. A mapping from Hermes `agent:start` fields to `conversation_id`, `channel`, `user_id`, and capped `content`.
3. A source for full inbound text, attachments, `message_type`, `received_at`, and raw payload references, or an explicit unavailable status for each.
4. Privacy proof that raw legal/customer payloads remain referenced, minimized, or redacted rather than embedded in contract logs.

Until then, AgentTurn coverage is source-confirmed only for the fields listed above and partial for `content`.
