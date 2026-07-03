# Architecture Research

**Domain:** V2 acceptance closure — requirement-to-code traceability audit, gap closure, and acceptance readiness reporting for an existing multi-package Python platform (InkStatute V2).
**Researched:** 2026-07-03
**Confidence:** HIGH

## Standard Architecture

### System Overview

The v1.5 milestone does not add a new runtime service. It adds an **audit-and-reporting layer** that sits above the existing shipped packages/services and consumes their test evidence, source modules, and gate output to close V2 acceptance. The closure workflow has four stages — audit, gap closure, traceability update, readiness report — each integrating with existing components rather than replacing them.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Acceptance Closure Layer (v1.5 NEW)                    │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────┐ │
│  │ Requirement  │  │  Gap Closure │  │  Traceability  │  │ Readiness  │ │
│  │ Audit Engine │→ │  (existing   │→ │  Update        │→ │ Report     │ │
│  │              │  │  pkgs/svcs)  │  │  (PROJECT.md)  │  │ Generator  │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────┘  └─────┬──────┘ │
│         │                 │                   │                │         │
├─────────┴─────────────────┴───────────────────┴────────────────┴─────────┤
│                      Evidence Sources (EXISTING)                          │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ V2 Gate Runner│  │ contract-test │  │ platform-    │  │ PROJECT.md│  │
│  │ run_v2_gates  │  │ -suite modules│  │ contract     │  │ + intel/  │  │
│  │ (--json-sum)  │  │ coverage/     │  │ schemas/     │  │ requiremnt│  │
│  │               │  │ trial/privacy │  │ fixtures     │  │ .md       │  │
│  └───────┬───────┘  └───────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
│          │                  │                 │                │         │
├──────────┴──────────────────┴─────────────────┴────────────────┴─────────┤
│                   Shipped Packages & Services (v1.1–v1.4)                  │
├──────────────────────────────────────────────────────────────────────────┤
│  platform-contract │ contract-test-suite │ platform-runtime │ channels   │ │
│  backends/hermes   │ solution-loader     │ wecom-service    │ hermes-    │ │
│  feedback-service  │ conversation-read-view                 │ contract   │ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status | Typical Implementation |
|-----------|----------------|--------|------------------------|
| Requirement Audit Engine | Parse unchecked PROJECT.md Active items + intel REQ-* entries; probe codebase for evidence; classify each as satisfied / gap / human-gate | NEW | Python script + `contract_test_suite.acceptance_audit` module |
| V2 Gate Runner | Run 8 gate suites (424 tests), emit JSON summary of pass/fail per gate | EXISTING (modified) | `scripts/run_v2_gates.py` — add audit gate / summary export |
| Gap Closure | Implement missing V2 code in existing services/packages; add/fix tests | EXISTING (in-place edits) | Edits to wecom-service, feedback-service, conversation-read-view, hermes-contract-layer, contract-test-suite |
| Traceability Update | Move validated requirements from Active `[ ]` to Validated `[x]` with phase refs in PROJECT.md | EXISTING (doc edit) | Manual/ scripted edit to `.planning/PROJECT.md` per Evolution protocol |
| Readiness Report Generator | Aggregate audit results + gate status + trial readiness into formal milestone audit document | NEW | Script that writes `.planning/milestones/v1.5-MILESTONE-AUDIT.md` |
| coverage_report.py | Compute contract-log coverage (turn/result pairing, breakage rate) | EXISTING (reused) | `contract_test_suite.coverage_report.CoverageReport` |
| trial_acceptance.py | Evaluate Phase 8 lawyer trial evidence; `readiness_gates_passed` flag gates live acceptance | EXISTING (reused) | `contract_test_suite.trial_acceptance.evaluate_trial_acceptance` |
| privacy_scan.py / boundary_checks.py | Privacy and output-boundary evidence for audit probes | EXISTING (reused) | `contract_test_suite.privacy_scan`, `boundary_checks` |

## Recommended Project Structure

