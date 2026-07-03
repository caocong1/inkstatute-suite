# Project Research Summary

**Project:** 墨律 InkStatute V2
**Domain:** V2 acceptance closure — requirement traceability, gap analysis, readiness reporting, human-gate documentation
**Researched:** 2026-07-03
**Confidence:** HIGH

## Executive Summary

v1.5 is not a feature milestone — it is an acceptance-closure milestone. The codebase has 4 shipped milestones (v1.1–v1.4), 424 passing tests across 7 gate suites, 4 services, and 7 packages. The 10 unchecked V2 Active requirements in PROJECT.md may already be satisfied by shipped code. The milestone's job is to audit each requirement against actual code, close any genuine gaps, update traceability, and produce a readiness report so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain before V2 is formally accepted.

The recommended approach is stdlib-only tooling that fits the existing dependency-free invariant. No new runtime dependencies, services, databases, or queues. The closure tooling lives in `scripts/` and a new `acceptance/` directory, extends the existing V2 gate runner with one new gate, and produces a machine-readable JSON traceability manifest plus a markdown readiness report. The audit invokes existing contract-test-suite evidence producers (`boundary_checks`, `privacy_scan`, `coverage_report`, `schema_validation`) rather than re-implementing checks.

The top risks are: (1) false positives — marking a requirement "done" because a module exists when production wiring is missing (this exact pattern occurred in v1.4 with MEM-07/MEM-16); (2) gap-closure regressions in shipped v1.2–v1.4 code; (3) overstating readiness by conflating autonomous code closure with formal V2 acceptance (human gates remain). Prevention requires three-level verification (schema → library surface → production wiring), test-first gap closure with full gate regression, and a two-tier status model (autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES).

## Key Findings

### Recommended Stack

No new runtime dependencies. The codebase is deliberately dependency-free (`dependencies = []` in every `pyproject.toml`, stdlib-only JSON-Schema subset validator). Acceptance-closure tooling must stay stdlib-only and live in `scripts/` or `acceptance/`, not in shipped packages.

**Core technologies:**
- Python stdlib only (3.11+): `pathlib`, `re`, `json`, `tomllib`, `argparse`, `dataclasses`, `subprocess`, `ast`, `datetime` — covers every traceability, gap-analysis, and report-generation need
- JSON (not YAML) for traceability manifest: `json` is stdlib; PyYAML is not installed; keeps tooling dependency-free and diff-friendly
- Markdown for readiness report: fits existing artifact convention (`MILESTONE-AUDIT.md`, `VERIFICATION.md`); no template engine needed

### Expected Features

**Must have (table stakes — 9 P1 features):**
- Requirement-to-code traceability matrix — maps 10 unchecked Active requirements to PRD §10 criteria, code evidence, test/gate evidence, phase references, status
- Per-requirement audit evidence collection — deterministic, reproducible evidence bundles (files, tests, gates, fixtures)
- Gap analysis — requirement vs. shipped code diff, classifying each as satisfied/partial/missing
- Code gap closure — implement missing V2 code work identified by audit, re-validate via gates
- PROJECT.md traceability update — move validated requirements from Active to Validated with phase references
- V2 acceptance readiness report — formal document mirroring PRD §10.1–10.4 structure
- Phase 5 human-gate documentation — live WeCom UAT checklist, fixture evidence summary, operator confirmation requirements
- Phase 8 human-gate documentation — trial protocol, metric-collection template, §10.4 thresholds, trial-log template
- V2 gate runner green re-confirmation — all gates pass post-gap-closure

**Should have (differentiators — 6 P2 features):**
- Machine-readable JSON traceability sidecar — enables future tooling (M2 admin console, automated re-audit, drift detection)
- Regenerable audit script — `scripts/audit_v2_requirements.py` re-runs entire audit deterministically
- PRD §10 criterion-to-test mapping — criterion-level (not just requirement-level) traceability
- Gap-closure change log — structured per-requirement changelog
- Composability fixture coverage report — §10.3 task types vs. fixture coverage
- Privacy/output-boundary fixture evidence summary — §10.2 output-boundary proof

**Defer (M2+):**
- Automated lawyer trial execution (human gate — not autonomous)
- Live WeCom UAT automation (human gate — not autonomous)
- Full requirements database (overkill for closure milestone)
- Real-time acceptance dashboard (M2+ admin console scope)

### Architecture Approach

The audit engine consumes the existing `run_v2_gates.py --json-summary` output as its primary evidence backbone. It parses PROJECT.md Active requirements + V2-PRD §10 acceptance criteria, probes code via evidence checks (file existence, test module presence, gate results, schema IDs, AST/import-root scans), and classifies each requirement as `satisfied` / `gap` / `human_gate`. Gap closure is in-place edits to existing services/packages — no new runtime service or database. The readiness report lives at `.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md` following the established milestone-audit convention.

**Major components:**
1. `acceptance/v2-traceability.json` — machine-readable manifest mapping requirements to code evidence (NEW)
2. `scripts/audit_v2_requirements.py` — gap analyzer following `check_v1_3_verification_artifacts.py` pattern (NEW)
3. `scripts/generate_v2_readiness_report.py` — report generator using stdlib string templates (NEW)
4. `scripts/run_v2_gates.py` — extended with 9th gate `v2-acceptance-traceability` (MODIFIED)
5. Gap-closure targets in existing services/packages — in-place edits driven by audit results (MODIFIED)

### Critical Pitfalls

