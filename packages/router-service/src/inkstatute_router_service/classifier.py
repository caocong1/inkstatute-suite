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
    substring in *message*.  Returns ``None`` for empty/``None`` message or
    when no keyword matches.
    """
    if not message:
        return None
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if re.search(re.escape(keyword), message, re.IGNORECASE):
                return intent
    return None