```
scripts/
├── run_v2_gates.py              # EXISTING — modified: add acceptance-audit gate
├── audit_v2_requirements.py     # NEW — CLI entrypoint for requirement audit
└── generate_v2_readiness_report.py  # NEW — CLI entrypoint for readiness report
packages/contract-test-suite/
├── src/contract_test_suite/
│   ├── acceptance_audit.py      # NEW — requirement registry, evidence probes, gap classification
│   ├── coverage_report.py       # EXISTING — reused by audit engine
│   ├── trial_acceptance.py      # EXISTING — reused by readiness report
│   ├── privacy_scan.py          # EXISTING — reused by audit engine
│   └── boundary_checks.py       # EXISTING — reused by audit engine
└── tests/
    └── test_acceptance_audit.py # NEW — tests for audit logic
.planning/
├── PROJECT.md                   # EXISTING — modified: traceability update
├── intel/requirements.md        # EXISTING — read by audit engine (REQ-* source)
└── milestones/
    └── v1.5-MILESTONE-AUDIT.md  # NEW — readiness report output (follows v1.1/v1.4 convention)
docs/
└── v2-acceptance-readiness-report.md  # NEW — public-facing readiness summary (optional)
```

### Structure Rationale

- **`scripts/audit_v2_requirements.py` + `generate_v2_readiness_report.py`:** Follows the existing pattern of `run_v2_gates.py` as a repo-root CLI script. Keeps audit/report logic invocable from CI and from GSD phase plans.
- **`contract_test_suite.acceptance_audit`:** The audit logic lives in the test-suite package because it is a verification/CI concern, matching where `coverage_report.py`, `trial_acceptance.py`, `privacy_scan.py`, and `boundary_checks.py` already live. This makes it importable by both the script and the test suite's own self-tests.
- **`v1.5-MILESTONE-AUDIT.md`:** Follows the established milestone audit convention (YAML frontmatter + markdown, see `v1.1-MILESTONE-AUDIT.md` and `v1.4-MILESTONE-AUDIT.md`). This is where the readiness report lives as the formal GSD artifact.
- **`docs/v2-acceptance-readiness-report.md`:** Optional public-facing summary for stakeholders who do not read `.planning/` artifacts. The `.planning/milestones/` version is the authoritative GSD source.

## Architectural Patterns

### Pattern 1: Evidence-Probe Audit (not static checklist)

**What:** The requirement audit engine does not hardcode "requirement X is done." It runs **evidence probes** — each probe is a function that inspects a specific codebase artifact (a gate result, a test file, a source module, a schema file, a fixture) and returns structured evidence. A requirement is classified as satisfied only when its probe set returns positive evidence.

**When to use:** Whenever closing acceptance against a large existing codebase where requirements were implemented across multiple milestones (v1.1–v1.4) without per-requirement traceability tracking.

**Trade-offs:** Probes must be maintained when code moves, but they catch false-positive "done" claims. Probes are read-only and fast (no live runtime needed).

**Example:**
```python
# contract_test_suite/acceptance_audit.py
@dataclass(frozen=True)
class RequirementAuditResult:
    req_id: str
    title: str
    status: str  # "satisfied" | "gap" | "human_gate"
    evidence: tuple[EvidenceItem, ...]
    gap_detail: str | None

def audit_wecom_service_requirement(gate_summary: dict) -> RequirementAuditResult:
    evidence = []
    # Probe 1: gate passes
    wecom_gate = next(g for g in gate_summary["gates"] if g["name"] == "wecom-service")
    evidence.append(EvidenceItem("gate", "wecom-service", wecom_gate["exit_code"] == 0))
    # Probe 2: source modules exist
    evidence.append(EvidenceItem("source", "services/wecom-service/src/wecom_service/sender.py", Path(...).exists()))
    # Probe 3: test coverage for output policy
    evidence.append(EvidenceItem("test", "test_phase55_wecom_service_loop", ...))
    status = "satisfied" if all(e.passed for e in evidence) else "gap"
    return RequirementAuditResult("REQ-wecom-service", ..., status, tuple(evidence), ...)
```

### Pattern 2: Gate Runner as Evidence Backbone

**What:** The existing `run_v2_gates.py --json-summary` already emits a sanitized JSON summary of all 8 gates. The audit engine consumes this as its primary evidence source rather than re-running tests independently. This avoids duplicate test execution and keeps a single source of truth for "do the gates pass."

**When to use:** Whenever the audit needs to know "is this area of the codebase verified." The gate runner already partitions the codebase by package/service.

**Trade-offs:** The audit is only as granular as the gate partitioning (8 gates). For finer evidence, probes supplement gate results with file/test existence checks. Adding a new `acceptance-audit` gate to the runner makes the audit itself CI-verifiable.

