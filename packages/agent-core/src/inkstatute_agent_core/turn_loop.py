"""Async turn loop — always-streaming, tool-call events, heartbeat.

This is the heart of Phase 100 — the fix for the "整轮静默" (whole-round
silence) defect.  The ``run_turn()`` async generator:

1. **Always streams** — uses ``provider.chat_stream()`` for every round,
   even during tool rounds.  The Rust original used ``stream: false``
   during tool rounds, causing complete event silence.

2. **Emits tool call events** — ``tool_call.started`` before execution,
   ``tool_call.delta`` during, ``tool_call.completed`` after.  The Rust
   original only emitted trace events (not unified events) during tools.

3. **Emits thought.delta heartbeats** — via ``emitter.maybe_heartbeat()``
   before LLM calls and during tool execution, ensuring no silence gap
   exceeds the threshold.

4. **Enforces turn limit** — ``config.max_turns`` (default 10).  When
   exceeded, emits ``error`` with ``turn_limit_exceeded`` and
   ``run.state_changed`` to ``"failed"``.

5. **Handles error recovery** — tool execution exceptions are caught and
   emitted as ``tool_call.completed`` with ``status="error"`` and
   ``ErrorInfo``.  The error is appended as a tool result message and the
   loop continues — the LLM can see the error and decide to retry or
   produce a final answer.

The turn loop yields ``RunEvent`` objects (Phase 88 unified events).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo, RunEvent

from .config import AgentCoreConfig
from .event_emitter import EventEmitter
from .model.provider import (
    ChatRequest,
    ContentDelta,
    FinishDelta,
    LlmProvider,
    ReasoningDelta,
    ToolCallDelta,
    UsageAccumulator,
    UsageDelta,
)

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# ToolResult dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result of a tool execution.

    Attributes:
        content: Tool result content string.
        error: ErrorInfo if the tool failed, None if succeeded.
        metadata: Optional metadata dict.
    """

    content: str
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


# Type alias for the tool executor callable
ToolExecutor = Callable[[str, str, dict], Awaitable[ToolResult]]


# ---------------------------------------------------------------------------
# run_turn — the async generator turn loop
# ---------------------------------------------------------------------------


