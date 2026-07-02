# Phase 26: Memory Provider Evaluation and Selection - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Re-evaluate 2026 external long-term memory providers and select the one that best fits the product goal of seamless, personalized, long-horizon memory. The bot should feel like one continuous companion: focused on the current task, yet remembering facts, preferences, and personality across days and tasks without exposing the user to sessions, context windows, or fallback modes.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Key constraints from user
- Single-tenant, open system; no complex multi-tenant isolation or manual legal-review gates.
- The product must feel complete, not half-finished. No user-visible fallback modes.
- Real API calls are allowed for evaluation.
- Long-term productization and generalization are the goal.

### Candidate providers
- Hindsight (Vectorize.io): LongMemEval leader, self-hosted via embedded Postgres, simple retain/recall/reflect API.
- Mem0: Popular, managed + self-hosted, simple API, lower benchmark scores.
- Zep: Graphiti temporal KG, strong enterprise features, higher complexity.
- Letta: Full agent platform, heavier integration.
- LangMem: LangGraph-native, framework lock-in.
- Supermemory: MCP-native, newer.
- Honcho: Dialectic pattern inference, newer.

</decisions>

<code_context>
## Existing Code Insights

- `packages/platform-runtime/` contains the existing memory interfaces and `SQLiteMemoryStore`.
- `services/wecom-service/` owns the WeCom runtime flow and is already integrated with memory orchestration.
- v1.3 produced sanitized adapter spikes; v1.4 replaces them with a real, primary external memory backend.
</code_context>

<specifics>
## Specific Ideas

1. Desk research matrix: accuracy, integration cost, self-hosting, latency, API simplicity, long-term personality retention.
2. Live smoke test against the top 2 candidates (Hindsight + one fallback) using real API calls.
3. Final selection artifact with rejection rationale.
</specifics>

<deferred>
## Deferred Ideas

- Production deployment tuning.
- Multi-user or multi-tenant isolation.
- Advanced memory management UI.
</deferred>
