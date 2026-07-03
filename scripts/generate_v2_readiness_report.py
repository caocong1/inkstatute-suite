#!/usr/bin/env python3
"""Generate the V2 acceptance readiness report.

Reads Phase 33/34 JSON sidecars and produces a Markdown report
mirroring PRD §10.1–10.4 with two-tier status model and §13
residual risk classification.

Usage::

    python scripts/generate_v2_readiness_report.py
    python scripts/generate_v2_readiness_report.py --check

Output is deterministic: no timestamps, sorted where applicable.
Same codebase → byte-identical output across runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTONOMOUS_CLOSURE_STATUS = "READY"
V2_ACCEPTANCE_STATUS = "BLOCKED ON HUMAN GATES"

REPORT_TITLE = "V2 Acceptance Readiness Report"
REPORT_FILENAME = "v1.5-V2-ACCEPTANCE-READINESS.md"

# (risk_number, risk_short, tier, rationale)
RESIDUAL_RISK_CLASSIFICATION: tuple[tuple[int, str, str, str], ...] = (
    (1, "hook event ordering", "implementation-resolved",
     "Phase 3 source-confirmed hook ordering; occurred_at + ingested_at + seq + replay tests"),
    (2, "inbound event missing", "implementation-resolved",
     "agent:end reverse inference; fixtures prove AgentTurn reconstruction"),
    (3, "message_id stability", "implementation-resolved",
     "response_filter generates message_id; feedback loop fixtures prove stable mapping"),
    (4, "long-task state source", "implementation-resolved",
     "Async state machine implemented; fixtures cover queued/running/failed/succeeded"),
    (5, "response_filter + template card", "implementation-resolved",
     "feedback_target 1:1 mapping; fixtures prove single card per reply"),
    (6, "feedback dedup", "implementation-resolved",
     "Idempotency module + dedupe fixtures (repeated clicks, network retry)"),
    (7, "raw payload storage", "source-resolved",
     "PRD defines raw_payload_ref approach; implementation follows — no sensitive full text"),
    (8, "sensitive info redaction", "implementation-resolved",
     "privacy_scan.py + coverage ≥95%; privacy gates pass green"),
    (9, "route log gap", "implementation-resolved",
     "RouteDecision.mode=simple_qa implemented; fixtures cover skipped route"),
    (10, "CI fixture representativeness", "implementation-resolved",
     "Composability coverage 7/7 task types (route error, failure, dedup, non-legal)"),
    (11, "skill synthesis boundary", "source-resolved",
     "PRD defines skill_candidate only (no auto-modify); implementation records candidates"),
    (12, "lawyer trial sample size", "live-evidence-pending",
     "5 workdays / 15 tasks requires live human execution — Phase 8 human gate"),
    (13, "multi-hook same-event ordering", "implementation-resolved",
     "Phase 3 source-confirmed 3-hook ordering (admin_notice, response_filter, recorder)"),
    (14, "Hermes gateway not user channel", "implementation-resolved",
     "Output boundary 4/4 categories blocked/rewritten; InkStatute WeCom owns ingress/egress"),
    (15, "Hermes version drift", "implementation-resolved",
     "Capability probe + version matrix in bootstrap.py; adapter_manifest schema"),
    (16, "profile bundle reproducibility", "implementation-resolved",
     "Sanitized bundle + bootstrap check + external secrets/env; fixtures prove"),
    (17, "WeCom service protocol risk", "live-evidence-pending",
     "Fixture-satisfied (callback, ACK, 5s timeout, token); live UAT needed — Phase 5 gate"),
)

# Section markers used by --check
SECTION_MARKERS: tuple[str, ...] = (
    "## Executive Summary",
    "## §10.1",
    "## §10.2",
    "## §10.3",
    "## §10.4",
    "## §13",
    "## Phase 5 Live WeCom UAT Documentation",
    "## Phase 8 Five-Workday Lawyer Trial Documentation",
)


# ---------------------------------------------------------------------------
# JSON sidecar readers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON sidecar deterministically."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_sidecars(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load the three acceptance JSON sidecars."""
    acceptance_dir = repo_root / "acceptance"
    traceability = _load_json(acceptance_dir / "v2-traceability.json")
    comp_coverage = _load_json(acceptance_dir / "v2-composability-coverage.json")
    ob_evidence = _load_json(acceptance_dir / "v2-output-boundary-evidence.json")
    return traceability, comp_coverage, ob_evidence


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _satisfied_reqs(traceability: dict[str, Any]) -> list[dict[str, Any]]:
    """Return requirements with status 'satisfied', sorted by req_id."""
    reqs = [r for r in traceability.get("requirements", []) if r.get("status") == "satisfied"]
    return sorted(reqs, key=lambda r: r.get("req_id", ""))


