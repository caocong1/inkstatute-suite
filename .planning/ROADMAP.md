# Roadmap: 墨律 InkStatute

## Overview

V2 is an InkStatute-owned WeCom lawyer assistant platform with backend-neutral contracts, runtime seams, memory/context support, and Hermes `lawfirm` as the first agent backend. Completed milestone details are archived under `.planning/milestones/` so this live roadmap stays focused on current and next work.

## Milestones

- Complete **V2 PRD Foundation** — Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** — Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** — Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Planned **Next milestone** — TBD via `$gsd-new-milestone`.

## Phase Groups

<details>
<summary>Complete: V2 PRD Foundation (Phases 1-8)</summary>

- [x] Phase 1: Platform Contract Foundation — completed 2026-06-27
- [x] Phase 2: Contract Test Suite Foundation — completed 2026-06-27
- [x] Phase 3: Hermes Integration Spike and Risk Closure — completed 2026-06-28
- [x] Phase 4: Hermes Shadow Event Layer — completed 2026-06-28
- [x] Phase 5: WeCom Shadow Loop Validation — completed 2026-06-28; live UAT remains a human gate
- [x] Phase 5.5: InkStatute WeCom Service and Hermes Agent Adapter — completed 2026-06-28
- [x] Phase 6: Read and Feedback Service APIs — completed 2026-06-28
- [x] Phase 7: CI, Composability, and Privacy Gates — completed 2026-06-28
- [x] Phase 8: Lawyer Trial Acceptance artifacts — completed 2026-06-30; five-workday lawyer trial remains a human gate

</details>

<details>
<summary>Complete: v1.1 Platform Foundation (Phases 09-13) — shipped 2026-06-30</summary>

Archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) | [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) | [v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

- [x] Phase 09: Platform Interface Contracts — completed 2026-06-29
- [x] Phase 10: Embeddable Run Runtime — completed 2026-06-29
- [x] Phase 11: Hermes Backend Adapter — completed 2026-06-29
- [x] Phase 12: Channel and Client Surface — completed 2026-06-29
- [x] Phase 13: Solution Loader and Lawfirm Pack — completed 2026-06-29

</details>

<details>
<summary>Complete: v1.2 Conversational Context and Memory Foundation (Phases 14-19) — shipped 2026-07-02</summary>

Archive: [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

- [x] Phase 14: Memory Research and Contract Spec — 3/3 plans, completed 2026-06-30
- [x] Phase 15: Session Resolver and Interrupt Runtime — 3/3 plans, completed 2026-07-01
- [x] Phase 16: Short-Term Context Assembler — 3/3 plans, completed 2026-07-01
- [x] Phase 17: Long-Term Memory and Feedback Learning — 3/3 plans, completed 2026-07-01
- [x] Phase 18: External Memory Adapter Evaluation and Acceptance Gates — 3/3 plans, completed 2026-07-02
- [x] Phase 19: Close gap: v1.2 WeCom session runtime E2E wiring — 1/1 plan, completed 2026-07-02

Audit result: `tech_debt`. No critical requirement, integration, or flow gaps remain after Phase 19. Accepted carry-forward items are tracked in `.planning/STATE.md`.

</details>

## Carried Gates

- Phase 5 live WeCom UAT remains an operator-confirmed human gate.
- Phase 8 five-workday lawyer trial remains a live legal/human gate.
- External memory services remain optional sanitized-spike candidates; platform-native memory stays the default legal path until privacy, residency, deletion/export, security, review, and procurement gates pass.
- Nyquist validation artifacts for Phases 14, 15, 16, 18, and 19 are accepted validation debt from the v1.2 close.

## Progress

| Phase Group | Milestone | Plans Complete | Status | Completed |
|-------------|-----------|----------------|--------|-----------|
| Phases 1-8 | V2 PRD Foundation | 27/27 | Complete with live human gates carried | 2026-06-30 |
| Phases 09-13 | v1.1 Platform Foundation | 20/20 | Shipped | 2026-06-30 |
| Phases 14-19 | v1.2 Conversational Context and Memory Foundation | 16/16 | Shipped with accepted tech debt | 2026-07-02 |
| Next milestone | TBD | 0/0 | Awaiting definition | - |
