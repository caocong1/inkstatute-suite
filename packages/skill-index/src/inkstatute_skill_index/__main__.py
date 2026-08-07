"""Module entry point for ``python -m inkstatute_skill_index``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