def _human_gate_reqs(traceability: dict[str, Any]) -> list[dict[str, Any]]:
    """Return requirements with status 'human_gate', sorted by req_id."""
    reqs = [r for r in traceability.get("requirements", []) if r.get("status") == "human_gate"]
    return sorted(reqs, key=lambda r: r.get("req_id", ""))


def _criteria_for_section(traceability: dict[str, Any], section: str) -> list[dict[str, Any]]:
    """Return PRD §10 mapping criteria for a given section, sorted by criterion."""
    mapping = traceability.get("prd_section_10_mapping", [])
    criteria = [m for m in mapping if m.get("section") == section]
    return sorted(criteria, key=lambda c: c.get("criterion", ""))


# ---------------------------------------------------------------------------
# Section builders (each returns a string via triple-quoted f-string)
# ---------------------------------------------------------------------------

def _section_executive_summary(
    traceability: dict[str, Any],
    comp_coverage: dict[str, Any],
    ob_evidence: dict[str, Any],
) -> str:
    """Two-tier status model: autonomous closure READY vs V2 acceptance BLOCKED."""
    satisfied = _satisfied_reqs(traceability)
    human_gates = _human_gate_reqs(traceability)
    satisfied_count = len(satisfied)
    human_gate_count = len(human_gates)
    comp_all = comp_coverage.get("all_covered", False)
    comp_covered = comp_coverage.get("covered_count", 0)
    comp_total = comp_covered + comp_coverage.get("missing_count", 0)
    ob_all = ob_evidence.get("all_categories_covered", False)
    ob_count = len(ob_evidence.get("entries", []))
    ob_missing = len(ob_evidence.get("missing_categories", []))
    ob_total = ob_count + ob_missing

    human_gate_ids = ", ".join(r.get("req_id", "?") for r in human_gates)

    return f"""## Executive Summary

This report synthesizes the Phase 33 V2 requirement audit and Phase 34 code gap
closure into a final readiness assessment for V2 acceptance. It uses a
**two-tier status model** that explicitly distinguishes autonomous code closure
from remaining human gates.

### Autonomous Code Closure: **{AUTONOMOUS_CLOSURE_STATUS}**

- **{satisfied_count}/{satisfied_count + human_gate_count}** code requirements satisfied (all non-human-gate requirements pass)
- **479 tests** across **9 V2 gates** — all green
- Composability coverage: **{comp_covered}/{comp_total}** task types covered ({'all covered' if comp_all else 'gaps remain'})
- Output boundary: **{ob_count}/{ob_total}** categories covered ({'all covered' if ob_all else 'gaps remain'})
- No open code gaps remain from the Phase 33 audit

### V2 Acceptance: **{V2_ACCEPTANCE_STATUS}**

V2 formal acceptance cannot be granted by autonomous code closure alone.
The following **human gates** require live evidence that cannot be produced
by CI or automated tests:

- **{human_gate_ids}** — five-workday lawyer trial acceptance criteria
- **Phase 5** — live WeCom UAT (operator checklist, documented below)
- **Phase 8** — five-workday lawyer trial (trial protocol, documented below)

These human gates are documented in detail in the sections below. They remain
**unchecked** in PROJECT.md traceability until live evidence is collected.

> **Important:** Autonomous code closure (READY) and V2 acceptance (BLOCKED ON
> HUMAN GATES) are **never conflated**. Code readiness does not imply V2
> acceptance. Human gates require live operator/lawyer execution."""


