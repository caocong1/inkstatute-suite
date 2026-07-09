"""Verify the QQBot adapter does NOT import from wecom_service.

This enforces the QQBOT-01 constraint that channel-generic logic lives in a
shared package and QQBot does not import directly from wecom_service.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src" / "inkstatute_channels_qqbot"


def _imported_modules(source: str) -> list[str]:
    """Return all module names referenced in import statements."""
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


class NoWecomImportTests(unittest.TestCase):
    def test_adapter_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "adapter.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"adapter.py imports from wecom_service: {module}",
            )

    def test_config_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "config.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"config.py imports from wecom_service: {module}",
            )

    def test_init_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "__init__.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"__init__.py imports from wecom_service: {module}",
            )

    def test_ed25519_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "_ed25519.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"_ed25519.py imports from wecom_service: {module}",
            )

    def test_signature_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "signature.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"signature.py imports from wecom_service: {module}",
            )

    def test_normalization_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "normalization.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"normalization.py imports from wecom_service: {module}",
            )

    def test_token_manager_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "token_manager.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"token_manager.py imports from wecom_service: {module}",
            )

    def test_sender_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "sender.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"sender.py imports from wecom_service: {module}",
            )

    def test_adapter_imports_channel_core(self) -> None:
        source = (PACKAGE_SRC / "adapter.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        self.assertTrue(
            any("channel_core" in module for module in modules),
            "adapter.py does not import from channel_core",
        )

    def test_no_wecom_service_string_in_source(self) -> None:
        source = (PACKAGE_SRC / "adapter.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "wecom_service",
            source,
            "adapter.py source contains the string 'wecom_service'",
        )


if __name__ == "__main__":
    unittest.main()
