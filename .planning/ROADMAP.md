# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Active **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 planned.

## v1.3 Production Memory System and Evaluation Spikes

## Overview

v1.3 turns the v1.2 memory foundation into a production-capable native memory loop for the lawyer assistant. The milestone keeps platform-native memory as the default legal path, adds durable storage, rolling summaries, pre-run recall orchestration, feedback-to-memory review, and a repeatable evaluation harness. External systems from the lawyer-assistant memory component study are evaluated only as sanitized adapter spikes and cannot become live legal defaults without passing privacy, deletion/export, tenant isolation, human-review, relevance, latency, runbook, and procurement gates.

**Requirements:** `.planning/REQUIREMENTS.md`
**Strategy:** `docs/architecture/memory/production-memory-system-strategy.md`

## Phases

**Phase Numbering:**

- Integer phases (20, 21, 22): Planned milestone work.
- Decimal phases (20.1, 20.2): Urgent insertions after planning.

- [x] **Phase 20: Durable Native Memory Store** - Implement the production-capable platform-native memory store, privacy guard, deletion/export, and baseline tests.
- [x] **Phase 21: Rolling Summary Pipeline** - Generate and persist safe summary refs for bounded long-running conversations.
- [ ] **Phase 22: Recall Orchestrator and Context Injection** - Retrieve approved memory and summary refs before backend submission and attach bounded context to WeCom runtime flows.
- [ ] **Phase 23: Feedback-to-Memory Review Loop** - Convert feedback into same-session corrections and human-reviewed durable memory candidates.
- [ ] **Phase 24: Memory Evaluation Harness and Privacy Gates** - Build the sanitized benchmark and gates that prove recall quality, isolation, deletion, and safety.
- [ ] **Phase 25: External Memory Adapter Spikes and Final Recommendation** - Evaluate Zep/Hindsight, OpenViking/ReMe, and Mem0-style candidates behind the adapter boundary.

## Phase Details

### Phase 20: Durable Native Memory Store

**Goal**: InkStatute has a durable, reference-first platform-native memory store that can become the default legal memory path without adding an external memory dependency.
**Depends on**: Phase 17 and Phase 18 from v1.2
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05
**Success Criteria** (what must be TRUE):

  1. Developer can persist and retrieve `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` evidence through a durable native store implementation.
  2. Queries can filter by tenant, workspace, user, session, labels, source refs, sensitivity, confidence, TTL, deletion status, and deterministic relevance.
  3. Recursive privacy guards reject raw payloads, full legal/customer text, callback bodies, document text, and secret-like metadata before storage.
  4. Delete, tombstone, retention expiry, and export workflows are represented by code and tests.
  5. Existing in-memory tests still pass, and the durable store can be used without changing `RunRuntime` or WeCom channel contracts.

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 20-01-PLAN.md — SQLiteMemoryStore durable core

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 20-02-PLAN.md — Durable query, retention, export, and adapter conformance

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 20-03-PLAN.md — Phase 20 contract fixture and validation sign-off

### Phase 21: Rolling Summary Pipeline

**Goal**: Long-running conversations can produce safe rolling summary references that preserve intent, constraints, open questions, artifacts, and outcomes without stuffing raw history into backend context.
**Depends on**: Phase 20
**Requirements**: SUM-01, SUM-02, SUM-03, SUM-04
**Success Criteria** (what must be TRUE):

  1. A policy-driven summary producer can create or update `RollingSummaryRecord` from safe source refs.
  2. Summary records carry `summary_ref`, hash, length, task intent refs, user constraint refs, unanswered question refs, artifact refs, outcome refs, timestamps, and scope.
  3. Summary generation can trigger from turn count, budget pressure, task completion, or explicit host request.
  4. Summary generation fails closed when source refs, summarizer policy, or privacy checks are missing.
  5. Contract or runtime tests prove summary text is not embedded in `ContextBundle` metadata by default.

**Plans**: 2 plans

Plans:

**Wave 1**

- [x] 21-01-PLAN.md — RollingSummaryPolicy, RollingSummaryTrigger, and RollingSummaryProducer core

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 21-02-PLAN.md — Phase 21 contract fixture and validation sign-off

### Phase 22: Recall Orchestrator and Context Injection

