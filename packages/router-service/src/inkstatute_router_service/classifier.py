"""Intent classifier for the RULE strategy.

Provides keyword/regex-based intent classification that maps a user message
to one of four intent categories: ``factual_qa``, ``drafting``, ``analysis``,
``review``.  The classifier is pure and stateless.
"""

from __future__ import annotations

import re

INTENT_KEYWORDS: dict[str, list[str]] = {
    "factual_qa": ["什么", "是否", "如何", "请问", "查询", "what", "is", "how"],
    "drafting": ["起草", "草拟", "撰写", "draft", "write", "generate"],
    "analysis": ["分析", "总结", "归纳", "analyze", "summarize"],
    "review": ["审查", "审核", "检查", "review", "check", "compliance"],
}


def classify_intent(message: str | None) -> str | None:
    """Classify *message* into an intent category via keyword matching.

    Returns the first intent whose any keyword appears as a case-insensitive
    match in *message*.  Chinese keywords are matched as substrings; English
    keywords are matched with word boundaries (``\\b``) to avoid false
    substring matches (e.g. ``"is"`` inside ``"this"``).  Returns ``None``
    for empty/``None`` message or when no keyword matches.
    """
    if not message:
        return None
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if _is_ascii(keyword):
                pattern = rf"\b{re.escape(keyword)}\b"
            else:
                pattern = re.escape(keyword)
            if re.search(pattern, message, re.IGNORECASE):
                return intent
    return None


def _is_ascii(text: str) -> bool:
    """Return True if *text* contains only ASCII characters."""
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False
