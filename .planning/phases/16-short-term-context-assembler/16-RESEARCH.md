# Phase 16: Short-Term Context Assembler - Research

**Researched:** 2026-07-01
**Domain:** Runtime context assembly (platform-runtime library surface)
**Confidence:** HIGH

## Summary

Phase 16 implements the short-term context assembler (`ContextAssembler`) inside `packages/platform-runtime`. Its job is narrow and decisive: given the current turn, pending clarification, active task state, recent turns, artifact refs, feedback corrections, and a rolling session summary, produce a `ContextBundle` (contract defined in Phase 14) whose measured size stays under a deterministic token budget and whose never-droppable section (current turn + pending clarification + output-policy constraints) survives every trim path.

This is a **greenfield runtime-library phase**, not a schema or fixture phase. All contracts it emits already exist: `ContextBundle`, `MemoryRecord`, `MemoryUse`, `RunInterrupt`, `AgentTurn`, `OutputConstraints`, `ArtifactRecord`, `FeedbackEvent`, `SessionScope`. Phase 14 defined the JSON Schema + Python bindings and fixture evidence; Phase 15 produced `SessionScope`, `resolve_session_turn`, `InMemorySessionResolutionStore`, `PendingInterruptSnapshot`, `ActiveTaskSnapshot`, and `InMemoryInterruptStore`. Phase 16 fills the one empty seat the architecture called out in `.planning/research/SUMMARY.md`: "ContextAssembler: assembles bounded model context from current turn, recent turns, summaries, retrieved memories, feedback, artifacts, and policy."

The phase must follow the four proven platform-runtime invariants, each of which is a hard constraint derived from prior locked decisions (see User Constraints below):

1. **Library-only / embeddable** (North Star N4, Phase 10/15 decisions): no server, channel, database, queue, network, or external memory dependency. Pure stdlib, injected ports, in-memory support types. Default-off behind a new `RuntimeFeatureFlags.context_assembly_enabled` flag mirroring `run_runtime_enabled`.
2. **Reference-first / privacy-safe** (AGENTS.md, Phase 14 policy, Phase 15 serialization rule): the assembler stores only `raw_payload_ref`, `summary_ref`, `*_ref` lists, IDs, hashes (`text_sha256_16`), lengths, statuses, and timestamps. The `_reject_forbidden_payload_storage` guard (already live in `store.py` and `session_resolver.py`) must reject `raw_payload` and the `_FORBIDDEN_FULL_TEXT_KEYS` set (`case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`) inside any emitted event/metadata. The rolling summary itself must be a reference (`summary_ref`), not embedded full text — the *content* of a summary lives behind a ref; the assembler only carries the ref plus optional bounded sanitized preview metadata.
3. **Backend-neutral** (North Star N2, Phase 10/15): the assembler speaks only injected ports and pure dataclasses. It must not import Hermes, WeCom, a specific LLM tokenizer, or any backend. Token budgeting is approximated by a deterministic, stdlib-only estimator (character/turn-count heuristic with a configurable ratio), NOT a real tokenizer — real tokenizers are backend-specific and would violate N2.
4. **Deterministic and replayable** (AGENTS.md coding rules, Phase 15 test discipline): trimming is a pure function of inputs + budget + policy. Same inputs → same `ContextBundle` (modulo timestamps/IDs injected by clock/id_factory). Contract-test-suite must be able to validate emitted `context_bundle` events and prove the never-droppable set survives every trim path (STM-04).

**Primary recommendation:** Implement `ContextAssembler` as a new `packages/platform-runtime/src/platform_runtime/context_assembler.py` module exporting `ContextAssembler`, `ContextAssemblyPolicy`, `ContextAssemblyInput`, `ContextAssemblyResult`, `RollingSummaryRecord`, and `InMemoryRollingSummaryStore`. Wire it into `DefaultRunRuntime` behind `context_assembly_enabled` so `create_run`/`resume_interrupt` can attach a `ContextBundle` to the `RunRequest.metadata` (additive, opt-in, no break to existing callers). Add a contract-test-suite fixture proving trim behavior and a privacy fixture proving raw text is never stored. Add `RuntimeFeatureFlags.context_assembly_enabled`. Reuse the existing `_reject_forbidden_payload_storage`, `_safe_metadata`, `_json_clone`, `_sha16`, `_timestamp`, `_new_id`, `_clock_now`, `_coerce_datetime` helpers — do NOT duplicate them; import from the existing modules or lift into a shared internal helper.

## User Constraints (from CONTEXT.md)

