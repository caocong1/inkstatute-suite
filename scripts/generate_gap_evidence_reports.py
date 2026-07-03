#!/usr/bin/env python3
"""Generate GAP-08 and GAP-09 evidence report JSON sidecars.

Calls the evidence producer functions in the contract-test-suite package
and writes deterministic JSON sidecars to the ``acceptance/`` directory.

Usage::

    python scripts/generate_gap_evidence_reports.py
    python scripts/generate_gap_evidence_reports.py --check

The ``--check`` flag exits non-zero if any §10.3 task type is uncovered
or any §10.2 output boundary category is missing — suitable for CI gates.

Output is deterministic: ``sort_keys=True``, no timestamps, sorted lists.
Same codebase → byte-identical output across runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate GAP-08/GAP-09 evidence report JSON sidecars.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if coverage is incomplete (for CI gate integration).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]

    # Make contract-test-suite and platform-contract importable for standalone runs.
    contract_src = repo_root / "packages" / "contract-test-suite" / "src"
    platform_src = repo_root / "packages" / "platform-contract" / "src"
    for src_path in (contract_src, platform_src):
        src_str = str(src_path)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)

    from contract_test_suite.boundary_checks import build_output_boundary_evidence_summary
    from contract_test_suite.coverage_report import build_composability_coverage_report

    # Generate composability coverage sidecar (GAP-08).
    comp_report = build_composability_coverage_report(repo_root=repo_root)
    comp_path = repo_root / "acceptance" / "v2-composability-coverage.json"
    comp_path.parent.mkdir(parents=True, exist_ok=True)
    comp_path.write_text(
        json.dumps(comp_report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Generate output boundary evidence sidecar (GAP-09).
    ob_report = build_output_boundary_evidence_summary(repo_root=repo_root)
    ob_path = repo_root / "acceptance" / "v2-output-boundary-evidence.json"
    ob_path.write_text(
        json.dumps(ob_report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {comp_path}")
    print(f"Wrote {ob_path}")
    print(
        f"Composability: {comp_report.covered_count}/{len(comp_report.entries)} "
        f"task types covered"
    )
    print(
        f"Output boundary: "
        f"{'all' if ob_report.all_categories_covered else 'PARTIAL'} "
        f"categories covered"
    )

    if args.check:
        failures: list[str] = []
        if not comp_report.all_covered:
            missing = [
                e.task_type for e in comp_report.entries if not e.covered
            ]
            failures.append(
                f"composability coverage incomplete: {missing}"
            )
        if not ob_report.all_categories_covered:
            failures.append(
                f"output boundary categories missing: "
                f"{list(ob_report.missing_categories)}"
            )
        if not ob_report.no_visible_backend_terms:
            failures.append(
                "output boundary: backend terms visible in block/rewrite cases"
            )
        if failures:
            for f in failures:
                print(f"FAIL: {f}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
