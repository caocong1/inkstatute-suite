"""Shared test fakes for WeCom event consumer tests.

Provides ``FakeGatewayClient`` and ``FakeWeComAdapter`` that implement the
same interfaces as the real classes but return canned responses — no
network required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from platform_runtime.protocols import (
    AckResponse,
    ChannelCapabilitySet,
    ChannelDelivery,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
)


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bot_events.json"


def load_fixture_events() -> list[dict[str, Any]]:
    """Load the ``bot_events.json`` fixture and return a list of event dicts."""
    with open(_FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# FakeGatewayClient
# ---------------------------------------------------------------------------


class FakeGatewayClient:
    """Fake Gateway HTTP client that returns canned responses.

    Implements the same interface as
    :class:`wecom_service.gateway_client.GatewayClient` but without any
    network calls.
    """

    def __init__(
        self,
        *,
        events: list[dict[str, Any]] | None = None,
    ) -> None:
        self._events = events if events is not None else load_fixture_events()
        self.create_session_called = False
        self.create_run_called = False
        self.download_artifact_called = False
        self.submit_elicitation_called = False
        self.submit_approval_called = False
        self.submit_feedback_called = False
        self.last_session_id: str | None = None
        self.last_run_body: dict[str, Any] | None = None

    def create_session(self, *, conversation_id: str) -> dict[str, Any]:
        self.create_session_called = True
        self.last_session_id = "sess-fake-1"
        return {"session_id": "sess-fake-1", "tenant_id": "default-tenant"}

    def create_run(
        self,
        *,
        turn: dict[str, Any],
        solution: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self.create_run_called = True
        self.last_run_body = {"turn": turn, "solution": solution, "session_id": session_id}
        return {"run_id": "run-fake-1", "status": "running"}

    def stream_events(
        self,
        run_id: str,
        *,
        last_event_id: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        for event in self._events:
            yield event

    def download_artifact(self, artifact_id: str) -> bytes:
        self.download_artifact_called = True
        return b"fake-artifact-content"

    def submit_elicitation(
        self,
        run_id: str,
        *,
        interrupt_id: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        self.submit_elicitation_called = True
        return {"status": "accepted"}

    def submit_approval(
        self,
        run_id: str,
        *,
        permission_id: str,
        decision: str,
    ) -> dict[str, Any]:
        self.submit_approval_called = True
        return {"status": "accepted"}

    def submit_feedback(
        self,
        *,
        run_id: str,
        feedback_data: dict[str, Any],
    ) -> dict[str, Any]:
        self.submit_feedback_called = True
        return {"status": "accepted"}


# ---------------------------------------------------------------------------
# FakeWeComAdapter
# ---------------------------------------------------------------------------


class FakeWeComAdapter:
    """Fake WeCom channel adapter that records all ``deliver()`` calls.

    Stores all deliveries in ``self.deliveries`` for assertions.
    """

    def __init__(self) -> None:
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return "wecom"

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=True,
            supports_cards=True,
            ack_deadline_ms=5000,
            verify_and_ack_support=True,
        )

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        return AckResponse(accepted=True, status_code=200)

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
        return InboundNormalized()

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        self.deliveries.append(delivery)
        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=True,
            idempotency_key=delivery.metadata.get("idempotency_key"),
            metadata={"channel_id": "wecom", "network_io": False},
        )

    async def health(self) -> ComponentHealth:
        return ComponentHealth(
            ok=True,
            component_id="wecom-fake",
            checked_at="2026-08-09T10:00:00Z",
        )