### Locked Decisions
None — CONTEXT.md is an auto-generated stub (discuss was skipped via `workflow.skip_discuss`). There are no user-locked decisions to honor verbatim.

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per `workflow.skip_discuss`. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions. [VERIFIED: .planning/phases/16-short-term-context-assembler/16-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. However, the following are explicitly out of scope per the milestone boundary and must NOT be built in this phase:
- Long-term `MemoryStore` persistence/retrieval (Phase 17 — LTM-03/LTM-04, FBK-01..04)
- External memory adapters / Mem0 / Zep (Phase 18 — EXT-02/03/04)
- Vector retrieval or embeddings (deferred beyond v1.2)
- User-facing memory management UI (deferred beyond v1.2)
- Automatic legal skill synthesis (deferred beyond v1.2)
- Making contract logs a raw conversation database (explicitly Out of Scope in REQUIREMENTS.md)

## Project Constraints (from AGENTS.md)

These directives have the same authority as locked decisions. Research does not recommend approaches that contradict them.

| # | Directive | How Phase 16 honors it |
|---|-----------|------------------------|
| C1 | V2 PRD is active spec; V1 retired | Phase 16 implements STM-01..04 from REQUIREMENTS.md, not V1 memory notions |
| C2 | Backend-neutral platform contract; Hermes is first backend, not channel boundary | Assembler is backend-neutral; no Hermes/WeCom/tokenizer imports |
| C3 | Hermes gateway/meta/system/update/command/help notices must not leak to ordinary lawyer users | Out of scope for assembler (output boundary owns this), but assembler must carry `output_constraints` ref so the boundary downstream has what it needs |
| C4 | Never commit secrets, tokens, runtime DBs, logs, customer docs, raw legal payloads | Assembler emits only refs + hashes + IDs; `_reject_forbidden_payload_storage` enforced |
| C5 | Contract logs prefer `raw_payload_ref`; must not store sensitive full text by default | `summary_ref` is a ref; summary *content* lives behind the ref; only bounded sanitized preview metadata may travel in `metadata` |
| C6 | Legal-specific fields belong in `industry_context`; platform schemas stay industry-neutral | Assembler passes `industry_context` through unchanged; no legal top-level fields |
| C7 | High-risk legal feedback stays human-reviewed; V2 records `skill_candidate`, does not auto-synthesize legal skills | Assembler only *references* feedback corrections by ref; it does not promote or auto-apply skill changes |
| C8 | Keep changes scoped to active GSD phase and plan | Only `packages/platform-runtime` (+ contract-test-suite fixture) touched; no new service/DB/queue |
| C9 | Add tests before or with behavior changes, especially for schemas, mappers, event ordering, dedupe, fixture replay | Tests written alongside assembler; contract-test-suite fixture replay extended |
| C10 | Prefer structured parsers and schema validators over ad hoc string parsing | Assembler operates on typed dataclasses and emits schema-validated `context_bundle` events |
| C11 | Do not introduce a new service, database, queue, or runtime dependency unless V2 PRD or active GSD plan requires it | Assembler is a library module + in-memory store; no new service/DB/queue/runtime dep |
| C12 | Update docs and GSD artifacts when implementation decisions change | Phase summary + STATE.md updated at execution time |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STM-01 | Runtime can assemble bounded short-term context from the current turn, recent turns, active task state, artifacts, pending clarification, and a rolling session summary. | `ContextAssembler.assemble(input)` returns `ContextAssemblyResult` carrying a `ContextBundle` whose `recent_turn_refs`, `active_task_refs`, `artifact_refs`, `interrupt_id`/pending-clarification refs, and `summary_ref` are populated from `ContextAssemblyInput`. Inputs come from injected ports (session store, interrupt store, rolling summary store) and the current `AgentTurn`. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/context_bundle.schema.json; packages/platform-contract/src/platform_contract/events.py ContextBundle dataclass] |
| STM-02 | Context assembly enforces a deterministic budget and never sends unbounded conversation history to the backend model. | `ContextAssemblyPolicy.budget_tokens` caps total emitted size. The assembler measures each section with a deterministic, stdlib-only estimator (no tokenizer dependency — backend-neutral per N2), then trims in a fixed priority order until measured size ≤ budget. A `trim_strategy` string is recorded on the `ContextBundle`. Long-conversation tests assert measured size ≤ budget regardless of input history length. [VERIFIED: .planning/research/SUMMARY.md line 10 "strict token/context budget"; North Star N2 backend-neutrality] |
| STM-03 | Rolling summaries preserve task intent, user constraints, unanswered questions, artifact refs, and final outcomes without storing sensitive full text by default. | `RollingSummaryRecord` carries `summary_ref` (ref to actual summary content, not the content), plus structured sanitized fields: `intent_ref`, `constraints_ref`, `open_questions_ref`, `artifact_refs`, `outcome_ref`, `text_sha256_16`, `text_length`, `created_at`, `updated_at`. The actual summary *text* lives behind `summary_ref` (e.g., `fixture://summaries/...` or a future store ref). No `full_text`/`raw_text`/`case_facts` keys — `_reject_forbidden_payload_storage` enforced. [VERIFIED: docs/architecture/memory/context-memory-contracts.md "Memory and context records are reference-first"; AGENTS.md C4/C5] |
| STM-04 | Contract tests prove current turn, pending clarification, and output-policy constraints are never dropped during trimming. | Contract-test-suite fixture + unit tests assert: (a) for every trim path exercised, `current_turn_ref` is present; (b) when a pending interrupt exists, `interrupt_id`/`pending_clarification_ref` is present; (c) `output_constraints_ref`/`output_policy_ref` is present whenever the input carried it. These are the "never-droppable" set; everything else (recent turns, memory refs, artifact refs beyond the must-keep) is trimmable. [VERIFIED: ROADMAP Phase 16 success criteria #2; .planning/research/SUMMARY.md] |
</phase_requirements>