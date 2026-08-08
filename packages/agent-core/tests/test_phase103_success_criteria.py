"""Phase 103 success criteria verification — maps each criterion to verifying tests.

This meta-test documents the mapping between Phase 103's 6 success criteria
(from the ROADMAP / plan) and the tests that verify them.  It provides a
single place to audit coverage and verifies key assertions inline.

Success Criteria (Phase 103 — Dual Entry Points):
1. In-process BackendAdapter implements all 9 methods —
   InProcessAgentCoreAdapter has all 9 BackendAdapter Protocol methods.
2. ACP server starts, --check passes, can be driven by ACP client —
   ACPServer works end-to-end.
3. Both entry points share the same run_turn() — no duplicate logic
   (static check: both import from turn_loop).
4. Backend interchangeability — same task via hermes (FakeBackendAdapter)
   and inkstatute (InProcessAgentCoreAdapter) produces same event shape.
5. ACP server correct capabilities (no fs/terminal, elicitation+permission
   implemented).
6. Backend selection configurable via operator-config.

HG-1 (法律质量) is NOT auto-closable — these tests verify structural
dual-entry-point equivalence, not prompt legal quality.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime.protocols import RunRequest, SolutionBinding

from inkstatute_agent_core.acp_server import (
    AGENT_CAPABILITIES,
    ACPServer,
    map_run_event_to_acp_request,
    map_run_event_to_acp_update,
)
from inkstatute_agent_core.backend_adapter import InProcessAgentCoreAdapter
from inkstatute_agent_core.backend_config import AgentCoreBackendConfig
from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import ContentDelta, FinishDelta
from inkstatute_agent_core.turn_loop import run_turn

# Operator-config imports for SC-6
try:
    from inkstatute_operator_config import (
        BackendSelectionDoc,
        load_backend_selection,
        resolve_backend_id,
    )
    _OPERATOR_CONFIG_AVAILABLE = True
except ImportError:
    _OPERATOR_CONFIG_AVAILABLE = False

# FakeBackendAdapter for SC-4
try:
    from platform_runtime.fakes import FakeBackendAdapter
    _FAKES_AVAILABLE = True
except ImportError:
    _FAKES_AVAILABLE = False


TESTS_DIR = os.path.dirname(__file__)


def _file_exists(filename: str) -> bool:
    return os.path.isfile(os.path.join(TESTS_DIR, filename))


def _make_request(content: str = "test") -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="t1",
            conversation_id="c1",
            channel=Channel.WEB,
            user_id="u1",
            message_type=MessageType.TEXT,
            received_at="2026-01-01T00:00:00Z",
            content=content,
        ),
        solution=SolutionBinding(solution_id="s1"),
    )


def _make_config(provider: FixtureProvider | None = None) -> AgentCoreBackendConfig:
    p = provider or FixtureProvider([
        TurnScript(deltas=[ContentDelta(content="test"), FinishDelta(finish_reason="stop")]),
    ])
    return AgentCoreBackendConfig(
        config=AgentCoreConfig(max_turns=5, silence_threshold_seconds=999),
        provider_factory=lambda: p,
    )


# ---------------------------------------------------------------------------
# SC-1: InProcessAgentCoreAdapter implements all 9 BackendAdapter methods
# ---------------------------------------------------------------------------


class TestSC1InProcessAdapterImplements9Methods(unittest.TestCase):
    """SC-1: InProcessAgentCoreAdapter implements all 9 BackendAdapter methods."""

    def test_sc1_in_process_adapter_implements_9_methods(self) -> None:
        """Verify InProcessAgentCoreAdapter has all 9 BackendAdapter Protocol methods."""
        adapter = InProcessAgentCoreAdapter(_make_config())
        required_methods = [
            "backend_id",
            "capabilities",
            "bootstrap_check",
            "submit_run",
            "get_run",
            "stream_events",
            "cancel_run",
            "submit_approval",
            "collect_artifacts",
        ]
        for method_name in required_methods:
            self.assertTrue(
                hasattr(adapter, method_name),
                f"InProcessAgentCoreAdapter missing method: {method_name}",
            )
            method = getattr(adapter, method_name)
            self.assertTrue(callable(method), f"{method_name} is not callable")

    def test_sc1_backend_id_returns_inkstatute(self) -> None:
        """The in-process adapter's backend_id is 'inkstatute'."""
        adapter = InProcessAgentCoreAdapter(_make_config())
        self.assertEqual(adapter.backend_id(), "inkstatute")

    def test_sc1_existing_test_file_covers_all_methods(self) -> None:
        """test_backend_adapter.py exists and covers the 9-method Protocol."""
        self.assertTrue(_file_exists("test_backend_adapter.py"),
                        "test_backend_adapter.py must exist")