async def run_turn(
    *,
    messages: list[dict],
    tools: list[dict] | None,
    provider: LlmProvider,
    emitter: EventEmitter,
    config: AgentCoreConfig,
    tool_executor: ToolExecutor | None = None,
    run_id: str,
    phase: str = "research",
) -> AsyncIterator[RunEvent]:
    """Run the async streaming turn loop.

    This is an async generator that yields ``RunEvent`` objects.  It
    always streams the LLM response (even during tool rounds), emits
    tool call events, enforces the turn limit, and handles error recovery.

    Args:
        messages: Initial message list (system + history + current turn).
        tools: Optional list of tool definitions (OpenAI format).
        provider: The LLM provider (implements ``LlmProvider`` Protocol).
        emitter: EventEmitter for constructing and numbering events.
        config: AgentCoreConfig with max_turns, temperature, etc.
        tool_executor: Optional callable ``(tool_call_id, tool_name,
            arguments) -> ToolResult``.  If None, a fixture result is
            produced (Phase 100 skeleton — no real tools yet).
        run_id: The run identifier for all emitted events.
        phase: Phase name to emit at the start of each round.
            Default ``"research"``.

    Yields:
        ``RunEvent`` objects with monotonic seq numbers.
    """
    # Work on a mutable copy of messages
    current_messages = list(messages)
    previous_phase: str | None = None

    for _round in range(config.max_turns):
        # 1. Emit phase_changed
        yield emitter.emit_phase_changed(phase, previous_phase=previous_phase)
        previous_phase = phase

        # 2. Pre-LLM thought
        yield emitter.emit_thought_delta("正在分析...")

        # 3. Heartbeat check before LLM call
        heartbeat = emitter.maybe_heartbeat("正在与模型通信...")
        if heartbeat is not None:
            yield heartbeat

        # 4. Build ChatRequest
        request = ChatRequest(
            messages=current_messages,
            tools=tools,
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            stream=True,
        )

        # 5. Stream LLM response
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_call_deltas: list[ToolCallDelta] = []
        usage_accumulator = UsageAccumulator()
        finish_reason: str | None = None

        try:
            async for delta in provider.chat_stream(request):
                if isinstance(delta, ContentDelta):
                    content_parts.append(delta.content)
                    yield emitter.emit_message_delta(delta.content)
                elif isinstance(delta, ReasoningDelta):
                    reasoning_parts.append(delta.reasoning)
                    yield emitter.emit_thought_delta(delta.reasoning)
                elif isinstance(delta, ToolCallDelta):
                    tool_call_deltas.append(delta)
                elif isinstance(delta, UsageDelta):
                    usage_accumulator.add(delta)
                elif isinstance(delta, FinishDelta):
                    finish_reason = delta.finish_reason
        except Exception as exc:
            # Provider error — emit error + run.state_changed to failed
            error_info = ErrorInfo(
                category=ErrorCategory.RUNTIME_ERROR,
                code="provider_error",
                message=str(exc),
                retryable=False,
            )
            yield emitter.emit_error(error_info)
            yield emitter.emit_run_state_changed(
                "failed",
                error=error_info,
                metadata={"provider_usage": usage_accumulator.to_dict()},
            )
            return

        # 6. Check accumulated tool calls
        if tool_call_deltas:
            # Build assistant message with tool calls and append to history
            assistant_msg = _build_assistant_message_with_tool_calls(
                content="".join(content_parts),
                tool_call_deltas=tool_call_deltas,
            )
            current_messages.append(assistant_msg)

            # Track whether any tool requested turn termination
            should_terminate = False

            # Execute each tool call
            for tc_delta in tool_call_deltas:
                # a. tool_call.started
                yield emitter.emit_tool_call_started(
                    tc_delta.tool_call_id,
                    tc_delta.tool_name,
                )

                # b. Heartbeat check during tool execution
                heartbeat = emitter.maybe_heartbeat("正在执行工具...")
                if heartbeat is not None:
                    yield heartbeat

                # c. Execute tool
                try:
                    if tool_executor is not None:
                        # Parse arguments from JSON string
                        import json
                        try:
                            args_dict = json.loads(tc_delta.arguments) if tc_delta.arguments else {}
                        except (json.JSONDecodeError, TypeError):
                            args_dict = {}

                        result = await tool_executor(
                            tc_delta.tool_call_id,
                            tc_delta.tool_name,
                            args_dict,
                        )

                        # Drain side-channel events emitted by the tool
                        # handler (e.g. elicitation.requested, artifact.created)
                        # and yield them before tool_call.completed.
                        for side_event in emitter.drain_side_channel_events():
                            yield side_event

                        if result.error is not None:
                            # Tool returned an error
                            yield emitter.emit_tool_call_completed(
                                tc_delta.tool_call_id,
                                status="error",
                                error=result.error,
                                content=result.content,
                            )
                            # Append error as tool result
                            current_messages.append(
                                _build_tool_result_message(
                                    tc_delta.tool_call_id,
                                    f"Error: {result.content}",
                                    is_error=True,
                                )
                            )
                        else:
                            # Tool succeeded
                            yield emitter.emit_tool_call_delta(
                                tc_delta.tool_call_id,
                                content="执行完成",
                            )
                            yield emitter.emit_tool_call_completed(
                                tc_delta.tool_call_id,
                                status="succeeded",
                                content=result.content,
                            )
                            current_messages.append(
                                _build_tool_result_message(
                                    tc_delta.tool_call_id,
                                    result.content,
                                )
                            )

                            # Check terminate_turn metadata — a tool can
                            # signal that the current turn should stop
                            # (e.g. clarification/ask_user tool).
                            if result.metadata.get("terminate_turn"):
                                should_terminate = True
                    else:
                        # Phase 100 skeleton — no real tools yet
                        yield emitter.emit_tool_call_delta(
                            tc_delta.tool_call_id,
                            content="执行完成",
                        )
                        yield emitter.emit_tool_call_completed(
                            tc_delta.tool_call_id,
                            status="succeeded",
                            content="[fixture tool result]",
                        )
                        current_messages.append(
                            _build_tool_result_message(
                                tc_delta.tool_call_id,
                                "[fixture tool result]",
                            )
                        )
                except Exception as exc:
                    # Tool execution exception — error recovery
                    error_info = ErrorInfo(
                        category=ErrorCategory.RUNTIME_ERROR,
                        code="tool_execution_error",
                        message=str(exc),
                        retryable=True,
                    )
                    yield emitter.emit_tool_call_completed(
                        tc_delta.tool_call_id,
                        status="error",
                        error=error_info,
                    )
                    # Append error as tool result — loop continues
                    current_messages.append(
                        _build_tool_result_message(
                            tc_delta.tool_call_id,
                            f"Error: {exc}",
                            is_error=True,
                        )
                    )

            # d. Check if any tool requested turn termination
            if should_terminate:
                # A tool (e.g. ask_user) signaled terminate_turn —
                # emit run.state_changed to waiting_for_user and return.
                yield emitter.emit_run_state_changed("waiting_for_user")
                return

            # e. Transition thought
            yield emitter.emit_thought_delta("工具执行完成，正在整合结果...")

            # f. Continue to next round
            continue

        # 7. No tool calls — final content round
        full_content = "".join(content_parts)
        usage_dict = usage_accumulator.to_dict()

        yield emitter.emit_message_completed(
            full_content,
            metadata={"provider_usage": usage_dict},
        )
        yield emitter.emit_run_state_changed(
            "succeeded",
            metadata={"provider_usage": usage_dict},
        )
        return

    # 8. Turn limit reached
    error_info = ErrorInfo(
        category=ErrorCategory.RUNTIME_ERROR,
        code="turn_limit_exceeded",
        message="达到最大轮次上限",
    )
    yield emitter.emit_error(error_info)
    yield emitter.emit_run_state_changed("failed", error=error_info)


# ---------------------------------------------------------------------------
# Internal message building helpers
# ---------------------------------------------------------------------------


def _build_tool_result_message(
    tool_call_id: str,
    content: str,
    is_error: bool = False,
) -> dict:
    """Build a tool result message dict.

    If ``is_error`` is True, the content is prefixed with ``"Error: "``.
    """
    if is_error and not content.startswith("Error: "):
        content = f"Error: {content}"
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def _build_assistant_message_with_tool_calls(
    content: str,
    tool_call_deltas: list[ToolCallDelta],
) -> dict:
    """Build an assistant message with tool calls for appending to history."""
    tool_calls = []
    for tc in tool_call_deltas:
        tool_calls.append({
            "id": tc.tool_call_id,
            "type": "function",
            "function": {
                "name": tc.tool_name,
                "arguments": tc.arguments,
            },
        })
    return {
        "role": "assistant",
        "content": content if content else None,
        "tool_calls": tool_calls,
    }


__all__ = [
    "run_turn",
    "ToolResult",
    "ToolExecutor",
]
