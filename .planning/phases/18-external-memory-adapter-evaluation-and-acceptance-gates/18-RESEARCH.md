---
phase: 18-external-memory-adapter-evaluation-and-acceptance-gates
created: 2026-07-01
sources: [local, official-docs-web]
status: ready
---

# Phase 18 Research

## Local Evidence

- Phase 14 created backend-neutral schemas for `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, `ContextBundle`, and `RunInterrupt`.
- Phase 14 documented the external memory evaluation criteria: deployment model, privacy, tenant isolation, deletion/export, latency/relevance, and adapter fit.
- Phase 17 implemented a dependency-free `InMemoryMemoryStore` plus feedback learning policy and synthetic contract fixture.
- Phase 17 verification explicitly states that external memory adapter production approval is deferred to Phase 18.

## Official Mem0 Findings

Sources checked on 2026-07-01:

- Mem0 API overview: https://docs.mem0.ai/api-reference
- Mem0 OSS REST API server: https://docs.mem0.ai/open-source/features/rest-api
- Mem0 delete memories API: https://docs.mem0.ai/api-reference/memory/delete-memories
- Mem0 memory export API: https://docs.mem0.ai/api-reference/memory/create-memory-export

Findings:

- Mem0 exposes hosted REST APIs for memory CRUD, semantic search with filters, update, delete, history, exports, entities, organizations/projects, and webhooks.
- Mem0 hosted API requires token authentication and docs warn not to expose API keys in client-side code or public repositories.
- Mem0 OSS REST server exposes memory operations over HTTP and supports create, retrieve, search, update, delete, and reset by `user_id`, `agent_id`, or `run_id`.
- Mem0 OSS docs distinguish hosted `/v1/` paths from self-hosted OSS paths and recommend API-key auth plus HTTPS before exposure beyond an internal network.
- Mem0 delete supports filtered deletes by user/agent/app/run/project/org metadata, and intentionally requires at least one filter.
- Mem0 export supports export jobs with filters and custom schema.

Implication for InkStatute:

- Mem0 is representable behind an adapter manifest and may be a good future sandbox/self-hosted spike candidate.
- Mem0 still needs legal privacy review for extraction behavior, raw input handling, model/provider configuration, data residency, secret management, deletion propagation, export completeness, and operational ownership.
- Mem0 must not become the default legal production memory path in Phase 18.

## Official Zep Findings

Sources checked on 2026-07-01:

- Zep quick start: https://help.getzep.com/quick-start-guide
- Zep FAQ: https://help.getzep.com/faq
- Zep GitHub examples repository: https://github.com/getzep/zep
- Zep deleting data from graph: https://help.getzep.com/deleting-data-from-the-graph
- Zep users and user graphs: https://help.getzep.com/users-and-user-graphs

Findings:

- Zep positions itself as hosted agent memory using a temporal Context Graph and SDKs such as `zep-cloud`.
- Zep docs claim user graphs and standalone graphs are isolated by `user_id` or `graph_id`.
- Zep FAQ says Zep Community Edition self-hosting is deprecated and no longer supported; current alternatives are Zep Cloud, Graphiti, or enterprise BYOC.
- The public GitHub repository is examples/integrations, not the product service; it points to Zep Cloud docs and notes deprecated CE code under `legacy`.
- Zep user deletion supports a Right To Be Forgotten style operation for user-associated data.
- Zep graph deletion behavior has graph-integrity caveats: deleting a thread removes its episodes, but nodes/edges shared with other episodes may be preserved.

Implication for InkStatute:

- Zep is representable behind an adapter manifest, especially for future graph memory evaluation.
- Zep Cloud/BYOC posture requires procurement, residency, security, and legal privacy review before any production legal data.
- Episode/thread deletion semantics need careful mapping to InkStatute deletion/export expectations before use as an authoritative legal memory store.
- Zep should not become the default legal production memory path in Phase 18.

## Recommendation Direction Before Implementation

- Keep platform-native memory as the default legal path for this milestone.
- Add a provider-neutral adapter capability manifest and evaluation function.
- Add synthetic Mem0/Zep-style manifest evidence and tests.
- Final recommendation should distinguish:
  - `accepted_for_sanitized_spike`
  - `deferred_for_legal_production`
  - `rejected_for_legal_memory`

## Non-Goals

- No live hosted Mem0/Zep account usage.
- No external API calls.
- No SDK install.
- No secrets or API keys.
- No customer/legal payload ingestion.