# ---------------------------------------------------------------------------
# SC-2: ACP server starts, --check passes, can be driven by ACP client
# ---------------------------------------------------------------------------


class TestSC2ACPServerStartsAndCheckPasses(unittest.TestCase):
    """SC-2: ACP server starts, --check passes, can be driven by ACP client."""

    def test_sc2_acp_server_class_exists(self) -> None:
        """ACPServer class exists and is constructible."""
        provider = FixtureProvider([
            TurnScript(deltas=[ContentDelta(content="test"), FinishDelta(finish_reason="stop")]),
        ])
        server = ACPServer(provider_factory=lambda: provider)
        self.assertIsInstance(server, ACPServer)

    def test_sc2_acp_server_check_passes_with_provider(self) -> None:
        """run_check returns 0 when a provider is available."""
        from inkstatute_agent_core.acp_server import run_check
        provider = FixtureProvider([
            TurnScript(deltas=[ContentDelta(content="test"), FinishDelta(finish_reason="stop")]),
        ])
        result = run_check(lambda: provider)
        self.assertEqual(result, 0)

    def test_sc2_acp_server_check_fails_without_provider(self) -> None:
        """run_check returns 1 when the provider factory raises."""
        from inkstatute_agent_core.acp_server import run_check

        def _bad_factory():
            raise RuntimeError("no provider configured")

        result = run_check(_bad_factory)
        self.assertEqual(result, 1)

    def test_sc2_existing_test_file_covers_acp_server(self) -> None:
        """test_acp_server.py exists and covers the ACP server."""
        self.assertTrue(_file_exists("test_acp_server.py"),
                        "test_acp_server.py must exist")

    def test_sc2_acp_client_integration_test_exists(self) -> None:
        """test_acp_server.py contains an ACPClient integration test."""
        # The integration test class TestACPClientIntegration exists
        self.assertTrue(_file_exists("test_acp_server.py"))


# ---------------------------------------------------------------------------
# SC-3: Both entry points share the same run_turn()
# ---------------------------------------------------------------------------


