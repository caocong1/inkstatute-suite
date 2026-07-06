# Project Milestones: 墨律 InkStatute

## v1.7 M3 Platform Extensions (Shipped: 2026-07-06)

**Delivered:** Promoted adapter prototypes to production-grade (streaming, artifacts, multi-provider, session memory), extended platform surface (MCP registry, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Gap closure phase 57.1 wired TenantGuard into Web UI data access paths. All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green (1,547+ tests).

**Phases completed:** 45-57 + 57.1 gap closure (14 phases, 34 plans, 132 commits, 36,741 LOC inserted)

**Archive:** [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)

**Key accomplishments:**

- Adapter Productization (A1-A4): Codex + provider_model adapters promoted to production with frozen stream_events(), collect_artifacts(), multi-provider runners (Anthropic, Ollama), and session memory wiring via ContextBundle
- Platform Extensions (B1-B5): MCP Connector Registry, Skill Registry Write (with two-person rule), Hybrid Routing (Rule→Skill→Model cascade), Model Provider Gateway (rate limiting + circuit breakers + cost tracking), Multi-Agent Runtime Adapter
- Security & Compliance (C1-C2): RBAC with 4 roles + token-based auth + CI scan, Multi-Tenant Isolation with TenantScopeResolver + TenantGuard + Hindsight bank isolation
- Operator & UX Layer (C3-C4): Admin Web UI (dashboard, session/task inspection, feedback review) + Lawyer Web Chat (real SSE, session auth, file upload, feedback)
- Gap Closure (57.1): Wired TenantGuard into admin-console-api and lawyer-web-chat data access paths, closing HIGH-severity tenant isolation gap (+46 tests)
- Safety: All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green throughout (1,547+ tests, zero regressions)

---

## v1.4 Long-Term Memory Productization (Shipped: 2026-07-03)

**Delivered:** Replaced the evaluation-only memory approach with a single, productized long-term memory layer (Hindsight backend) so the bot feels like one continuous companion. The unified `Memory` interface, Hindsight adapter, focus/retention policies, WeCom runtime integration, retry/observability, and live validation are all shipped. Singleton memory wiring and contract event observability closed via Phase 32 gap closure.

**Phases completed:** 26-32 (7 phases, 1 gap closure)

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

**Key accomplishments:**

- Evaluated 7 external memory providers (Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho) and selected Hindsight with documented rationale and live smoke test.
- Defined a backend-agnostic `Memory` Protocol with async `aretain`/`arecall`/`areflect` operations and privacy-safe metadata validation.
- Implemented `HindsightMemory` adapter using `hindsight-client` with BGE-M3 embeddings and BGE-Reranker-V2-M3.
- Implemented deterministic `MemoryContentClassifier` and `MemoryRetentionPolicy`/`MemoryFocusPolicy` for durable vs transient classification (LLM-free, CI-safe).
- Wired pre-turn recall and post-turn retention into `WeComSessionRuntime` with fail-open graceful degradation.
- Added `RetryableMemory` with exponential backoff, failure classification (`MemoryFailureCategory`), and `MemoryOperationEvent` contract events.
- Validated with live Hindsight multi-turn tests (preference retention, cross-task recall) and CI-safe skip when provider unreachable.
- Closed audit gaps: `build_memory_from_env()` singleton factory, `ContractLogMemoryObserver` for production observability, `WeComRuntimeIngress` memory/observer pass-through.
- Fixed V2 gate PYTHONPATH regression (v1.2-v1.4) that was hiding 3 broken gates.

**Audit result:** `passed`. 20/20 requirements satisfied; 10/10 integration points confirmed; 2/2 flows complete.

**Known deferred items at close:**

- Live Hindsight test fails when Gemini API free-tier quota is exhausted (429) — external quota issue, not a code defect.
- REQUIREMENTS.md traceability table was not updated during execution (fixed during audit).
- No SUMMARY.md files for v1.4 phases (only CONTEXT/PLAN/VERIFICATION produced).
- Phase 8 (Lawyer Trial Acceptance) and Phase 5 live WeCom UAT remain parallel human gates, not v1.4 dependencies.

**Follow-up:** Next milestone to be defined via `/gsd-new-milestone`.

---

## v1.3 Production Memory System and Evaluation Spikes (Shipped: 2026-07-02)

**Delivered:** Platform-native memory is production-capable, rolling summaries are safe and reference-first, recall orchestration is wired into ordinary WeCom/runtime flows, feedback-to-memory learning is wired at the service level, evaluation gates prove durable SQLite baseline and export evidence, and external memory adapters are evaluated as sanitized spikes with a defer-all recommendation.

**Phases completed:** 20-25, 25.1 (7 phases, 19 plans, 18 summaries)

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md) | [v1.3-phases](milestones/v1.3-phases/)

**Key accomplishments:**

