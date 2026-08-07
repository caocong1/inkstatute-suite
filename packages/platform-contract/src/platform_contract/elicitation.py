"""Elicitation contract — ask-user protocol and RunInterrupt interconversion.

Implements the clarification question contract matching
``ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md``
(2-4 questions, single-select / multi-select / free-text, ``allow_multiple``
field) and bidirectional conversion functions between
:class:`~platform_contract.unified_events.ElicitationRequestedPayload` and
V2 :class:`~platform_contract.events.RunInterrupt`.

Reference-first principle (AGENTS.md): ``prompt_ref`` is a reference string
(``elicitation://<interrupt_id>``), not the full intro/questions text.  The
full question structure is stored in ``RunInterrupt.metadata`` for round-trip
fidelity.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .enums import InterruptStatus
from .events import RunInterrupt
from .unified_events import (
    ElicitationOption,
    ElicitationQuestion,
    ElicitationRequestedPayload,
)

__all__ = [
    "elicitation_to_run_interrupt",
    "run_interrupt_to_elicitation",
    "validate_question_count",
    "format_answer_display",
]

# Schema ref for the standalone elicitation_question schema (Task 88-03-01).
_ELICITATION_QUESTION_SCHEMA_REF = (
    "https://inkstatute.dev/schemas/platform-contract/"
    "elicitation_question.schema.json"
)


def elicitation_to_run_interrupt(
    payload: ElicitationRequestedPayload,
    run_id: str,
    session_id: str,
    created_at: str,
) -> RunInterrupt:
    """Convert an :class:`ElicitationRequestedPayload` to a :class:`RunInterrupt`.

    Field mapping:
    - ``interrupt_id`` ← ``payload.interrupt_id``
    - ``run_id`` / ``session_id`` / ``created_at`` ← caller parameters
    - ``status`` ← :attr:`InterruptStatus.WAITING_FOR_USER`
    - ``reason`` ← ``"clarification"``
    - ``prompt_ref`` ← ``"elicitation://<interrupt_id>"`` (reference-first)
    - ``resume_state_ref`` ← ``payload.resume_state_ref`` (or ``""`` if None)
    - ``expected_response_schema_ref`` ← elicitation_question schema URL
    - ``expires_at`` ← ``payload.expires_at``
    - ``metadata`` ← ``{"intro": ..., "questions": [...], **payload.metadata}``
    """
    questions_serialized = [dataclasses.asdict(q) for q in payload.questions]
    metadata: dict[str, Any] = {
        "intro": payload.intro,
        "questions": questions_serialized,
    }
    # Merge caller-supplied metadata (does not overwrite intro/questions).
    for key, value in payload.metadata.items():
        if key not in ("intro", "questions"):
            metadata[key] = value

    return RunInterrupt(
        interrupt_id=payload.interrupt_id,
        run_id=run_id,
        session_id=session_id,
        status=InterruptStatus.WAITING_FOR_USER,
        reason="clarification",
        created_at=created_at,
        prompt_ref=f"elicitation://{payload.interrupt_id}",
        resume_state_ref=payload.resume_state_ref or "",
        expected_response_schema_ref=_ELICITATION_QUESTION_SCHEMA_REF,
        expires_at=payload.expires_at,
        resolved_at=None,
        resolved_turn_id=None,
        metadata=metadata,
    )


def run_interrupt_to_elicitation(
    interrupt: RunInterrupt,
) -> ElicitationRequestedPayload:
    """Convert a :class:`RunInterrupt` back to an :class:`ElicitationRequestedPayload`.

    Reconstructs ``intro`` and ``questions`` from ``interrupt.metadata``.
    Remaining metadata keys (excluding ``intro`` and ``questions``) are
    preserved in the returned payload's ``metadata``.
    """
    raw_questions = interrupt.metadata.get("questions", [])
    questions: list[ElicitationQuestion] = []
    for raw in raw_questions:
        options = [
            ElicitationOption(label=opt["label"], value=opt["value"])
            for opt in raw.get("options", [])
        ]
        questions.append(
            ElicitationQuestion(
                id=raw["id"],
                question=raw["question"],
                allow_multiple=raw.get("allow_multiple", False),
                options=options,
            )
        )

    remaining_metadata = {
        k: v
        for k, v in interrupt.metadata.items()
        if k not in ("intro", "questions")
    }

    return ElicitationRequestedPayload(
        interrupt_id=interrupt.interrupt_id,
        intro=interrupt.metadata.get("intro", ""),
        questions=questions,
        resume_state_ref=interrupt.resume_state_ref or None,
        expires_at=interrupt.expires_at,
        metadata=remaining_metadata,
    )


def validate_question_count(questions: list[ElicitationQuestion]) -> None:
    """Raise ``ValueError`` if *questions* is not 2-4 items long.

    Enforces the 2-4 question constraint from ASK-USER-PROTOCOL.md.
    """
    count = len(questions)
    if count < 2:
        raise ValueError(
            f"Elicitation requires at least 2 questions, got {count}."
        )
    if count > 4:
        raise ValueError(
            f"Elicitation allows at most 4 questions, got {count}."
        )


def format_answer_display(
    questions: list[ElicitationQuestion],
    answers: dict[str, str],
) -> str:
    """Format answer display text per ASK-USER-PROTOCOL.md.

    Produces a numbered list with question text and answer:
    - **Single-select** (``allow_multiple=False`` with options): display the
      label for the selected value.
    - **Multi-select** (``allow_multiple=True`` with options): answer values
      are joined by ``|``; display Chinese labels joined by ``、``.
    - **Free-text** (no options): display the raw answer string.

    Example output::

        1. 贵方在本交易中是甲方还是乙方？
        回答：甲方

        2. 本次涉及哪类合同？
        回答：租赁合同、买卖合同
    """
    lines: list[str] = []
    for idx, question in enumerate(questions, start=1):
        raw_answer = answers.get(question.id, "")
        if question.options:
            value_to_label = {opt.value: opt.label for opt in question.options}
            if question.allow_multiple:
                selected_values = [
                    v for v in raw_answer.split("|") if v
                ]
                labels = [
                    value_to_label.get(v, v) for v in selected_values
                ]
                display = "、".join(labels)
            else:
                display = value_to_label.get(raw_answer, raw_answer)
        else:
            # Free-text question — show raw answer.
            display = raw_answer
        lines.append(f"{idx}. {question.question}")
        lines.append(f"回答：{display}")
        lines.append("")
    # Strip trailing empty line.
    return "\n".join(lines).rstrip() + "\n"
