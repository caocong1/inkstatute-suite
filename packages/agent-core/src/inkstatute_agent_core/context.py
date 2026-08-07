"""AgentContextAssembler — context budget with history trim + skill body injection.

Combines two existing patterns:

1. **Conversation history trimming** (from ``context_assembler.py``):
   Truncate to ``max_history_turns`` most recent turns, then drop oldest
   turns first when over the history budget fraction.

2. **Skill body injection** (from ``body_injector.py``):
   Parse skill body into sections by ``## `` headers, assign priorities
   (Protected → High → Medium → Low), and trim from lowest priority with
   most tokens until the skill body fits within its budget fraction.

The assembler enforces a total token budget across system prompt + skill
bodies + conversation history + current turn.  It is deterministic: the
same input + same budget always produces the same output.

CJK-aware token estimation:
    token_estimate = CJK_chars * 1.0 + non_CJK_chars // chars_per_token

This matches the heuristic used by ``inkstatute_skill_materializer.body_injector``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# CJK-aware token estimation (matching body_injector.py)
# ---------------------------------------------------------------------------


def _is_cjk(char: str) -> bool:
    """Return True if *char* is a CJK Unified Ideograph or related character."""
    cp = ord(char)
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    if 0x3400 <= cp <= 0x4DBF:
        return True
    if 0xF900 <= cp <= 0xFAFF:
        return True
    return False


def _estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    """Estimate the token count of *text* using a CJK-aware heuristic.

    CJK characters count as 1 token each; non-CJK characters count as
    approximately 1 token per *chars_per_token* characters.
    """
    cjk_count = sum(1 for c in text if _is_cjk(c))
    non_cjk_count = len(text) - cjk_count
    return cjk_count + non_cjk_count // chars_per_token


def _estimate_message_tokens(message: dict, chars_per_token: int = 4) -> int:
    """Estimate tokens for a single message dict by summing all string values."""
    total_chars_cjk = 0
    total_chars_non_cjk = 0
    for val in _iter_string_values(message):
        for ch in val:
            if _is_cjk(ch):
                total_chars_cjk += 1
            else:
                total_chars_non_cjk += 1
    return total_chars_cjk + total_chars_non_cjk // chars_per_token


def _iter_string_values(obj: Any):
    """Recursively yield all string values from a nested dict/list structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_string_values(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_string_values(item)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ContextAssemblyBudgetError(ValueError):
    """Raised when protected sections alone exceed the configured budget."""


# ---------------------------------------------------------------------------
# Section model (for skill body parsing)
# ---------------------------------------------------------------------------

# Priority ordering: lower number = higher priority (trimmed last)
_PRIORITY_PROTECTED = 0
_PRIORITY_HIGH = 1
_PRIORITY_MEDIUM = 2
_PRIORITY_LOW = 3

_PRIORITY_NAMES: dict[int, str] = {
    _PRIORITY_PROTECTED: "protected",
    _PRIORITY_HIGH: "high",
    _PRIORITY_MEDIUM: "medium",
    _PRIORITY_LOW: "low",
}


@dataclass
class _Section:
    """A parsed section of a skill body."""

    name: str
    text: str
    priority: int
    token_estimate: int
    is_protected: bool = False


# Section parsing regexes
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_H2_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Keywords for priority assignment
_HIGH_KEYWORDS = ("research-gate", "ask-user")
_LOW_KEYWORDS = ("example", "appendix", "reference")


def _parse_sections(skill_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse skill body into frontmatter and section list.

    Returns:
        A tuple of (frontmatter_text, sections) where sections is a list of
        (header_name, section_text) pairs. The frontmatter_text includes the
        ``---`` fences. The description (text before the first ``##`` header
        but after frontmatter) is included as the first section with name
        ``"__description__"``.
    """
    fm_match = _FRONTMATTER_RE.match(skill_text)
    if fm_match:
        frontmatter = skill_text[: fm_match.end()]
        remaining = skill_text[fm_match.end():]
    else:
        frontmatter = ""
        remaining = skill_text

    h2_positions: list[tuple[int, str]] = []
    for match in _H2_HEADER_RE.finditer(remaining):
        h2_positions.append((match.start(), match.group(1).strip()))

    sections: list[tuple[str, str]] = []

    if h2_positions:
        first_pos = h2_positions[0][0]
        desc_text = remaining[:first_pos].strip()
        if desc_text:
            sections.append(("__description__", desc_text + "\n"))
    else:
        desc_text = remaining.strip()
        if desc_text:
            sections.append(("__description__", desc_text + "\n"))

    for i, (pos, header_name) in enumerate(h2_positions):
        if i + 1 < len(h2_positions):
            section_text = remaining[pos : h2_positions[i + 1][0]]
        else:
            section_text = remaining[pos:]
        sections.append((header_name, section_text))

    return frontmatter, sections


def _assign_priority(
    section_name: str,
    index: int,
    is_description: bool,
) -> int:
    """Assign a priority level to a section."""
    if is_description:
        return _PRIORITY_PROTECTED
    if index == 1:  # First ## section is protected
        return _PRIORITY_PROTECTED

    name_lower = section_name.lower()

    for keyword in _HIGH_KEYWORDS:
        if keyword in name_lower:
            return _PRIORITY_HIGH

    for keyword in _LOW_KEYWORDS:
        if keyword in name_lower:
            return _PRIORITY_LOW

    return _PRIORITY_MEDIUM


def _build_sections(
    frontmatter: str,
    raw_sections: list[tuple[str, str]],
    chars_per_token: int,
) -> list[_Section]:
    """Build _Section objects from parsed sections with priorities and token estimates."""
    sections: list[_Section] = []

    for i, (name, text) in enumerate(raw_sections):
        is_description = name == "__description__"
        priority = _assign_priority(name, i, is_description)

        if is_description:
            token_text = frontmatter + text
        else:
            token_text = text

        token_est = _estimate_tokens(token_text, chars_per_token)

        sections.append(
            _Section(
                name=name,
                text=text,
                priority=priority,
                token_estimate=token_est,
                is_protected=(priority == _PRIORITY_PROTECTED),
            )
        )

    return sections


def _trim_skill_body(
    skill_text: str,
    budget_tokens: int,
    chars_per_token: int,
) -> tuple[str, list[dict[str, Any]]]:
    """Trim a skill body to fit within *budget_tokens* using section-priority.

    Returns:
        A tuple of (trimmed_text, trimmed_sections_report) where
        trimmed_sections_report is a list of dicts describing each trimmed
        section.
    """
    frontmatter, raw_sections = _parse_sections(skill_text)
    sections = _build_sections(frontmatter, raw_sections, chars_per_token)
    original_tokens = _estimate_tokens(skill_text, chars_per_token)

    protected_tokens = sum(s.token_estimate for s in sections if s.is_protected)
    if protected_tokens > budget_tokens:
        raise ContextAssemblyBudgetError(
            f"protected skill sections require {protected_tokens} estimated tokens, "
            f"budget is {budget_tokens}"
        )

    active_sections: list[_Section] = list(sections)
    trimmed_sections: list[dict[str, Any]] = []
    current_tokens = original_tokens

    while current_tokens > budget_tokens:
        candidates = [s for s in active_sections if not s.is_protected]
        if not candidates:
            break

        candidates.sort(key=lambda s: (-s.priority, -s.token_estimate))
        section_to_trim = candidates[0]

        trimmed_sections.append(
            {
                "section_name": section_to_trim.name,
                "priority": _PRIORITY_NAMES.get(section_to_trim.priority, "unknown"),
                "original_tokens": section_to_trim.token_estimate,
                "reason": "budget_trim",
            }
        )

        active_sections.remove(section_to_trim)
        current_tokens -= section_to_trim.token_estimate

    if not trimmed_sections:
        injected_text = skill_text
    else:
        injected_parts: list[str] = []
        if frontmatter:
            injected_parts.append(frontmatter)
        for section in active_sections:
            injected_parts.append(section.text)
        injected_text = "\n".join(injected_parts)

    return injected_text, trimmed_sections


# ---------------------------------------------------------------------------
# Policy and Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentContextPolicy:
    """Policy for context assembly budget and trimming.

    Attributes:
        budget_tokens: Total token budget for the assembled context.
            Default 32768 (generous for skill bodies 2K-20K).
        chars_per_token: Non-CJK characters per token for estimation.
            Default 4.
        system_prompt_protected: If True, system prompt is never trimmed.
            Default True.
        skill_body_budget_fraction: Max fraction of budget for skill bodies.
            Default 0.6.
        history_budget_fraction: Max fraction of budget for conversation history.
            Default 0.3.
        max_history_turns: Maximum number of history turns to retain.
            Default 20.
        trim_strategy: Name of the trim strategy.
            Default "protected_then_skill_then_history".
    """

    budget_tokens: int = 32768
    chars_per_token: int = 4
    system_prompt_protected: bool = True
    skill_body_budget_fraction: float = 0.6
    history_budget_fraction: float = 0.3
    max_history_turns: int = 20
    trim_strategy: str = "protected_then_skill_then_history"


@dataclass(frozen=True, slots=True)
class AgentContextResult:
    """Result of context assembly.

    Attributes:
        messages: Assembled message list (system + skill bodies + history
            + current turn).
        estimated_tokens: Total estimated token count of the assembled messages.
        dropped_sections: Dict recording what was trimmed (e.g.
            ``{"history_turns_dropped": 3}``).
        trimmed_skill_sections: List of dicts describing trimmed skill body
            sections, each with ``skill_index``, ``section_name``,
            ``priority``, ``original_tokens``, and ``reason``.
        protected_sections: Tuple of section names that were never trimmed.
    """

    messages: list[dict]
    estimated_tokens: int
    dropped_sections: JsonObject = field(default_factory=dict)
    trimmed_skill_sections: list[dict[str, Any]] = field(default_factory=list)
    protected_sections: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# AgentContextAssembler
# ---------------------------------------------------------------------------


class AgentContextAssembler:
    """Assemble context messages with history trim + skill body injection.

    Combines conversation history trimming (oldest-first) with skill body
    section-priority trimming under a total token budget.  Deterministic:
    same input + same budget → same output.

    Args:
        policy: Default policy for assembly.  Can be overridden per-call.
    """

    def __init__(self, policy: AgentContextPolicy | None = None) -> None:
        self.policy = policy or AgentContextPolicy()

    def assemble(
        self,
        *,
        system_prompt: str,
        skill_bodies: list[dict],
        history: list[dict],
        current_turn: dict,
        policy: AgentContextPolicy | None = None,
    ) -> AgentContextResult:
        """Assemble messages under a total token budget.

        Args:
            system_prompt: The system prompt string (always included first,
                protected from trimming).
            skill_bodies: List of skill body dicts, each with a ``"body"``
                key containing the SKILL.md text and optionally a
                ``"skill_id"`` key for identification.
            history: List of conversation history message dicts (each with
                ``"role"`` and ``"content"`` keys).
            current_turn: The current turn message dict (always included,
                protected from trimming).
            policy: Optional policy override.  If None, uses the assembler's
                default policy.

        Returns:
            An ``AgentContextResult`` with the assembled messages and trim
            reports.

        Raises:
            ContextAssemblyBudgetError: If protected sections alone exceed
                the budget.
        """
        cfg = policy or self.policy
        chars_per_token = max(1, int(cfg.chars_per_token))
        budget = cfg.budget_tokens
        skill_budget = int(budget * cfg.skill_body_budget_fraction)
        history_budget = int(budget * cfg.history_budget_fraction)

        protected_sections: list[str] = ["system_prompt", "current_turn"]
        dropped_sections: JsonObject = {}
        trimmed_skill_sections: list[dict[str, Any]] = []

        # 1. System prompt — always included, protected
        system_message = {"role": "system", "content": system_prompt}
        system_tokens = _estimate_message_tokens(system_message, chars_per_token)

        # 2. Current turn — always included, protected
        current_tokens = _estimate_message_tokens(current_turn, chars_per_token)

        # Check if protected sections alone exceed budget
        protected_tokens = system_tokens + current_tokens
        if protected_tokens > budget:
            raise ContextAssemblyBudgetError(
                f"protected sections (system_prompt + current_turn) require "
                f"{protected_tokens} estimated tokens, budget is {budget}"
            )

        # 3. Skill body injection — section-priority trim
        skill_messages: list[dict] = []
        skill_tokens_total = 0
        for idx, skill_body in enumerate(skill_bodies):
            body_text = skill_body.get("body", "")
            skill_id = skill_body.get("skill_id", f"skill_{idx}")

            trimmed_text, trimmed_secs = _trim_skill_body(
                body_text, skill_budget, chars_per_token
            )

            for ts in trimmed_secs:
                ts["skill_index"] = idx
                ts["skill_id"] = skill_id
                trimmed_skill_sections.append(ts)

            skill_msg = {"role": "system", "content": trimmed_text}
            skill_msg_tokens = _estimate_message_tokens(skill_msg, chars_per_token)
            skill_messages.append(skill_msg)
            skill_tokens_total += skill_msg_tokens

        # 4. Conversation history — truncate to max_history_turns, then oldest-first
        # Each "turn" is a pair of (user, assistant) messages, so we count
        # individual messages and truncate to max_history_turns * 2.
        max_history_messages = cfg.max_history_turns * 2
        truncated_history = list(history[-max_history_messages:])
        dropped_count = len(history) - len(truncated_history)
        if dropped_count > 0:
            dropped_sections["history_turns_truncated"] = dropped_count

        # Estimate history tokens
        history_tokens = sum(
            _estimate_message_tokens(msg, chars_per_token)
            for msg in truncated_history
        )

        # Drop oldest turns if over history budget
        while history_tokens > history_budget and truncated_history:
            dropped_msg = truncated_history.pop(0)
            msg_tokens = _estimate_message_tokens(dropped_msg, chars_per_token)
            history_tokens -= msg_tokens
            dropped_sections["history_turns_dropped"] = (
                int(dropped_sections.get("history_turns_dropped", 0)) + 1
            )

        # 5. Total budget check — trim history further, then skill bodies
        total_tokens = (
            system_tokens
            + skill_tokens_total
            + history_tokens
            + current_tokens
        )

        # Trim history further if over total budget
        while total_tokens > budget and truncated_history:
            dropped_msg = truncated_history.pop(0)
            msg_tokens = _estimate_message_tokens(dropped_msg, chars_per_token)
            history_tokens -= msg_tokens
            total_tokens -= msg_tokens
            dropped_sections["history_turns_dropped"] = (
                int(dropped_sections.get("history_turns_dropped", 0)) + 1
            )

        # Trim skill bodies (low priority first) if still over budget
        if total_tokens > budget and skill_messages:
            # Re-trim skill bodies by removing lowest-priority sections
            # We re-process each skill body with a smaller budget
            remaining_skill_budget = budget - system_tokens - history_tokens - current_tokens
            if remaining_skill_budget <= 0:
                remaining_skill_budget = 1  # minimum to avoid division issues

            skill_messages = []
            skill_tokens_total = 0
            # Re-trim all skill bodies with the remaining budget split evenly
            per_skill_budget = max(1, remaining_skill_budget // max(1, len(skill_bodies)))

            for idx, skill_body in enumerate(skill_bodies):
                body_text = skill_body.get("body", "")
                skill_id = skill_body.get("skill_id", f"skill_{idx}")

                # Use progressively smaller budget
                try:
                    trimmed_text, trimmed_secs = _trim_skill_body(
                        body_text, per_skill_budget, chars_per_token
                    )
                except ContextAssemblyBudgetError:
                    # Protected sections exceed even the reduced budget
                    # — include only frontmatter + description
                    frontmatter, raw_sections = _parse_sections(body_text)
                    protected_text_parts = [frontmatter] if frontmatter else []
                    for name, text in raw_sections:
                        is_desc = name == "__description__"
                        if is_desc or raw_sections.index((name, text)) == 1:
                            protected_text_parts.append(text)
                    trimmed_text = "\n".join(protected_text_parts)
                    trimmed_secs = [
                        {
                            "section_name": s.name,
                            "priority": _PRIORITY_NAMES.get(s.priority, "unknown"),
                            "original_tokens": s.token_estimate,
                            "reason": "total_budget_trim",
                            "skill_index": idx,
                            "skill_id": skill_id,
                        }
                        for s in _build_sections(frontmatter, raw_sections, chars_per_token)
                        if not s.is_protected
                    ]

                for ts in trimmed_secs:
                    ts["skill_index"] = idx
                    ts["skill_id"] = skill_id
                    ts["reason"] = ts.get("reason", "total_budget_trim")
                    # Avoid duplicating already-recorded trims
                    if not any(
                        existing.get("section_name") == ts.get("section_name")
                        and existing.get("skill_index") == ts.get("skill_index")
                        and existing.get("reason") == ts.get("reason")
                        for existing in trimmed_skill_sections
                    ):
                        trimmed_skill_sections.append(ts)

                skill_msg = {"role": "system", "content": trimmed_text}
                skill_msg_tokens = _estimate_message_tokens(skill_msg, chars_per_token)
                skill_messages.append(skill_msg)
                skill_tokens_total += skill_msg_tokens

            total_tokens = (
                system_tokens
                + skill_tokens_total
                + history_tokens
                + current_tokens
            )

        # 6. Assemble final message list
        messages: list[dict] = [system_message]
        messages.extend(skill_messages)
        messages.extend(truncated_history)
        messages.append(current_turn)

        return AgentContextResult(
            messages=messages,
            estimated_tokens=total_tokens,
            dropped_sections=dropped_sections,
            trimmed_skill_sections=trimmed_skill_sections,
            protected_sections=tuple(protected_sections),
        )


__all__ = [
    "AgentContextAssembler",
    "AgentContextPolicy",
    "AgentContextResult",
    "ContextAssemblyBudgetError",
]
