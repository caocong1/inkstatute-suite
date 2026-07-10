"""Host package skeleton layout and empty-deps assertions (Phase 68 SAFE-01)."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOST_ROOT = REPO_ROOT / "services" / "qqbot-service"
PYPROJECT = HOST_ROOT / "pyproject.toml"
INIT_PY = HOST_ROOT / "src" / "qqbot_service" / "__init__.py"


class TestHostSkeleton(unittest.TestCase):
    def test_pyproject_has_empty_dependencies(self) -> None:
        self.assertTrue(PYPROJECT.is_file(), f"missing {PYPROJECT}")
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)

    def test_src_layout_exists(self) -> None:
        self.assertTrue(INIT_PY.is_file(), f"missing {INIT_PY}")

    def test_package_importable(self) -> None:
        import qqbot_service  # noqa: F401

        self.assertTrue(hasattr(qqbot_service, "__all__"))


if __name__ == "__main__":
    unittest.main()
