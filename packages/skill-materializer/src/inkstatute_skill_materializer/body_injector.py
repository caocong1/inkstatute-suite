"""Skill body injector — budget-constrained body injection.

Parses SKILL.md into sections, assigns priorities, and trims from lowest
priority to fit within a token budget. Produces a trim report for
observability.

The injector uses a CJK-aware token estimation heuristic:

    token_estimate = (CJK_character_count * 1.0) + (non_CJK_character_count // 4)

This is an estimate for routing and context budget purposes, not an exact
count. It matches the heuristic used by ``inkstatute_skill_index``.

Section priority assignment:
- **Protected** (never trimmed): frontmatter + description + first ``##`` section
- **High**: sections containing "research-gate" or "ask-user" in the header
- **Low**: sections containing "example", "appendix", or "reference" in the header
- **Medium**: all other sections

Trim algorithm:
1. Parse SKILL.md into sections by ``## `` headers
2. Assign priorities
3. While ``injected_token_estimate > budget_tokens``:
   - Remove the lowest-priority section with the most tokens
   - Record in ``trimmed_sections``
   - Re-estimate
4. If protected sections alone exceed budget, raise ``SkillBodyBudgetError``

Deterministic: same input + same budget → same output (no random, no LLM).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Token estimation (CJK-aware heuristic, matching skill-index)
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


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SkillBodyBudgetError(ValueError):
    """Raised when protected sections alone exceed the configured budget."""


class SkillNotFoundError(KeyError):
    """Raised when a skill_id is not found in the index."""


class SourceFileNotFoundError(FileNotFoundError):
    """Raised when the SKILL.md file does not exist at the resolved path."""


# ---------------------------------------------------------------------------
# Section model
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
    """A parsed section of a SKILL.md body."""

    name: str
    text: str
    priority: int
    token_estimate: int
    is_protected: bool = False


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillBodyInjectionResult:
    """Result of a skill body injection with budget trimming.

    Attributes:
        injected_text: The trimmed body text (may equal original if no trim needed).
        original_token_estimate: Token count of the full body before trimming.
        injected_token_estimate: Token count of the trimmed body.
        trimmed_sections: List of dicts describing trimmed sections, each with
            ``section_name``, ``priority``, ``original_tokens``, and ``reason``.
        budget_used: Tokens consumed by the injected text.
        budget_tokens: The configured budget.
    """

    injected_text: str
    original_token_estimate: int
    injected_token_estimate: int
    trimmed_sections: list[dict[str, Any]] = field(default_factory=list)
    budget_used: int = 0
    budget_tokens: int = 0


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_H2_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Keywords for priority assignment
_HIGH_KEYWORDS = ("research-gate", "ask-user")
_LOW_KEYWORDS = ("example", "appendix", "reference")


def _parse_sections(skill_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse SKILL.md into frontmatter and section list.

    Returns:
        A tuple of (frontmatter_text, sections) where sections is a list of
        (header_name, section_text) pairs. The frontmatter_text includes the
        ``---`` fences. The description (text before the first ``##`` header
        but after frontmatter) is included as the first section with name
        "__description__".
    """
    # Extract frontmatter
    fm_match = _FRONTMATTER_RE.match(skill_text)
    if fm_match:
        frontmatter = skill_text[: fm_match.end()]
        remaining = skill_text[fm_match.end():]
    else:
        frontmatter = ""
        remaining = skill_text

    # Split remaining by ## headers
    # Find all ## header positions
    h2_positions: list[tuple[int, str]] = []
    for match in _H2_HEADER_RE.finditer(remaining):
        h2_positions.append((match.start(), match.group(1).strip()))

    sections: list[tuple[str, str]] = []

    # Text before the first ## header is the description section
    if h2_positions:
        first_pos = h2_positions[0][0]
        desc_text = remaining[:first_pos].strip()
        if desc_text:
            sections.append(("__description__", desc_text + "\n"))
    else:
        # No ## headers at all — entire remaining is description
        desc_text = remaining.strip()
        if desc_text:
            sections.append(("__description__", desc_text + "\n"))

    # Extract each ## section
    for i, (pos, header_name) in enumerate(h2_positions):
        if i + 1 < len(h2_positions):
            section_text = remaining[pos : h2_positions[i + 1][0]]
        else:
            section_text = remaining[pos:]
        sections.append((header_name, section_text))

    return frontmatter, sections


