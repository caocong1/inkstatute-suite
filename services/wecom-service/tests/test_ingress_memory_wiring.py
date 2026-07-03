"""Tests for WeComRuntimeIngress memory and observer wiring (MEM-07, MEM-16 closure)."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from platform_contract.events import AgentTurn
from platform_runtime import (
    ContractLogMemoryObserver,
    FakeMemory,
    InMemoryMemoryObserver,
    MemoryRetainInput,
    Run,
    RunRequest,
    SessionScope,
    SolutionBinding,
)
from platform_runtime import RunRuntime

from wecom_service.ingress_runtime import WeComRuntimeIngress
from wecom_service.memory_factory import build_memory_from_env


@dataclass(slots=True)
class RecordingRuntime:
    created: list[RunRequest] = field(default_factory=list)

    async def create_run(self, req: RunRequest) -> Run:
        self.created.append(req)
        return Run(
            run_id=f"created-{len(self.created):03d}",
            status="running",
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={"session_id": req.session_id},
        )


def _make_solution() -> SolutionBinding:
    return SolutionBinding(solution_id="test", version="1.0.0")


class IngressMemoryWiringTests(unittest.TestCase):
    def test_ingress_passes_memory_to_session_runtime(self) -> None:
        memory = FakeMemory()
        ingress = WeComRuntimeIngress(
            runtime=RecordingRuntime(),
            solution=_make_solution(),
            tenant_id="t",
            workspace_id="w",
            bot_instance_id="b",
            memory=memory,
        )
        self.assertIsNotNone(ingress.session_runtime.memory)

    def test_ingress_passes_memory_observer_to_session_runtime(self) -> None:
        observer = InMemoryMemoryObserver()
        memory = FakeMemory()
        ingress = WeComRuntimeIngress(
            runtime=RecordingRuntime(),
            solution=_make_solution(),
            tenant_id="t",
            workspace_id="w",
            bot_instance_id="b",
            memory=memory,
            memory_observer=observer,
        )
        self.assertIsNotNone(ingress.session_runtime.memory)

    def test_ingress_without_memory_defaults_to_none(self) -> None:
        ingress = WeComRuntimeIngress(
            runtime=RecordingRuntime(),
            solution=_make_solution(),
            tenant_id="t",
            workspace_id="w",
            bot_instance_id="b",
        )
        self.assertIsNone(ingress.session_runtime.memory)

    def test_ingress_passes_memory_policy(self) -> None:
        memory = FakeMemory()
        policy = object()  # sentinel
        ingress = WeComRuntimeIngress(
            runtime=RecordingRuntime(),
            solution=_make_solution(),
            tenant_id="t",
            workspace_id="w",
            bot_instance_id="b",
            memory=memory,
            memory_policy=policy,
        )
        self.assertIs(ingress.session_runtime.memory_policy, policy)


class ContractLogObserverWiringTests(unittest.TestCase):
    def test_contract_log_observer_wired_through_ingress(self) -> None:
        contract_log = MagicMock()
        contract_log.append = MagicMock()
        observer = ContractLogMemoryObserver(contract_log)
        memory = FakeMemory()

        ingress = WeComRuntimeIngress(
            runtime=RecordingRuntime(),
            solution=_make_solution(),
            tenant_id="t",
            workspace_id="w",
            bot_instance_id="b",
            memory=memory,
            memory_observer=observer,
        )

        self.assertIsNotNone(ingress.session_runtime.memory)


class MemoryFactoryTests(unittest.TestCase):
    def test_returns_none_when_base_url_unset(self) -> None:
        import os

        old = os.environ.pop("HINDSIGHT_BASE_URL", None)
        try:
            result = build_memory_from_env()
            self.assertIsNone(result)
        finally:
            if old is not None:
                os.environ["HINDSIGHT_BASE_URL"] = old

    def test_returns_hindsight_memory_when_configured(self) -> None:
        fake_module = MagicMock()
        fake_client = MagicMock()
        fake_module.Hindsight.return_value = fake_client

        result = build_memory_from_env(
            base_url="http://localhost:8888",
            api_key="test-key",
            hindsight_client_module=fake_module,
        )

        self.assertIsNotNone(result)
        fake_module.Hindsight.assert_called_once_with(
            base_url="http://localhost:8888", api_key="test-key"
        )

    def test_returns_none_when_base_url_empty(self) -> None:
        result = build_memory_from_env(base_url="", hindsight_client_module=MagicMock())
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