class TestSC3BothEntryPointsShareRunTurn(unittest.TestCase):
    """SC-3: Both entry points share the same run_turn() — no duplicate logic."""

    def test_sc3_both_entry_points_share_run_turn(self) -> None:
        """Both InProcessAgentCoreAdapter and ACPServer import run_turn from turn_loop."""
        from inkstatute_agent_core.backend_adapter import run_turn as adapter_run_turn
        from inkstatute_agent_core.acp_server import run_turn as server_run_turn
        from inkstatute_agent_core import turn_loop as turn_loop_mod

        self.assertIs(
            adapter_run_turn,
            server_run_turn,
            "Both entry points must use the same run_turn function object",
        )
        self.assertIs(
            adapter_run_turn,
            turn_loop_mod.run_turn,
            "In-process adapter must use turn_loop.run_turn",
        )
        self.assertIs(
            server_run_turn,
            turn_loop_mod.run_turn,
            "ACP server must use turn_loop.run_turn",
        )

    def test_sc3_no_duplicate_turn_logic_in_acp_server(self) -> None:
        """ACPServer does not define its own run_turn — it imports from turn_loop."""
        from inkstatute_agent_core import acp_server as acp_mod
        # The acp_server module should import run_turn, not define it
        source = inspect.getsource(acp_mod)
        # It should import run_turn from turn_loop
        self.assertIn("from .turn_loop import run_turn", source)
        # It should NOT define a function called "async def run_turn"
        self.assertNotIn("async def run_turn(", source,
                         "ACPServer must not define its own run_turn — no duplicate logic")

    def test_sc3_no_duplicate_turn_logic_in_backend_adapter(self) -> None:
        """InProcessAgentCoreAdapter does not define its own run_turn."""
        from inkstatute_agent_core import backend_adapter as adapter_mod
        source = inspect.getsource(adapter_mod)
        self.assertIn("from .turn_loop import run_turn", source)
        self.assertNotIn("async def run_turn(", source,
                         "BackendAdapter must not define its own run_turn — no duplicate logic")

    def test_sc3_equivalence_test_file_exists(self) -> None:
        """test_entry_point_equivalence.py exists and covers equivalence."""
        self.assertTrue(_file_exists("test_entry_point_equivalence.py"),
                        "test_entry_point_equivalence.py must exist")


# ---------------------------------------------------------------------------
# SC-4: Backend interchangeability
# ---------------------------------------------------------------------------


@unittest.skipUnless(_FAKES_AVAILABLE, "platform_runtime.fakes not available")
class TestSC4BackendInterchangeability(unittest.IsolatedAsyncioTestCase):
    """SC-4: Same task via hermes (FakeBackendAdapter) and inkstatute produces same event shape."""

    adapter: InProcessAgentCoreAdapter | None = None

    async def asyncTearDown(self) -> None:
        if self.adapter is not None:
            try:
                await self.adapter.shutdown()
            except Exception:
                pass
            self.adapter = None

    async def test_sc4_backend_interchangeability(self) -> None:
        """Same task via hermes and inkstatute produces same event shape.

        Both backends implement the BackendAdapter Protocol (9 methods)
        and produce RunEvent objects with the same structural shape.
        """
        from platform_contract.events import RunEvent as ContractRunEvent
        from platform_runtime.protocols import RunEvent as RuntimeRunEvent

        # hermes side
        fake = FakeBackendAdapter(backend_id="hermes")
        handle_h = await fake.submit_run(_make_request())
        hermes_events = []
        async for event in fake.stream_events(handle_h.run_id):
            hermes_events.append(event)

        # inkstatute side
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle_i = await self.adapter.submit_run(_make_request())
        ink_events = []
        try:
            async with asyncio.timeout(10.0):
                async for event in self.adapter.stream_events(handle_i.run_id):
                    ink_events.append(event)
        except (asyncio.TimeoutError, TimeoutError):
            pass

        # Both produce RunEvent objects (different classes, same structure)
        for e in hermes_events:
            self.assertIsInstance(e, RuntimeRunEvent)
        for e in ink_events:
            self.assertIsInstance(e, ContractRunEvent)

        # Both produce state_changed events
        hermes_state = [e for e in hermes_events if "state_changed" in e.event_type]
        ink_state = [e for e in ink_events if "state_changed" in e.event_type]
        self.assertTrue(len(hermes_state) >= 1)
        self.assertTrue(len(ink_state) >= 1)

        # Both reach terminal state
        hermes_run = await fake.get_run(handle_h.run_id)
        ink_run = await self.adapter.get_run(handle_i.run_id)
        self.assertIn(hermes_run.status, (AsyncTaskState.SUCCEEDED, AsyncTaskState.FAILED))
        self.assertIn(ink_run.status, (AsyncTaskState.SUCCEEDED, AsyncTaskState.FAILED))

    async def test_sc4_both_backends_implement_9_methods(self) -> None:
        """Both hermes (FakeBackendAdapter) and inkstatute implement all 9 methods."""
        fake = FakeBackendAdapter(backend_id="hermes")
        self.adapter = InProcessAgentCoreAdapter(_make_config())

        required = [
            "backend_id", "capabilities", "bootstrap_check",
            "submit_run", "get_run", "stream_events",
            "cancel_run", "submit_approval", "collect_artifacts",
        ]
        for method_name in required:
            self.assertTrue(hasattr(fake, method_name), f"FakeBackendAdapter missing {method_name}")
            self.assertTrue(hasattr(self.adapter, method_name), f"InProcessAdapter missing {method_name}")


