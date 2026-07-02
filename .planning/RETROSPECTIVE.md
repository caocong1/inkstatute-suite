# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.2 — Conversational Context and Memory Foundation

**Shipped:** 2026-07-02
**Phases:** 6 | **Plans:** 16 | **Sessions:** multiple autonomous/resumed GSD sessions

### What Was Built

- Backend-neutral context, memory, and interrupt contracts with Python bindings and sanitized fixtures.
- Scoped session resolution, interrupt lifecycle, and WeCom session runtime behavior for continuation, new-task splitting, active-task precedence, and clarification resume.
- Deterministic short-term context assembly with protected refs, rolling summaries, memory refs, feedback corrections, artifacts, and budget trimming.
- Platform-native memory and feedback learning policies with human-reviewed candidates and no automatic legal skill modification.
- External memory adapter contracts and recommendation, keeping platform-native memory as the live legal default while allowing future sanitized spikes.
- Phase 19 E2E closure so ordinary WeCom continue/start callbacks reach runtime run creation through a pure ingress boundary.

### What Worked

- Reference-first privacy rules stayed consistent across contracts, runtime metadata, fixtures, and tests.
- Keeping WeCom ingress as a dependency-injected library boundary avoided adding a server, queue, database, live WeCom dependency, or Hermes core coupling during the closure phase.
- The milestone audit caught a real E2E wiring gap that unit-level phase completion had missed, and a small closure phase resolved it cleanly.

### What Was Inefficient

- Nyquist validation artifacts were not produced uniformly during the earlier v1.2 phases, so milestone close had to accept validation-documentation debt.
- The milestone completion tool overcounted historical phases because the live roadmap still contained older phase details; future milestones should keep `ROADMAP.md` compact after archive.
- Phase 18 expanded after a broader memory component study arrived, which was useful but added late-stage fixture and recommendation updates.

### Patterns Established

- Treat context/memory data as derived support state; contract logs and references remain the audit source.
- Resume clarification through runtime interrupts, not user-visible session commands.
- Represent external memory providers through capability manifests and local evaluations before any SDK or live provider integration.
- Add a closure phase when milestone audit finds critical wiring gaps instead of burying the fix inside closeout.

### Key Lessons

1. Milestone audits must exercise cross-layer flows, not just per-phase summaries and tests.
2. Live legal acceptance and operator UAT should stay explicit human gates even when fixture and library evidence pass.
3. Closeout tools need a compact current roadmap; otherwise archive summaries can accidentally mix historical and active phase scopes.
4. Privacy-safe metadata helpers should reject raw/full-text keys at ingress boundaries, not only at storage boundaries.

### Cost Observations

- Model mix: not tracked in repo-local artifacts.
- Sessions: multiple resumed autonomous sessions.
- Notable: The most valuable late work was audit-driven integration closure, not additional feature expansion.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.1 | multiple | 5 | Established default-off reusable platform seams. |
| v1.2 | multiple | 6 | Added memory/context runtime behavior and enforced audit-driven closure before archive. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.1 | 287 V2 gate tests | Contract, runtime, channel, backend, and solution-loader gates | Runtime, adapter, channel, SDK, and solution-loader foundations default-off |
| v1.2 | 51 WeCom-service tests plus contract/runtime suites cited in phase verification | Context, memory, interrupt, feedback, adapter, and WeCom session-runtime flows | Memory/context contracts, resolver, interrupt store, memory policy, adapter manifest, ingress helper |

### Top Lessons

1. Keep active planning files small after archive; full history belongs in milestone snapshots.
2. Separate autonomous-completable code/fixture work from live legal and operator gates.
3. Use post-phase milestone audits to catch missing cross-layer behavior before declaring a milestone shipped.
