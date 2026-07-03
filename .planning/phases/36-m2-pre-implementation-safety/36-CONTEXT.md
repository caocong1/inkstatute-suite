# Phase 36: M2 Pre-Implementation Safety - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can verify that all cross-cutting safety measures (selection gate bypass fix, contract freeze, privacy scrub unification, M2 feature flags default-OFF, output boundary rules, contract-count assertions) are in place before any M2 feature code is written, protecting the 479-test V2 gate suite and parallel V2 human gates.

Requirements: SAFETY-01, SAFETY-02, SAFETY-03, SAFETY-04, SAFETY-05, SAFETY-06

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to inform planning (from `.planning/research/SUMMARY.md`):
- `select_agent_backend` bypass at `agent_backend.py:50-51`: non-Hermes modes with `metadata.production_ready: True` become live-acceptance-eligible. Fix: `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready`.
- `_FORBIDDEN_FULL_TEXT_KEYS` gap: `store.py` rejects 7 keys; `privacy.py` only checks 1 (`raw_payload`). New backend field names (`prompt_content`, `completion_text`, `function_call_result`, `tool_output`) bypass both. Unify and add read-time scrubbing.
- Output boundary rules in `output_boundary.py` are Hermes-specific. Add generic patterns for provider/model name leakage, API errors, rate-limit notices.
- All M2 feature flags must default to `False` in `RuntimeFeatureFlags`.
- Contract freeze: baseline hash of `packages/platform-contract/` schema files against v1.5 to detect modifications during V2 human gate period.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Key files to investigate:
- `services/wecom-service/src/wecom_service/agent_backend.py` (selection gate bypass, lines 50-51)
- `packages/platform-runtime/src/platform_runtime/store.py` (`_FORBIDDEN_FULL_TEXT_KEYS`, 7 keys)
- `services/conversation-read-view/src/conversation_read_view/privacy.py` (1 forbidden key)
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` (Hermes-specific regex rules)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` (RuntimeFeatureFlags)
- `packages/platform-contract/src/platform_contract/protocols.py` (BackendAdapter, ChannelAdapter Protocols)
- `packages/platform-contract/src/platform_contract/agent_adapter.py` (AdapterCapabilitySet)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
