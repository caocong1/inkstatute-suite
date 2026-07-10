"""ADAPTER-04: host package must not import or mention wecom_service."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src" / "qqbot_service"


def _imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


class HostNoWecomImportTests(unittest.TestCase):
    def test_all_production_modules_have_no_wecom_service_substring(self) -> None:
        self.assertTrue(PACKAGE_SRC.is_dir(), f"missing {PACKAGE_SRC}")
        offenders: list[str] = []
        for path in sorted(PACKAGE_SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            rel = path.relative_to(PACKAGE_SRC).as_posix()
            if "wecom_service" in source:
                offenders.append(rel)
            for module in _imported_modules(source):
                if module.startswith("wecom_service"):
                    offenders.append(f"{rel}:{module}")
        self.assertEqual(
            offenders,
            [],
            f"wecom_service found in host production modules: {offenders}",
        )

    def test_each_module_import_graph_excludes_wecom_service(self) -> None:
        for path in sorted(PACKAGE_SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for module in _imported_modules(source):
                self.assertFalse(
                    module.startswith("wecom_service"),
                    f"{path.name} imports from wecom_service: {module}",
                )


if __name__ == "__main__":
    unittest.main()
