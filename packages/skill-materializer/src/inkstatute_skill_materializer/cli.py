"""CLI entry point for inkstatute-skill-materializer.

Usage::

    python -m inkstatute_skill_materializer materialize --target hermes --index <path> --output <path>
    python -m inkstatute_skill_materializer materialize --target acp --index <path> --output <path>
    python -m inkstatute_skill_materializer routing-manifest --index <path> --output <path>

Stub — full CLI wired in Task 97-04 (Wave 3).
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """CLI main entry point.

    Stub — full CLI wired in Task 97-04 (Wave 3).
    """
    print(
        "inkstatute-skill-materializer CLI — "
        "use 'materialize --target hermes|acp' or 'routing-manifest'",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
