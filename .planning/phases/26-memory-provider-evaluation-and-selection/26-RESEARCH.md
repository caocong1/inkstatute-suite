# Phase 26 Research: Long-Term Memory Provider Landscape (2026)

**Research date:** 2026-07-03
**Scope:** Evaluate external long-term memory providers for a single-tenant, productized lawyer-assistant bot where users have no session/context awareness and the bot must feel like one continuous companion.

---

## Evaluation Dimensions

| Dimension | Weight | Why it matters |
|-----------|--------|--------------|
| Recall accuracy | High | The bot must remember the right things at the right time. |
| Integration simplicity | High | We want one unified memory layer, not a complex platform migration. |
| Self-hosting / data sovereignty | High | Single-tenant deployment; no forced managed-cloud dependency. |
| Long-term personality retention | High | Preferences, facts, and project state must persist across days and tasks. |
| Latency / efficiency | Medium | Memory operations should not dominate response time. |
| API surface | Medium | Should expose retain/recall/reflect or equivalent cleanly. |
| Framework lock-in | Low | Prefer standalone systems over framework-specific ones. |

---

## Candidate Providers

### 1. Hindsight (vectorize.io/hindsight)

**Architecture:** Temporal + semantic + entity memory stored in PostgreSQL with pgvector. Biomimetic memory banks (world facts + experiences). Uses LLM to extract facts, entities, relationships, and temporal data during `retain`.

**Deployment:** Self-hosted via Docker or `pip install hindsight-all`; embedded Postgres (`pg0`) by default; external Postgres supported. Also offers Hindsight Cloud.

**API:** Three core operations:
- `retain`: push information into memory banks
- `recall`: retrieve relevant memories
- `reflect`: generate observations/insights from existing memories

**Integration:** LLM Wrapper can add memory to an existing agent in ~2 lines by swapping the LLM client. Also exposes REST API and MCP server.

**Benchmarks:** Reported 91-94% on LongMemEval, ahead of Mem0 (66.9%), Zep (75.1%), and Hindsight's own paper (83.6% on LongMemEval with a 20B open model). Note: third-party ByteRover benchmark reports Hindsight at 89.6%.

**Pros:**
- Strong recall on long-horizon tasks.
- Simple self-hosting with embedded Postgres.
- Clean API surface.
- Standalone; no agent-framework lock-in.

**Cons:**
- Requires LLM calls during retain/reflection, adding cost.
- Less proven in production than Zep/Mem0.
- Best reported numbers may rely on Gemini 3 Pro.

### 2. Mem0 (mem0.ai)

**Architecture:** Vector + optional graph memory (Mem0g). Facts extracted from conversations and stored in collections.

**Deployment:** Managed cloud (`mem0.ai`) and open-source self-hosted (`mem0ai/mem0`).

**API:** `add`, `get`, `search`, `update`, `delete`.

**Benchmarks:** 66.9% on LongMemEval per ByteRover; 66.88-68.44 on LoCoMo depending on graph mode.

**Pros:**
- Very popular, simple API.
- Good documentation and ecosystem.
- Quick to try.

**Cons:**
- Lower recall accuracy than Hindsight/Zep on long-horizon benchmarks.
- Managed cloud may be a dependency concern.
- Graph mode gains are thin relative to cost.

### 3. Zep (getzep.com / Graphiti)

**Architecture:** Temporal knowledge graph built on Graphiti + Neo4j. Ingests chat, documents, business data; constructs context graph; invalidates outdated facts.

**Deployment:** Zep Cloud managed service or self-hosted with Neo4j.

**API:** High-level Memory API (`memory.add`, `memory.get`) and lower-level Graph API.

**Benchmarks:** 75.1% LongMemEval per ByteRover; paper claims 94.8% on DMR and up to 18.5% accuracy improvement on LongMemEval with 90% latency reduction vs baseline.

**Pros:**
- Strong enterprise feature set (governance, retention, structured data).
- Explicit temporal invalidation of facts.
- Observations derived from graph patterns.

**Cons:**
- Requires Neo4j; heavier operational footprint.
- More complex integration than Hindsight/Mem0.
- Enterprise-oriented features may be overkill for a single-tenant product.

### 4. Letta (letta-ai/letta, formerly MemGPT)

**Architecture:** Stateful agent platform with memory blocks, skills, conversations, and self-improvement. Memory stored in git-backed MemFS or cloud.

**Deployment:** Letta Cloud, local backend, or `letta-code` CLI.

**Pros:**
- Full agent platform with memory as a first-class concept.
- Self-improvement through memory rewriting.

**Cons:**
- Heavy integration: Letta wants to own the agent runtime, not just memory.
- Tight coupling to Letta's agent model; not a standalone memory layer.
- Overkill if we only need a memory backend.

### 5. LangMem (LangChain)

**Architecture:** Memory primitives for LangGraph, including memory tools and background memory manager.

**Pros:**
- Native to LangGraph.
- Background consolidation and prompt optimization.

**Cons:**
- Framework lock-in to LangGraph.
- Not suitable if the runtime is not LangGraph-based.

### 6. Supermemory

**Architecture:** MCP-native memory system.

**Pros:**
- MCP integration could fit a tool-based architecture.

**Cons:**
- Very new; limited documentation and track record.
- 85.4% headline score but from a single third-party benchmark.

### 7. Honcho

**Architecture:** Dialectic pattern inference.

**Pros:**
- Interesting approach to user modeling.

**Cons:**
- Very new; limited adoption and documentation.

---

## Preliminary Recommendation

**Primary recommendation: Hindsight.**

Reasons:
1. Best reported long-horizon recall on LongMemEval, which maps directly to the product goal of "remembering things from days ago."
2. Self-hosting with embedded Postgres is the simplest operational path for a single-tenant deployment.
3. API is small and focused (retain/recall/reflect), matching the unified `Memory` interface we want to design.
4. Standalone; does not require replacing the agent runtime or framework.
5. Compared to Zep, it avoids Neo4j operational overhead. Compared to Mem0, it has higher recall scores. Compared to Letta, it does not try to own the agent.

**Risk:** Hindsight is newer than Mem0/Zep and requires LLM calls for extraction. We should validate with a real smoke test before committing.

**Smoke-test plan:**
1. Run `hindsight-api` locally with embedded Postgres.
2. Retain a synthetic persona and a few project facts.
3. Send a new turn and verify the relevant memories are recalled.
4. Verify preference retention across multiple turns.
5. Compare the same exercise with Mem0 if time permits.