**Example:**
```python
# scripts/audit_v2_requirements.py
def main() -> int:
    gate_summary = _run_gates_for_summary()  # calls run_v2_gates.py --json-summary
    requirements = load_requirement_registry()  # from intel/requirements.md + PROJECT.md Active
    results = [audit_requirement(req, gate_summary) for req in requirements]
    _write_audit_report(results, output_path)
    return 1 if any(r.status == "gap" for r in results) else 0
```

### Pattern 3: Reuse trial_acceptance.readiness_gates_passed as the Human-Gate Boundary

**What:** The existing `evaluate_trial_acceptance(rows, readiness_gates_passed=...)` function already encodes the separation between autonomous-completable readiness gates and the live human gate. The `readiness_gates_passed` flag is the exact hook the readiness report uses: the audit engine sets it to `True` when all code-level gates pass, and the trial acceptance evaluator then reports `blocked` until live Phase 8 evidence arrives.

**When to use:** For the readiness report's "remaining human gates" section. This is already the designed boundary — v1.5 should not invent a new one.

**Trade-offs:** The trial acceptance module is fixture-evidence-only by design (rejects `raw_payload`). The readiness report must clearly state that `readiness_gates_passed=True` means "code gates green," not "V2 accepted."

## Data Flow

### Audit → Gap Closure → Traceability → Readiness Report

```
[1. AUDIT]
  PROJECT.md (Active [ ] items)
    + intel/requirements.md (REQ-* acceptance criteria)
    + V2-PRD §10 (acceptance criteria 10.1–10.4)
        ↓
  audit_v2_requirements.py
    → run_v2_gates.py --json-summary (gate evidence)
    → acceptance_audit probes (source/test/schema/fixture evidence)
    → coverage_report (contract coverage evidence)
    → privacy_scan / boundary_checks (boundary evidence)
        ↓
  Audit Result (per-requirement: satisfied | gap | human_gate + evidence)
        ↓
[2. GAP CLOSURE]
  For each requirement with status=gap:
    → implement/fix code in target service/package
    → add/fix tests in contract-test-suite or service tests
    → run run_v2_gates.py (verify gate stays green)
    → re-run audit_v2_requirements.py (verify status flips to satisfied)
        ↓
[3. TRACEABILITY UPDATE]
  Audit Result (all gaps closed)
    → edit .planning/PROJECT.md:
        - Active [ ] → [x] for satisfied requirements
        - move satisfied items Active → Validated with phase reference
        - update "Current State" and "Last updated"
    → (follows PROJECT.md Evolution protocol)
        ↓
[4. READINESS REPORT]
  Audit Result + Gate Summary + trial_acceptance readiness status
        ↓
  generate_v2_readiness_report.py
    → evaluate_trial_acceptance([], readiness_gates_passed=all_gates_green)
    → write .planning/milestones/v1.5-MILESTONE-AUDIT.md
      (YAML frontmatter: status, scores, gaps, gap_resolution, tech_debt)
    → write docs/v2-acceptance-readiness-report.md (public summary)
        ↓
  Report explicitly lists remaining human gates:
    - Phase 5 live WeCom UAT (operator confirmation)
    - Phase 8 five-workday lawyer trial (live evidence)
```

### Key Data Flows

1. **Gate summary → audit engine:** `run_v2_gates.py --json-summary` emits `{"passed": bool, "gates": [{"name": str, "exit_code": int}]}`. The audit engine maps gate names to requirements (e.g., `wecom-service` gate → REQ-wecom-daily-test-loop, `phase7-privacy-boundary` gate → REQ-security-privacy-baseline, `contract-test-suite` gate → REQ-contract-test-suite + REQ-composability-validation).

2. **Coverage report → audit engine:** `summarize_fixture_bundle_coverage` and `summarize_event_stream_coverage` produce `CoverageReport` with `paired_turn_result_coverage` and `breakage_rate`. The audit engine checks these against PRD §10.2 thresholds (coverage ≥ 95%, breakage ≤ 5%).

3. **Trial acceptance → readiness report:** `evaluate_trial_acceptance` with `readiness_gates_passed=True` and empty live rows returns `status=blocked` with issue code `no_live_trial_evidence`. The readiness report interprets this as "code readiness confirmed, live human gate remains."

