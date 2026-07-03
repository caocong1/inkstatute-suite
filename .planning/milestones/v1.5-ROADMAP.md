# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)
- Complete **v1.4 Long-Term Memory Productization** - Phases 26-32 shipped 2026-07-03. Productized long-term memory with Hindsight backend, singleton wiring, and contract event observability. Audit passed (20/20 requirements).
  - Archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

## Current Milestone: v1.5 V2 Acceptance Closure

**Goal:** Audit all unchecked V2 Active requirements against the actual codebase, close every code gap found, mark validated requirements in PROJECT.md, and produce a final V2 acceptance readiness report so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain before V2 is formally accepted.

**Requirements:** `.planning/REQUIREMENTS.md`

## Phases

- [x] **Phase 33: V2 Requirement Audit & Traceability Infrastructure** - Build deterministic audit tooling that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied/partial/gap/human_gate.
- [x] **Phase 34: V2 Code Gap Closure** - Close every genuine code gap identified by the audit in existing services/packages with tests, keeping all V2 gate suites green.
- [x] **Phase 35: V2 Acceptance Readiness Report & Traceability Update** - Update PROJECT.md traceability honestly and produce the final V2 acceptance readiness report with human-gate documentation.

## Status

**Status:** COMPLETE — all 3 phases shipped (33-35), 23/23 requirements satisfied, 479 tests green.

## Phase Details

### Phase 33: V2 Requirement Audit & Traceability Infrastructure

**Goal:** Operator can run a deterministic audit that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied, partial, gap, or human_gate using three-level verification.
**Depends on:** v1.4 completion (Phase 32)
**Requirements:** AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06, AUDIT-07
**Success Criteria** (what must be TRUE):

1. Operator runs `scripts/audit_v2_requirements.py` and receives a complete requirement-to-code traceability matrix with file paths, test modules, gate names, and schema IDs for each unchecked V2 Active requirement, reproducible across runs.
2. Operator can inspect a per-requirement evidence bundle showing which files implement each requirement, which tests cover it, which gate suite proves it, and which fixtures exercise it.
3. Each unchecked requirement is classified as `satisfied`, `partial`, `gap`, or `human_gate` using three-level verification (schema definition → library surface → production wiring path), preventing the false-positive pattern seen in v1.4 MEM-07/MEM-16.
4. CI runs a 9th V2 gate (`v2-acceptance-traceability`) that fails when any requirement is `status: gap` or evidence is missing.
5. Operator can read a machine-readable JSON traceability sidecar (`acceptance/v2-traceability.json`) and a PRD §10 criterion-to-test mapping showing which specific tests and fixtures prove each §10.1–10.4 acceptance criterion.

**Plans:** TBD

### Phase 34: V2 Code Gap Closure

**Goal:** Every genuine code gap identified by the Phase 33 audit is closed in-place with tests, and all existing V2 gate suites pass green with no regressions.
**Depends on:** Phase 33
**Requirements:** GAP-01, GAP-02, GAP-03, GAP-04, GAP-05, GAP-06, GAP-07, GAP-08, GAP-09
**Success Criteria** (what must be TRUE):

1. All genuine code gaps identified by the audit in WeCom service (receive/send, ACK, normalization, delivery, feedback callbacks, idempotency, retry, output policy), assistant output boundary, feedback normalization, conversation-read-view, CI composability, and observability/replay/privacy baselines are closed with tests.
2. All 7 existing V2 gate suites (424+ tests) pass green after gap closure with no regressions.
3. Operator can view a composability fixture coverage report showing which §10.3 synthetic task types are covered by fixtures and which are missing.
4. Operator can view a privacy/output-boundary fixture evidence summary proving gateway/update/command/meta samples are blocked or rewritten per §10.2.

**Plans:** TBD

### Phase 35: V2 Acceptance Readiness Report & Traceability Update

**Goal:** Operator can read a final V2 acceptance readiness report and updated PROJECT.md traceability that honestly distinguishes autonomous code closure from remaining human gates.
**Depends on:** Phase 34
**Requirements:** DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07
**Success Criteria** (what must be TRUE):

1. PROJECT.md Active requirements are updated — validated requirements move to Validated with phase references and stale sections are updated, while human-gate requirements (Phase 5 live WeCom UAT, Phase 8 five-workday lawyer trial) remain unchecked until real evidence exists.
2. Operator can read a V2 acceptance readiness report (`.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`) mirroring PRD §10.1–10.4 structure with satisfied criteria, closed gaps, and remaining human gates.
3. Operator can read Phase 5 live WeCom UAT documentation (pre-UAT fixture evidence summary, operator checklist, pass/fail criteria) and Phase 8 five-workday lawyer trial documentation (trial protocol, metric-collection template, §10.4 thresholds, trial-log template).
4. The readiness report uses a two-tier status model (autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES) and classifies each V2-PRD §13 residual risk as source-resolved, implementation-resolved, or live-evidence-pending.

**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 33. V2 Requirement Audit & Traceability Infrastructure | 1/1 | Complete | 2026-07-03 |
| 34. V2 Code Gap Closure | 1/1 | Complete | 2026-07-03 |
| 35. V2 Acceptance Readiness Report & Traceability Update | 1/1 | Complete | 2026-07-03 |

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | 33 | Complete |
| AUDIT-02 | 33 | Complete |
| AUDIT-03 | 33 | Complete |
| AUDIT-04 | 33 | Complete |
| AUDIT-05 | 33 | Complete |
| AUDIT-06 | 33 | Complete |
| AUDIT-07 | 33 | Complete |
| GAP-01 | 34 | Complete |
| GAP-02 | 34 | Complete |
| GAP-03 | 34 | Complete |
| GAP-04 | 34 | Complete |
| GAP-05 | 34 | Complete |
| GAP-06 | 34 | Complete |
| GAP-07 | 34 | Complete |
| GAP-08 | 34 | Complete |
| GAP-09 | 34 | Complete |
| DOC-01 | 35 | Complete |
| DOC-02 | 35 | Complete |
| DOC-03 | 35 | Complete |
| DOC-04 | 35 | Complete |
| DOC-05 | 35 | Complete |
| DOC-06 | 35 | Complete |
| DOC-07 | 35 | Complete |

**Coverage: 23/23 requirements mapped (100%)**
