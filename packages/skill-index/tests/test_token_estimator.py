"""Unit tests for CJK-aware token estimation heuristic.

Verifies is_cjk, estimate_tokens, and estimate_tokens_for_file.
No external tokenizer dependency.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from inkstatute_skill_index.token_estimator import (
    estimate_tokens,
    estimate_tokens_for_file,
    is_cjk,
)


class TestTokenEstimator(unittest.TestCase):
    """Verify CJK-aware token estimation heuristic."""

    def test_is_cjk_chinese(self) -> None:
        """Chinese characters are CJK."""
        self.assertTrue(is_cjk("合"))
        self.assertTrue(is_cjk("审"))

    def test_is_cjk_latin(self) -> None:
        """Latin characters are not CJK."""
        self.assertFalse(is_cjk("a"))
        self.assertFalse(is_cjk("A"))

    def test_is_cjk_digit(self) -> None:
        """Digits are not CJK."""
        self.assertFalse(is_cjk("1"))

    def test_is_cjk_punctuation(self) -> None:
        """CJK punctuation (。U+3002) is not in the ideographs range."""
        self.assertFalse(is_cjk("。"))

    def test_estimate_tokens_pure_english(self) -> None:
        """11 chars // 4 = 2."""
        self.assertEqual(estimate_tokens("hello world"), 2)

    def test_estimate_tokens_pure_chinese(self) -> None:
        """4 CJK chars × 1.0 = 4."""
        self.assertEqual(estimate_tokens("合同审查"), 4)

    def test_estimate_tokens_mixed(self) -> None:
        """4 CJK + 6 non-CJK // 4 = 4 + 1 = 5."""
        self.assertEqual(estimate_tokens("合同审查 hello"), 5)

    def test_estimate_tokens_empty(self) -> None:
        """Empty string → 0 tokens."""
        self.assertEqual(estimate_tokens(""), 0)

    def test_estimate_tokens_long_text(self) -> None:
        """100 'A' chars → 100 // 4 = 25."""
        self.assertEqual(estimate_tokens("A" * 100), 25)

    def test_estimate_tokens_for_file(self) -> None:
        """File reading returns same result as estimate_tokens(content), file unchanged."""
        content = "合同审查 hello world"
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)
        try:
            mtime_before = path.stat().st_mtime_ns
            # Sleep briefly to ensure any mtime change would be detectable
            time.sleep(0.01)
            result = estimate_tokens_for_file(path)
            mtime_after = path.stat().st_mtime_ns
            self.assertEqual(result, estimate_tokens(content))
            self.assertEqual(mtime_before, mtime_after)
        finally:
            path.unlink()

    def test_no_external_imports(self) -> None:
        """Module must not import tiktoken, transformers, or sentencepiece."""
        # Check sys.modules for unwanted tokenizer libraries
        for mod_name in ("tiktoken", "transformers", "sentencepiece"):
            self.assertNotIn(
                mod_name,
                sys.modules,
                f"Module {mod_name} should not be imported by token_estimator",
            )
        # Also inspect the source file for forbidden imports
        source = Path(__file__).resolve().parents[1] / "src" / "inkstatute_skill_index" / "token_estimator.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in ("tiktoken", "transformers", "sentencepiece"):
            self.assertNotIn(
                f"import {forbidden}",
                text,
                f"Source must not contain 'import {forbidden}'",
            )


if __name__ == "__main__":
    unittest.main()