4. **Gap closure → re-audit loop:** Each gap fix triggers a targeted gate run (only the affected gate) followed by a full audit re-run. This is the same incremental-verify pattern used in v1.1 and v1.4 milestone audits.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 14 requirements (current) | Single-pass audit script with one probe set per requirement. Runs in seconds. |
| 30+ requirements (M2+) | Partition probe sets into per-package modules; parallelize gate runs. |
| 100+ requirements | Consider a requirement registry YAML/JSON as the single source, generated from PRD + intel, consumed by both audit and PROJECT.md traceability. |

### Scaling Priorities

1. **First bottleneck — probe maintenance:** If code moves between packages (likely in M2 refactor), probes break. Mitigate by keying probes on stable identifiers (gate names, test file names, schema filenames) rather than deep import paths.
2. **Second bottleneck — audit runtime:** At 14 requirements with 8 gates, the audit is fast. If gates grow, use the existing `--list` + selective gate execution pattern.

## Anti-Patterns

### Anti-Pattern 1: Hardcoding Requirement Status

**What people do:** Write a static table in the readiness report saying "REQ-X: done" without probing the codebase.
**Why it's wrong:** This is exactly what happened in v1.4 (REQUIREMENTS.md showed all 20 as "Not started" despite being implemented — TD-03). Static tables drift from reality.
**Do this instead:** Every "satisfied" classification must come with machine-gathered evidence (gate name + exit code, test file path, source file path, coverage metric).

### Anti-Pattern 2: Substituting Fixture Evidence for Live Human Gates

**What people do:** Mark Phase 5 WeCom UAT or Phase 8 lawyer trial as complete because fixture-based tests pass.
**Why it's wrong:** The V2 PRD §10.4 and the existing `trial_acceptance.py` explicitly reject fixture evidence for live trial (`evidence_kind="fixture"` → `status=blocked`). The PROJECT.md Constraints and STATE.md "Parallel Human Gate" both forbid this.
**Do this instead:** The readiness report must list Phase 5 and Phase 8 as "carried human gates" with `status=human_gate`, never `satisfied`. Use `evaluate_trial_acceptance(rows, readiness_gates_passed=True)` to confirm code readiness while preserving the live gate.

### Anti-Pattern 3: Adding New Runtime Services for Audit

**What people do:** Build a new audit microservice or database to track requirements.
**Why it's wrong:** V2 PRD §1.2 and AGENTS.md forbid introducing new services/databases unless the PRD requires it. The audit is a build-time/CI concern, not a runtime service.
**Do this instead:** Audit logic lives in `contract_test_suite` (a test/verification package) and `scripts/` (CLI entrypoints). No new service, no new database, no new runtime dependency.

### Anti-Pattern 4: Reintroducing V1 Scope During Gap Closure

**What people do:** While closing a gap, expand scope to rebuild Hermes core, add a new authoritative conversation database, or add Web/Tauri/QQBot loops.
**Why it's wrong:** PROJECT.md Out of Scope and V2-PRD §1.1 explicitly forbid this. Gap closure must stay within the existing service/package boundaries.
**Do this instead:** Each gap closure is scoped to the specific requirement's acceptance criteria. If a gap seems to require out-of-scope work, it is a PRD constraint conflict, not a code gap — escalate, do not implement.

## Integration Points

### Existing Services/Packages (Audit Evidence Targets)