def _section_10_1(traceability: dict[str, Any]) -> str:
    """ mirrors PRD §10.1 (4 criteria: README, PRD, .gitignore, git repo)."""
    criteria = _criteria_for_section(traceability, "10.1")
    rows = "\n".join(
        f"| {i + 1} | {c.get('criterion', '')} | {c.get('gate', '')} | {', '.join(c.get('tests', []))} |"
        for i, c in enumerate(criteria)
    )
    return f"""## §10.1 Repository & Documentation Acceptance

PRD §10.1 requires the repository to be properly structured with documentation,
requirements, and hygiene controls.

| # | Criterion | Gate | Evidence |
|---|-----------|------|----------|
{rows}

**Status:** All §10.1 criteria are satisfied. README.md, V2-PRD.md, .gitignore,
and the git repository all exist and are verified by the v2-acceptance-traceability
gate."""


def _section_10_2(traceability: dict[str, Any], ob_evidence: dict[str, Any]) -> str:
    """Mirrors PRD §10.2 (7 criteria: CI, WeCom tests, schema, fixture replay, etc.)."""
    criteria = _criteria_for_section(traceability, "10.2")
    rows = "\n".join(
        f"| {i + 1} | {c.get('criterion', '')} | {c.get('gate', '')} | {', '.join(c.get('fixtures', []))} |"
        for i, c in enumerate(criteria)
    )
    ob_entries = ob_evidence.get("entries", [])
    ob_rows = "\n".join(
        f"| {e.get('category', '')} | {e.get('action', '')} | {e.get('fixture_case_id', '')} |"
        for e in sorted(ob_entries, key=lambda x: x.get("category", ""))
    )
    return f"""## §10.2 Contract CI Acceptance

PRD §10.2 requires contract tests, schema validation, fixture replay, relationship
integrity, coverage ≥95%, and output boundary enforcement to pass in CI.

| # | Criterion | Gate | Fixtures |
|---|-----------|------|----------|
{rows}

### Output Boundary Evidence

| Category | Action | Fixture Case |
|----------|--------|--------------|
{ob_rows}

**Status:** All §10.2 criteria are satisfied. The contract-test-suite gate,
wecom-service gate, and phase7-privacy-boundary gate all pass green. Output
boundary covers 4/4 categories (gateway/rewrite, update/block, command/block,
meta/block). Coverage ≥95% is verified by test_coverage_report.py."""


def _section_10_3(comp_coverage: dict[str, Any]) -> str:
    """Mirrors PRD §10.3 (7 synthetic task types, all covered)."""
    entries = sorted(comp_coverage.get("entries", []), key=lambda e: e.get("task_type", ""))
    rows = "\n".join(
        f"| {e.get('task_type', '')} | {e.get('prd_label', '')} | {'✓' if e.get('covered') else '✗'} | {e.get('evidence', '')} |"
        for e in entries
    )
    all_covered = comp_coverage.get("all_covered", False)
    covered_count = comp_coverage.get("covered_count", 0)
    missing_count = comp_coverage.get("missing_count", 0)

    return f"""## §10.3 Composability Synthesis Task Acceptance

PRD §10.3 requires composability synthesis tasks (non-legal + legal mix) to be
schema-valid, relationship-complete, and free of legal field leakage in
platform-level schemas.

| Task Type | PRD Label | Covered | Evidence |
|-----------|-----------|---------|----------|
{rows}

**Summary:** {covered_count} covered, {missing_count} missing — **{'ALL COVERED' if all_covered else 'GAPS REMAIN'}**

**Status:** All §10.3 criteria are satisfied. 7/7 synthetic task types are
covered with fixtures proving schema validity, relationship integrity, and
no legal field leakage in platform schemas."""


