# External Memory Adapter Recommendation

Phase 18 recommends keeping **platform-native memory** as the current InkStatute legal-memory path, while evaluating external providers only behind the `MemoryStoreAdapter` contract and the capability manifest gates.

This recommendation incorporates local Phase 18 evidence plus the root-level lawyer-assistant component study `律师助理 Bot 的 Agent 记忆组件选型研究.md`.

## Current Recommendation

Use platform-native memory for v1.2 legal use.

- It already preserves `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, and `ContextBundle` semantics.
- It keeps memory reference-first: refs, hashes, lengths, statuses, scopes, TTL, deletion metadata, confidence, and review state are stored instead of raw legal/customer text.
- It works with the short-term context assembler and feedback learning policy without changing `RunRuntime`, WeCom channel code, or backend adapter contracts.
- It keeps high-risk legal conclusions, route mismatch repairs, and skill candidates pending human review.

Do not make Mem0, Zep, Hindsight, OpenViking, ReMe, or another external memory store the live legal memory default until the live legal memory gates below pass.

## Decision Labels

| Decision | Meaning |
|---|---|
| `accepted_for_current_legal_use` | Allowed for the current v1.2 legal-memory path under existing local contract evidence. |
| `accepted_for_sanitized_spike` | Allowed only for local or synthetic evaluation with sanitized fixtures and no live legal/customer payloads. |
| `deferred_for_legal_production` | Not blocked as a future candidate, but missing production evidence or operational approval. |
| `rejected_for_legal_memory` | Has a hard privacy, deletion, isolation, or approval blocker for legal memory use. |

## Provider Matrix

| Provider route | Phase 18 decision | Best future role | Legal-memory blockers before production |
|---|---|---|---|
| platform-native | `accepted_for_current_legal_use` | Default legal path for bounded context, long-term memory records, candidates, feedback corrections, and human review. | Production storage hardening remains future work, but current v1.2 evidence is local, reference-first, and contract-tested. |
| Zep-style graph memory | `accepted_for_sanitized_spike` | Enterprise context graph and cross-thread case relationship evaluation. | Procurement, residency, export completeness, graph deletion semantics, security review, and right-to-be-forgotten mapping. |
| Hindsight-style audit memory | `accepted_for_sanitized_spike` | Audit-focused retain/recall/reflect spike for legal research continuity and observable retrieval. | Tenant isolation evidence, secret handling, deployment ownership, deletion/export mapping, and latency/relevance benchmarks. |
| OpenViking-style file context | `accepted_for_sanitized_spike` | Local or object-storage backed file/context memory for evidence-chain review and human-readable case trees. | License review, fine-grained deletion, permissions, encryption/KMS ownership, export mapping, and team concurrency controls. |
| ReMe-style markdown memory | `accepted_for_sanitized_spike` | Human-auditable Markdown memory for case notes, work patterns, and reviewable knowledge traces. | File locking, permissions, tenant/workspace isolation, encryption, deletion/export procedures, and retrieval benchmark evidence. |
| Mem0-style memory layer | `accepted_for_sanitized_spike` | Fast PoC for user preferences, safe summaries, task tags, and reusable non-sensitive facts. | Audit trail, extraction controls, deletion propagation, export completeness, model/provider data flow, and secret/data residency review. |
| Letta/MemOS/memU/other systems | `deferred_for_legal_production` until represented by a manifest | Watch-list or specialized future spikes after the first candidate lanes are benchmarked. | Must implement the same adapter manifest, fixture privacy scan, deletion/export mapping, and human-review gate. |

## Optimized Memory Architecture

The lawyer assistant should keep three distinct memory layers:

1. Short-term context bundle: current turn, pending clarification, active task state, artifact refs, recent turn refs, output-policy constraints, feedback corrections, and rolling summary refs.
2. Platform-native long-term memory: approved memory records, pending memory candidates, and memory-use evidence, all scoped by tenant/workspace/session/user and stored as refs-first metadata.
3. External adapter lane: optional future provider adapters selected by manifest, never called directly by channel services and never allowed to bypass privacy, deletion/export, or human-review gates.

The external lane should be evaluated in this order:

1. Zep or Hindsight for enterprise graph/audit memory.
2. OpenViking or ReMe for local, file-auditable memory.
3. Mem0 for the fastest PoC path.

This ordering optimizes for legal traceability, reviewability, deletion/export, and governance before personalization convenience.

## Live Legal Memory Gates

No external provider may store live legal/customer memory until all gates pass:

| Gate | Required evidence |
|---|---|
| Privacy review | Raw legal/customer text, callback bodies, documents, secrets, and unreviewed high-risk legal conclusions are blocked or transformed into safe refs before storage. |
| Tenant isolation evidence | Tenant, workspace, user, bot, conversation, and session scopes cannot retrieve each other's memory. |
| Deletion/export evidence | Delete, tombstone, retention expiry, export, and right-to-be-forgotten workflows are mapped to `MemoryRecord` metadata and provider operations. |
| Data residency review | Hosted, BYOC, local, object-storage, and model-provider paths are documented and approved for legal data. |
| Security and secret review | API keys, KMS, credentials, transport security, access controls, audit logs, and incident response are approved. |
| Human-review policy | Route mismatch, legal-skill updates, high-risk conclusions, and repeated negative feedback remain pending human review. |
| Latency/relevance evaluation | Candidate retrieval is benchmarked on synthetic and sanitized legal-like fixtures for P50/P95 latency, relevance, source traceability, and token impact. |
| Operator runbook | Backup, restore, deletion, export, incident response, monitoring, and rollback steps are documented. |
| License/procurement review | Cloud terms, BYOC terms, OSS licenses, commercial redistribution, and support posture are approved where relevant. |

## Evidence Mapping

| Requirement | Evidence |
|---|---|
| EXT-02 | `packages/platform-runtime/src/platform_runtime/memory_adapters.py` defines `MemoryStoreAdapter`, `MemoryStoreCapabilityManifest`, and manifest evaluation decisions without SDK, network, channel, or runtime coupling. |
| EXT-03 | `packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json` and focused tests prove external adapter evidence is synthetic, sanitized, and refs-only. |
| EXT-04 | This recommendation selects platform-native memory as the current path and names Zep, Hindsight, OpenViking, ReMe, and Mem0 as gated future spikes. |

## Final Decision

For the current lawyer assistant, use platform-native memory by default.

For the next production-oriented evaluation, run two sanitized spikes in parallel:

- Zep or Hindsight for enterprise graph/audit retrieval.
- OpenViking or ReMe for local file-auditable memory.

Mem0 remains useful for a fast PoC, but it should not be the first live legal production default unless audit, deletion/export, and governance evidence catches up with the legal-memory gates.
