"""Shared turn script fixtures for e2e integration tests.

These fixtures provide pre-configured ``TurnScript`` lists that simulate
realistic multi-turn tool orchestration scenarios without external LLM
calls.  They are used by the e2e test files (``test_e2e_turn_orchestration``,
``test_silence_threshold``, ``test_e2e_error_recovery``).
"""

from __future__ import annotations

from inkstatute_agent_core.fixtures import TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ReasoningDelta,
    ToolCallDelta,
    UsageDelta,
)


# ---------------------------------------------------------------------------
# Legal research scenario — 2 tool rounds
# ---------------------------------------------------------------------------

LEGAL_RESEARCH_2_ROUND: list[TurnScript] = [
    # Round 1: LLM decides to search for legal references
    TurnScript(deltas=[
        ReasoningDelta(reasoning="用户询问合同法第三条，我需要先检索相关法规。"),
        ToolCallDelta(
            tool_call_id="call_1",
            tool_name="legal_search",
            arguments='{"query":"合同法 第三条"}',
        ),
        UsageDelta(usage={"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 2: LLM produces final content based on tool results
    TurnScript(deltas=[
        ReasoningDelta(reasoning="根据检索结果，合同法第三条涉及自愿原则。"),
        ContentDelta(content="根据检索结果，"),
        ContentDelta(content="合同法第三条规定："),
        ContentDelta(content="当事人订立、履行合同，应当遵循自愿原则。"),
        UsageDelta(usage={"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280}),
        FinishDelta(finish_reason="stop"),
    ]),
]


# ---------------------------------------------------------------------------
# Legal research scenario — 3 tool rounds (two tools then final content)
# ---------------------------------------------------------------------------

LEGAL_RESEARCH_3_ROUND: list[TurnScript] = [
    # Round 1: LLM calls legal_search
    TurnScript(deltas=[
        ToolCallDelta(
            tool_call_id="call_1",
            tool_name="legal_search",
            arguments='{"query":"劳动合同法 经济补偿"}',
        ),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 2: LLM calls read_file_relative based on search results
    TurnScript(deltas=[
        ToolCallDelta(
            tool_call_id="call_2",
            tool_name="read_file_relative",
            arguments='{"path":"法规/劳动合同法.txt"}',
        ),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 3: LLM produces final content
    TurnScript(deltas=[
        ContentDelta(content="根据《劳动合同法》第四十七条，经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付。"),
        UsageDelta(usage={"prompt_tokens": 300, "completion_tokens": 100, "total_tokens": 400}),
        FinishDelta(finish_reason="stop"),
    ]),
]


# ---------------------------------------------------------------------------
# Single-turn (no tools) — immediate final content
# ---------------------------------------------------------------------------

SINGLE_TURN_CONTENT: list[TurnScript] = [
    TurnScript(deltas=[
        ContentDelta(content="你好，我是法律助手。"),
        ContentDelta(content="请问有什么可以帮助您的？"),
        UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
        FinishDelta(finish_reason="stop"),
    ]),
]


# ---------------------------------------------------------------------------
# Tool failure then recovery — round 1 tool fails, round 2 final content
# ---------------------------------------------------------------------------

TOOL_FAILURE_THEN_RECOVERY: list[TurnScript] = [
    # Round 1: LLM calls a tool that will fail
    TurnScript(deltas=[
        ToolCallDelta(
            tool_call_id="call_1",
            tool_name="legal_search",
            arguments='{"query":"合同法"}',
        ),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 2: LLM sees the error and produces content without the tool
    TurnScript(deltas=[
        ContentDelta(content="抱歉，检索工具暂时不可用。"),
        ContentDelta(content="根据我的知识，合同法第三条规定当事人订立合同应当遵循自愿原则。"),
        FinishDelta(finish_reason="stop"),
    ]),
]


# ---------------------------------------------------------------------------
# Provider error — first call raises ConnectionError
# ---------------------------------------------------------------------------

PROVIDER_ERROR_SCRIPT: list[TurnScript] = [
    TurnScript(error=ConnectionError("API connection refused")),
]


# ---------------------------------------------------------------------------
# Turn limit exceeded — always returns tool calls, never final content
# ---------------------------------------------------------------------------

def make_turn_limit_scripts(count: int = 15) -> list[TurnScript]:
    """Generate scripts that always return tool calls (never final content)."""
    return [
        TurnScript(deltas=[
            ToolCallDelta(
                tool_call_id=f"call_{i}",
                tool_name="legal_search",
                arguments="{}",
            ),
            FinishDelta(finish_reason="tool_calls"),
        ])
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Multiple tool failures then recovery — rounds 1-2 fail, round 3 succeeds
# ---------------------------------------------------------------------------

MULTIPLE_FAILURES_THEN_RECOVERY: list[TurnScript] = [
    # Round 1: first tool call fails
    TurnScript(deltas=[
        ToolCallDelta(
            tool_call_id="call_1",
            tool_name="legal_search",
            arguments='{"query":"合同法"}',
        ),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 2: second tool call also fails
    TurnScript(deltas=[
        ToolCallDelta(
            tool_call_id="call_2",
            tool_name="read_file_relative",
            arguments='{"path":"nonexistent.txt"}',
        ),
        FinishDelta(finish_reason="tool_calls"),
    ]),
    # Round 3: LLM gives up on tools and produces final content
    TurnScript(deltas=[
        ContentDelta(content="由于工具暂时不可用，我将基于已有知识回答。"),
        ContentDelta(content="合同法第三条规定当事人订立、履行合同应当遵循自愿原则。"),
        FinishDelta(finish_reason="stop"),
    ]),
]


__all__ = [
    "LEGAL_RESEARCH_2_ROUND",
    "LEGAL_RESEARCH_3_ROUND",
    "SINGLE_TURN_CONTENT",
    "TOOL_FAILURE_THEN_RECOVERY",
    "PROVIDER_ERROR_SCRIPT",
    "make_turn_limit_scripts",
    "MULTIPLE_FAILURES_THEN_RECOVERY",
]