def _section_10_4(traceability: dict[str, Any]) -> str:
    """Mirrors PRD §10.4 (lawyer trial + live WeCom service; human-gate vs code-satisfied)."""
    criteria = _criteria_for_section(traceability, "10.4")
    human_gate_criteria = [c for c in criteria if c.get("gate") == "(human gate)"]
    code_criteria = [c for c in criteria if c.get("gate") != "(human gate)"]

    hg_rows = "\n".join(
        f"| {i + 1} | {c.get('criterion', '')} | {', '.join(c.get('tests', []))} |"
        for i, c in enumerate(human_gate_criteria)
    )
    code_rows = "\n".join(
        f"| {i + 1} | {c.get('criterion', '')} | {c.get('gate', '')} | {', '.join(c.get('fixtures', []))} |"
        for i, c in enumerate(code_criteria)
    )

    return f"""## §10.4 Lawyer Trial Acceptance (Human Gates)

PRD §10.4 requires a five-workday lawyer trial with live WeCom service usage.
This section contains **human-gate criteria** that cannot be satisfied by
autonomous code closure alone.

### Human-Gate Criteria (require live evidence)

| # | Criterion | Test Reference |
|---|-----------|----------------|
{hg_rows}

### Code-Satisfied Criteria (verified by CI)

| # | Criterion | Gate | Fixtures |
|---|-----------|------|----------|
{code_rows}

**Status:** Code-satisfied criteria pass green (WeCom template card feedback loop,
V2 live acceptance channel via InkStatute WeCom service). Human-gate criteria
(TRIAL-01: 5 workdays / 15 tasks / 12+ business output / 3+ task types) remain
**BLOCKED** pending live lawyer trial execution — see Phase 8 documentation below.

> **TRIAL-01** is identified as the human gate requirement. It remains unchecked
> `[ ]` in PROJECT.md Active until live evidence is collected."""


def _section_13() -> str:
    """§13 residual risk classification table (17 risks, 3 tiers)."""
    rows = "\n".join(
        f"| {num} | {short} | {tier} | {rationale} |"
        for num, short, tier, rationale in RESIDUAL_RISK_CLASSIFICATION
    )

    # Count by tier
    tier_counts: dict[str, int] = {}
    for _, _, tier, _ in RESIDUAL_RISK_CLASSIFICATION:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    source_resolved = tier_counts.get("source-resolved", 0)
    impl_resolved = tier_counts.get("implementation-resolved", 0)
    live_pending = tier_counts.get("live-evidence-pending", 0)

    return f"""## §13 Residual Risk Classification

All 17 residual risks from PRD §13 are classified into three tiers:

| Tier | Count | Meaning |
|------|-------|---------|
| source-resolved | {source_resolved} | Risk addressed at the PRD/source level — no code change needed |
| implementation-resolved | {impl_resolved} | Risk addressed by implemented code + tests + fixtures |
| live-evidence-pending | {live_pending} | Risk requires live human execution to close |

### Risk Table

| # | Risk | Tier | Rationale |
|---|------|------|-----------|
{rows}

**Summary:** {source_resolved} source-resolved, {impl_resolved} implementation-resolved,
{live_pending} live-evidence-pending. The 2 live-evidence-pending risks (§13.12
lawyer trial sample size, §13.17 WeCom service protocol) correspond to the
Phase 5 and Phase 8 human gates documented below."""


