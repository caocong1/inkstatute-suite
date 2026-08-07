"""CLI entry point for the skill index scanner.

Usage::

    python -m inkstatute_skill_index scan \
        --repo /path/to/ai-for-china-legal --repo-name ai-for-china-legal \
        --repo /path/to/legal-skills --repo-name legal-skills \
        --output /tmp/skill-index.json

CRITICAL: The CLI validates that the output path is NOT inside any source
repo.  This is the last line of defense for read-only enforcement (SAFE-05).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import SCANNER_VERSION
from .index_builder import build_index, write_index


def _validate_output_path(output_path: str, repo_paths: list[str]) -> None:
    """Assert that *output_path* is not inside any of the *repo_paths*.

    Raises ``ValueError`` if the output path resolves to a location inside
    any source repo directory.
    """
    out_resolved = Path(output_path).resolve()
    for repo in repo_paths:
        repo_resolved = Path(repo).resolve()
        try:
            out_resolved.relative_to(repo_resolved)
        except ValueError:
            continue
        # output is inside a repo — violation
        raise ValueError(
            f"Output path '{output_path}' is inside source repo '{repo}'. "
            f"The skill index scanner is read-only (SAFE-05) and must not "
            f"write to source repos. Use a path outside the repos."
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="InkStatute Skill Index Scanner",
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan subcommand
    scan_parser = subparsers.add_parser(
        "scan", help="Scan repos and generate skill-index.json"
    )
    scan_parser.add_argument(
        "--repo",
        action="append",
        required=True,
        help="Path to a repo to scan. Can be specified multiple times.",
    )
    scan_parser.add_argument(
        "--repo-name",
        action="append",
        required=True,
        help="Name for each repo (must match the number of --repo args).",
    )
    scan_parser.add_argument(
        "--output",
        required=True,
        help="Output path for skill-index.json.",
    )
    scan_parser.add_argument(
        "--previous-index",
        default=None,
        help="Path to a previous skill-index.json for conflict classification.",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "scan":
        return _run_scan(args)

    parser.print_help()
    return 1


def _run_scan(args: argparse.Namespace) -> int:
    """Execute the scan subcommand."""
    repos = args.repo or []
    repo_names = args.repo_name or []

    if len(repos) != len(repo_names):
        print(
            f"Error: --repo ({len(repos)}) and --repo-name ({len(repo_names)}) "
            f"must have the same count.",
            file=sys.stderr,
        )
        return 1

    # Validate output path is not inside any source repo (SAFE-05)
    try:
        _validate_output_path(args.output, repos)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Build repo configs
    repo_configs = [
        {"name": name, "path": path} for path, name in zip(repos, repo_names)
    ]

    # Build the index
    try:
        index = build_index(
            repo_configs,
            previous_index_path=args.previous_index,
        )
    except Exception as exc:
        print(f"Error building index: {exc}", file=sys.stderr)
        return 1

    # Write the index
    try:
        write_index(index, args.output)
    except Exception as exc:
        print(f"Error writing index: {exc}", file=sys.stderr)
        return 1

    # Print summary
    print(f"Skill index written to: {args.output}")
    print(f"Scanner version: {SCANNER_VERSION}")
    print(f"Generated at: {index.generated_at}")
    print(f"Total skills: {len(index.skills)}")
    for repo_name, meta in index.repos.items():
        print(f"  {repo_name}: {meta['skill_count']} skills (commit: {meta['commit']})")

    # Merge report summary
    mr = index.merge_report
    if mr and "conflict_classification" in mr:
        cc = mr["conflict_classification"]
        print("Conflict classification:")
        for status in ("in-sync", "upstream-changed", "both-changed", "local-missing"):
            count = len(cc.get(status, []))
            print(f"  {status}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
