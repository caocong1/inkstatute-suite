# Phase 26: Final Memory Provider Selection

**Date:** 2026-07-03
**Selected provider:** Hindsight (https://github.com/vectorize-io/hindsight)

---

## Why Hindsight

1. **Best long-horizon recall.** Hindsight leads reported LongMemEval scores (91-94% in third-party benchmarks, 83.6% in the authors' open-model test). For a bot that must remember things across days and tasks, this is the primary selection criterion.
2. **Simple self-hosting.** The `ghcr.io/vectorize-io/hindsight:latest-slim` image runs with embedded Postgres (`pg0`) and needs only an LLM API key. No Neo4j, no managed-cloud dependency, no separate vector store.
3. **Small, focused API.** Three operations — `retain`, `recall`, `reflect` — map cleanly to a unified `Memory` interface.
4. **No framework lock-in.** Hindsight is a standalone memory service; it does not require replacing the agent runtime or adopting LangGraph/Letta's agent model.
5. **Biomimetic memory design.** World facts + experiences pathways, entity/relationship/temporal representation, and disposition traits align with the goal of a bot that develops a stable personality.

---

## Rejection Rationale

| Provider | Rejected because |
|----------|------------------|
| **Mem0** | Lower long-horizon recall scores (66.9% LongMemEval). The gap vs. Hindsight/Zep is large enough that it would compromise the "continuous companion" feel. |
| **Zep** | Strong recall, but requires Neo4j and a graph-centric operational model. The extra complexity is not justified for a single-tenant product at this stage. |
| **Letta** | A full agent platform, not a memory layer. Adopting it would mean replacing the existing Hermes/WeCom runtime, which violates the "add memory, don't rebuild" goal. |
| **LangMem** | Tightly coupled to LangGraph. The current runtime is not LangGraph-based, so the integration would force a framework migration. |
| **Supermemory** | Too new; headline benchmark is promising but documentation and production track record are insufficient. |
| **Honcho** | Too new; limited public evidence and integration examples. |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Hindsight is newer than Mem0/Zep | Pin the Docker image tag (`latest-slim` or a specific version) and validate each milestone with live tests. |
| LLM extraction adds cost and latency | Make retention async where possible; Phase 28 will define a retention policy that limits extraction frequency. |
| Best benchmark scores rely on Gemini 3 Pro | Use an OpenAI/Anthropic/Groq provider that is already available; evaluate recall quality empirically in the smoke test. |
| Self-hosted embedding models need GPU | Use the `slim` image with external embeddings provider (OpenAI/Cohere/Groq) to avoid local model serving. |

---

## Smoke Test Plan

1. Run `ghcr.io/vectorize-io/hindsight:latest-slim` with embedded Postgres on port 8888.
2. Configure an LLM provider (OpenAI, Anthropic, Groq, or Gemini) for fact extraction and response generation.
3. Create a memory bank `lawyer-assistant`.
4. Retain a synthetic persona: user name, role, preferences, active project.
5. Simulate a later turn that references the project indirectly.
6. Call `recall` and verify the relevant persona/project facts are returned.
7. Verify unrelated facts are not recalled.
8. Record latency and API responses in `26-SMOKE-TEST.md`.

---

## Decision

Proceed with Hindsight as the primary and only long-term memory backend for v1.4. Phase 27 will design the unified `Memory` interface and implement the Hindsight adapter.
