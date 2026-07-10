# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.9 — QQBot Host Composition

**Shipped:** 2026-07-10
**Phases:** 5 | **Plans:** 14 | **Tasks:** 29

### What Was Built

- Empty-deps `services/qqbot-service/` host skeleton with V2 gate coverage and secret-ref process-edge resolution.
- Dual-knob runtime wiring injecting `QQBotChannelAdapter` into `DefaultRunRuntime.channels` with disabled-path refuse.
- ACK-first stdlib webhook composing package Protocol methods end-to-end with Fake transports.
- Smoke `--dry-run` Protocol-path hardening via host helpers; sanitized non-acceptance evidence.
- Controlled `--live` honesty gates + operator runbook; live OpenAPI acceptance remains HUMAN GATE.

### What Worked

- Closing only v1.8 accepted host gaps kept scope tight and avoided re-phasing package crypto/normalize/send.
- Composition-only host + Protocol freeze preserved ADAPTER-04 and empty-deps invariants.
- Same-day 14-plan execution with audit-passed close kept planning files compact after archive.

### What Was Inefficient

- Info-tier review leftovers (CALLBACK_PATH duplication, AST dynamic-import miss) remain as non-blocking debt.
- `--live` stayed on leaf OpenAPI path rather than host Protocol rewrite — documented tradeoff, but splits proof surfaces.

### Patterns Established

- Host services compose package Protocol methods; they do not reimplement channel crypto/normalize/send.
- Dual default-OFF knobs + explicit channel injection beat auto-discovery for live-IO safety.
- CI dry-run must exercise the same host helpers as production composition, or fail closed.

### Key Lessons

1. Accepted audit gaps make excellent next-milestone scope when they are composition/wiring, not feature rewrites.
2. Preserve carried human-gate phase dirs (Phase 08) during phase archival — never delete them with milestone phases.
3. Force `not_live_acceptance=true` in evidence schemas so CI cannot silently claim live success.

### Cost Observations

- Model mix: not tracked in repo-local artifacts.
- Sessions: single-day autonomous GSD execution for Phases 68–72.
- Notable: Milestone closed same calendar day as execution start after audit passed.

---

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
| v1.9 | same-day | 5 | Closed prior-milestone accepted gaps via composition-only host + Protocol-path CI honesty. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|------|----------|-------------------|
| v1.1 | 287 V2 gate tests | Contract, runtime, channel, backend, and solution-loader gates | Runtime, adapter, channel, SDK, and solution-loader foundations default-off |
| v1.2 | 51 WeCom-service tests plus contract/runtime suites cited in phase verification | Context, memory, interrupt, feedback, adapter, and WeCom session-runtime flows | Memory/context contracts, resolver, interrupt store, memory policy, adapter manifest, ingress helper |
| v1.9 | Host + smoke Protocol-path suites; 27 V2 gates with qqbot-service entry | Host composition, dual-knob wiring, ACK-first webhook, Protocol-path dry-run | `services/qqbot-service/` empty-deps composition host |

### Top Lessons

1. Keep active planning files small after archive; full history belongs in milestone snapshots.
2. Separate autonomous-completable code/fixture work from live legal and operator gates.
3. Use post-phase milestone audits to catch missing cross-layer behavior before declaring a milestone shipped.
4. Composition hosts should call the same Protocol helpers CI dry-run proves — leaf-only paths must fail closed.
