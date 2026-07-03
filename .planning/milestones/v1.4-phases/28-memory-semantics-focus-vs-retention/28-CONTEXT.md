# Phase 28 Context: Memory Semantics — Focus vs Retention

**Date:** 2026-07-03
**Phase goal:** Distinguish transient task context from durable memory and implement a recall/retention policy that keeps the agent focused while building long-term personality.

---

## Current State

- Phase 27 shipped a backend-agnostic `Memory` interface with `aretain`, `arecall`, and `areflect`.
- `HindsightMemory` is the primary adapter; `FakeMemory` is the test double.
- The runtime still uses `MemoryOrchestrator` (native record-style) for context assembly.
- No policy yet decides what gets retained, what gets recalled, or how to avoid polluting long-term memory with throwaway details.

## Product Requirement

The bot must feel like one continuous companion. That means:

- Durable: facts, preferences, project context, lessons learned across sessions/tasks.
- Focused: each turn only recalls memories relevant to the current topic and task.
- Clean: transient task details (e.g., specific file content, temporary clarifications) do not become durable memory.

## Key Decisions Already Made

- Hindsight is the long-term memory backend.
- The `Memory` interface is async, scoped by tenant/workspace/user.
- Privacy and secrets must stay out of the neutral runtime package.
- V2 gates must remain green.

---

## Open Questions

1. What categories of content are durable vs transient? (user preference, project fact, lesson, throwaway task detail)
2. Who performs the classification: caller before `retain`, or the memory layer via a policy?
3. How does recall relevance interact with Hindsight's own ranking? Do we add a post-filter threshold?
4. Should we introduce a `MemoryPolicy` object that can be passed to `aretain`/`arecall`?

---

## Suggested Minimal Shippable Scope

- Define a `MemoryRetentionPolicy` and `MemoryFocusPolicy` dataclass.
- Implement a simple `MemoryContentClassifier` (rule-based, no LLM) that labels content as durable/transient and assigns a category.
- Add a `MemoryRetentionDecision` object returned by `aretain` indicating what was retained and what was discarded.
- Add a `MemoryRecallPolicy` with `minimum_relevance_score` and `max_results` to filter recalled memories.
- Add a `MemoryFocusResult` for `arecall` that marks selected memories vs. filtered ones.
- Provide contract tests using `FakeMemory` and a test classifier.
- Keep Hindsight adapter honest: it must respect the policy fields it understands (max_results, category hints).
