"""Host assumption rewriter — pattern-based, deterministic, auditable.

Applies three deterministic regex-based transformation rules to SKILL.md body
text:

1. ``/plugin:skill`` trigger patterns → natural language trigger description
2. ``ask_user`` / ``ask-user`` → ``elicitation``
3. ``CLAUDE.md`` references → flagged but not rewritten

Stub — full implementation in Task 97-01-03.
"""

from __future__ import annotations


class HostAssumptionRewriter:
    """Pattern-based text transformation for host assumption rewriting.

    Stub — full implementation in Task 97-01-03.
    """

    def rewrite(self, text: str, file_path: str = "") -> tuple[str, object]:
        raise NotImplementedError("Host assumption rewriter not yet implemented")
