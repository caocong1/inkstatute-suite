"""CJK-aware token estimation heuristic.

No external tokenizer dependency (no tiktoken, no transformers, no sentencepiece).
The formula:

    token_estimate = (CJK_character_count * 1.0) + (non_CJK_character_count // 4)

This is an estimate for routing and context budget purposes, not an exact count.
"""

from __future__ import annotations

from pathlib import Path


def is_cjk(char: str) -> bool:
    """Return True if *char* is a CJK Unified Ideograph or related character.

    Covers:
    - CJK Unified Ideographs: U+4E00–U+9FFF
    - CJK Extension A: U+3400–U+4DBF
    - CJK Compatibility Ideographs: U+F900–U+FAFF
    """
    cp = ord(char)
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    if 0x3400 <= cp <= 0x4DBF:
        return True
    if 0xF900 <= cp <= 0xFAFF:
        return True
    return False


def estimate_tokens(text: str) -> int:
    """Estimate the token count of *text* using a CJK-aware heuristic.

    CJK characters count as 1 token each; non-CJK characters count as
    approximately 1 token per 4 characters.
    """
    cjk_count = sum(1 for c in text if is_cjk(c))
    non_cjk_count = len(text) - cjk_count
    return cjk_count + non_cjk_count // 4


def estimate_tokens_for_file(path: Path) -> int:
    """Read *path* and return the estimated token count.

    Uses ``path.read_text(encoding="utf-8")`` — read-only, never modifies the file.
    """
    content = path.read_text(encoding="utf-8")
    return estimate_tokens(content)
