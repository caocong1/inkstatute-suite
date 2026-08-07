"""Clarification (ask_user) tool — emits elicitation.requested and terminates the turn.

The clarification tool is special — it **terminates the current turn** (matching
Rust ``finish_ask_user_turn()``).  When the LLM calls the ``ask_user`` tool:

1. The handler parses ``intro`` and ``questions`` from the arguments dict.
2. Questions are parsed into ``ElicitationQuestion`` objects (each option is
   ``ElicitationOption(label, value)``).
3. Questions are validated to be 2-4 items (via ``validate_question_count()``).
4. Empty ``id`` fields are auto-assigned as ``q1``, ``q2``, etc.
5. Empty ``value`` fields are auto-filled from ``label``.
6. If no options on a question, it's free-text (empty options list).
7. An ``interrupt_id`` (UUID) is generated.
8. ``elicitation.requested`` is emitted via the EventEmitter.
9. A ``ToolResult`` with ``metadata={"terminate_turn": True, "elicitation_id": ...}``
   is returned — the turn loop checks this and stops.

Since ``ToolHandler`` signature is ``Callable[[dict], Awaitable[ToolResult]]``
(no emitter access), the clarification tool is constructed as a **factory
function** that captures the emitter: ``create_clarification_tool(emitter) -> ToolHandler``.
"""

from __future__ import annotations

import uuid
from typing import Any

from platform_contract.elicitation import validate_question_count
from platform_contract.unified_events import (
    ElicitationOption,
    ElicitationQuestion,
)

from ..event_emitter import EventEmitter
from ..turn_loop import ToolResult

JsonObject = dict[str, Any]

# OpenAI function-calling tool definition for the clarification tool.
CLARIFICATION_TOOL_DEFINITION: dict = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "向用户提出澄清问题（2-4题，单选/多选/自由文本）。"
            "调用此工具会暂停当前对话轮次，等待用户回答后继续。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intro": {
                    "type": "string",
                    "description": "澄清问题的引导语",
                },
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "问题ID（可为空，自动分配）",
                            },
                            "question": {
                                "type": "string",
                                "description": "问题文本",
                            },
                            "allow_multiple": {
                                "type": "boolean",
                                "description": "是否允许多选",
                            },
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                },
                            },
                        },
                        "required": ["question"],
                    },
                    "minItems": 2,
                    "maxItems": 4,
                },
            },
            "required": ["intro", "questions"],
        },
    },
}


def _parse_questions(raw_questions: list[dict]) -> list[ElicitationQuestion]:
    """Parse raw question dicts into ``ElicitationQuestion`` objects.

    - Auto-assigns ``q1``, ``q2``, etc. if ``id`` is empty or missing.
    - Auto-fills ``value`` from ``label`` if ``value`` is empty or missing.
    - Questions with no options are free-text (empty options list).
    """
    parsed: list[ElicitationQuestion] = []
    for idx, raw in enumerate(raw_questions, start=1):
        qid = raw.get("id") or raw.get("id", "")
        if not qid:
            qid = f"q{idx}"

        question_text = raw.get("question", "")
        allow_multiple = raw.get("allow_multiple", False)

        raw_options = raw.get("options", [])
        options: list[ElicitationOption] = []
        for opt in raw_options:
            label = opt.get("label", "")
            value = opt.get("value", "")
            if not value:
                value = label
            options.append(ElicitationOption(label=label, value=value))

        parsed.append(
            ElicitationQuestion(
                id=qid,
                question=question_text,
                allow_multiple=allow_multiple,
                options=options,
            )
        )
    return parsed


def create_clarification_tool(emitter: EventEmitter):
    """Create a clarification (ask_user) tool handler bound to an EventEmitter.

    The returned handler is a ``ToolHandler`` — ``Callable[[dict], Awaitable[ToolResult]]``.
    It parses the arguments, validates question count, emits
    ``elicitation.requested``, and returns a ``ToolResult`` with
    ``metadata={"terminate_turn": True, "elicitation_id": ...}``.

    Args:
        emitter: The ``EventEmitter`` to use for emitting ``elicitation.requested``.

    Returns:
        An async callable ``(arguments: dict) -> ToolResult``.
    """

    async def clarification_handler(arguments: dict) -> ToolResult:
        intro = arguments.get("intro", "")
        raw_questions = arguments.get("questions", [])

        # Parse questions into ElicitationQuestion objects
        questions = _parse_questions(raw_questions)

        # Validate 2-4 questions
        try:
            validate_question_count(questions)
        except ValueError as exc:
            return ToolResult(
                content=f"澄清问题数量不符合要求: {exc}",
                error=None,
                metadata={"terminate_turn": False, "validation_error": True},
            )

        # Generate interrupt_id
        interrupt_id = str(uuid.uuid4())

        # Emit elicitation.requested
        emitter.emit_elicitation_requested(
            interrupt_id=interrupt_id,
            intro=intro,
            questions=questions,
        )

        # Return ToolResult with terminate_turn metadata
        return ToolResult(
            content=f"已向用户提出澄清问题 (interrupt_id={interrupt_id})",
            metadata={
                "terminate_turn": True,
                "elicitation_id": interrupt_id,
            },
        )

    return clarification_handler


__all__ = [
    "create_clarification_tool",
    "CLARIFICATION_TOOL_DEFINITION",
]
