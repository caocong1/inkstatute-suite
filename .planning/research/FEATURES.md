# Feature Research

**Domain:** V2 acceptance closure tooling — requirement traceability, gap analysis, readiness reporting, and human-gate documentation for a backend-neutral agent platform (InkStatute V2).
**Researched:** 2026-07-03
**Confidence:** HIGH

## Scope Note

This research covers **acceptance closure features only** — the audit, traceability, gap-analysis, readiness-report, and human-gate-documentation capabilities needed to close the v1.5 milestone. The underlying product features (WeCom service, platform contracts, Hermes contract layer, feedback service, conversation read view, platform runtime, V2 gate runner) are already shipped across v1.1–v1.4 and are explicitly out of scope for re-research.

The ten unchecked V2 Active requirements in `PROJECT.md` (lines 43–52) and the V2-PRD §10 acceptance criteria (sections 10.1–10.4) are the closure targets. Closure features must prove each requirement is satisfied by shipped code, surface any residual code gaps, and document exactly which human gates remain.

## Feature Landscape

### Table Stakes (Users Expect These)

Features the milestone cannot close without. Missing any of these means the acceptance audit is incomplete and V2 cannot be declared ready.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Requirement-to-code traceability matrix | V2-PRD §10 acceptance is requirement-driven; each unchecked Active requirement in PROJECT.md must map to concrete code (services, packages, tests, fixtures) with phase references. Without a matrix, "validated" claims are unverifiable. | MEDIUM | Builds on existing V2 gate runner (424 tests / 7 suites) and MILESTONES.md phase archives. Matrix rows = the 10 unchecked Active requirements; columns = PRD clause, shipped artifact path, test/gate evidence, phase reference, status. Output as a markdown table embedded in the readiness report plus a machine-readable JSON sidecar. |
| Per-requirement audit evidence collection | Each unchecked requirement needs a deterministic, reproducible evidence bundle: which files implement it, which tests cover it, which gate suite proves it, which fixtures exercise it. Hand-waving "it's in the code" is not acceptance-grade. | MEDIUM | Script-driven: grep/glob over `packages/`, `services/`, `solutions/`, `tests/`, `fixtures/` keyed by requirement ID. Reuses `scripts/run_v2_gates.py --json-summary` for gate-level evidence. Evidence must be regenerable, not hand-edited. |
| Gap analysis — requirement vs. shipped code diff | The audit's core output is "what's done vs. what's missing." For each unchecked requirement, the closure tooling must classify it as satisfied / partial / missing against actual code, not against intent or roadmap claims. | HIGH | Hardest table-stakes item. Requires reading PRD §10 acceptance criteria (10.1 repo/docs, 10.2 contract CI, 10.3 composability, 10.4 lawyer trial), mapping each criterion to a code probe, and emitting a gap list. Partial items must cite the specific missing sub-capability (e.g., "WeCom service ships ACK + normalization + delivery but output-policy fixture coverage is incomplete"). |
| Code gap closure (implementation, not just detection) | v1.5 milestone goal explicitly says "close every code gap found." The audit is not done when gaps are listed; gaps in WeCom service completeness, output boundary, feedback normalization, read-view, CI composability, and observability/replay/privacy baselines must be implemented and re-validated. | HIGH | Scope is bounded by the 10 unchecked requirements and PRD §10.2/10.3 criteria. Each closed gap must add or extend tests in the relevant V2 gate suite and re-run `run_v2_gates.py` green. Out of scope: rebuilding shipped milestones, new product features beyond closure. |
| PROJECT.md traceability update | PROJECT.md is the persistent requirement ledger. Validated requirements must move from Active `[ ]` to Validated with phase references (per the Evolution protocol, lines 159–164). Stale sections updated. This is the durable artifact, not a throwaway report. | LOW | Mechanical once the audit matrix is complete. Edit PROJECT.md Active/Validated sections, add phase refs, update Current State. Must be done as part of closure, not after. |
| V2 acceptance readiness report | PRD §10 has four acceptance sections; the milestone goal requires a "final V2 acceptance readiness report" summarizing what's done, what gaps were closed, and exactly which human gates remain. This is the deliverable that triggers formal acceptance. | MEDIUM | Single markdown document (e.g., `.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`). Structure mirrors PRD §10.1–10.4: repo/docs status, contract CI status, composability status, lawyer trial status (human gate). Each section: satisfied criteria with evidence, closed gaps, remaining human gates. |
| Human gate documentation — Phase 5 live WeCom UAT | PROJECT.md Current State (line 150) carries Phase 5 as a human gate "fixture-satisfied, operator confirmation needed." Closure must document exactly what operator confirmation is required, what fixtures already satisfy the automated portion, and the precise live-UAT checklist. | LOW | Not the UAT itself (that's human). The feature is the documentation artifact: pre-UAT fixture evidence summary, operator checklist, pass/fail criteria drawn from PRD §10.2/10.4. |
| Human gate documentation — Phase 8 five-workday lawyer trial | PRD §10.4 defines 13 trial acceptance criteria (5 workdays, 15 tasks, 12 with output, 3 task types, 80% long-task success, 85% normal success, 60% feedback capture, 60% positive, 48h negative response, ≤3 route_mismatch, no WeCom regression, InkStatute-owned channel, no Hermes meta leakage, bootstrap evidence, zero-breakage). Closure must produce the trial protocol, metric-collection template, and evidence-acceptance criteria. | MEDIUM | Not the trial itself (5 workdays, human). The feature is the trial readiness package: metric definitions matching §10.4, collection method (from contract logs + feedback service + read view), pass/fail thresholds, and a structured trial-log template. The readiness report must state the trial is "ready to commence" with all automated prerequisites green. |
| V2 gate runner green re-confirmation | All 7 gate suites (424 tests) must pass after any gap-closure code changes. The gate runner already exists; closure must re-run it and capture the result as readiness evidence. | LOW | `scripts/run_v2_gates.py --json-summary`. Already green per PROJECT.md line 148; closure re-confirms post-gap-closure. If gap closure adds tests, the count grows and must be reported. |

### Differentiators (Competitive Advantage)

Features that elevate the closure from "checkbox audit" to "reproducible, regenerable acceptance evidence." Not required to close V2, but valuable for M2+ and for audit defensibility.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Machine-readable traceability sidecar (JSON) | A JSON traceability file alongside the markdown matrix enables future tooling (M2 admin console, automated re-audit on PR, drift detection between PROJECT.md and code). Markdown-only is human-readable but not re-consumable. | LOW | Schema: `{requirement_id, prd_clause, status, artifacts: [path], tests: [gate_suite], phase_ref, gap_notes}`. Generated by the audit script, committed alongside the readiness report. |
| Regenerable audit script | A script that re-runs the entire requirement-to-code audit and emits the matrix + gap list deterministically. Means the readiness report is reproducible, not a one-time hand-written artifact. Critical for M2+ when requirements evolve. | MEDIUM | `scripts/audit_v2_requirements.py` — reads PROJECT.md Active requirements, probes code per requirement, runs gates, emits matrix + gap list + JSON sidecar. Depends on stable requirement IDs and code-path conventions. |
| PRD §10 criterion-to-test mapping | Explicit mapping from each §10.1–10.4 acceptance criterion to the specific test(s)/fixture(s) that prove it. Goes beyond requirement-level traceability to criterion-level. Makes the readiness report auditable by a third party who reads the PRD. | MEDIUM | ~25 criteria across §10.1–10.4. Each mapped to gate suite + test name + fixture path. Most already exist in the 424-test suite; the mapping is the missing piece. |
| Gap-closure change log | Structured log of every code change made during v1.5 gap closure: file, requirement ID, before/after, test added. Provides an audit trail for "what did closure actually change" beyond a git log. | LOW | Can be derived from git log filtered to the v1.5 commit range, but a structured per-requirement changelog is more useful for the readiness report. |
| Composability fixture coverage report | PRD §10.3 lists 7 synthetic task types (simple QA, contract review, legal retrieval, route mismatch, WeCom feedback, long-task failure, non-legal synthetic). A report showing which are covered by fixtures and which are missing differentiates "CI passes" from "CI proves §10.3." | MEDIUM | Probes `contract-test-suite` fixtures against the §10.3 task list. The non-legal synthetic task (tax/engineering/education returning valid AgentResult without legal fields) is the key differentiator per PRD §10.3. |
| Privacy/output-boundary fixture evidence summary | PRD §10.2 requires an output-boundary fixture proving gateway/update/command/meta samples are blocked or rewritten. A focused evidence summary (fixtures in, policy decisions out, no leakage) is more convincing than "gate suite passed." | LOW | Aggregates `phase7-privacy-boundary` gate results + output-policy fixtures into a human-readable summary for the readiness report. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good for an acceptance closure milestone but create problems or scope creep.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automated lawyer trial execution | "Can't we simulate the 5-workday trial with fixtures?" | PRD §10.4 explicitly requires real lawyer usage, real tasks, real business output. Simulated trials defeat the purpose of the human gate and would be acceptance fraud. The trial is a human gate by design (PROJECT.md line 98, line 151). | Produce the trial readiness package (protocol, metrics, templates) and declare the automated prerequisites green. The trial itself stays human. |
| Live WeCom UAT automation | "Run the UAT programmatically against a live WeCom tenant." | Phase 5 is an operator-confirmation human gate (PROJECT.md line 150). Live WeCom involves real credentials, real tenant, real message delivery — automating it risks sending real messages and is not autonomously completable. | Document the pre-UAT fixture evidence and operator checklist. Mark the gate as "ready for operator confirmation." |
| Full requirement-management system / database | "Build a requirements DB with IDs, status, history, dashboards." | Over-engineering for a closure milestone. PROJECT.md markdown + a JSON sidecar is sufficient and aligns with the GSD artifact model. A DB introduces a new runtime dependency, violating the AGENTS.md "no new service/DB unless PRD requires" rule. | Markdown traceability matrix in the readiness report + JSON sidecar. Evolve to a DB only if M2 admin console requires it. |
| Re-auditing already-validated requirements | "Re-check the 5 already-validated requirements and the 5 checked `[x]` Active items too." | The 5 `[x]` Active items (platform contract, event modeling, test suite, integration risk, shadow layer) are already validated across v1.1–v1.4 with phase evidence. Re-auditing them burns effort without changing the acceptance outcome. | Trust the MILESTONES.md audit records. Focus closure audit on the 10 unchecked `[ ]` items only. Note any drift if found incidentally, but don't re-run full validation. |
| Scope expansion into M2 features | "While auditing, also prototype the Codex adapter / Router Service / Skill Registry." | M2 is gated on V2 acceptance (PRD §11, PROJECT.md line 153). Building M2 features before V2 closure violates the binding development order (PRD §12) and re-introduces the V1 over-scoping failure mode. | Closure only. M2 features are explicitly Out of Scope until V2 is accepted. |
| Real-time acceptance dashboard / live status page | "A live web dashboard showing acceptance status." | The readiness report is a point-in-time artifact for a milestone gate, not an operational monitoring surface. A dashboard implies ongoing maintenance and a serving runtime the milestone doesn't need. | Static markdown readiness report + JSON sidecar. Regenerable on demand via the audit script. |
| Rebuilding shipped milestones to "improve" them | "The v1.2 audit was tech_debt; let's fix that during closure." | v1.2–v1.4 are shipped and audited. Reopening them expands scope beyond the 10 unchecked requirements and risks regressions. The v1.2 tech_debt was accepted at close (MILESTONES.md line 85). | Carry accepted tech debt forward. Only touch shipped code if a v1.5 gap-closure item requires it (e.g., extending a gate suite with missing fixtures). |

## Feature Dependencies

```
[Requirement-to-code traceability matrix]
    └──requires──> [Per-requirement audit evidence collection]
                       └──requires──> [V2 gate runner green re-confirmation] (existing)

[Gap analysis — requirement vs. shipped code]
    └──requires──> [Per-requirement audit evidence collection]
    └──requires──> [PRD §10 criterion-to-test mapping] (enhances accuracy)

[Code gap closure]
    └──requires──> [Gap analysis — requirement vs. shipped code]
    └──requires──> [V2 gate runner green re-confirmation] (re-run after changes)

[PROJECT.md traceability update]
    └──requires──> [Gap analysis — requirement vs. shipped code]
    └──requires──> [Code gap closure] (so validated status is accurate)

[V2 acceptance readiness report]
    └──requires──> [Requirement-to-code traceability matrix]
    └──requires──> [Gap analysis — requirement vs. shipped code]
    └──requires──> [Code gap closure]
    └──requires──> [Human gate documentation — Phase 5]
    └──requires──> [Human gate documentation — Phase 8]

[Human gate documentation — Phase 8]
    └──requires──> [PRD §10 criterion-to-test mapping] (to define trial metrics)

[Regenerable audit script]
    └──enhances──> [Per-requirement audit evidence collection]
    └──enhances──> [Requirement-to-code traceability matrix]
    └──enhances──> [Gap analysis — requirement vs. shipped code]

[Machine-readable traceability sidecar]
    └──enhances──> [Requirement-to-code traceability matrix]

[Composability fixture coverage report]
    └──enhances──> [V2 acceptance readiness report] (proves §10.3)

[Privacy/output-boundary fixture evidence summary]
    └──enhances──> [V2 acceptance readiness report] (proves §10.2 output boundary)
```

### Dependency Notes

- **Traceability matrix requires audit evidence collection:** The matrix is only as credible as the evidence behind each row. Evidence collection must be script-driven and reproducible, not hand-asserted.
- **Gap analysis requires PRD §10 criterion-to-test mapping:** Requirement-level audit (10 unchecked items) is necessary but not sufficient — PRD §10 defines ~25 finer-grained acceptance criteria. The criterion mapping ensures no criterion is silently skipped.
- **Code gap closure requires gap analysis first:** Closure is reactive to the audit. Do not pre-emptively change code before the gap list is produced, or the audit becomes post-hoc rationalization.
- **PROJECT.md update requires gap closure:** Moving a requirement to Validated is only honest after its gaps are closed and gates are green. Updating PROJECT.md before closure completes would be premature.
- **Readiness report requires all other closure features:** The report is the synthesis artifact. It cannot be written until the matrix, gap analysis, closure, and human-gate docs all exist.
- **Regenerable audit script enhances (not requires) the matrix:** The matrix can be produced manually the first time, but a script makes it reproducible and is a differentiator for M2+.

## Mapping to Unchecked V2 Active Requirements

Each unchecked Active requirement (PROJECT.md lines 43–52) maps to closure-audit features and PRD §10 criteria:

| # | Unchecked Active Requirement | PRD §10 Criteria | Closure Audit Focus | Likely Status (pre-audit) |
|---|---|---|---|---|
| 1 | WeCom service (receive/send, ACK, normalization, delivery, feedback callbacks, idempotency, retry, output policy) | §10.2 (WeCom contract tests), §10.4 (InkStatute-owned channel) | Probe `services/wecom-service/` for all 8 sub-capabilities; verify wecom-service gate suite covers each; check output-policy fixture coverage | Partial — service shipped in v1.1/v1.2, gate suite green, but output-policy fixture completeness per §10.2 needs verification |
| 2 | Agent backend adapter contract + runtime selector (Hermes first, Codex/provider-model future) | §8 (可替换性), §10.4 (bootstrap evidence) | Probe `packages/backends/hermes/` + adapter contract; verify mode-selection contract exists; confirm Codex/provider_model modes are contract-compatible stubs | Likely satisfied — v1.1 shipped BackendAdapter + Hermes adapter; verify future-mode contract compatibility |
| 3 | Hermes agent adapter bootstrap (sanitized profile bundle, version/capability matrix, secrets/env, health checks) | §10.4 (bootstrap evidence), §8 (可部署性) | Probe for version/capability manifest, sanitized bundle path, health-check implementation; verify secrets-out-of-repo | Partial — v1.1 shipped Hermes adapter + sanitizing materializer; verify health checks + version matrix completeness |
| 4 | Assistant output boundary (filter Hermes gateway/update/command/meta) | §10.2 (output boundary fixture), §8 (用户出口纯净性), §10.4 (no Hermes meta leakage) | Probe output-policy implementation + phase7-privacy-boundary gate; verify gateway/update/command/meta fixtures are blocked/rewritten | Partial — output boundary shipped in v1.1; fixture coverage against all notice types per §10.2 needs verification |
| 5 | WeCom task→agent→reply→card→feedback loop validation | §10.2 (关联完整性, 断裂率 ≤5%), §10.4 (no WeCom regression) | Probe for end-to-end loop fixtures; verify message→task→route→response→feedback chain integrity tests exist | Partial — components shipped across v1.1–v1.4; integrated loop fixture may need strengthening |
| 6 | Feedback normalization (FeedbackEvent, dedupe, classification, skill candidates) | §10.3 (WeCom feedback → FeedbackEvent), §10.4 (feedback capture ≥60%, skill_candidate generation) | Probe `services/feedback-service/` for dedupe, classification, skill_candidate; verify feedback-service gate suite | Likely satisfied — feedback service shipped; verify skill_candidate human-review enforcement |
| 7 | Read-only conversation/task/feedback APIs from contract logs | §10.3 (read view for failed long-task), §10.4 (metric collection) | Probe `services/conversation-read-view/`; verify query by conversation_id/task_id/trace_id; confirm read-only | Likely satisfied — read view shipped in v1.1; verify API completeness |
| 8 | Observability, replay, privacy, legal safety baselines | §8 (可观测性, 可审计性), §10.2 (coverage ≥95%, fixture replay) | Probe for execution_trace coverage, occurred_at/ingested_at/seq, replay fixtures, privacy scan, raw_payload_ref usage | Partial — observability built across milestones; verify ≥95% coverage claim and replay fixture completeness |
| 9 | Composability + industry-neutral CI | §10.3 (7 synthetic tasks incl. non-legal), §8 (可组合性 hard) | Probe contract-test-suite for 7 §10.3 task types; verify non-legal synthetic returns valid AgentResult without legal fields; confirm CI gate | Partial — composability gate exists; verify all 7 task types + non-legal synthetic fixture |
| 10 | Five-workday lawyer trial acceptance criteria | §10.4 (13 trial criteria) | Not code — produce trial readiness package (protocol, metrics, templates); declare automated prerequisites green; gate stays human | Human gate — documentation only; trial itself is not autonomously completable |

## MVP Definition

### Launch With (v1.5 closure — all required)

Minimum viable acceptance closure — what's needed to declare V2 ready for the two remaining human gates.

- [ ] Per-requirement audit evidence collection — script-driven, reproducible, covers all 10 unchecked Active requirements
- [ ] Requirement-to-code traceability matrix — markdown table + JSON sidecar, mapping each requirement to artifacts/tests/phase/status
- [ ] Gap analysis — requirement vs. shipped code diff, classifying each as satisfied/partial/missing with specific gap notes
- [ ] Code gap closure — implement every missing/partial V2 code item, re-run V2 gates green
- [ ] PROJECT.md traceability update — move validated requirements Active→Validated with phase refs; update Current State
- [ ] Human gate documentation — Phase 5 live WeCom UAT checklist + pre-UAT fixture evidence
- [ ] Human gate documentation — Phase 8 lawyer trial readiness package (protocol, §10.4 metrics, templates)
- [ ] V2 acceptance readiness report — formal document synthesizing all of the above against PRD §10.1–10.4
- [ ] V2 gate runner green re-confirmation — post-closure gate run captured as readiness evidence

### Add After Validation (v1.5.x / M2 prep)

Features to add once the core closure is working and V2 is approaching formal acceptance.

- [ ] Regenerable audit script (`scripts/audit_v2_requirements.py`) — trigger: need to re-audit after M2 requirement changes
- [ ] PRD §10 criterion-to-test mapping (criterion-level, not just requirement-level) — trigger: third-party audit or M2 admin console
- [ ] Gap-closure change log — trigger: need to explain closure changes to stakeholders beyond git log
- [ ] Composability fixture coverage report — trigger: §10.3 coverage questioned or M2 adds new task types
- [ ] Privacy/output-boundary fixture evidence summary — trigger: security review or M2 multi-tenant work

### Future Consideration (M2+)

Features to defer until V2 is formally accepted and M2 begins.

- [ ] Automated re-audit on PR (CI integration of the audit script) — defer until requirement IDs are stable and M2 adds requirements
- [ ] Requirement drift detection (PROJECT.md vs. code) — defer until M2 admin console provides a UI surface
- [ ] Live acceptance status dashboard — defer; static report is sufficient for a milestone gate, not an operational surface
- [ ] Multi-milestone traceability (v1.1–v1.5 + M2+ unified view) — defer until M2 ships and historical view adds value

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Per-requirement audit evidence collection | HIGH | MEDIUM | P1 |
| Requirement-to-code traceability matrix | HIGH | MEDIUM | P1 |
| Gap analysis — requirement vs. shipped code | HIGH | HIGH | P1 |
| Code gap closure | HIGH | HIGH | P1 |
| PROJECT.md traceability update | HIGH | LOW | P1 |
| V2 acceptance readiness report | HIGH | MEDIUM | P1 |
| Human gate documentation — Phase 5 | HIGH | LOW | P1 |
| Human gate documentation — Phase 8 | HIGH | MEDIUM | P1 |
| V2 gate runner green re-confirmation | HIGH | LOW | P1 |
| Machine-readable traceability sidecar (JSON) | MEDIUM | LOW | P2 |
| Regenerable audit script | MEDIUM | MEDIUM | P2 |
| PRD §10 criterion-to-test mapping | MEDIUM | MEDIUM | P2 |
| Gap-closure change log | LOW | LOW | P2 |
| Composability fixture coverage report | MEDIUM | MEDIUM | P2 |
| Privacy/output-boundary fixture evidence summary | MEDIUM | LOW | P2 |

**Priority key:**
- P1: Must have for v1.5 closure — without these, V2 acceptance cannot be declared ready
- P2: Should have — add when possible to strengthen audit defensibility and enable M2+ re-audit
- P3: Nice to have — future consideration after V2 formal acceptance

## Competitor / Industry Feature Analysis

There are no direct competitors for InkStatute's specific acceptance closure (it is a single-product internal milestone). The relevant comparison is against industry acceptance-closure practices:

| Feature | Industry Norm (enterprise software) | Audit-Grade Practice (regulated/safety-critical) | Our Approach (v1.5) |
|---------|-------------------------------------|---------------------------------------------------|---------------------|
| Requirement traceability matrix | Spreadsheet or ALM tool (Jama, Polarion, DOORS) linking requirements to tests | Bidirectional trace (requirement ↔ test ↔ code), automated, regenerable, version-controlled | Markdown matrix + JSON sidecar in repo, script-regenerable; bidirectional via PRD clause ↔ test ↔ artifact paths |
| Gap analysis | Manual review or ALM diff report | Automated requirement-vs-implementation diff with evidence probes | Script-driven code probes per requirement + gate evidence; gap list with satisfied/partial/missing classification |
| Acceptance readiness report | Sign-off document with stakeholder signatures | Formal readiness review with criteria-by-criteria evidence, independent verification | Markdown report mirroring PRD §10.1–10.4, each criterion with evidence/gap/human-gate status |
| Human gate documentation | Checklist in a wiki or ticket | Pre-defined protocol with pass/fail criteria, evidence requirements, and escalation paths | Phase 5 operator checklist + Phase 8 trial protocol with §10.4 metrics, thresholds, and collection templates |
| Regression re-confirmation | CI pipeline re-run | Full regression + coverage delta + gate re-run post-change | V2 gate runner (424 tests, 7 suites) re-run with `--json-summary` captured in readiness report |

## Sources

- `.planning/PROJECT.md` — 10 unchecked V2 Active requirements (lines 43–52), Current State with carried human gates (lines 144–153), Evolution protocol (lines 159–164)
- `docs/requirements/V2-PRD.md` — §10 验收标准 (lines 586–634: 10.1 repo/docs, 10.2 contract CI, 10.3 composability, 10.4 lawyer trial), §12 开发顺序 (lines 645–686), §8 非功能需求 (lines 558–569)
- `.planning/MILESTONES.md` — v1.1–v1.4 shipped milestone audit results and deferred items (establishes what is already validated and must not be re-audited)
- `scripts/run_v2_gates.py` — existing V2 gate runner (424 tests, 7 gate suites, `--json-summary` output)
- `.planning/research/SUMMARY.md` — prior v1.2 research pattern (research → architecture implications → milestone shape)

---
*Feature research for: V2 acceptance closure (requirement traceability, gap analysis, readiness reporting, human-gate documentation)*
*Researched: 2026-07-03*
