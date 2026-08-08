"""CLI entry point for ``inkstatute-agent``.

Usage::

    inkstatute-agent acp            # Start ACP server (stdio)
    inkstatute-agent acp --check    # Bootstrap check, exit 0/1
    inkstatute-agent --version      # Print version

The ``acp`` subcommand starts the ACP v1 server which reads JSON-RPC 2.0
from stdin and writes responses to stdout.  This is the second entry
point for the self-built agent core — the same ``run_turn()``
implementation powers both the in-process ``InProcessAgentCoreAdapter``
and this ACP subprocess server.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .acp_server import ACPServer, default_provider_factory, run_check


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``inkstatute-agent``."""
    parser = argparse.ArgumentParser(
        prog="inkstatute-agent",
        description="InkStatute agent core CLI — ACP server entry point.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"inkstatute-agent {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # acp subcommand
    acp_parser = subparsers.add_parser(
        "acp",
        help="Start the ACP v1 server (reads stdin, writes stdout).",
    )
    acp_parser.add_argument(
        "--check",
        action="store_true",
        help="Run bootstrap check (verify model provider is available), then exit.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Returns the exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "acp":
        if args.check:
            return run_check(default_provider_factory)
        # Start the ACP server
        server = ACPServer(provider_factory=default_provider_factory)
        server.run_sync()
        return 0

    # No subcommand — print help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