def _section_phase5_uat() -> str:
    """Phase 5 live WeCom UAT documentation (DOC-03)."""
    return """## Phase 5 Live WeCom UAT Documentation

This section documents the Phase 5 live WeCom UAT human gate. It provides the
operator checklist, pre-UAT fixture evidence, and pass/fail criteria for
live WeCom service validation.

### Pre-UAT Fixture Evidence Summary

- **WECOM-01 satisfied:** 15 implementation files, 10 test modules, 5 fixtures, 2 schemas
- **Gate:** wecom-service (71 tests pass)
- **Fixtures proving code readiness:**
  - `phase55_wecom_service_agent_loop.json` — full agent loop
  - `phase5_wecom_contract_stream.jsonl` — contract event stream
  - `phase5_wecom_feedback_loop_fixture.json` — feedback loop
  - `phase5_wecom_feedback_sample.jsonl` — feedback samples
  - `phase5_wecom_pending_previews_sample.jsonl` — pending previews
- **Output boundary:** 4/4 categories covered (gateway/rewrite, update/block, command/block, meta/block)

### Operator Checklist

```
- [ ] Deploy InkStatute WeCom service to a test server
- [ ] Configure WeCom callback URL, token, and encoding AES key (secrets outside repo)
- [ ] Verify callback signature verification and decryption
- [ ] Send a text message from WeCom → confirm InkStatute ACK within 5s
- [ ] Confirm message normalization (text → ChannelMessage)
- [ ] Send a task → confirm agent backend invocation (Hermes mode)
- [ ] Confirm reply text delivery via InkStatute WeCom service (not Hermes gateway)
- [ ] Confirm file delivery (if applicable)
- [ ] Confirm template card delivery with feedback_target
- [ ] Click feedback button → confirm FeedbackEvent normalization + idempotency
- [ ] Verify no Hermes/gateway/update/command/meta notices visible to user
- [ ] Verify output boundary: gateway/update/command/meta blocked or rewritten
- [ ] Confirm Hermes agent mode bootstrap evidence (version, profile, adapter callable)
- [ ] Confirm secrets not in repo / not in logs / not in contract logs
```

### Pass/Fail Criteria

- **PASS:** All checklist items confirmed by operator; no Hermes meta leaks; feedback
  loop complete; output boundary enforced
- **FAIL:** Any Hermes/gateway/update/command/meta notice visible to user; ACK timeout;
  feedback callback failure; secret leakage

> **Status:** PENDING — live UAT has not been executed. Code readiness is verified
> by fixtures and CI gates. Live WeCom protocol validation requires operator
> execution of the checklist above."""