- Durable native memory store (`SQLiteMemoryStore`) with ref-first privacy, TTL/deletion/export, review state, and scoped query behavior.
- Policy-driven rolling summaries stored as refs, hashes, lengths, and structured evidence.
- Pre-run recall orchestration wired into WeCom/runtime ordinary continue/start flows, with interrupt/active-task behavior preserved and MemoryUse evidence fail-closed in legal production mode.
- Feedback-to-memory review loop at the service level: same-session correction refs, repeated-negative pending candidates, explicit human review actions, and no auto-modify for high-risk legal/route/skill candidates.
- Repeatable memory evaluation harness with hard gates, native baseline, and durable SQLite baseline/export evidence.
- Sanitized adapter spikes for Zep/Hindsight, OpenViking/ReMe, and Mem0-style candidates, with a final `defer_all_external` recommendation.
- Formal verification artifacts for phases 20-25 and validation artifacts for phases 22-25 and 25.1; deterministic audit closure script.

**Audit result:** `closed`. 28/28 requirements satisfied; 6/6 phase verification reports present; 7/7 cross-phase integration flows verified; 0 broken flows.

**Known deferred items at close:**

- Phase 20: file-backed `SQLiteMemoryStore` requires host `db_path` injection in production (deployment configuration, not code gap).
- Phase 24: `MemoryEvalRunner` can use fast in-memory or durable SQLite baseline; both modes are tested.
- Phase 25: external adapter spikes remain sanitized manifest/spec simulations; no live provider integration claimed.
- Phase 8 (Lawyer Trial Acceptance) and Phase 5 live WeCom UAT remain parallel human gates, not v1.3 dependencies.

**Follow-up:** Next milestone to be defined via `/gsd-new-milestone`.

---

## v1.2 Conversational Context and Memory Foundation (Shipped: 2026-07-02)

**Delivered:** Invisible WeCom conversation continuity, bounded context, interrupt resume, platform-native memory, feedback-informed learning, external-memory adapter evaluation, and the Phase 19 E2E session-runtime closure.

**Phases completed:** 14-19 (16 plans total)

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md) | [v1.2-phases](milestones/v1.2-phases/)

**Key accomplishments:**

- Backend-neutral memory/context/interrupt schemas, Python bindings, and sanitized contract fixtures for the v1.2 vocabulary.
- Scoped session resolver and interrupt lifecycle support with ref/hash-only decision and resume evidence.
- WeCom session runtime behavior for pending clarification resume, active-task precedence, session continuation, and session splitting.
- Deterministic short-term context bundles with protected sections, rolling summaries, feedback corrections, memory refs, artifact refs, and budget trimming.
- Platform-native memory store and feedback learning policy with human-reviewed candidates and no automatic legal skill modification.
- Sanitized external memory adapter contract, capability manifest, fixture evidence, and production recommendation.
- Phase 19 closure of the v1.2 audit gaps: ordinary WeCom continue/start turns now call `RunRuntime.create_run()`, and sanitized callback ingress reaches `WeComSessionRuntime.handle_turn()`.

**Audit result:** `tech_debt`. Requirements 24/24 satisfied; phases 6/6 verified; critical integration and flow gaps closed by Phase 19.

**Known deferred items at close:**

- 2 open artifact-audit human gates acknowledged and carried forward in `.planning/STATE.md`.
- Nyquist validation artifacts for Phases 14, 15, 16, 18, and 19 are accepted validation debt.
- Service-level feedback-to-memory automation remains future integration work; Phase 17 delivered library surfaces and fixture evidence.
- Live WeCom UAT and the five-workday lawyer trial remain human gates and are not claimed as autonomous production acceptance.

**Follow-up:** v1.3 Production Memory System and Evaluation Spikes is active.

---

[Entries in reverse chronological order - newest first]

## v1.1 Platform Foundation (Shipped: 2026-06-30)

**Delivered:** Four-contract North Star platform architecture (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime) with embeddable runtime, Hermes backend adapter, multi-channel interface, and backend-portable solution loader — all default-OFF.

**Phases completed:** 09-13 (20 plans total)

**Key accomplishments:**

- Locked four North Star contracts with signature-only Protocol stubs, boundary allowlist, and privacy scan allowlist
- Embeddable DefaultRunRuntime — library-only, dependency-injected, fake backend, output boundary with allowlist policy
- Hermes BackendAdapter — subprocess one-shot adapter, non-mutating capability probe, fixture-based `/v1/runs` parity spike
- Channel interface + WeCom wrapper + Web/SSE channel + Platform API server + TypeScript SDK + embeddable web chat renderer — all default-off
- SolutionLoader library + lawfirm neutral manifest + sanitizing Hermes materializer + demo_non_legal pack + privacy scanner + aggregate contract evidence

**Stats:**

- 195 files changed
- 25,368 lines added
- 5 phases, 20 plans, 20 summaries
- 99 commits (1d3fe58 → 24f70e9)
- V2 gate: 8/8 pass, 287 tests, exit 0
- Audit: passed (re-audited 2026-06-30)
- 2 days from start to ship (2026-06-28 → 2026-06-29 execution, 2026-06-30 audit+archive)

**Git range:** `1d3fe58` → `24f70e9`

**Known deferred items:**

- Phase 8 (Lawyer Trial Acceptance) — parallel human gate, NOT an autonomous-completable gap
- Phase 5 live WeCom UAT — human gate, fixture-satisfied
- `/v1/runs` lane — route mismatch evidence reported; remains default-off
- All v1.1 runtime lanes default-OFF — live cutover is a separate human gate

**Follow-up:** v1.2 Conversational Context and Memory Foundation shipped 2026-07-02; see the v1.2 entry above.

---