| Component | Integration Pattern | Audit Probe |
|-----------|---------------------|-------------|
| `scripts/run_v2_gates.py` | Call `--json-summary`, parse gate results | Gate name → exit code mapping; 8 gates cover all packages/services |
| `packages/platform-contract` | Check schema files exist + `platform-contract` gate passes | Schema file count (5 core + extensions), enum/required validation via `schema_validation.py` |
| `packages/contract-test-suite` | Reuse `coverage_report`, `trial_acceptance`, `privacy_scan`, `boundary_checks` | Coverage metrics, trial readiness, privacy scan results, boundary allowlist |
| `services/wecom-service` | Check `wecom-service` gate + source module existence | `sender.py`, `output_policy.py`, `delivery_guard.py`, `idempotency.py`, `task_flow.py` exist + gate green |
| `services/hermes-contract-layer` | Check `hermes-contract-layer` gate + hook/mapper/writer | `hook.py`, `mapper.py`, `writer.py`, `bootstrap.py`, `adapter_manifest.py` exist + gate green |
| `services/feedback-service` | Check `feedback-service` gate + normalizer/classification | `wecom_normalizer.py`, `classification.py`, `queue.py` exist + gate green |
| `services/conversation-read-view` | Check `conversation-read-view` gate + read model | `read_model.py`, `api.py`, `privacy.py` exist + gate green |
| `packages/backends/hermes` | Check `contract-test-suite` gate (includes backend tests) | Backend adapter contract tests pass |
| `packages/platform-runtime` | Check `output_boundary.py` + runtime contracts | `output_boundary.py`, `runtime.py` exist + Phase 10 tests pass |
| `.planning/PROJECT.md` | Parse Active `[ ]` items; write traceability update | Checkbox state, section membership (Active vs Validated) |
| `.planning/intel/requirements.md` | Parse REQ-* entries with acceptance criteria | Requirement registry source |
| `docs/requirements/V2-PRD.md` §10 | Parse acceptance criteria 10.1–10.4 | Threshold mapping (95% coverage, 5% breakage, 80% long-task success) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| audit script ↔ gate runner | subprocess + JSON stdout | `run_v2_gates.py --json-summary` is the contract; audit script parses JSON |
| audit script ↔ contract-test-suite | Python import | `acceptance_audit` module imports `coverage_report`, `trial_acceptance`, `privacy_scan` — same package |
| readiness report ↔ trial_acceptance | Python import | `evaluate_trial_acceptance` called with `readiness_gates_passed` derived from gate summary |
| gap closure ↔ existing services | in-place code edits | No new service; edits flow through existing test → gate → audit verify loop |
| traceability update ↔ PROJECT.md | file edit | Follows PROJECT.md Evolution protocol (move Validated, add phase ref) |

## New vs Modified Components

### NEW Components

| Component | Path | Purpose |
|-----------|------|---------|
| Requirement Audit Engine | `packages/contract-test-suite/src/contract_test_suite/acceptance_audit.py` | Requirement registry, evidence probes, gap classification logic |
| Audit CLI | `scripts/audit_v2_requirements.py` | CLI entrypoint: runs gates for summary, executes probes, writes audit report |
| Readiness Report CLI | `scripts/generate_v2_readiness_report.py` | CLI entrypoint: aggregates audit + gates + trial readiness, writes milestone audit doc |
| Audit Tests | `packages/contract-test-suite/tests/test_acceptance_audit.py` | Self-tests for audit logic (probe correctness, gap classification, evidence validation) |
| V1.5 Milestone Audit | `.planning/milestones/v1.5-MILESTONE-AUDIT.md` | Readiness report output (YAML frontmatter + markdown, follows v1.1/v1.4 convention) |
| Public Readiness Summary | `docs/v2-acceptance-readiness-report.md` | Optional stakeholder-facing summary |

### MODIFIED Components

| Component | Path | Change |
|-----------|------|--------|
| V2 Gate Runner | `scripts/run_v2_gates.py` | Add `acceptance-audit` gate that runs `audit_v2_requirements.py`; OR add `--audit` flag that runs audit after gates. Keeps audit CI-verifiable. |
| PROJECT.md | `.planning/PROJECT.md` | Traceability update: move satisfied Active `[ ]` → `[x]`, move to Validated with phase refs, update Current State |
| ROADMAP.md | `.planning/ROADMAP.md` | Add v1.5 milestone entry to milestones list |
| STATE.md | `.planning/STATE.md` | Update milestone progress and status as phases complete |
| Gap-closure targets | `services/wecom-service/`, `services/feedback-service/`, `services/conversation-read-view/`, `services/hermes-contract-layer/`, `packages/contract-test-suite/` | In-place code fixes for any gaps found by the audit (content depends on audit results) |

## Suggested Build Order

The build order respects dependencies on v1.1–v1.4 shipped code and the V2 PRD §12 development order. The audit must run against stable shipped code; gap closure depends on audit results; traceability depends on gap closure; the readiness report depends on all three.

### Phase A: Audit Infrastructure (no dependency on gap closure)

1. **Build `acceptance_audit.py` module** — requirement registry (parse PROJECT.md Active + intel/requirements.md REQ-*), evidence probe framework, gap classification logic. Depends on: existing `coverage_report.py`, `privacy_scan.py`, `boundary_checks.py`, `trial_acceptance.py` (all shipped in contract-test-suite).
2. **Build `audit_v2_requirements.py` CLI** — subprocess call to `run_v2_gates.py --json-summary`, probe execution, structured audit report output (JSON + markdown). Depends on: step 1.
3. **Add audit tests** — `test_acceptance_audit.py` verifying probe correctness and gap classification. Depends on: step 1.
4. **Run the first audit** — execute the audit against the current codebase to produce the initial gap list. This is the key v1.5 deliverable: the unchecked-requirement audit.