def _assign_priority(
    section_name: str,
    section_text: str,
    index: int,
    is_description: bool,
) -> int:
    """Assign a priority level to a section.

    Priority assignment rules:
    - Protected: description (index 0) + first ``##`` section (index 1)
    - High: sections containing "research-gate" or "ask-user" in header
    - Low: sections containing "example", "appendix", or "reference" in header
    - Medium: all others
    """
    # Protected: description and first ## section
    if is_description:
        return _PRIORITY_PROTECTED
    if index == 1:  # First ## section is protected
        return _PRIORITY_PROTECTED

    name_lower = section_name.lower()

    # High priority: gate sections
    for keyword in _HIGH_KEYWORDS:
        if keyword in name_lower:
            return _PRIORITY_HIGH

    # Low priority: examples, appendices, references
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
        priority = _assign_priority(name, text, i, is_description)

        # For the description section, include frontmatter in token estimate
        # (frontmatter is always protected and part of the description block)
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


# ---------------------------------------------------------------------------
# SkillBodyInjector
# ---------------------------------------------------------------------------


class SkillBodyInjector:
    """Budget-constrained skill body injection with section-priority trim.

    Parses SKILL.md into sections, assigns priorities, and trims from
    lowest priority to fit within a token budget.

    Args:
        budget_tokens: Maximum token budget for the injected body.
        chars_per_token: Non-CJK characters per token (default: 4).
    """

    def __init__(self, budget_tokens: int = 2048, chars_per_token: int = 4) -> None:
        if budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self.budget_tokens = budget_tokens
        self.chars_per_token = chars_per_token

    def inject(self, skill_body_text: str) -> SkillBodyInjectionResult:
        """Inject a skill body with budget-constrained trimming.

        Args:
            skill_body_text: The full SKILL.md text (including frontmatter).

        Returns:
            A ``SkillBodyInjectionResult`` with the trimmed body and trim report.
        """
        return self._inject_with_budget(skill_body_text, self.budget_tokens)

    def _inject_with_budget(
        self,
        skill_text: str,
        budget_tokens: int,
    ) -> SkillBodyInjectionResult:
        """Core trim algorithm."""
        # Parse into frontmatter + sections
        frontmatter, raw_sections = _parse_sections(skill_text)

        # Build section objects with priorities and token estimates
        sections = _build_sections(frontmatter, raw_sections, self.chars_per_token)

        # Calculate original token estimate (full body)
        original_tokens = _estimate_tokens(skill_text, self.chars_per_token)

        # Check if protected sections alone exceed budget
        protected_tokens = sum(s.token_estimate for s in sections if s.is_protected)
        if protected_tokens > budget_tokens:
            raise SkillBodyBudgetError(
                f"protected sections require {protected_tokens} estimated tokens, "
                f"budget is {budget_tokens}"
            )

        # Trim from lowest priority until under budget
        # Work on a mutable list of active sections
        active_sections: list[_Section] = list(sections)
        trimmed_sections: list[dict[str, Any]] = []

        current_tokens = original_tokens

        while current_tokens > budget_tokens:
            # Find the lowest-priority section with the most tokens
            # among non-protected active sections
            candidates = [
                s for s in active_sections if not s.is_protected
            ]
            if not candidates:
                # No more trimmable sections — protected exceed budget
                # (already checked above, but just in case)
                break

            # Sort by priority (descending = lowest priority first),
            # then by token_estimate (descending = most tokens first)
            candidates.sort(
                key=lambda s: (-s.priority, -s.token_estimate)
            )
            section_to_trim = candidates[0]

            # Record the trim
            trimmed_sections.append(
                {
                    "section_name": section_to_trim.name,
                    "priority": _PRIORITY_NAMES.get(
                        section_to_trim.priority, "unknown"
                    ),
                    "original_tokens": section_to_trim.token_estimate,
                    "reason": "budget_trim",
                }
            )

            # Remove from active sections
            active_sections.remove(section_to_trim)
            current_tokens -= section_to_trim.token_estimate

        # Reconstruct the injected text
        if not trimmed_sections:
            # No trimming needed — return original text unchanged
            injected_text = skill_text
        else:
            # Rebuild from frontmatter + active sections in original order
            injected_parts: list[str] = []
            if frontmatter:
                injected_parts.append(frontmatter)

            for section in active_sections:
                injected_parts.append(section.text)

            injected_text = "\n".join(injected_parts)

        # Recalculate to be precise
        injected_tokens = _estimate_tokens(injected_text, self.chars_per_token)

        return SkillBodyInjectionResult(
            injected_text=injected_text,
            original_token_estimate=original_tokens,
            injected_token_estimate=injected_tokens,
            trimmed_sections=trimmed_sections,
            budget_used=injected_tokens,
            budget_tokens=budget_tokens,
        )


