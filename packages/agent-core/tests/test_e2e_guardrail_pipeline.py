"""E2E integration tests for the full guardrail pipeline in the turn loop.

This test file verifies that the Phase 102 guardrail modules are correctly
wired into ``run_turn()``:

1. **Leak detection + retry** — first round yields leaked DSML content,
   second round yields clean content; the final ``message.completed`` has
   clean (sanitized) content.
2. **Leak retry exhaustion** — all rounds yield leaked content; after
   ``max_leak_retries`` the sanitized content is emitted.
3. **Citation audit** — final content contains a law citation; a
   ``citation.recorded`` event is emitted with the correct
   ``CitationRecord``.
4. **De-AI polish** — final content contains AI disclaimers; the
   ``message.completed`` content has them removed.
5. **Citation audit metadata** — ``message.completed`` metadata includes
   the citation audit summary (total/verified/retrieved/unverified).
6. **Retrieval evidence collection** — tool results in message history are
   collected as retrieval evidence and fed to the citation audit.

These tests use ``FixtureProvider`` with ``TurnScript`` objects that yield
controlled deltas — no external LLM calls.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ToolCallDelta,
    UsageDelta,
)
from inkstatute_agent_core.turn_loop import ToolResult, run_turn


# ---------------------------------------------------------------------------
# Golden fixture constant — verbatim from tool_leak.rs:295 (via test_tool_leak.py)
# ---------------------------------------------------------------------------

REAL_DSML_LEAK: str = (
    "<｜｜DSML｜｜tool_c>\n"
    '<｜｜DSML｜｜invoke="search_">\n'
    '<｜｜DSML｜｜parameter namek" stringfalse">13｜｜DSML｜｜parameter>\n'
    '<｜｜DSML｜｜ name="query" stringtrue">保 投标见即付不可</｜｜DSML｜｜parameter>\n'
    "</invoke>\n"
    "</｜｜DSML｜｜_calls>"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events(gen) -> list[RunEvent]:
    """Collect all events from an async generator into a list."""
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


def _make_emitter(
    run_id: str = "run-guardrail",
    config: AgentCoreConfig | None = None,
) -> EventEmitter:
    return EventEmitter(run_id, config or AgentCoreConfig())


def _message_completed(events: list[RunEvent]) -> RunEvent:
    """Return the single message.completed event from *events*."""
    matches = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
    assert len(matches) == 1, f"Expected 1 message.completed, got {len(matches)}"
    return matches[0]


def _citation_recorded_events(events: list[RunEvent]) -> list[RunEvent]:
    """Return all citation.recorded events from *events*."""
    return [e for e in events if e.event_type == RunEventType.CITATION_RECORDED.value]


# ---------------------------------------------------------------------------
# Test 1: Leak retry — leaked first round, clean second round
# ---------------------------------------------------------------------------


class TestLeakRetryIntegration(unittest.TestCase):
    """Leak detection + retry loop wired into run_turn()."""

    def test_leaked_first_round_clean_second_round(self) -> None:
        """First round yields leaked DSML; second round yields clean content.

        The final message.completed must have clean content (no DSML markers).
        The provider must have been called twice (one retry).
        """
        script = [
            # Round 1: leaked content
            TurnScript(deltas=[
                ContentDelta(content=REAL_DSML_LEAK),
                UsageDelta(usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}),
                FinishDelta(finish_reason="stop"),
            ]),
            # Round 2: clean content
            TurnScript(deltas=[
                ContentDelta(content="根据《民法典》第五百八十五条，当事人可以约定违约金。"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "什么是违约金？"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-leak-retry",
            )
        ))

        # Provider called twice (one leak retry)
        self.assertEqual(provider.call_count, 2)

        # Final message.completed has clean content
        completed = _message_completed(events)
        content = completed.payload["content"]
        self.assertNotIn("DSML", content)
        self.assertNotIn("tool_c", content)
        self.assertNotIn("invoke", content)
        self.assertIn("违约金", content)

    def test_leak_retry_exhaustion_sanitizes(self) -> None:
        """All rounds yield leaked content; after max retries, sanitized output.

        With ``max_leak_retries=1``, the first round leaks (retry), the second
        round also leaks (retries exhausted → sanitized empty content emitted).
        """
        script = [
            TurnScript(deltas=[
                ContentDelta(content=REAL_DSML_LEAK),
                FinishDelta(finish_reason="stop"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content=REAL_DSML_LEAK),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig(max_leak_retries=1)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-leak-exhaust",
            )
        ))

        # Provider called twice: first leak (retry), second leak (exhausted)
        self.assertEqual(provider.call_count, 2)

        completed = _message_completed(events)
        content = completed.payload["content"]
        # Sanitized content should be empty (REAL_DSML_LEAK sanitizes to "")
        self.assertEqual(content, "")


# ---------------------------------------------------------------------------
# Test 2: Citation audit — citation.recorded event emitted
# ---------------------------------------------------------------------------


class TestCitationAuditIntegration(unittest.TestCase):
    """Citation audit pipeline wired into run_turn() before message.completed."""

    def test_citation_recorded_event_emitted_for_law_citation(self) -> None:
        """Final content with a law citation triggers citation.recorded."""
        script = [
            TurnScript(deltas=[
                ContentDelta(content="根据《中华人民共和国民法典》第五百八十五条，"),
                ContentDelta(content="当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金。"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "违约金条款是什么？"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-citation",
            )
        ))

        # citation.recorded event emitted
        citation_events = _citation_recorded_events(events)
        self.assertEqual(len(citation_events), 1)

        # The citation record should reference the law source
        payload = citation_events[0].payload
        citations = payload["citations"]
        self.assertGreaterEqual(len(citations), 1)
        # Source should contain "民法典" (the law name)
        sources = [c["source"] for c in citations]
        self.assertTrue(any("民法典" in s for s in sources))
        # Status should be "unverified" (no law library, no retrievals)
        statuses = [c["status"] for c in citations]
        self.assertTrue(all(s == "unverified" for s in statuses))

    def test_citation_audit_metadata_in_message_completed(self) -> None:
        """message.completed metadata includes citation_audit summary."""
        script = [
            TurnScript(deltas=[
                ContentDelta(content="根据《民法典》第五百八十五条的规定，违约金可以约定。"),
                UsageDelta(usage={"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-citation-meta",
            )
        ))

        completed = _message_completed(events)
        metadata = completed.metadata
        self.assertIn("citation_audit", metadata)
        audit = metadata["citation_audit"]
        self.assertIn("total", audit)
        self.assertIn("verified", audit)
        self.assertIn("retrieved", audit)
        self.assertIn("unverified", audit)
        self.assertGreater(audit["total"], 0)
        self.assertEqual(audit["unverified"], audit["total"])  # no library/retrievals

    def test_no_citation_recorded_when_no_citations(self) -> None:
        """No citation.recorded event when content has no legal citations."""
        script = [
            TurnScript(deltas=[
                ContentDelta(content="你好，请问有什么可以帮助您的？"),
                UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "你好"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-no-citation",
            )
        ))

        citation_events = _citation_recorded_events(events)
        self.assertEqual(len(citation_events), 0)

        completed = _message_completed(events)
        # No citation_audit key when total is 0
        self.assertNotIn("citation_audit", completed.metadata)


# ---------------------------------------------------------------------------
# Test 3: De-AI polish — AI disclaimers removed before message.completed
# ---------------------------------------------------------------------------


class TestDeAiPolishIntegration(unittest.TestCase):
    """De-AI polish pipeline wired into run_turn() before message.completed."""

    def test_ai_disclaimer_removed(self) -> None:
        """Content with '作为一个AI助手' prefix is polished before completed."""
        script = [
            TurnScript(deltas=[
                ContentDelta(content="作为一个AI助手，我为您分析如下："),
                ContentDelta(content="根据《民法典》第五百八十五条，违约金可以约定。"),
                UsageDelta(usage={"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "分析违约金"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-polish",
            )
        ))

        completed = _message_completed(events)
        content = completed.payload["content"]
        # AI disclaimer removed
        self.assertNotIn("作为一个AI助手", content)
        # Legal content preserved
        self.assertIn("违约金", content)
        self.assertIn("民法典", content)

    def test_not_legal_advice_disclaimer_removed(self) -> None:
        """'以上分析仅供参考，不构成法律建议' boilerplate is removed."""
        script = [
            TurnScript(deltas=[
                ContentDelta(content="根据《民法典》第五百八十五条，违约金可以约定。"),
                ContentDelta(content="以上分析仅供参考，不构成法律建议。"),
                UsageDelta(usage={"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-polish2",
            )
        ))

        completed = _message_completed(events)
        content = completed.payload["content"]
        self.assertNotIn("仅供参考", content)
        self.assertNotIn("不构成法律建议", content)
        self.assertIn("违约金", content)


# ---------------------------------------------------------------------------
# Test 4: Retrieval evidence collection from tool results
# ---------------------------------------------------------------------------


class TestRetrievalEvidenceIntegration(unittest.TestCase):
    """Retrieval evidence from tool results feeds into citation audit."""

    def test_retrieved_citation_from_tool_result(self) -> None:
        """A citation found in a tool result is labelled 'retrieved'."""
        tool_result_content = (
            "《中华人民共和国民法典》第五百八十五条："
            "当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金。"
        )

        async def tool_executor(tool_call_id: str, tool_name: str, args: dict) -> ToolResult:
            return ToolResult(content=tool_result_content)

        script = [
            # Round 1: LLM calls legal_search
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="legal_search",
                    arguments='{"query":"民法典 违约金"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # Round 2: LLM produces final content citing the law
            TurnScript(deltas=[
                ContentDelta(content="根据《中华人民共和国民法典》第五百八十五条，违约金可以约定。"),
                UsageDelta(usage={"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "搜索民法典违约金条款"}],
                tools=[{"type": "function", "function": {"name": "legal_search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=tool_executor,
                run_id="run-retrieval",
            )
        ))

        # citation.recorded emitted
        citation_events = _citation_recorded_events(events)
        self.assertEqual(len(citation_events), 1)

        payload = citation_events[0].payload
        citations = payload["citations"]
        self.assertGreaterEqual(len(citations), 1)

        # The citation should be "retrieved" (found in tool result)
        statuses = [c["status"] for c in citations]
        self.assertIn("retrieved", statuses)

        # message.completed metadata has citation_audit with retrieved > 0
        completed = _message_completed(events)
        audit = completed.metadata["citation_audit"]
        self.assertGreater(audit["retrieved"], 0)


# ---------------------------------------------------------------------------
# Test 5: Guardrail sequence — all guardrails run in order
# ---------------------------------------------------------------------------


class TestGuardrailSequenceIntegration(unittest.TestCase):
    """All guardrails execute in the correct sequence before message.completed."""

    def test_full_pipeline_leak_citation_polish(self) -> None:
        """Leaked first round → clean second round with citation + AI disclaimer.

        Verifies: leak retry → citation audit → de-AI polish → message.completed
        all execute in sequence.
        """
        script = [
            # Round 1: leaked content (triggers retry)
            TurnScript(deltas=[
                ContentDelta(content=REAL_DSML_LEAK),
                FinishDelta(finish_reason="stop"),
            ]),
            # Round 2: clean content with citation + AI disclaimer
            TurnScript(deltas=[
                ContentDelta(content="作为一个AI助手，根据《民法典》第五八十五条，违约金可以约定。以上分析仅供参考。"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-full-pipeline",
            )
        ))

        # Provider called twice (leak retry)
        self.assertEqual(provider.call_count, 2)

        # citation.recorded emitted (citation audit ran on clean content)
        citation_events = _citation_recorded_events(events)
        self.assertEqual(len(citation_events), 1)

        # message.completed has polished content
        completed = _message_completed(events)
        content = completed.payload["content"]
        self.assertNotIn("作为一个AI助手", content)
        self.assertNotIn("仅供参考", content)
        self.assertIn("违约金", content)

        # message.completed metadata has citation_audit
        self.assertIn("citation_audit", completed.metadata)


if __name__ == "__main__":
    unittest.main()