### Phase B: Gap Closure (depends on Phase A audit results)

5. **Close code gaps** — for each requirement classified `gap`, implement/fix code in the target service/package. The specific targets depend on audit results but likely candidates (based on PROJECT.md Active `[ ]` items):
   - WeCom service completeness (if any sub-feature is missing)
   - Agent adapter contract / runtime selector (if incomplete)
   - Hermes agent adapter bootstrap path (if incomplete)
   - Assistant output boundary (if incomplete)
   - WeCom task-to-agent-to-reply-to-card-to-feedback loop (if incomplete)
   - Feedback normalization (if incomplete)
   - Conversation-read-view APIs (if incomplete)
   - Observability/replay/privacy baselines (if incomplete)
   - Composability/CI behavior (if incomplete)
   Each gap closure follows: edit code → add/fix tests → run affected gate → re-audit.
6. **Re-run full V2 gate suite** — confirm all 8 gates stay green after all gap closures.

### Phase C: Traceability Update (depends on Phase B)

7. **Update PROJECT.md** — move all satisfied requirements from Active `[ ]` to Validated `[x]` with phase references. Update Current State, Last updated. Follow the Evolution protocol.
8. **Update ROADMAP.md and STATE.md** — add v1.5 milestone entry, update progress.

### Phase D: Readiness Report (depends on Phase C)

9. **Build `generate_v2_readiness_report.py` CLI** — aggregates final audit results + gate summary + `evaluate_trial_acceptance(readiness_gates_passed=True)` status. Depends on: steps 1–2, 6.
10. **Generate `v1.5-MILESTONE-AUDIT.md`** — YAML frontmatter (status, scores, gaps, gap_resolution, tech_debt) + markdown body. Follows v1.1/v1.4 audit convention. Explicitly lists Phase 5 and Phase 8 as carried human gates.
11. **Generate public readiness summary** — `docs/v2-acceptance-readiness-report.md` for stakeholders.

### Dependency Graph

```
Phase A (audit infra)
  ├─→ Phase B (gap closure) ─→ Phase C (traceability) ─→ Phase D (readiness report)
  │                                                      ↑
  └─→ Phase D step 9 (report CLI reuses audit engine) ───┘
```

### Why This Order

- **Audit before gap closure:** Cannot close gaps without first knowing which requirements are unsatisfied. The audit is the v1.5 milestone's reason for existing.
- **Gap closure before traceability:** PROJECT.md traceability update must reflect reality, not aspiration. Only move requirements to Validated after code is verified.
- **Traceability before readiness report:** The readiness report cites the PROJECT.md state as evidence that traceability is closed.
- **No conflict with V2 PRD §12:** The PRD development order (steps 1–9) governs the V2 feature build itself, which is already shipped in v1.1–v1.4. The v1.5 build order governs the audit/closure tooling, which sits above the shipped code. No PRD sequencing constraint is violated because v1.5 does not change the feature build order — it verifies and reports on it.

## Sources

- `.planning/PROJECT.md` — Active requirements (11 unchecked `[ ]` items), Validated items, Evolution protocol, Constraints
- `docs/requirements/V2-PRD.md` §10 — acceptance criteria (10.1 repo/docs, 10.2 contract CI, 10.3 composability, 10.4 lawyer trial); §12 — development order and dependency graph
- `scripts/run_v2_gates.py` — existing gate runner architecture (8 gates, `Gate` dataclass, `--json-summary`, `--list`)
- `packages/contract-test-suite/src/contract_test_suite/` — existing `coverage_report.py`, `trial_acceptance.py`, `privacy_scan.py`, `boundary_checks.py`, `schema_validation.py`, `fixture_replay.py`, `event_stream_replay.py`
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md`, `v1.4-MILESTONE-AUDIT.md` — milestone audit document convention (YAML frontmatter + markdown)
- `.planning/intel/requirements.md` — 14 REQ-* entries with acceptance criteria extracted from V2-PRD
- `.planning/STATE.md` — current milestone state, carried human gates (Phase 5, Phase 8)
- `AGENTS.md` — coding rules (no new service/database unless PRD requires; scoped changes; tests with behavior changes)

---
*Architecture research for: V2 acceptance closure — audit, gap closure, traceability, readiness reporting*
*Researched: 2026-07-03*