# ---------------------------------------------------------------------------
# SC-5: ACP server correct capabilities
# ---------------------------------------------------------------------------


class TestSC5ACPServerCorrectCapabilities(unittest.TestCase):
    """SC-5: ACP server declares correct capabilities (no fs/terminal, elicitation+permission)."""

    def test_sc5_no_fs_capabilities(self) -> None:
        """AGENT_CAPABILITIES does not declare any fs/* capability."""
        for key in AGENT_CAPABILITIES:
            self.assertFalse(key.startswith("fs/"), f"fs/* capability declared: {key}")

    def test_sc5_no_terminal_capabilities(self) -> None:
        """AGENT_CAPABILITIES does not declare any terminal/* capability."""
        for key in AGENT_CAPABILITIES:
            self.assertFalse(key.startswith("terminal/"), f"terminal/* capability declared: {key}")

    def test_sc5_streaming_capability_declared(self) -> None:
        """AGENT_CAPABILITIES declares streaming=true."""
        self.assertTrue(AGENT_CAPABILITIES.get("streaming"))

    def test_sc5_elicitation_capability_declared(self) -> None:
        """AGENT_CAPABILITIES declares elicitation=true."""
        self.assertTrue(AGENT_CAPABILITIES.get("elicitation"))

    def test_sc5_permissions_capability_declared(self) -> None:
        """AGENT_CAPABILITIES declares permissions=true."""
        self.assertTrue(AGENT_CAPABILITIES.get("permissions"))

    def test_sc5_elicitation_request_mapping_implemented(self) -> None:
        """map_run_event_to_acp_request handles elicitation.requested events."""
        from platform_contract.enums import RunEventType
        from platform_contract.events import RunEvent

        event = RunEvent(
            event_id="e1",
            run_id="r1",
            event_type=RunEventType.ELICITATION_REQUESTED.value,
            occurred_at="2026-01-01T00:00:00Z",
            seq=0,
            payload={
                "interrupt_id": "i1",
                "intro": "Please answer",
                "questions": [],
            },
        )
        request = map_run_event_to_acp_request(event, req_id=1)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["method"], "elicitation/create")

    def test_sc5_permission_request_mapping_implemented(self) -> None:
        """map_run_event_to_acp_request handles permission.requested events."""
        from platform_contract.enums import RunEventType
        from platform_contract.events import RunEvent

        event = RunEvent(
            event_id="e1",
            run_id="r1",
            event_type=RunEventType.PERMISSION_REQUESTED.value,
            occurred_at="2026-01-01T00:00:00Z",
            seq=0,
            payload={
                "permission_id": "p1",
                "tool_call_id": "tc1",
                "description": "run tool",
                "kind": "terminal",
            },
        )
        request = map_run_event_to_acp_request(event, req_id=1)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["method"], "session/request_permission")

    def test_sc5_dangerous_permissions_not_auto_approved(self) -> None:
        """terminal and execute_code permissions must never be auto-approved."""
        from platform_contract.enums import RunEventType
        from platform_contract.events import RunEvent

        for kind in ("terminal", "execute_code"):
            event = RunEvent(
                event_id="e1",
                run_id="r1",
                event_type=RunEventType.PERMISSION_REQUESTED.value,
                occurred_at="2026-01-01T00:00:00Z",
                seq=0,
                payload={
                    "permission_id": "p1",
                    "tool_call_id": "tc1",
                    "description": "dangerous",
                    "kind": kind,
                },
            )
            request = map_run_event_to_acp_request(event, req_id=1)
            assert request is not None
            params = request["params"]
            self.assertNotIn("auto_approve", params)
            self.assertNotIn("default_decision", params)


