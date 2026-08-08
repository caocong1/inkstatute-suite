"""ENGINE-06 AST gate test — fresh context, no session/resume in arena-engine.

Static analysis test that AST-parses every ``.py`` file in
``packages/arena-engine/src/arena_engine/`` and asserts that:

1. No call has ``func.attr == "resume"`` or ``func.id == "resume_session"``
2. No string literal ``"session/resume"`` appears as a method argument
3. No function/method named ``resume_session`` or ``resume`` is defined

Every arena run must use a fresh context — session resumption is
forbidden in the arena engine boundary layer.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "arena_engine"


class TestFreshContext(unittest.TestCase):
    """Assert zero session/resume calls or definitions in arena-engine source."""

    def test_no_session_resume_calls(self) -> None:
        """No ``session.resume()`` calls or ``resume_session()`` calls."""
        violations: list[str] = []
        for py_file in sorted(_SOURCE_DIR.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        if func.attr == "resume":
                            violations.append(
                                f"{py_file}:{node.lineno}: "
                                f"call to .resume() (forbidden session resume)"
                            )
                    elif isinstance(func, ast.Name):
                        if func.id == "resume_session":
                            violations.append(
                                f"{py_file}:{node.lineno}: "
                                f"call to resume_session() (forbidden)"
                            )
                # Check string literal "session/resume" in any constant
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value == "session/resume":
                        violations.append(
                            f"{py_file}:{node.lineno}: "
                            f'string literal "session/resume" (forbidden)'
                        )

        self.assertEqual(
            violations,
            [],
            "Forbidden session/resume calls found in arena-engine source:\n"
            + "\n".join(violations),
        )

    def test_no_resume_session_method(self) -> None:
        """No ``resume_session`` or ``resume`` function/method definitions."""
        violations: list[str] = []
        for py_file in sorted(_SOURCE_DIR.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in ("resume_session", "resume"):
                        violations.append(
                            f"{py_file}:{node.lineno}: "
                            f"def {node.name}() (forbidden resume definition)"
                        )

        self.assertEqual(
            violations,
            [],
            "Forbidden resume method definitions found in arena-engine source:\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