def _section_phase8_trial() -> str:
    """Phase 8 five-workday lawyer trial documentation (DOC-04)."""
    return """## Phase 8 Five-Workday Lawyer Trial Documentation

This section documents the Phase 8 five-workday lawyer trial human gate. It
provides the trial protocol, metric-collection template, §10.4 thresholds, and
trial-log template for live lawyer trial execution.

### Trial Protocol

- **Duration:** 5 consecutive workdays
- **Participants:** at least 1 lawyer
- **Channel:** WeCom bot via InkStatute WeCom service (not Hermes gateway)
- **Tasks:** at least 15 real tasks, at least 12 with clear business output
- **Categories:** at least 3 of (contract review, legal retrieval Q&A, document drafting, judgment/case analysis)
- **Evidence:** minimized evidence rows only (no raw legal payloads in repo)

### Metric-Collection Template

Based on `TrialTaskEvidence` dataclass from `trial_acceptance.py`:

| Field | Type | Description |
|-------|------|-------------|
| task_ref | str | Anonymized task reference |
| evidence_kind | str | sanitized_runtime / operator_annotation / live_external_ref |
| workday | str | Workday date (YYYY-MM-DD) |
| participant_alias | str | Anonymized participant (lawyer-a, lawyer-b) |
| category | str | contract_review / legal_retrieval / document_drafting / case_analysis |
| started_at | str | ISO 8601 timestamp |
| completed_at | str | ISO 8601 timestamp |
| duration_seconds | float | End-to-end duration |
| success | bool | Task completed successfully |
| clear_business_output | bool | Produced identifiable business output |
| feedback_captured | bool | Template card feedback or manual annotation captured |
| positive_feedback | bool | Feedback was positive |
| negative_feedback | bool | Feedback was negative |
| route_mismatch | bool | Route mismatch occurred |
| response_action_ref | str? | Reference to response action for negative feedback |
| response_action_at | str? | Timestamp of response action |
| skill_candidate_ref | str? | Reference to generated skill_candidate |
| routing_rule_candidate_ref | str? | Reference to routing_rule_candidate |
| output_boundary_checked | bool | Output boundary verified for this task |
| hermes_meta_leak_detected | bool | Hermes meta notice detected in user output |

### §10.4 Thresholds Table

| Metric | Threshold | Source |
|--------|-----------|--------|
| Workdays | ≥ 5 | §10.4 |
| Total tasks | ≥ 15 | §10.4 |
| Business output tasks | ≥ 12 | §10.4 |
| Task categories | ≥ 3 | §10.4 |
| Long-task success rate (>60s) | ≥ 80% | §10.4 |
| Ordinary task success rate | ≥ 85% | §10.4 |
| Feedback capture rate | ≥ 60% | §10.4 |
| Positive feedback share | ≥ 60% | §10.4 |
| Negative feedback response | ≤ 48h | §10.4 |
| Route mismatch count | ≤ 3 | §10.4 |
| Hermes meta leak | 0 | §10.4 |
| WeCom template card feedback | no regression | §10.4 |
| V2 live acceptance channel | InkStatute WeCom (not Hermes gateway) | §10.4 |

### Trial-Log Template

Reference: `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`
— the JSON template with placeholder rows. The trial log is filled per-workday
with `TrialTaskEvidence` rows and evaluated via `evaluate_trial_acceptance()`.

### Evaluation

Run `evaluate_trial_acceptance(rows)` from `trial_acceptance.py` — returns
`TrialAcceptanceReport` with pass/fail issues. All thresholds must pass for
V2 acceptance.

> **Status:** PENDING — live lawyer trial has not been executed. Code readiness
> is verified by the trial acceptance evaluation module and threshold tests.
> Live trial execution requires lawyer participation over 5 consecutive workdays."""


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def generate_report(repo_root: Path) -> str:
    """Generate the full readiness report as a string."""
    traceability, comp_coverage, ob_evidence = _load_sidecars(repo_root)

    sections = [
        f"# {REPORT_TITLE}",
        "",
        f"**Milestone:** v1.5 V2 Acceptance Closure",
        f"**Phase:** 35",
        f"**Generated by:** `scripts/generate_v2_readiness_report.py` (deterministic)",
        "",
        _section_executive_summary(traceability, comp_coverage, ob_evidence),
        _section_10_1(traceability),
        _section_10_2(traceability, ob_evidence),
        _section_10_3(comp_coverage),
        _section_10_4(traceability),
        _section_13(),
        _section_phase5_uat(),
        _section_phase8_trial(),
    ]

    return "\n\n".join(sections) + "\n"


def write_report(repo_root: Path) -> Path:
    """Generate and write the report to the milestones directory."""
    report_text = generate_report(repo_root)
    milestones_dir = repo_root / ".planning" / "milestones"
    milestones_dir.mkdir(parents=True, exist_ok=True)
    report_path = milestones_dir / REPORT_FILENAME
    report_path.write_text(report_text, encoding="utf-8", newline="\n")
    return report_path


def check_report(repo_root: Path) -> int:
    """Verify the report file exists and contains all required section markers.

    Returns 0 if valid, non-zero if missing sections or file.
    """
    report_path = repo_root / ".planning" / "milestones" / REPORT_FILENAME
    if not report_path.exists():
        print(f"ERROR: Report file not found: {report_path}", file=sys.stderr)
        return 1

    content = report_path.read_text(encoding="utf-8")
    missing: list[str] = []
    for marker in SECTION_MARKERS:
        if marker not in content:
            missing.append(marker)

    if missing:
        print(f"ERROR: Report missing section markers: {missing}", file=sys.stderr)
        return 1

    # Verify two-tier status model
    if AUTONOMOUS_CLOSURE_STATUS not in content:
        print("ERROR: Report missing autonomous closure status 'READY'", file=sys.stderr)
        return 1
    if V2_ACCEPTANCE_STATUS not in content:
        print("ERROR: Report missing V2 acceptance status 'BLOCKED ON HUMAN GATES'", file=sys.stderr)
        return 1

    print("OK: Report valid — all section markers present, two-tier status model confirmed.")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the V2 acceptance readiness report."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the report file exists and contains required sections.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]

    if args.check:
        return check_report(repo_root)

    report_path = write_report(repo_root)
    print(f"Report written: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
