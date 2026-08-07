"""CLI entry point for inkstatute-skill-materializer.

Usage::

    python -m inkstatute_skill_materializer materialize --target hermes --index <path> --output <path>
    python -m inkstatute_skill_materializer materialize --target acp --index <path> --output <path>
    python -m inkstatute_skill_materializer inject-body --skill-id <id> --index <path> --budget <tokens>
    python -m inkstatute_skill_materializer routing-manifest --index <path> --output <path>

The CLI is a thin wrapper over the Python API.  It follows the same
pattern as ``packages/skill-index/cli.py`` (Phase 96).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import MATERIALIZER_VERSION


def main(argv: list[str] | None = None) -> int:
    """CLI main entry point.

    Returns 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="InkStatute Skill Materializer — per-backend skill layout materialization.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # materialize subcommand
    mat_parser = subparsers.add_parser(
        "materialize", help="Materialize skills to a backend-specific layout."
    )
    mat_parser.add_argument(
        "--target",
        required=True,
        choices=["hermes", "acp"],
        help="Target backend: 'hermes' (Hermes profile) or 'acp' (ACP agent skills).",
    )
    mat_parser.add_argument(
        "--index",
        required=True,
        help="Path to skill-index.json.",
    )
    mat_parser.add_argument(
        "--output",
        required=True,
        help="Output directory for materialized skills.",
    )
    mat_parser.add_argument(
        "--profile",
        default="lawfirm",
        help="Hermes profile name (default: lawfirm, hermes target only).",
    )

    # inject-body subcommand
    inj_parser = subparsers.add_parser(
        "inject-body", help="Inject a skill body with budget-constrained trimming."
    )
    inj_parser.add_argument(
        "--skill-id",
        required=True,
        help="Skill ID to look up in the index.",
    )
    inj_parser.add_argument(
        "--index",
        required=True,
        help="Path to skill-index.json.",
    )
    inj_parser.add_argument(
        "--budget",
        type=int,
        required=True,
        help="Maximum token budget for the injected body.",
    )
    inj_parser.add_argument(
        "--chars-per-token",
        type=int,
        default=4,
        help="Non-CJK characters per token (default: 4).",
    )

    # routing-manifest subcommand
    rm_parser = subparsers.add_parser(
        "routing-manifest", help="Produce a metadata-only routing manifest."
    )
    rm_parser.add_argument(
        "--index",
        required=True,
        help="Path to skill-index.json.",
    )
    rm_parser.add_argument(
        "--output",
        required=True,
        help="Output path for the routing manifest JSON.",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "materialize":
        return _run_materialize(args)
    if args.command == "inject-body":
        return _run_inject_body(args)
    if args.command == "routing-manifest":
        return _run_routing_manifest(args)

    parser.print_help()
    return 1


def _run_materialize(args: argparse.Namespace) -> int:
    """Execute the materialize subcommand."""
    target = args.target
    index_path = args.index
    output_dir = args.output

    if not Path(index_path).exists():
        print(f"Error: index file not found: {index_path}", file=sys.stderr)
        return 1

    if target == "hermes":
        from .hermes_materializer import materialize_hermes

        try:
            result = materialize_hermes(
                index_path, output_dir, profile_name=args.profile
            )
        except Exception as exc:
            print(f"Error materializing to Hermes: {exc}", file=sys.stderr)
            return 1

        print(f"Hermes materialization complete: {output_dir}")
        print(f"  Profile: {result.profile_name}")
        print(f"  Total skills: {result.materialized_count}")
        print(f"  Symlinked: {result.symlinked_count}")
        print(f"  Copied (scripts/): {result.copied_count}")
        print(f"  Fallback copies: {result.fallback_count}")
        if result.errors:
            print(f"  Errors: {len(result.errors)}", file=sys.stderr)
            for err in result.errors[:10]:
                print(f"    - {err}", file=sys.stderr)
        return 0

    # target == "acp"
    from .acp_materializer import materialize_acp

    try:
        result = materialize_acp(index_path, output_dir)
    except Exception as exc:
        print(f"Error materializing to ACP: {exc}", file=sys.stderr)
        return 1

    print(f"ACP materialization complete: {output_dir}")
    print(f"  Total skills: {result.materialized_count}")
    print(f"  Symlinked: {result.symlinked_count}")
    print(f"  Copied (scripts/): {result.copied_count}")
    print(f"  Rewritten: {result.rewritten_count}")
    print(f"  Fallback copies: {result.fallback_count}")
    print(f"  Total rewrites: {result.rewrite_report.total_rewrites}")
    if result.errors:
        print(f"  Errors: {len(result.errors)}", file=sys.stderr)
        for err in result.errors[:10]:
            print(f"    - {err}", file=sys.stderr)
    return 0


def _run_inject_body(args: argparse.Namespace) -> int:
    """Execute the inject-body subcommand."""
    from .body_injector import (
        SkillBodyBudgetError,
        SkillNotFoundError,
        SourceFileNotFoundError,
        read_skill_body,
    )

    if not Path(args.index).exists():
        print(f"Error: index file not found: {args.index}", file=sys.stderr)
        return 1

    try:
        result = read_skill_body(
            skill_id=args.skill_id,
            index_path=args.index,
            budget_tokens=args.budget,
            chars_per_token=args.chars_per_token,
        )
    except SkillNotFoundError as exc:
        print(f"Error: skill not found: {exc}", file=sys.stderr)
        return 1
    except SourceFileNotFoundError as exc:
        print(f"Error: source file not found: {exc}", file=sys.stderr)
        return 1
    except SkillBodyBudgetError as exc:
        print(f"Error: budget exceeded by protected sections: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Print summary as JSON
    summary = {
        "skill_id": args.skill_id,
        "original_token_estimate": result.original_token_estimate,
        "injected_token_estimate": result.injected_token_estimate,
        "budget_tokens": result.budget_tokens,
        "budget_used": result.budget_used,
        "trimmed_sections": result.trimmed_sections,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _run_routing_manifest(args: argparse.Namespace) -> int:
    """Execute the routing-manifest subcommand."""
    from .three_separation import produce_routing_manifest

    if not Path(args.index).exists():
        print(f"Error: index file not found: {args.index}", file=sys.stderr)
        return 1

    try:
        produce_routing_manifest(args.index, args.output)
    except Exception as exc:
        print(f"Error producing routing manifest: {exc}", file=sys.stderr)
        return 1

    # Read back and print summary
    data = json.loads(Path(args.output).read_text(encoding="utf-8"))
    print(f"Routing manifest written to: {args.output}")
    print(f"  Version: {data.get('version', '?')}")
    print(f"  Skill count: {data.get('skill_count', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