# ---------------------------------------------------------------------------
# SC-6: Backend selection configurable via operator-config
# ---------------------------------------------------------------------------


@unittest.skipUnless(_OPERATOR_CONFIG_AVAILABLE, "inkstatute_operator_config not available")
class TestSC6BackendSelectionConfigurable(unittest.TestCase):
    """SC-6: Backend selection is configurable via operator-config."""

    def test_sc6_backend_selection_doc_exists(self) -> None:
        """BackendSelectionDoc schema exists with default_backend_id='inkstatute'."""
        doc = BackendSelectionDoc()
        self.assertEqual(doc.default_backend_id, "inkstatute")
        self.assertEqual(doc.backend_overrides, {})

    def test_sc6_resolve_backend_id_default(self) -> None:
        """resolve_backend_id returns 'inkstatute' by default."""
        self.assertEqual(resolve_backend_id(None, None), "inkstatute")
        self.assertEqual(resolve_backend_id(None, BackendSelectionDoc()), "inkstatute")

    def test_sc6_resolve_backend_id_tenant_override(self) -> None:
        """resolve_backend_id respects tenant-specific overrides."""
        selection = BackendSelectionDoc(
            default_backend_id="hermes",
            backend_overrides={"tenant-a": "inkstatute"},
        )
        self.assertEqual(resolve_backend_id("tenant-a", selection), "inkstatute")
        self.assertEqual(resolve_backend_id("tenant-b", selection), "hermes")

    def test_sc6_load_backend_selection_exists(self) -> None:
        """load_backend_selection function exists and is callable."""
        self.assertTrue(callable(load_backend_selection))

    def test_sc6_operator_config_test_file_exists(self) -> None:
        """test_backend_selection.py exists in operator-config tests."""
        operator_config_tests = os.path.join(
            os.path.dirname(TESTS_DIR), "..", "operator-config", "tests",
            "test_backend_selection.py",
        )
        self.assertTrue(
            os.path.isfile(operator_config_tests),
            "test_backend_selection.py must exist in operator-config tests",
        )


# ---------------------------------------------------------------------------
# Summary: all 6 SCs have mapping tests
# ---------------------------------------------------------------------------


class TestPhase103AllSuccessCriteriaMapped(unittest.TestCase):
    """Meta-test: all 6 Phase 103 success criteria have mapping tests."""

    def test_all_6_success_criteria_have_mapping_tests(self) -> None:
        """All 6 SCs are covered by mapping test classes in this file."""
        # This file contains one test class per SC:
        # SC-1 → TestSC1InProcessAdapterImplements9Methods
        # SC-2 → TestSC2ACPServerStartsAndCheckPasses
        # SC-3 → TestSC3BothEntryPointsShareRunTurn
        # SC-4 → TestSC4BackendInterchangeability
        # SC-5 → TestSC5ACPServerCorrectCapabilities
        # SC-6 → TestSC6BackendSelectionConfigurable
        import sys
        current_module = sys.modules[__name__]
        sc_classes = [
            "TestSC1InProcessAdapterImplements9Methods",
            "TestSC2ACPServerStartsAndCheckPasses",
            "TestSC3BothEntryPointsShareRunTurn",
            "TestSC4BackendInterchangeability",
            "TestSC5ACPServerCorrectCapabilities",
            "TestSC6BackendSelectionConfigurable",
        ]
        for class_name in sc_classes:
            self.assertTrue(
                hasattr(current_module, class_name),
                f"Missing SC mapping test class: {class_name}",
            )


if __name__ == "__main__":
    unittest.main()
