"""End-to-end integration tests for the Arena Service — all 4 modes (GATE-01).

Exercises the full arena flow (create → stream → score → review → synthesis
→ export) across all 4 modes using fixture agents (MockACPBackendAdapter).
These tests verify the complete pipeline from arena-service HTTP endpoints
through the arena engine to SSE event emission, validating that the entire
arena workflow produces the expected event sequence and structured outputs.

Test coverage:
- Mode 1: parallel execution, per-slot message.completed, workflow lifecycle
- Mode 2: self-score iteration, arena.score_recorded with rounds
- Mode 3: cross-review with findings, synthesis_started/completed
- Mode 4: adversarial challenge, multi-round synthesis, early_stop_triggered
- Event ordering: seq-ordered with no gaps, no duplicates
- SSE reconnection: Last-Event-ID produces no duplication
- Auth enforced: 401 without token, 403 non-localhost
- Output boundary: no backend/gateway/system events in stream
- Review findings: categorical confidence (Certain/Likely/Possible)
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from arena_engine.mock_acp import MockACPBackendAdapter
from arena_service import ArenaServiceApp, ArenaServiceAuth, ArenaServiceConfig
from arena_service.engine_integration import ArenaServiceEngine
from arena_service.sse import ArenaSseStream
from inkstatute_acp_event_bridge.output_filter import (
    ACP_ALLOWED_EVENT_TYPES,
    ACPOutputFilter,
    FilterAction,
    FilterDecision,
)
from platform_contract.enums import RunEventType

from fixtures.arena_e2e_mode1 import make_mode1_fixtures
from fixtures.arena_e2e_mode2 import make_mode2_fixtures
from fixtures.arena_e2e_mode3 import make_mode3_fixtures
from fixtures.arena_e2e_mode4 import make_mode4_fixtures

_TEST_TOKEN = "test-token-12345"

_ARENA_EVENT_TYPES = frozenset(
    {
        RunEventType.ARENA_WORKFLOW_STARTED.value,
        RunEventType.ARENA_WORKFLOW_COMPLETED.value,
        RunEventType.ARENA_SCORE_RECORDED.value,
        RunEventType.ARENA_REVIEW_COMPLETED.value,
        RunEventType.ARENA_SYNTHESIS_STARTED.value,
        RunEventType.ARENA_SYNTHESIS_COMPLETED.value,
        RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED.value,
        RunEventType.ARENA_EARLY_STOP_TRIGGERED.value,
    }
)

#: The mock adapter emits ``message_delta`` (underscore, the legacy V2
#: enum value) rather than ``message.delta`` (dot, the V3 value in the
#: ACP allowlist).  We allow both in the test output filter so the full
#: event stream is visible for seq-ordering and output-boundary checks.
_MOCK_MESSAGE_DELTA_TYPE = RunEventType.MESSAGE_DELTA.value  # "message_delta"

#: Event types that are backend/gateway/system noise — must never reach the client.
_BLOCKED_EVENT_PREFIXES = frozenset(
    {"meta", "gateway", "system", "update", "command", "help", "terminal"}
)


class ArenaTestOutputFilter:
    """Output filter that allows arena event types + delegates to ACP filter.

    The standard ``ACPOutputFilter`` uses a default-deny policy that blocks
    arena event types (they are not in ``ACP_ALLOWED_EVENT_TYPES``).  This
    filter extends the allowlist to include all ``arena.*`` event types so
    they pass through to the SSE stream, while still blocking backend
    meta/gateway/system noise via the standard ACP filter.
    """

    def __init__(self) -> None:
        self._acp_filter = ACPOutputFilter()

    def filter_event(
        self,
        event_type: str,
        content: str | None,
        metadata: dict | None = None,
    ) -> FilterDecision:
        if event_type in _ARENA_EVENT_TYPES or event_type == _MOCK_MESSAGE_DELTA_TYPE:
            return FilterDecision(
                action=FilterAction.ALLOW.value,
                visible_content=content,
                audit_metadata={},
                reason="arena_event_allowed",
            )
        return self._acp_filter.filter_event(event_type, content, metadata)


class ArenaE2EIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """E2E integration tests covering all 4 arena modes via the full service stack."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auth_headers(self, token: str = _TEST_TOKEN) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    async def _setup_service(
        self,
        fixture_fn: Any,
    ) -> tuple[ArenaServiceApp, ArenaServiceEngine, ArenaServiceConfig, dict]:
        """Create the arena service with mock adapters from the fixture."""
        fixtures = fixture_fn()
        config = ArenaServiceConfig(token=_TEST_TOKEN)
        auth = ArenaServiceAuth(config)
        arena_id = fixtures["config"].arena_id

        adapters: dict[str, MockACPBackendAdapter] = fixtures["adapters"]

        def adapter_factory(slot_id: str, body: dict) -> MockACPBackendAdapter:
            return adapters[slot_id]

        engine = ArenaServiceEngine(config, adapter_factory=adapter_factory)

        # Register synthesis/adversarial adapters before create_arena so
        # they are available when the background run starts.
        if fixtures.get("synthesis_adapter") is not None:
            engine.arena_engine.register_synthesis_adapter(
                arena_id, fixtures["synthesis_adapter"],
            )
        if fixtures.get("adversarial_adapter") is not None:
            engine.arena_engine.register_adversarial_adapter(
                arena_id, fixtures["adversarial_adapter"],
            )

        # Replace the SSE stream with one that allows arena event types.
        engine._sse_stream = ArenaSseStream(output_filter=ArenaTestOutputFilter())

        app = ArenaServiceApp(config, auth=auth, engine=engine)
        return app, engine, config, fixtures

    async def _create_arena(
        self,
        app: ArenaServiceApp,
        engine: ArenaServiceEngine,
        fixtures: dict,
        headers: dict[str, str],
    ) -> str:
        """Create an arena via POST /v1/arena and wait for the event queue."""
        wf_config = fixtures["config"]
        body = {
            "arena_id": wf_config.arena_id,
            "mode": wf_config.mode,
            "agent_slots": list(wf_config.agent_slots),
            "task": wf_config.task_instruction,
        }
        result = await app.dispatch("POST", "/v1/arena", headers, body)
        self.assertEqual(result["status"], 201)
        arena_id = result["body"]["arena_id"]
        self.assertEqual(result["body"]["status"], "created")

        # Wait for the background task to create the event queue.
        for _ in range(500):
            if arena_id in engine._event_queues:
                break
            await asyncio.sleep(0.001)
        self.assertIn(arena_id, engine._event_queues)

        return arena_id

    async def _collect_sse_frames(
        self,
        app: ArenaServiceApp,
        arena_id: str,
        headers: dict[str, str],
        last_event_id: int | None = None,
    ) -> list[str]:
        """Collect all SSE frames from the stream."""
        stream_headers = dict(headers)
        if last_event_id is not None:
            stream_headers["Last-Event-ID"] = str(last_event_id)
        frames: list[str] = []
        async for frame in app.stream(
            "GET",
            f"/v1/arena/{arena_id}/stream",
            stream_headers,
            client_address="127.0.0.1",
        ):
            frames.append(frame)
        return frames

    @staticmethod
    def _parse_frames(frames: list[str]) -> list[dict[str, Any]]:
        """Parse SSE frames into event dicts (from the ``data:`` line)."""
        events: list[dict[str, Any]] = []
        for frame in frames:
            for line in frame.split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    break
        return events

    async def _create_and_collect(
        self,
        fixture_fn: Any,
    ) -> tuple[list[dict[str, Any]], str, ArenaServiceEngine, ArenaServiceApp, ArenaServiceConfig]:
        """Full helper: setup → create → stream → parse. Returns events + context."""
        app, engine, config, fixtures = await self._setup_service(fixture_fn)
        headers = self._auth_headers()
        arena_id = await self._create_arena(app, engine, fixtures, headers)
        frames = await self._collect_sse_frames(app, arena_id, headers)
        events = self._parse_frames(frames)
        return events, arena_id, engine, app, config

    @staticmethod
    def _event_types(events: list[dict[str, Any]]) -> list[str]:
        return [e["event_type"] for e in events]

    @staticmethod
    def _events_of_type(
        events: list[dict[str, Any]],
        event_type: str,
    ) -> list[dict[str, Any]]:
        return [e for e in events if e["event_type"] == event_type]

    # ------------------------------------------------------------------
    # Test 1: Mode 1 full flow
    # ------------------------------------------------------------------

    async def test_mode1_full_flow(self) -> None:
        """Mode 1: create → stream → workflow_started first, per-slot
        message.completed, workflow_completed last."""
        events, arena_id, engine, app, config = await self._create_and_collect(
            make_mode1_fixtures,
        )

        self.assertGreater(len(events), 0)

        # workflow_started is first
        self.assertEqual(events[0]["event_type"], RunEventType.ARENA_WORKFLOW_STARTED.value)
        self.assertEqual(events[0]["payload"]["arena_id"], "e2e-mode1")
        self.assertEqual(events[0]["payload"]["agent_slots"], ["slot-0", "slot-1", "slot-2"])

        # workflow_completed is last
        self.assertEqual(events[-1]["event_type"], RunEventType.ARENA_WORKFLOW_COMPLETED.value)

        # Each per-slot event has metadata.agent_slot
        lifecycle = {
            RunEventType.ARENA_WORKFLOW_STARTED.value,
            RunEventType.ARENA_WORKFLOW_COMPLETED.value,
        }
        per_slot = [e for e in events if e["event_type"] not in lifecycle]
        self.assertGreater(len(per_slot), 0)
        for ev in per_slot:
            self.assertIn("agent_slot", ev["metadata"])

        # 3 slots each produced message.completed events
        completed = self._events_of_type(events, RunEventType.MESSAGE_COMPLETED.value)
        self.assertEqual(len(completed), 3)
        completed_slots = {e["metadata"]["agent_slot"] for e in completed}
        self.assertEqual(completed_slots, {"slot-0", "slot-1", "slot-2"})

    # ------------------------------------------------------------------
    # Test 2: Mode 2 full flow
    # ------------------------------------------------------------------

    async def test_mode2_full_flow(self) -> None:
        """Mode 2: create → stream → score_recorded with rounds, workflow_completed."""
        events, arena_id, engine, app, config = await self._create_and_collect(
            make_mode2_fixtures,
        )

        self.assertGreater(len(events), 0)

        # score_recorded events emitted with agent_slot, round, score
        score_events = self._events_of_type(events, RunEventType.ARENA_SCORE_RECORDED.value)
        self.assertGreater(len(score_events), 0)
        for ev in score_events:
            payload = ev["payload"]
            self.assertIn("agent_slot", payload)
            self.assertIn("round", payload)
            self.assertIn("score", payload)
            self.assertGreaterEqual(payload["score"], 1)
            self.assertLessEqual(payload["score"], 10)

        # At least 2 rounds of scoring per agent (max_rounds=3)
        slot_scores: dict[str, set[int]] = {}
        for ev in score_events:
            slot = ev["payload"]["agent_slot"]
            slot_scores.setdefault(slot, set()).add(ev["payload"]["round"])
        for slot, rounds in slot_scores.items():
            self.assertGreaterEqual(
                len(rounds), 2,
                f"Slot {slot} only had {len(rounds)} rounds of scoring",
            )

        # workflow_completed at end
        self.assertEqual(events[-1]["event_type"], RunEventType.ARENA_WORKFLOW_COMPLETED.value)

    # ------------------------------------------------------------------
    # Test 3: Mode 3 full flow
    # ------------------------------------------------------------------

    async def test_mode3_full_flow(self) -> None:
        """Mode 3: create → stream → score_recorded, review_completed with
        findings, synthesis_started/completed, workflow_completed."""
        events, arena_id, engine, app, config = await self._create_and_collect(
            make_mode3_fixtures,
        )

        self.assertGreater(len(events), 0)

        # score_recorded events
        score_events = self._events_of_type(events, RunEventType.ARENA_SCORE_RECORDED.value)
        self.assertGreater(len(score_events), 0)

        # review_completed events with reviewer_slot, reviewed_slot, round, findings
        review_events = self._events_of_type(events, RunEventType.ARENA_REVIEW_COMPLETED.value)
        self.assertGreater(len(review_events), 0)
        for ev in review_events:
            payload = ev["payload"]
            self.assertIn("reviewer_slot", payload)
            self.assertIn("reviewed_slot", payload)
            self.assertIn("round", payload)
            self.assertIn("findings", payload)
            self.assertIsInstance(payload["findings"], list)

        # synthesis_started and synthesis_completed
        synth_started = self._events_of_type(events, RunEventType.ARENA_SYNTHESIS_STARTED.value)
        synth_completed = self._events_of_type(events, RunEventType.ARENA_SYNTHESIS_COMPLETED.value)
        self.assertGreaterEqual(len(synth_started), 1)
        self.assertGreaterEqual(len(synth_completed), 1)

        # workflow_completed at end
        self.assertEqual(events[-1]["event_type"], RunEventType.ARENA_WORKFLOW_COMPLETED.value)

    # ------------------------------------------------------------------
    # Test 4: Mode 4 full flow
    # ------------------------------------------------------------------

    async def test_mode4_full_flow(self) -> None:
        """Mode 4: create → stream → adversarial_challenge_completed,
        synthesis_started/completed, early_stop_triggered, workflow_completed."""
        events, arena_id, engine, app, config = await self._create_and_collect(
            make_mode4_fixtures,
        )

        self.assertGreater(len(events), 0)

        # adversarial_challenge_completed with challenger_slot, challenged_slot, findings
        adv_events = self._events_of_type(
            events, RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED.value,
        )
        self.assertGreaterEqual(len(adv_events), 1)
        for ev in adv_events:
            payload = ev["payload"]
            self.assertEqual(payload["challenger_slot"], "adversarial")
            self.assertEqual(payload["challenged_slot"], "synthesis")
            self.assertIn("round", payload)
            self.assertIsInstance(payload["findings"], list)

        # synthesis_started/completed
        synth_started = self._events_of_type(events, RunEventType.ARENA_SYNTHESIS_STARTED.value)
        synth_completed = self._events_of_type(events, RunEventType.ARENA_SYNTHESIS_COMPLETED.value)
        self.assertGreaterEqual(len(synth_started), 1)
        self.assertGreaterEqual(len(synth_completed), 1)

        # early_stop_triggered (converged or max rounds)
        stop_events = self._events_of_type(events, RunEventType.ARENA_EARLY_STOP_TRIGGERED.value)
        self.assertGreaterEqual(len(stop_events), 1)

        # workflow_completed at end
        self.assertEqual(events[-1]["event_type"], RunEventType.ARENA_WORKFLOW_COMPLETED.value)

    # ------------------------------------------------------------------
    # Test 5: Event ordering — seq ascending, no gaps, no duplicates
    # ------------------------------------------------------------------

    async def test_event_ordering_all_modes(self) -> None:
        """All modes: events are seq-ordered with no gaps and no duplicates."""
        for fixture_fn in (
            make_mode1_fixtures,
            make_mode2_fixtures,
            make_mode3_fixtures,
            make_mode4_fixtures,
        ):
            with self.subTest(fixture=fixture_fn.__name__):
                events, _, _, _, _ = await self._create_and_collect(fixture_fn)
                self.assertGreater(len(events), 0)
                seqs = [e["seq"] for e in events]
                # No duplicates
                self.assertEqual(len(seqs), len(set(seqs)))
                # Ascending
                self.assertEqual(seqs, sorted(seqs))
                # No gaps (1, 2, 3, ...)
                self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    # ------------------------------------------------------------------
    # Test 6: SSE reconnection — no duplication
    # ------------------------------------------------------------------

    async def test_sse_reconnection_no_duplication(self) -> None:
        """Reconnect with Last-Event-ID → only events with seq > last_seq."""
        for fixture_fn in (
            make_mode1_fixtures,
            make_mode2_fixtures,
            make_mode3_fixtures,
            make_mode4_fixtures,
        ):
            with self.subTest(fixture=fixture_fn.__name__):
                app, engine, config, fixtures = await self._setup_service(fixture_fn)
                headers = self._auth_headers()
                arena_id = await self._create_arena(app, engine, fixtures, headers)

                # First connection: collect all events
                frames1 = await self._collect_sse_frames(app, arena_id, headers)
                events1 = self._parse_frames(frames1)
                self.assertGreater(len(events1), 0)

                # Remove the queue so the reconnection only replays from buffer
                # (otherwise the stream would block on an empty queue).
                engine._event_queues.pop(arena_id, None)

                # Reconnect from the halfway point
                halfway = len(events1) // 2
                last_seq = events1[halfway]["seq"] if halfway > 0 else 0

                frames2 = await self._collect_sse_frames(
                    app, arena_id, headers, last_event_id=last_seq,
                )
                events2 = self._parse_frames(frames2)

                # Only events with seq > last_seq should be returned
                for ev in events2:
                    self.assertGreater(ev["seq"], last_seq)

                # No duplication: events2 seqs should not overlap with
                # the first half of events1
                first_half_seqs = {e["seq"] for e in events1[:halfway + 1]}
                second_seqs = {e["seq"] for e in events2}
                self.assertEqual(first_half_seqs & second_seqs, set())

    # ------------------------------------------------------------------
    # Test 7: workflow_completed payload has status and agent_slots
    # ------------------------------------------------------------------

    async def test_workflow_completed_status(self) -> None:
        """All modes: workflow_completed payload has status and agent_slots.

        Mode 4 may report ``status="stopped_early"`` when the adversarial
        loop converges — this is a valid terminal state, not an error.
        """
        valid_statuses = {"completed", "stopped_early"}
        for fixture_fn in (
            make_mode1_fixtures,
            make_mode2_fixtures,
            make_mode3_fixtures,
            make_mode4_fixtures,
        ):
            with self.subTest(fixture=fixture_fn.__name__):
                events, _, _, _, _ = await self._create_and_collect(fixture_fn)
                completed = self._events_of_type(
                    events, RunEventType.ARENA_WORKFLOW_COMPLETED.value,
                )
                self.assertEqual(len(completed), 1)
                payload = completed[0]["payload"]
                self.assertIn(payload["status"], valid_statuses)
                self.assertIn("agent_slots", payload)
                self.assertGreater(len(payload["agent_slots"]), 0)

    # ------------------------------------------------------------------
    # Test 8: Review findings have categorical confidence
    # ------------------------------------------------------------------

    async def test_review_findings_categorical_confidence(self) -> None:
        """Mode 3/4: review findings have confidence in {Certain, Likely, Possible}."""
        valid_confidences = {"Certain", "Likely", "Possible"}
        for fixture_fn in (make_mode3_fixtures, make_mode4_fixtures):
            with self.subTest(fixture=fixture_fn.__name__):
                events, _, _, _, _ = await self._create_and_collect(fixture_fn)
                review_events = self._events_of_type(
                    events, RunEventType.ARENA_REVIEW_COMPLETED.value,
                )
                for ev in review_events:
                    for finding in ev["payload"]["findings"]:
                        self.assertIn(
                            finding["confidence"], valid_confidences,
                            f"Confidence {finding['confidence']!r} is not categorical",
                        )
                        # Must NOT be a numeric percentage
                        self.assertFalse(
                            finding["confidence"].endswith("%"),
                            "Confidence must not be a numeric percentage",
                        )

    # ------------------------------------------------------------------
    # Test 9: Auth enforced
    # ------------------------------------------------------------------

    async def test_auth_enforced(self) -> None:
        """Auth: no token → 401, wrong token → 401, non-localhost → 403."""
        app, engine, config, fixtures = await self._setup_service(make_mode1_fixtures)

        # No token → 401
        result = await app.dispatch(
            "POST", "/v1/arena", {}, {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

        # Wrong token → 401
        result = await app.dispatch(
            "POST", "/v1/arena",
            {"Authorization": "Bearer wrong-token"},
            {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

        # Non-localhost → 403
        result = await app.dispatch(
            "POST", "/v1/arena",
            self._auth_headers(),
            {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
            client_address="192.168.1.100",
        )
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["error"]["code"], "forbidden_remote")

    # ------------------------------------------------------------------
    # Test 10: Output boundary — no backend/gateway/system events
    # ------------------------------------------------------------------

    async def test_output_boundary(self) -> None:
        """All modes: no backend meta/gateway/system event types in the stream."""
        for fixture_fn in (
            make_mode1_fixtures,
            make_mode2_fixtures,
            make_mode3_fixtures,
            make_mode4_fixtures,
        ):
            with self.subTest(fixture=fixture_fn.__name__):
                events, _, _, _, _ = await self._create_and_collect(fixture_fn)
                for ev in events:
                    et = ev["event_type"]
                    # No blocked event type prefixes
                    for prefix in _BLOCKED_EVENT_PREFIXES:
                        self.assertFalse(
                            et.startswith(prefix),
                            f"Blocked event type {et!r} appeared in the SSE stream",
                        )
                    # All event types should be user-facing
                    self.assertTrue(
                        et in _ARENA_EVENT_TYPES
                        or et in ACP_ALLOWED_EVENT_TYPES
                        or et == _MOCK_MESSAGE_DELTA_TYPE,
                        f"Event type {et!r} is not in the user-facing allowlist",
                    )


# ---------------------------------------------------------------------------
# Mock track-changes module for export tests (no lawfirm-profile dependency)
# ---------------------------------------------------------------------------


class _MockTrackChangesBuilder:
    """Mock TrackChangesBuilder — does not require lxml or a real docx."""

    def __init__(self, input_path: str) -> None:
        self._input_path = input_path

    def process(self) -> list[tuple]:
        return [(1, "P2", "applied", "mock comment")]

    def save(self, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"mock docx content")


class _MockTrackChangesModule:
    """Mock module mimicking contract_review_trackchanges.py interface."""

    TrackChangesBuilder = _MockTrackChangesBuilder
    REVIEWER = "mock-reviewer"
    REVIEW_ITEMS: list[dict] = []


# ---------------------------------------------------------------------------
# Test 11: Export flow — create → stream → synthesis → export docx
# ---------------------------------------------------------------------------


class ArenaExportFlowTests(unittest.IsolatedAsyncioTestCase):
    """E2E export flow test: create → stream → synthesis → export docx.

    Uses Mode 3 fixtures (which produce synthesis content + review findings)
    and mocks the track-changes module so the test does NOT depend on the
    ``lawfirm-profile`` sibling repo being cloned in CI.
    """

    def _auth_headers(self, token: str = _TEST_TOKEN) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    async def _setup_service(
        self,
        fixture_fn: Any,
    ) -> tuple[ArenaServiceApp, ArenaServiceEngine, ArenaServiceConfig, dict]:
        """Create the arena service with mock adapters from the fixture."""
        fixtures = fixture_fn()
        config = ArenaServiceConfig(token=_TEST_TOKEN)
        auth = ArenaServiceAuth(config)
        arena_id = fixtures["config"].arena_id

        adapters: dict[str, MockACPBackendAdapter] = fixtures["adapters"]

        def adapter_factory(slot_id: str, body: dict) -> MockACPBackendAdapter:
            return adapters[slot_id]

        engine = ArenaServiceEngine(config, adapter_factory=adapter_factory)

        if fixtures.get("synthesis_adapter") is not None:
            engine.arena_engine.register_synthesis_adapter(
                arena_id, fixtures["synthesis_adapter"],
            )
        if fixtures.get("adversarial_adapter") is not None:
            engine.arena_engine.register_adversarial_adapter(
                arena_id, fixtures["adversarial_adapter"],
            )

        engine._sse_stream = ArenaSseStream(output_filter=ArenaTestOutputFilter())

        app = ArenaServiceApp(config, auth=auth, engine=engine)
        return app, engine, config, fixtures

    async def _create_arena_with_metadata(
        self,
        app: ArenaServiceApp,
        engine: ArenaServiceEngine,
        fixtures: dict,
        headers: dict[str, str],
        metadata: dict[str, Any],
    ) -> str:
        """Create an arena via POST /v1/arena with extra metadata in the body."""
        wf_config = fixtures["config"]
        body = {
            "arena_id": wf_config.arena_id,
            "mode": wf_config.mode,
            "agent_slots": list(wf_config.agent_slots),
            "task": wf_config.task_instruction,
            "metadata": metadata,
        }
        result = await app.dispatch("POST", "/v1/arena", headers, body)
        assert result["status"] == 201, f"arena creation failed: {result}"
        arena_id = result["body"]["arena_id"]

        # Wait for the background task to create the event queue.
        for _ in range(500):
            if arena_id in engine._event_queues:
                break
            await asyncio.sleep(0.001)
        assert arena_id in engine._event_queues

        return arena_id

    @staticmethod
    def _parse_frames(frames: list[str]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for frame in frames:
            for line in frame.split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    break
        return events

    async def test_export_flow(self) -> None:
        """E2E export flow: create → stream → synthesis → export docx.

        Creates a Mode 3 arena (which produces synthesis content + review
        findings), streams events until synthesis_completed, then calls
        POST /v1/arena/{id}/export with a mocked track-changes module.

        The track-changes module is mocked via patching
        ``_load_trackchanges_module`` so the test does NOT depend on
        ``lawfirm-profile/scripts/contract_review_trackchanges.py``
        being present in the CI environment.
        """
        app, engine, config, fixtures = await self._setup_service(
            make_mode3_fixtures,
        )
        headers = self._auth_headers()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_docx = Path(tmpdir) / "input_contract.docx"
            input_docx.write_bytes(b"mock input docx content")
            output_docx = Path(tmpdir) / "test_arena_export.docx"

            # Create the arena with input_docx_path in metadata (required
            # by the export endpoint to locate the original contract).
            arena_id = await self._create_arena_with_metadata(
                app, engine, fixtures, headers,
                metadata={"input_docx_path": str(input_docx)},
            )

            # Collect SSE frames (stream ends when the background run completes)
            frames: list[str] = []
            async for frame in app.stream(
                "GET",
                f"/v1/arena/{arena_id}/stream",
                headers,
                client_address="127.0.0.1",
            ):
                frames.append(frame)
            events = self._parse_frames(frames)

            # Verify synthesis_completed was emitted
            self.assertGreater(len(events), 0)
            synth_completed = [
                e for e in events
                if e["event_type"] == RunEventType.ARENA_SYNTHESIS_COMPLETED.value
            ]
            self.assertGreaterEqual(
                len(synth_completed), 1,
                "synthesis_completed event not found in stream",
            )

            # Call POST /v1/arena/{id}/export with mocked track-changes module.
            # The mock avoids depending on lawfirm-profile/scripts/
            # contract_review_trackchanges.py in CI.
            with patch(
                "inkstatute_agent_core.tools.document_generate._load_trackchanges_module",
                return_value=_MockTrackChangesModule,
            ):
                result = await app.dispatch(
                    "POST",
                    f"/v1/arena/{arena_id}/export",
                    headers,
                    {"output_path": str(output_docx)},
                )

            # Assert 200 + ok: True
            self.assertEqual(result["status"], 200)
            self.assertTrue(result["body"]["ok"])
            self.assertEqual(result["body"]["output_path"], str(output_docx))

            # Verify the output file was created by the mock builder
            self.assertTrue(output_docx.exists())
            self.assertEqual(output_docx.read_bytes(), b"mock docx content")


if __name__ == "__main__":
    unittest.main()