# ---------------------------------------------------------------------------
# On-demand body reading API (for self-built core path)
# ---------------------------------------------------------------------------


def _load_index_for_read(index_path: str | Path) -> dict[str, Any]:
    """Load a skill-index.json file and return the parsed dict."""
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"skill-index.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_source_path(
    record: dict[str, Any],
    repos: dict[str, dict[str, Any]],
) -> str:
    """Resolve the absolute path to the SKILL.md file.

    Uses ``repos[record["source_repo"]]["path"]`` + ``record["relative_path"]``
    to construct the absolute path to the SKILL.md file.
    """
    repo_name = record["source_repo"]
    repo_info = repos.get(repo_name)
    if repo_info is None:
        raise KeyError(f"Repo '{repo_name}' not found in index repos metadata")
    repo_path = Path(repo_info["path"])
    relative_path = Path(record["relative_path"])
    skill_file = repo_path / relative_path
    return str(skill_file)


def read_skill_body(
    skill_id: str,
    index_path: str | Path,
    budget_tokens: int,
    chars_per_token: int = 4,
) -> SkillBodyInjectionResult:
    """Read a skill body on-demand from the source repo and apply budget trimming.

    This is the API the self-built core (Phase 100+) uses for on-demand
    body injection. It reads the skill-index.json, finds the record by
    ``skill_id``, resolves the source path, reads the SKILL.md, and
    applies ``SkillBodyInjector.inject()``.

    No materialization step is needed — the core reads the index directly
    and reads bodies on-demand from source repos (read-only).

    Args:
        skill_id: The skill ID to look up in the index.
        index_path: Path to ``skill-index.json``.
        budget_tokens: Maximum token budget for the injected body.
        chars_per_token: Non-CJK characters per token (default: 4).

    Returns:
        A ``SkillBodyInjectionResult`` with the trimmed body and trim report.

    Raises:
        SkillNotFoundError: If ``skill_id`` is not in the index.
        SourceFileNotFoundError: If the SKILL.md file does not exist at the
            resolved path.
    """
    # Load index (read-only)
    index_data = _load_index_for_read(index_path)
    repos = index_data.get("repos", {})
    skills = index_data.get("skills", [])

    # Find the record by skill_id
    record: dict[str, Any] | None = None
    for s in skills:
        if s.get("skill_id") == skill_id:
            record = s
            break

    if record is None:
        raise SkillNotFoundError(
            f"Skill '{skill_id}' not found in index: {index_path}"
        )

    # Resolve source path
    source_path = _resolve_source_path(record, repos)

    # Read the SKILL.md (read-only)
    skill_file = Path(source_path)
    if not skill_file.exists():
        raise SourceFileNotFoundError(
            f"SKILL.md not found at resolved path: {source_path}"
        )

    skill_text = skill_file.read_text(encoding="utf-8")

    # Apply budget trimming
    injector = SkillBodyInjector(
        budget_tokens=budget_tokens,
        chars_per_token=chars_per_token,
    )
    return injector.inject(skill_text)
