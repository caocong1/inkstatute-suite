"""ENGINE-05 AST gate test — no LLM provider imports in arena-engine source.

Static analysis test that AST-parses every ``.py`` file in
``packages/arena-engine/src/arena_engine/`` and asserts that no file
imports from forbidden LLM provider modules: ``openai``, ``anthropic``,
``ollama``.

The orchestrator never produces content — arena-engine must not depend
on any LLM provider SDK.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

FORBIDDEN_MODULES = frozenset({"openai", "anthropic", "ollama"})

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "arena_engine"


class TestNoLLMImports(unittest.TestCase):
    """Assert zero LLM provider imports in arena-engine source."""

    def test_no_llm_provider_imports(self) -> None:
        """No ``import openai`` / ``import anthropic`` / ``import ollama``."""
        violations: list[str] = []
        for py_file in sorted(_SOURCE_DIR.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_module = alias.name.split(".")[0]
                        if root_module in FORBIDDEN_MODULES:
                            violations.append(
                                f"{py_file}:{node.lineno}: "
                                f"import {alias.name} (forbidden LLM provider)"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    root_module = module.split(".")[0]
                    if root_module in FORBIDDEN_MODULES:
                        violations.append(
                            f"{py_file}:{node.lineno}: "
                            f"from {module} import ... (forbidden LLM provider)"
                        )

        self.assertEqual(
            violations,
            [],
            "Forbidden LLM provider imports found in arena-engine source:\n"
            + "\n".join(violations),
        )

    def test_no_indirect_llm_imports(self) -> None:
        """No ``from openai.xxx`` / ``from anthropic.xxx`` / ``from ollama.xxx``."""
        violations: list[str] = []
        for py_file in sorted(_SOURCE_DIR.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for forbidden in FORBIDDEN_MODULES:
                        if module.startswith(f"{forbidden}."):
                            violations.append(
                                f"{py_file}:{node.lineno}: "
                                f"from {module} import ... (indirect LLM provider)"
                            )

        self.assertEqual(
            violations,
            [],
            "Indirect LLM provider imports found in arena-engine source:\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