1. **False positive traceability** — marking a requirement "done" because a module exists when production wiring is missing (v1.4 MEM-07/MEM-16 pattern). Prevention: three-level verification (schema → library surface → production wiring path).
2. **Gap-closure regressions** — modifying shipped `WeComSessionRuntime`/`OutputPolicy`/`ingress_runtime.py` and breaking v1.2–v1.4 tests. Prevention: pre-change baseline, test-first, full gate-suite regression check.
3. **Readiness overstatement** — report says "V2 ready for acceptance" without distinguishing autonomous code closure from formal V2 acceptance. Prevention: two-tier status model (autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES).
4. **PROJECT.md checkbox conflation** — checking `[x]` on "Complete the five-workday lawyer trial" after code closure. Prevention: human-gate requirements remain unchecked until real trial evidence exists.
5. **PYTHONPATH gate runner regression** — the 424-test baseline was silently inaccurate from v1.2–v1.4 due to missing PYTHONPATH entries. Prevention: verify gate runner as the first audit step.

## Implications for Roadmap

Based on research, suggested phase structure (continues numbering from Phase 33):

### Phase 33: V2 Requirement Audit & Traceability Infrastructure
**Rationale:** Must come first — cannot close gaps without knowing which requirements are unsatisfied. Builds the audit tooling that all subsequent phases depend on.
**Delivers:** `acceptance/v2-traceability.json`, `scripts/audit_v2_requirements.py`, extended `run_v2_gates.py` with 9th gate, audit results classifying all 10 unchecked requirements as satisfied/partial/gap/human_gate.
**Addresses:** Traceability matrix, per-requirement evidence collection, gap analysis, gate runner extension
**Avoids:** False positive pitfall by using three-level verification (schema → library surface → production wiring)

### Phase 34: V2 Code Gap Closure
**Rationale:** Depends on Phase 33 audit results. Closes genuine code gaps identified by the audit in existing services/packages. No new services or dependencies.
**Delivers:** In-place fixes to WeCom service, output boundary, feedback normalization, conversation-read-view, CI composability, observability/replay/privacy baselines as identified by audit. Each closed gap adds/extends tests and re-runs gates green.
**Uses:** Existing services/packages, existing V2 gate suites, stdlib-only tooling
**Avoids:** Gap-closure regression pitfall via test-first approach and full gate-suite regression check

### Phase 35: V2 Acceptance Readiness Report & Traceability Update
**Rationale:** Must come after gap closure — updates PROJECT.md traceability honestly based on closed gaps and generates the final readiness report.
**Delivers:** `scripts/generate_v2_readiness_report.py`, `.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`, updated PROJECT.md (Active → Validated with phase refs), Phase 5/8 human-gate documentation packages, regenerable audit script committed.
**Addresses:** Readiness report, PROJECT.md traceability update, human-gate documentation, gate runner green re-confirmation
**Avoids:** Readiness overstatement pitfall via two-tier status model; checkbox conflation pitfall by keeping human-gate requirements unchecked

### Phase Ordering Rationale

- Phase 33 → 34: Audit must precede closure — you cannot close gaps without knowing which requirements are unsatisfied
- Phase 34 → 35: Closure must precede traceability update — PROJECT.md validated status must reflect actual post-closure state, not pre-closure intent
- Phase 35 is last: Readiness report synthesizes all prior work; human-gate documentation is only honest once code gaps are closed and gates are green
- This order respects the dependency chain: audit → gap closure → traceability → readiness report

### Research Flags

Phases with standard patterns (skip deep research during planning):
- **Phase 33:** Follows proven `check_v1_3_verification_artifacts.py` pattern; stdlib-only tooling well understood
- **Phase 34:** In-place edits to existing code; gap scope determined by audit, not pre-planned
- **Phase 35:** Report generation follows existing milestone-audit convention; markdown template well established

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; stdlib-only pattern proven by existing gate runner and audit scripts |
| Features | HIGH | Closure features are well-defined by PRD §10 and PROJECT.md Active requirements; 9 P1 + 6 P2 clearly scoped |
| Architecture | HIGH | Integrates with existing gate runner and contract-test-suite evidence producers; no new architecture |
| Pitfalls | HIGH | Informed by actual v1.1–v1.4 history (PYTHONPATH regression, traceability table gap, MEM-07/MEM-16 partial wiring) |

**Overall confidence:** HIGH

### Gaps to Address

- Actual gap scope unknown until Phase 33 audit runs — the 10 unchecked requirements may be mostly satisfied already, or may reveal significant gaps. Phase 34 scope is deliberately reactive.
- Phase 5/8 human-gate documentation quality depends on access to live UAT/trial artifacts — the documentation packages define what's needed, but live evidence collection is out of scope.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — 10 unchecked Active requirements, constraints, evolution protocol
- `docs/requirements/V2-PRD.md` — §10 acceptance criteria, §12 development order, §13 residual risks
- `scripts/run_v2_gates.py` — existing gate runner architecture (424 tests, 7 suites, `--json-summary`)
- `.planning/MILESTONES.md` — v1.1–v1.4 shipped milestone audit results
- Existing source: `scripts/check_v1_3_verification_artifacts.py` — proven audit script pattern

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` — stack analysis (stdlib-only, no new dependencies)
- `.planning/research/FEATURES.md` — feature categorization (9 P1, 6 P2, 7 anti-features)
- `.planning/research/ARCHITECTURE.md` — integration architecture (audit → closure → traceability → report)
- `.planning/research/PITFALLS.md` — 10 pitfalls informed by v1.1–v1.4 history

---
*Research completed: 2026-07-03*
*Ready for roadmap: yes*
