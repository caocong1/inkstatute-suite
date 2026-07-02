# Research Summary: Conversation Context and Memory

**Defined:** 2026-06-30
**Milestone:** v1.2 Conversational Context and Memory Foundation
**Purpose:** Ground the next milestone in current agent-memory patterns while keeping InkStatute's legal privacy and backend-neutral platform boundaries intact.

## Key Findings

- Modern agent frameworks separate **short-term thread/session state** from **long-term memory**. Short-term state keeps the active conversation coherent; long-term memory stores reusable user, organization, task, or procedural facts across sessions.
- Long histories should not be appended wholesale to every model call. The common pattern is to combine recent turns, rolling summaries, retrieved memories, active task state, and feedback corrections under a strict token/context budget.
- Human-in-the-loop interruption is a first-class workflow pattern: the run pauses, persists state, asks the user a question, and resumes when the next user message arrives. This directly maps to InkStatute's lost one-shot skill questioning problem.
- External memory systems such as Mem0 and Zep are credible adapter candidates, not default legal-path dependencies. They should be evaluated against privacy, deployment, tenant isolation, deletion, export, and on-prem/self-host options before any production use.

## Source Notes

| Source | What to reuse | Fit for InkStatute |
|--------|---------------|--------------------|
| LangGraph memory docs (`https://docs.langchain.com/oss/python/concepts/memory`) | Short-term thread memory vs long-term namespace memory; thread checkpoints; summary/trimming guidance | Strong conceptual fit for `SessionResolver`, `ContextAssembler`, and `MemoryStore` contracts |
| LangGraph interrupts docs (`https://docs.langchain.com/oss/python/langgraph/interrupts`) | Pause-and-resume semantics for asking users questions mid-run | Strong fit for `RunInterrupt` / `ClarificationRequest` |
| OpenAI Agents SDK sessions (`https://openai.github.io/openai-agents-python/sessions/`) | Automatic conversation history management and session abstraction | Useful reference for API ergonomics; do not bind platform to one SDK |
| LlamaIndex memory docs (`https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/`) | Agent memory blocks and composable memory retrieval | Useful reference for pluggable memory composition |
| Mem0 docs (`https://docs.mem0.ai/core-concepts/memory-types`) | User/session/agent/org memory scopes; procedural and semantic memory types | Candidate adapter; requires privacy/security review before legal use |
| Zep concepts (`https://help.getzep.com/concepts`) | Temporal graph memory and fact extraction across conversations | Candidate adapter; requires privacy/security review before legal use |

## Architecture Implications

- Add a platform-native memory layer first:
  - `SessionResolver`: maps channel/user/bot messages to an active or new session without user commands.
  - `InterruptStore`: persists pending clarification and approval states.
  - `ContextAssembler`: assembles bounded model context from current turn, recent turns, summaries, retrieved memories, feedback, artifacts, and policy.
  - `MemoryStore`: stores privacy-safe memory records and candidates.
  - `FeedbackLearningPolicy`: converts feedback into current-session corrections, long-term memory candidates, or human-review items.
- Keep contract logs authoritative for audit facts. Memory indexes and summaries are derived/cacheable state and must be rebuildable or invalidatable.
- Store raw legal/customer content by reference only. Memory records should contain minimized summaries, source refs, confidence, sensitivity, TTL, and deletion metadata.
- Treat external memory vendors as `MemoryStore` implementations behind a capability manifest. Default production legal path remains platform-native until an adapter passes privacy, retention, and deployment gates.

## Recommended Milestone Shape

1. Research and contract specification: define memory records, context bundles, session policy, and external adapter evaluation criteria.
2. Runtime session and interruption: implement invisible session continuation and skill clarification resume.
3. Short-term context assembly: bounded recent turns, rolling summary, active task state, and budget tests.
4. Long-term memory and feedback learning: memory candidates, approval gates, feedback-to-context flow.
5. External adapter spike and acceptance gates: evaluate Mem0/Zep-style stores without making them the default.

## Open Questions for Implementation Phases

- Exact default session idle windows for WeCom and Web/SSE.
- Whether summaries are generated synchronously at run end or asynchronously during idle compaction.
- Whether first version uses only lexical matching for memory retrieval or includes vector retrieval behind a default-off flag.
- Which memory scopes are allowed for ordinary lawyer users: user, bot instance, workspace, tenant, or organization.
- What user/admin deletion/export controls are mandatory before any long-term memory is enabled in live legal use.