**Goal**: WeCom and runtime flows can automatically retrieve approved memory refs and rolling summaries before backend submission, then attach a bounded `ContextBundle` without exposing session commands to ordinary users.
**Depends on**: Phase 21
**Requirements**: REC-01, REC-02, REC-03, REC-04, REC-05
**Success Criteria** (what must be TRUE):

  1. A memory orchestration layer runs before backend submission and retrieves approved memory refs for the resolved session scope.
  2. Retrieved memory refs, rolling summary refs, recent turn refs, feedback correction refs, artifact refs, and output-policy refs are passed into `ContextAssembler`.
  3. Tenant/workspace/user/session isolation is enforced, with fail-closed behavior on ambiguous or cross-scope retrieval.
  4. `MemoryUse` evidence records selected memories and context-bundle association without raw legal/customer text.
  5. Ordinary WeCom continue/start flows can use the orchestrator while preserving interrupt resume and active-task behavior.

**Plans**: TBD

Plans:

- [ ] TBD (run `$gsd-plan-phase 22` to break down)

### Phase 23: Feedback-to-Memory Review Loop

**Goal**: Feedback can safely affect future context through correction refs and human-reviewed memory candidates, while high-risk legal conclusions and skill/route changes remain review-only.
**Depends on**: Phase 22
**Requirements**: FBL-01, FBL-02, FBL-03, FBL-04, FBL-05
**Success Criteria** (what must be TRUE):

  1. Safe feedback corrections can enter the next same-session context as refs.
  2. Repeated negative feedback creates pending memory candidates with source refs, confidence, proposed scope, sensitivity, and review metadata.
  3. Reviewer actions can approve, reject, edit, tombstone, or defer candidates without auto-promoting unsafe content.
  4. Approved candidates become durable `MemoryRecord` entries, and rejected/deferred candidates do not enter recall.
  5. Route mismatch, skill candidate, and high-risk legal conclusion evidence remains human-reviewed with `no_auto_modify`.

**Plans**: TBD

Plans:

- [ ] TBD (run `$gsd-plan-phase 23` to break down)

### Phase 24: Memory Evaluation Harness and Privacy Gates

**Goal**: InkStatute has a repeatable sanitized evaluation suite that proves native memory behavior and creates a fair baseline for external adapter candidates.
**Depends on**: Phase 23
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):

  1. A sanitized memory benchmark covers multi-turn recall, cross-session continuity, deletion/export, tenant isolation, feedback learning, and false-recall cases.
  2. Evaluation reports include relevance, source traceability, P50/P95 latency where applicable, context-size impact, deletion correctness, and privacy scan results.
  3. Local or CI gates fail on unsafe payload fields, cross-tenant recall, missing deletion/export evidence, or unreviewed high-risk memory promotion.
  4. The native memory path is measured as the baseline that external adapters must beat or complement.
  5. Evaluation fixtures remain synthetic or sanitized and do not claim live legal acceptance.

**Plans**: TBD

Plans:

- [ ] TBD (run `$gsd-plan-phase 24` to break down)

### Phase 25: External Memory Adapter Spikes and Final Recommendation

**Goal**: External memory systems are compared against the native baseline through sanitized adapter spikes, producing an evidence-backed decision for whether any provider should enter a later production gate.
**Depends on**: Phase 24
**Requirements**: XMEM-01, XMEM-02, XMEM-03, XMEM-04, XMEM-05
**Success Criteria** (what must be TRUE):

  1. Zep/Hindsight-style graph or audit memory can be evaluated through `MemoryStoreAdapter` using sanitized fixtures only.
  2. OpenViking/ReMe-style file-auditable memory can be evaluated through `MemoryStoreAdapter` using sanitized fixtures only.
  3. Mem0-style quick PoC memory can be represented as an add/search/delete/export candidate without becoming the legal production default.
  4. Candidate manifests record deployment model, data residency, secrets, tenant isolation, raw-payload blocking, human-review support, delete/export support, and source refs.
  5. The final recommendation either keeps platform-native memory only, adds a gated external adapter candidate, or defers external adoption with evidence.

**Plans**: TBD

Plans:

- [ ] TBD (run `$gsd-plan-phase 25` to break down)

## Carried Gates

- Phase 5 live WeCom UAT remains an operator-confirmed human gate.
- Phase 8 five-workday lawyer trial remains a live legal/human gate.
- External memory providers may not store live legal/customer payloads in v1.3.
- Nyquist validation debt from v1.2 remains carried unless a dedicated validation phase is added.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 20. Durable Native Memory Store | v1.3 | 0/3 | Not started | - |
| 21. Rolling Summary Pipeline | v1.3 | 0/TBD | Not started | - |
| 22. Recall Orchestrator and Context Injection | v1.3 | 0/TBD | Not started | - |
| 23. Feedback-to-Memory Review Loop | v1.3 | 0/TBD | Not started | - |
| 24. Memory Evaluation Harness and Privacy Gates | v1.3 | 0/TBD | Not started | - |
| 25. External Memory Adapter Spikes and Final Recommendation | v1.3 | 0/TBD | Not started | - |
