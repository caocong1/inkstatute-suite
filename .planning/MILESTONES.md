# Project Milestones: 墨律 InkStatute

## v1.3 Production Memory System and Evaluation Spikes (Shipped: 2026-07-02)

**Delivered:** Platform-native memory is production-capable, rolling summaries are safe and reference-first, recall orchestration is wired into ordinary WeCom/runtime flows, feedback-to-memory learning is wired at the service level, evaluation gates prove durable SQLite baseline and export evidence, and external memory adapters are evaluated as sanitized spikes with a defer-all recommendation.

**Phases completed:** 20-25, 25.1 (7 phases, 19 plans, 18 summaries)

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

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

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

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
