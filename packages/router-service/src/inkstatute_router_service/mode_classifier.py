"""ModeClassifierPort — Chat / Draft / Evidence three-mode detection.

Ported 1:1 from ``lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`` (691 lines).

Defines the core data structures for three-mode detection:

- ``AgentMode`` — StrEnum with values ``chat``, ``draft``, ``evidence``
  (lowercase, matching Rust ``#[serde(rename_all = "lowercase")]``).
- ``ClassifyContext`` — 7-field dataclass mirroring the Rust struct.
- ``ClassifyResult`` — 7-field dataclass mirroring the Rust struct.
- ``ModeClassifierPort`` — Protocol with ``classify(context) -> ClassifyResult``.

The ``AgentMode`` enum provides ``ui_label()`` returning the Chinese labels
("法律问答", "文书起草", "案情分析").

This module defines only the Protocol and data shapes — the actual LLM
call is host-injected, preserving the ``dependencies = []`` invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class AgentMode(StrEnum):
    """Three interaction modes for the agent.

    Values are lowercase to match the Rust ``#[serde(rename_all = "lowercase")]``.
    """

    CHAT = "chat"       # 法律问答
    DRAFT = "draft"      # 文书起草
    EVIDENCE = "evidence"  # 案情分析

    def ui_label(self) -> str:
        """Return the Chinese UI label for this mode."""
        if self is AgentMode.CHAT:
            return "法律问答"
        if self is AgentMode.DRAFT:
            return "文书起草"
        return "案情分析"

    def is_evidence(self) -> bool:
        """Return True if this mode is Evidence."""
        return self is AgentMode.EVIDENCE


@dataclass
class ClassifyContext:
    """Context for mode classification — mirrors Rust ``ClassifyContext``.

    Fields (same 7 as Rust struct):
    - ``user_message`` — the user's message text
    - ``has_directory_ref`` — whether user attached a case directory
    - ``has_file_ref`` — whether user attached a file
    - ``directory_aliases`` — alias names for attached directories
    - ``current_mode`` — mode of the committed task ("draft"/"evidence") or None
    - ``current_task_label`` — human label of committed task
    - ``has_active_document`` — whether a document/report already exists
    """

    user_message: str
    has_directory_ref: bool = False
    has_file_ref: bool = False
    directory_aliases: list[str] = field(default_factory=list)
    current_mode: str | None = None
    current_task_label: str | None = None
    has_active_document: bool = False


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    """Result of mode classification — mirrors Rust ``ClassifyResult``.

    Fields (same 7 as Rust struct):
    - ``mode`` — AgentMode (Chat / Draft / Evidence)
    - ``label`` — short Chinese task label
    - ``reason`` — one-sentence reason
    - ``action`` — "continue" | "switch" | "aside"
    - ``source`` — "llm" | "fallback"
    - ``fallback_reason`` — error category when fallback used (or None)
    - ``diagnostic`` — error detail (or None)
    """

    mode: AgentMode
    label: str
    reason: str
    action: str
    source: str
    fallback_reason: str | None = None
    diagnostic: str | None = None


class ModeClassifierPort(Protocol):
    """Protocol for injectable mode classifiers.

    Implementations must be stateless and side-effect free.  When no
    classifier is injected (``None``), mode detection is skipped and
    no mode-related metadata is added to ``RouteDecision``.
    """

    def classify(self, context: ClassifyContext) -> ClassifyResult:
        """Classify *context* and return mode + action + label + reason."""
        ...


__all__ = [
    "AgentMode",
    "ClassifyContext",
    "ClassifyResult",
    "ModeClassifierPort",
]
