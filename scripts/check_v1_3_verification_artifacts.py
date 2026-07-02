#!/usr/bin/env python3
"""Deterministic audit closure check for the v1.3 milestone.

Modes:
  --mode artifacts      Verify Phase 20-25 VERIFICATION.md and Phase 22-25/25.1
                        VALIDATION.md artifacts exist and contain required headers.
  --mode traceability   Verify .planning/REQUIREMENTS.md marks all v1.3 requirements
                        as Complete in the traceability table.
  --mode audit          Run artifacts + traceability and assert v1.3-MILESTONE-AUDIT.md
                        no longer reports gaps_found/unsatisfied status or unresolved
                        critical gaps.

Exit codes:
  0  pass
  1  artifact or traceability failure
  2  audit-statement failure (the milestone still reports gaps)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANNING = REPO_ROOT / ".planning"
PHASES = PLANNING / "phases"
V1_3_PHASES_ARCHIVE = PLANNING / "milestones" / "v1.3-phases"

VERIFICATION_FILES = [
    "20-durable-native-memory-store/20-VERIFICATION.md",
    "21-rolling-summary-pipeline/21-VERIFICATION.md",
    "22-recall-orchestrator-context-injection/22-VERIFICATION.md",
    "23-feedback-to-memory-review-loop/23-VERIFICATION.md",
    "24-memory-evaluation-harness-privacy-gates/24-VERIFICATION.md",
    "25-external-memory-adapter-spikes/25-VERIFICATION.md",
]

VALIDATION_FILES = [
    "22-recall-orchestrator-context-injection/22-VALIDATION.md",
    "23-feedback-to-memory-review-loop/23-VALIDATION.md",
    "24-memory-evaluation-harness-privacy-gates/24-VALIDATION.md",
    "25-external-memory-adapter-spikes/25-VALIDATION.md",
    "25.1-close-gap-v1-3-memory-runtime-and-feedback-wiring/25.1-VALIDATION.md",
]

REQUIRED_VERIFICATION_HEADERS = ["## Goal", "## Must-Haves", "## Evidence", "## Automated Checks", "## Notes", "## Result"]
REQUIRED_VALIDATION_HEADERS = ["## Test Infrastructure", "## Sampling Rate", "## Per-Task Verification Map", "## Wave 0 Requirements", "## Validation Sign-Off"]

REQUIREMENTS_FILE = PLANNING / "milestones" / "v1.3-REQUIREMENTS.md"
AUDIT_FILE = PLANNING / "milestones" / "v1.3-MILESTONE-AUDIT.md"


def _resolve_artifact(rel_path: str) -> Path | None:
    """Return the active or archived path for a v1.3 artifact, if it exists."""
    active = PHASES / rel_path
    archived = V1_3_PHASES_ARCHIVE / rel_path
    if active.exists():
        return active
    if archived.exists():
        return archived
    return None

V1_3_REQUIREMENTS = {
    "MEM-01", "MEM-02", "MEM-03", "MEM-04", "MEM-05",
    "SUM-01", "SUM-02", "SUM-03", "SUM-04",
    "REC-01", "REC-02", "REC-03", "REC-04", "REC-05",
    "FBL-01", "FBL-02", "FBL-03", "FBL-04", "FBL-05",
    "EVAL-01", "EVAL-02", "EVAL-03", "EVAL-04",
    "XMEM-01", "XMEM-02", "XMEM-03", "XMEM-04", "XMEM-05",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_artifacts() -> list[str]:
    failures: list[str] = []
    for rel_path in VERIFICATION_FILES:
        path = _resolve_artifact(rel_path)
        if path is None:
            failures.append(f"missing verification artifact: {rel_path}")
            continue
        text = _read(path)
        for header in REQUIRED_VERIFICATION_HEADERS:
            if header not in text:
                failures.append(f"{path.relative_to(REPO_ROOT)} missing header {header}")
    for rel_path in VALIDATION_FILES:
        path = _resolve_artifact(rel_path)
        if path is None:
            failures.append(f"missing validation artifact: {rel_path}")
            continue
        text = _read(path)
        for header in REQUIRED_VALIDATION_HEADERS:
            if header not in text:
                failures.append(f"{path.relative_to(REPO_ROOT)} missing header {header}")
    return failures


def check_traceability() -> list[str]:
    failures: list[str] = []
    if not REQUIREMENTS_FILE.exists():
        failures.append("missing .planning/milestones/v1.3-REQUIREMENTS.md")
        return failures
    text = _read(REQUIREMENTS_FILE)

    # Traceability table: | Requirement | Phase | Status |
    table_rows = re.findall(r"\|\s*([A-Z]{2,4}-\d+)\s*\|\s*([^|]+)\|\s*(\w+)\s*\|", text)
    found = {req: status for req, _phase, status in table_rows}
    missing = V1_3_REQUIREMENTS - set(found)
    if missing:
        failures.append(f"requirements missing from traceability table: {sorted(missing)}")
    for req in sorted(V1_3_REQUIREMENTS):
        status = found.get(req, "")
        if status.lower() != "complete":
            failures.append(f"{req} traceability status is {status!r} (expected Complete)")
    return failures


def check_audit_state() -> list[str]:
    failures: list[str] = []
    if not AUDIT_FILE.exists():
        failures.append("missing .planning/milestones/v1.3-MILESTONE-AUDIT.md")
        return failures
    text = _read(AUDIT_FILE)
    if "status: gaps_found" in text:
        failures.append("audit frontmatter still contains status: gaps_found")
    if "unsatisfied" in text:
        failures.append("audit still contains 'unsatisfied' entries")
    # Critical unresolved gap text from the previous audit
    unresolved_markers = [
        "Recall orchestration is not wired into ordinary WeCom/runtime flows",
        "Feedback-to-memory is not wired from feedback callbacks to future context",
        "MemoryUse evidence recording is fail-open",
        "Formal verification artifacts are missing",
    ]
    for marker in unresolved_markers:
        if marker in text:
            failures.append(f"audit still contains unresolved critical gap text: {marker!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="v1.3 milestone audit closure checker")
    parser.add_argument("--mode", choices=["artifacts", "traceability", "audit"], default="audit")
    args = parser.parse_args()

    failures: list[str] = []
    if args.mode in ("artifacts", "audit"):
        failures.extend(check_artifacts())
    if args.mode in ("traceability", "audit"):
        failures.extend(check_traceability())
    if args.mode == "audit":
        failures.extend(check_audit_state())

    if not failures:
        print(f"v1.3 {args.mode} check: PASS")
        return 0

    print(f"v1.3 {args.mode} check: FAIL")
    for failure in failures:
        print(f" - {failure}")
    if args.mode == "audit" and any("audit" in f for f in failures):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
