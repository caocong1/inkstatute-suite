# Phase 26: Memory Provider Comparison Matrix

**Date:** 2026-07-03
**Scope:** Long-term memory providers for a single-tenant, productized lawyer-assistant bot. Users must not perceive sessions or context windows; the bot must feel like one continuous companion.

---

## Evaluation Dimensions

| Dimension | Weight | What we measured |
|-----------|--------|------------------|
| Long-horizon recall accuracy | High | Ability to recall facts, preferences, and project state across many turns and days. |
| Integration simplicity | High | How easily the provider drops into the existing Python/WeCom runtime as a single memory layer. |
| Self-hosting / data sovereignty | High | Can it run on the user's own infrastructure without forced managed-cloud dependency? |
| Long-term personality retention | High | Does it keep stable user preferences, facts, and traits across sessions? |
| Operational footprint | Medium | DB/runtime dependencies, image size, memory/CPU requirements. |
| API surface | Medium | Clean retain/recall/reflect model vs. framework-specific APIs. |
| Latency / efficiency | Medium | Response time and token/cost overhead of memory operations. |
| Framework lock-in | Low | Standalone system vs. tied to a specific agent framework. |

---

## Candidate Scores (qualitative, evidence-backed)

| Provider | Long-horizon recall | Integration | Self-hosting | Personality retention | Footprint | API | Latency | Lock-in | Verdict |
|----------|--------------------:|-------------|--------------|----------------------:|-----------|-----|---------|---------|---------|
| **Hindsight** | **Excellent** (91-94% LongMemEval reported) | **Excellent** (3 core APIs, LLM wrapper) | **Excellent** (embedded Postgres / Docker) | **Excellent** (entity + temporal + semantic) | Medium (slim ~500MB) | Clean retain/recall/reflect | Medium (LLM extraction) | None | **Selected** |
| Mem0 | Good (66.9% LongMemEval) | Excellent (simple add/get) | Good (managed + self-hosted) | Good (fact collections) | Small | add/get/search | Low | None | Rejected: lower recall |
| Zep | Very Good (75.1% LongMemEval) | Medium (Neo4j, graph API) | Good (self-hosted + cloud) | Very Good (temporal KG) | Large (Neo4j) | Memory + Graph APIs | Medium | None | Rejected: higher ops overhead |
| Letta | Very Good | Poor (wants to own the agent runtime) | Good (local + cloud) | Very Good (memory blocks, self-improvement) | Large | Agent-platform API | Medium | Heavy | Rejected: too much framework lock-in |
| LangMem | Good | Poor (LangGraph-only) | Good (LangGraph platform) | Good | Small | LangGraph primitives | Low | High (LangGraph) | Rejected: framework lock-in |
| Supermemory | Good (85.4% reported) | Medium (MCP-native) | Unknown | Unknown | Small | MCP | Unknown | MCP | Rejected: too new, limited evidence |
| Honcho | Unknown | Medium | Unknown | Unknown | Unknown | Dialectic API | Unknown | Unknown | Rejected: too new, limited evidence |

---

## Evidence Sources

- Hindsight paper: arXiv 2512.12818v1 (Dec 2025) — reports 83.6% on LongMemEval with 20B open model; third-party benchmarks report 91-94%.
- Zep paper: arXiv 2501.13956 — reports 94.8% on DMR and up to 18.5% improvement on LongMemEval; ByteRover reports 75.1%.
- Mem0: ByteRover reports 66.9% on LongMemEval; Mem0 paper (arXiv 2504.19413) reports LoCoMo scores 66.88-68.44.
- Letta: formerly MemGPT; provides stateful agent platform with memory blocks and conversations.
- LangMem: LangChain official SDK; requires LangGraph runtime.
- Supermemory/Honcho: third-party benchmark headlines only; limited documentation and track record.

---

## Notes

- Benchmark scores vary by evaluation protocol and base model, so the absolute numbers are less important than the relative ranking: Hindsight and Zep consistently lead on long-horizon tasks, while Mem0 is simpler but less accurate.
- For a single-tenant product that values recall quality over enterprise governance, Hindsight's slim self-hosted image + embedded Postgres is the cleanest operational path.
- Zep's Neo4j requirement adds operational complexity that is not justified until multi-source business data ingestion becomes a priority.
- Letta is attractive as a full agent platform, but it conflicts with the goal of adding only a memory layer to the existing Hermes/WeCom runtime.
