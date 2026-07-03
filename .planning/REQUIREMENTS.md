# Milestone v1.5: V2 Acceptance Closure — Requirements

**Defined:** 2026-07-03
**Milestone:** v1.5 V2 Acceptance Closure
**Goal:** Audit all unchecked V2 Active requirements against the actual codebase, close every code gap found, mark validated requirements in PROJECT.md, and produce a final V2 acceptance readiness report so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain before V2 is formally accepted.

## Requirements

### Audit Infrastructure (AUDIT)

- [x] **AUDIT-01**: Operator can run a traceability audit that maps each unchecked V2 Active requirement to concrete code evidence (file paths, test modules, gate names, schema IDs) with phase references.
- [x] **AUDIT-02**: Operator can view a per-requirement evidence bundle showing which files implement each requirement, which tests cover it, which gate suite proves it, and which fixtures exercise it.
- [x] **AUDIT-03**: Operator can run a gap analysis that classifies each unchecked requirement as `satisfied`, `partial`, `gap`, or `human_gate` against actual code using three-level verification (schema → library surface → production wiring).
- [x] **AUDIT-04**: CI runs a 9th V2 gate (`v2-acceptance-traceability`) that fails when any requirement is `status: gap` or evidence is missing.
- [x] **AUDIT-05**: Operator can read a machine-readable JSON traceability sidecar (`acceptance/v2-traceability.json`) mapping requirement IDs to evidence and status.
- [x] **AUDIT-06**: Operator can re-run the entire requirement-to-code audit deterministically via `scripts/audit_v2_requirements.py` and reproduce the same matrix and gap list.
- [x] **AUDIT-07**: Operator can view a PRD §10 criterion-to-test mapping showing which specific test(s) and fixture(s) prove each §10.1–10.4 acceptance criterion.

### Gap Closure (GAP)

- [x] **GAP-01**: All genuine code gaps identified by the audit in WeCom service (receive/send, ACK, normalization, delivery, feedback callbacks, idempotency, retry, output policy) are closed with tests.
- [x] **GAP-02**: All genuine code gaps in the assistant output boundary (blocking/rewriting Hermes gateway/update/command/meta notices) are closed with tests.
- [x] **GAP-03**: All genuine code gaps in feedback normalization (FeedbackEvent dedupe, classification, human-reviewed skill candidates) are closed with tests.
- [x] **GAP-04**: All genuine code gaps in conversation-read-view (read-only APIs from contract logs) are closed with tests.
- [x] **GAP-05**: All genuine code gaps in CI composability (industry-neutral contract behavior, synthetic task coverage) are closed with tests.
- [x] **GAP-06**: All genuine code gaps in observability/replay/privacy baselines are closed with tests.
- [x] **GAP-07**: All 7 existing V2 gate suites (424+ tests) pass green after gap closure with no regressions.
- [x] **GAP-08**: Operator can view a composability fixture coverage report showing which §10.3 synthetic task types are covered by fixtures and which are missing.
- [x] **GAP-09**: Operator can view a privacy/output-boundary fixture evidence summary proving gateway/update/command/meta samples are blocked or rewritten per §10.2.

### Traceability and Documentation (DOC)

- [x] **DOC-01**: PROJECT.md Active requirements are updated — validated requirements move to Validated with phase references; stale sections updated.
- [x] **DOC-02**: Operator can read a V2 acceptance readiness report (`.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`) mirroring PRD §10.1–10.4 structure with satisfied criteria, closed gaps, and remaining human gates.
- [x] **DOC-03**: Operator can read Phase 5 live WeCom UAT documentation including pre-UAT fixture evidence summary, operator checklist, and pass/fail criteria.
- [x] **DOC-04**: Operator can read Phase 8 five-workday lawyer trial documentation including trial protocol, metric-collection template, §10.4 thresholds, and trial-log template.
- [x] **DOC-05**: The readiness report uses a two-tier status model: autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES — never conflating code closure with formal acceptance.
- [x] **DOC-06**: Human-gate requirements (Phase 5 live WeCom UAT, Phase 8 five-workday lawyer trial) remain unchecked in PROJECT.md until real evidence exists.
- [x] **DOC-07**: The readiness report classifies each V2-PRD §13 residual risk as source-resolved, implementation-resolved, or live-evidence-pending.

## Future Requirements (Deferred)

- **FUTURE-01**: Automated re-audit on PR via CI integration (M2+ scope)
- **FUTURE-02**: Real-time acceptance dashboard (M2+ admin console scope)
- **FUTURE-03**: Full requirements database with drift detection (M2+ scope)
- **FUTURE-04**: Gap-closure change log as structured per-requirement changelog (derivable from git log for v1.5)

## Out of Scope

- **Automated lawyer trial execution** — Phase 8 five-workday lawyer trial is a human gate requiring live evidence; v1.5 documents the trial protocol but does not execute the trial.
- **Live WeCom UAT automation** — Phase 5 live WeCom UAT is a human gate requiring operator confirmation; v1.5 documents the UAT checklist but does not execute live UAT.
- **M2 scope expansion** — Codex/provider_model adapter prototypes, Router Service, Skill Registry read, Admin Console API, QQBot loop are M2 per V2-PRD §11, gated on V2 acceptance.
- **Rebuilding shipped milestones** — v1.1–v1.4 code is the baseline; gap closure is in-place edits, not rebuilds.
- **New runtime dependencies** — The codebase is deliberately dependency-free; acceptance-closure tooling is stdlib-only.
- **New services, databases, or queues** — AGENTS rule forbids new runtime infrastructure unless PRD or active GSD plan requires it.

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
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

---
*Requirements defined: 2026-07-03*
*Total: 23 requirements (7 AUDIT + 9 GAP + 7 DOC)*
