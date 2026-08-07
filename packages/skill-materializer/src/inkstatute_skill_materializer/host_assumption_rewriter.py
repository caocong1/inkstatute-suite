"""Host assumption rewriter — pattern-based, deterministic, auditable.

Applies three deterministic regex-based transformation rules to SKILL.md body
text:

1. ``/plugin:skill`` trigger patterns → natural language trigger description
   (e.g., ``/commercial-legal:risk-identification`` →
   ``When the user asks about risk-identification...``)
2. ``ask_user`` / ``ask-user`` → ``elicitation`` (ACP protocol term)
3. ``CLAUDE.md`` references → flagged in the report as
   ``practice_profile_dependency`` but NOT rewritten in the text

Each rewrite is logged in a :class:`RewriteReport` with
:class:`RewriteEntry` records containing ``original_text``,
``rewritten_text``, ``rule_applied``, and ``location`` (file path + line
number).

The rewriter is:
- **Deterministic** — same input → same output (regex-based, no LLM)
- **Auditable** — every rewrite logged in the report
- **Reversible** — the report contains enough information to reconstruct
  the original text
- **Testable** — fixture SKILL.md snippets with known patterns
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RewriteEntry:
    """A single rewrite operation record.

    Attributes:
        original_text: The text before rewriting.
        rewritten_text: The text after rewriting (same as original for
            flag-only rules like CLAUDE.md).
        rule_applied: Which rule triggered — ``"trigger_to_natural_language"``,
            ``"ask_user_to_elicitation"``, or ``"claude_md_flag"``.
        location: File path + line number (e.g., ``"path/to/SKILL.md:42"``).
        line_number: 1-based line number in the source text.
    """

    original_text: str
    rewritten_text: str
    rule_applied: str
    location: str
    line_number: int


@dataclass(frozen=True, slots=True)
class RewriteReport:
    """Aggregated report of all rewrites applied to a text.

    Attributes:
        entries: List of :class:`RewriteEntry` records.
        total_rewrites: Total number of rewrites (including flag-only).
        text_changed: Whether the text was actually modified (False if
            only flag-only rules triggered).
    """

    entries: list[RewriteEntry] = field(default_factory=list)
    total_rewrites: int = 0
    text_changed: bool = False


# ---------------------------------------------------------------------------
# Rule patterns
# ---------------------------------------------------------------------------

# Rule 1: /plugin:skill trigger patterns
# Matches /<plugin>:<skill> where plugin and skill are alphanumeric + - _
_TRIGGER_PATTERN: re.Pattern[str] = re.compile(
    r"/[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+"
)

# Rule 2: ask_user / ask-user → elicitation (case-insensitive)
_ASK_USER_PATTERN: re.Pattern[str] = re.compile(
    r"\bask[_-]user\b", re.IGNORECASE
)

# Rule 3: CLAUDE.md references (flag only, no rewrite)
_CLAUDE_MD_PATTERN: re.Pattern[str] = re.compile(
    r"CLAUDE\.md"
)


# ---------------------------------------------------------------------------
# Rewriter
# ---------------------------------------------------------------------------


class HostAssumptionRewriter:
    """Pattern-based text transformation for host assumption rewriting.

    Applies three deterministic regex-based rules to SKILL.md body text.
    Each rewrite is logged in a :class:`RewriteReport` for auditability.

    Usage::

        rewriter = HostAssumptionRewriter()
        rewritten, report = rewriter.rewrite(text, file_path="path/to/SKILL.md")
    """

    def rewrite(self, text: str, file_path: str = "") -> tuple[str, RewriteReport]:
        """Apply all rewriting rules to *text*.

        Args:
            text: The SKILL.md body text to rewrite.
            file_path: Optional file path for location tracking in the report.

        Returns:
            A tuple of ``(rewritten_text, RewriteReport)``.
        """
        entries: list[RewriteEntry] = []
        rewritten = text
        text_changed = False

        # --- Rule 1: /plugin:skill → natural language ---
        rewritten, rule1_entries = self._apply_trigger_rule(
            rewritten, file_path
        )
        entries.extend(rule1_entries)
        if rule1_entries:
            text_changed = True

        # --- Rule 2: ask_user / ask-user → elicitation ---
        rewritten, rule2_entries = self._apply_ask_user_rule(
            rewritten, file_path
        )
        entries.extend(rule2_entries)
        if rule2_entries:
            text_changed = True

        # --- Rule 3: CLAUDE.md → flag only (no text change) ---
        _, rule3_entries = self._apply_claude_md_rule(
            rewritten, file_path
        )
        entries.extend(rule3_entries)
        # Rule 3 does NOT change text_changed (flag only)

        return rewritten, RewriteReport(
            entries=entries,
            total_rewrites=len(entries),
            text_changed=text_changed,
        )

    # --- Rule implementations -------------------------------------------

    def _apply_trigger_rule(
        self, text: str, file_path: str
    ) -> tuple[str, list[RewriteEntry]]:
        """Rule 1: /plugin:skill → natural language trigger description.

        ``/commercial-legal:risk-identification`` →
        ``When the user asks about risk-identification...``
        """
        entries: list[RewriteEntry] = []
        lines = text.split("\n")
        changed_lines: list[str] = []

        for line_num, line in enumerate(lines, start=1):
            matches = list(_TRIGGER_PATTERN.finditer(line))
            if not matches:
                changed_lines.append(line)
                continue

            new_line = line
            # Process matches in reverse order to preserve offsets
            for match in reversed(matches):
                trigger = match.group(0)
                # Extract skill name from /plugin:skill
                # trigger is /<plugin>:<skill>
                parts = trigger[1:].split(":", 1)  # remove leading /
                if len(parts) != 2:
                    continue
                _plugin, skill_name = parts
                natural = f"When the user asks about {skill_name}..."
                location = f"{file_path}:{line_num}" if file_path else str(line_num)
                entries.append(
                    RewriteEntry(
                        original_text=trigger,
                        rewritten_text=natural,
                        rule_applied="trigger_to_natural_language",
                        location=location,
                        line_number=line_num,
                    )
                )
                new_line = (
                    new_line[: match.start()] + natural + new_line[match.end() :]
                )

            changed_lines.append(new_line)

        # Sort entries by line number for deterministic order
        entries.sort(key=lambda e: (e.line_number, e.original_text))
        return "\n".join(changed_lines), entries

    def _apply_ask_user_rule(
        self, text: str, file_path: str
    ) -> tuple[str, list[RewriteEntry]]:
        """Rule 2: ask_user / ask-user → elicitation (case-insensitive)."""
        entries: list[RewriteEntry] = []
        lines = text.split("\n")
        changed_lines: list[str] = []

        for line_num, line in enumerate(lines, start=1):
            matches = list(_ASK_USER_PATTERN.finditer(line))
            if not matches:
                changed_lines.append(line)
                continue

            new_line = line
            for match in reversed(matches):
                original = match.group(0)
                location = f"{file_path}:{line_num}" if file_path else str(line_num)
                entries.append(
                    RewriteEntry(
                        original_text=original,
                        rewritten_text="elicitation",
                        rule_applied="ask_user_to_elicitation",
                        location=location,
                        line_number=line_num,
                    )
                )
                new_line = (
                    new_line[: match.start()] + "elicitation" + new_line[match.end() :]
                )

            changed_lines.append(new_line)

        entries.sort(key=lambda e: (e.line_number, e.original_text))
        return "\n".join(changed_lines), entries

    def _apply_claude_md_rule(
        self, text: str, file_path: str
    ) -> tuple[str, list[RewriteEntry]]:
        """Rule 3: CLAUDE.md references → flag only (no text rewrite)."""
        entries: list[RewriteEntry] = []
        lines = text.split("\n")

        for line_num, line in enumerate(lines, start=1):
            matches = list(_CLAUDE_MD_PATTERN.finditer(line))
            if not matches:
                continue

            for match in matches:
                original = match.group(0)
                location = f"{file_path}:{line_num}" if file_path else str(line_num)
                entries.append(
                    RewriteEntry(
                        original_text=original,
                        rewritten_text=original,  # unchanged — flag only
                        rule_applied="claude_md_flag",
                        location=location,
                        line_number=line_num,
                    )
                )

        entries.sort(key=lambda e: (e.line_number, e.original_text))
        # Text is NOT changed for this rule
        return text, entries
