#!/usr/bin/env python3
"""Run the package-local InkStatute contract test suite."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    repo_root = package_root.parents[1]
    source_paths = (
        package_root / "src",
        repo_root / "packages" / "platform-contract" / "src",
        repo_root / "packages" / "platform-runtime" / "src",
        repo_root / "packages" / "backends" / "hermes" / "src",
        repo_root / "services" / "wecom-service" / "src",
    )
    for source_path in reversed(source_paths):
        sys.path.insert(0, str(source_path))

    suite = unittest.defaultTestLoader.discover(str(package_root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
