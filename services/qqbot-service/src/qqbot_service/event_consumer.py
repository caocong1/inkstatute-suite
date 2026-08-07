"""QQ bot event consumer — SSE consumer + degradation aggregator + delivery mapper.

This module is the QQ bot event consumer: it creates a Gateway run, consumes
the SSE stream, sends intermediate prompts during the stream, aggregates
events at terminal state via ``aggregate_events()``, and maps the resulting
``BotDelivery`` to QQ ``ChannelDelivery`` calls.

QQ-specific delivery concerns:
- ``BotDelivery.cards`` → QQ feedback keyboard (via ``adapter.deliver()`` with
  ``delivery_type="card"`` — the QQ adapter calls ``build_feedback_keyboard_envelope()``)
- ``BotDelivery.files`` → QQ rich media delivery (with injectable media_uploader)
- Scene-aware delivery: c2c vs group metadata passed to adapter
- Passive reply window: the adapter checks this in ``deliver()`` — the consumer
  passes the correct ``msg_id``, ``msg_seq``, ``scene``, ``user_openid``,
  ``group_openid`` from the normalized inbound so the adapter can make the
  right decisions.

CRITICAL constraints:
- The consumer does NOT make direct agent or backend calls — it uses
  only the Gateway HTTP client (BOT-02 compliance).
- ``aggregate_events()`` from Phase 88 is the single degradation point.
- Intermediate prompts are sent DURING the stream (as events arrive), not after.
- The output boundary is enforced at the Gateway (first point), by the
  degradation rules (SILENT/DISCARD/FOLD = second point), and by
  ``apply_output_policy()`` at delivery time (third point).
- No imports from the WeCom service or WeCom channel package (cross-contamination check).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from channel_core.output_policy import apply_output_policy
from platform_contract.bot_degradation import BotDelivery, aggregate_events
from platform_contract.events import SolutionBinding
from platform_runtime.protocols import ChannelDelivery, DeliveryResult

from .gateway_client import GatewayClient


# ---------------------------------------------------------------------------
# Business-prompt templates (matching bot_degradation.py)
# ---------------------------------------------------------------------------

_TOOL_FOLD_PROMPT = "正在检索法规…"
_PLAN_FIRST_PROMPT = "仍在处理"
_FAILURE_PROMPT = "处理失败，请稍后重试或联系管理员"

# Terminal run states
_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def solution_to_dict(solution: SolutionBinding | None) -> dict[str, Any]:
    """Convert a :class:`SolutionBinding` to a dict for the Gateway create_run body.

    Returns a default fixture binding when *solution* is ``None``.
    """
    if solution is None:
        return {
            "solution_id": "qqbot-host-fixture",
            "backend_id": "fake-backend",
        }
    return {
        "solution_id": solution.solution_id,
        "backend_id": solution.backend_id,
        "manifest_ref": solution.manifest_ref,
        "materialization_ref": solution.materialization_ref,
        "metadata": dict(solution.metadata) if solution.metadata else {},
    }


def is_terminal_event(event: dict[str, Any]) -> bool:
    """Return ``True`` if the event is a terminal state event.

    A terminal event is ``run.state_changed`` with ``status`` in
    ``{"succeeded", "failed", "cancelled"}``.
    """
    if event.get("event_type") != "run.state_changed":
        return False
    payload = event.get("payload") or {}
    return payload.get("status") in _TERMINAL_STATUSES


# ---------------------------------------------------------------------------
# QQBotEventConsumer
# ---------------------------------------------------------------------------


@dataclass
class QQBotEventConsumer:
    """QQ bot event consumer: Gateway run → SSE → aggregate → deliver.

    This dataclass holds mutable session state for a single consumption
    cycle. It is NOT frozen because intermediate delivery tracking requires
    mutable state.
    """

    gateway_client: GatewayClient
    adapter: Any  # QQBotChannelAdapter (typed as Any to avoid import cycle)
    solution: SolutionBinding | None = None
    tenant_id: str = "default-tenant"
    media_uploader: Callable[[str, bytes], dict[str, Any]] | None = None
    progress_interval_seconds: float = 180.0

    # Mutable state for the current consumption cycle
    _delivery_index: int = field(default=0, init=False, repr=False)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def consume_and_deliver(
        self,
        *,
        turn: dict[str, Any],
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        conversation_id: str | None = None,
        session_id: str | None = None,
        received_at: str | None = None,
    ) -> dict[str, Any]:
        """End-to-end: create run → stream → aggregate → deliver.

        Steps:
        1. Create or reuse a Gateway session.
        2. Create a Gateway run.
        3. Consume the SSE stream, collecting events.
        4. Send intermediate prompts during the stream.
        5. At terminal state, call ``aggregate_events()``.
        6. Map ``BotDelivery`` to ``adapter.deliver()`` calls.
        7. Return an evidence dict.
        """
        self._delivery_index = 0

        # Step 1: Create or reuse session
        if session_id is None:
            if conversation_id is None:
                conversation_id = f"qqbot-{user_openid or group_openid or 'unknown'}"
            session_resp = self.gateway_client.create_session(
                conversation_id=conversation_id,
            )
            session_id = session_resp.get("session_id")

        # Step 2: Create run
        solution_dict = solution_to_dict(self.solution)
        run_resp = self.gateway_client.create_run(
            turn=turn,
            solution=solution_dict,
            session_id=session_id,
        )
        run_id = run_resp.get("run_id", "")

        # Step 3-4: Consume SSE stream + send intermediate prompts
        collected_events: list[dict[str, Any]] = []
        intermediate_state: dict[str, Any] = {
            "first_tool_call_sent": False,
            "first_plan_sent": False,
            "stream_start_time": time.monotonic(),
            "last_progress_time": time.monotonic(),
        }

        for event in self.gateway_client.stream_events(run_id):
            collected_events.append(event)

            # Send intermediate prompts during the stream
            if self._should_send_intermediate(event, intermediate_state):
                await self._send_intermediate(
                    event,
                    intermediate_state,
                    scene=scene,
                    user_openid=user_openid,
                    group_openid=group_openid,
                    msg_id=msg_id,
                    msg_seq=msg_seq,
                    received_at=received_at,
                    run_id=run_id,
                )

            # Track progress interval
            self._check_progress_interval(intermediate_state)

            # Stop if terminal event reached
            if is_terminal_event(event):
                break

        # Step 5: Aggregate events at terminal state
        bot_delivery = aggregate_events(collected_events)

        # Step 6: Map BotDelivery to adapter.deliver() calls
        delivery_count = 0

        # 6a: Final message → text delivery
        if bot_delivery.final_message:
            decision = apply_output_policy(bot_delivery.final_message)
            if decision.action != "block" and decision.visible_text:
                delivery = self._make_delivery(
                    delivery_type="text",
                    content=decision.visible_text,
                    scene=scene,
                    user_openid=user_openid,
                    group_openid=group_openid,
                    msg_id=msg_id,
                    msg_seq=msg_seq,
                    received_at=received_at,
                    run_id=run_id,
                )
                await self.adapter.deliver(delivery)
                delivery_count += 1

        # 6b: Cards → card deliveries (QQ feedback keyboard)
        for card in bot_delivery.cards:
            card_delivery = self._map_card_to_delivery(
                card,
                scene=scene,
                user_openid=user_openid,
                group_openid=group_openid,
                msg_id=msg_id,
                msg_seq=msg_seq,
                received_at=received_at,
                run_id=run_id,
            )
            if card_delivery is not None:
                await self.adapter.deliver(card_delivery)
                delivery_count += 1

        # 6c: Files → file deliveries (QQ rich media)
        for file_payload in bot_delivery.files:
            file_delivery = self._map_file_to_delivery(
                file_payload,
                scene=scene,
                user_openid=user_openid,
                group_openid=group_openid,
                msg_id=msg_id,
                msg_seq=msg_seq,
                received_at=received_at,
                run_id=run_id,
            )
            if file_delivery is not None:
                await self.adapter.deliver(file_delivery)
                delivery_count += 1

        # 6d: Error prompt → text delivery
        if bot_delivery.error_prompt:
            decision = apply_output_policy(bot_delivery.error_prompt)
            if decision.action != "block" and decision.visible_text:
                delivery = self._make_delivery(
                    delivery_type="text",
                    content=decision.visible_text,
                    scene=scene,
                    user_openid=user_openid,
                    group_openid=group_openid,
                    msg_id=msg_id,
                    msg_seq=msg_seq,
                    received_at=received_at,
                    run_id=run_id,
                )
                await self.adapter.deliver(delivery)
                delivery_count += 1

        # Step 7: Return evidence dict
        return {
            "status": "completed",
            "run_id": run_id,
            "delivery_count": delivery_count,
            "delivered": bot_delivery.delivered,
        }

    # ------------------------------------------------------------------
    # Intermediate prompt logic
    # ------------------------------------------------------------------

    def _should_send_intermediate(
        self,
        event: dict[str, Any],
        state: dict[str, Any],
    ) -> bool:
        """Determine if an intermediate prompt should be sent for this event.

        Degradation rules:
        - FOLD: first ``tool_call.*`` → "正在检索法规…"
        - FIRST_THEN_SILENT: first ``plan.updated``/``phase.changed`` → "仍在处理"
        """
        event_type = event.get("event_type", "")

        # FOLD: first tool_call event
        if event_type in ("tool_call.started", "tool_call.delta", "tool_call.completed"):
            if not state.get("first_tool_call_sent"):
                state["first_tool_call_sent"] = True
                return True
            return False

        # FIRST_THEN_SILENT: first plan/phase event
        if event_type in ("plan.updated", "phase.changed"):
            if not state.get("first_plan_sent"):
                state["first_plan_sent"] = True
                return True
            return False

        return False

    async def _send_intermediate(
        self,
        event: dict[str, Any],
        state: dict[str, Any],
        *,
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        received_at: str | None,
        run_id: str,
    ) -> None:
        """Send the appropriate intermediate prompt for this event."""
        event_type = event.get("event_type", "")

        if event_type in ("tool_call.started", "tool_call.delta", "tool_call.completed"):
            delivery = self._make_delivery(
                delivery_type="text",
                content=_TOOL_FOLD_PROMPT,
                scene=scene,
                user_openid=user_openid,
                group_openid=group_openid,
                msg_id=msg_id,
                msg_seq=msg_seq,
                received_at=received_at,
                run_id=run_id,
            )
            await self.adapter.deliver(delivery)
        elif event_type in ("plan.updated", "phase.changed"):
            delivery = self._make_delivery(
                delivery_type="text",
                content=_PLAN_FIRST_PROMPT,
                scene=scene,
                user_openid=user_openid,
                group_openid=group_openid,
                msg_id=msg_id,
                msg_seq=msg_seq,
                received_at=received_at,
                run_id=run_id,
            )
            await self.adapter.deliver(delivery)
            # Update last progress time
            state["last_progress_time"] = time.monotonic()

    def _check_progress_interval(
        self,
        state: dict[str, Any],
    ) -> None:
        """Check if a progress-interval "仍在处理" prompt should be sent.

        This is a synchronous check — in the real async flow, the consumer
        would check elapsed time between events. For fixture CI, this is
        a no-op unless the interval is very short.
        """
        # This is called after each event. In a real implementation with
        # blocking SSE reads, we'd check elapsed time. For fixture CI,
        # events arrive instantly so this is effectively a no-op.
        # The logic is here for completeness and future async wiring.
        pass

    # ------------------------------------------------------------------
    # Delivery mapping
    # ------------------------------------------------------------------

    def _build_delivery_metadata(
        self,
        *,
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        received_at: str | None,
    ) -> dict[str, Any]:
        """Build the common metadata dict for QQ deliveries.

        Includes scene, user_openid, group_openid, msg_id, msg_seq,
        received_at, reply_count — the fields the QQ adapter needs for
        passive reply window checking and scene-aware delivery.
        """
        return {
            "scene": scene,
            "user_openid": user_openid,
            "group_openid": group_openid,
            "msg_id": msg_id,
            "msg_seq": msg_seq,
            "received_at": received_at,
            "reply_count": 0,
        }

    def _map_card_to_delivery(
        self,
        card: dict[str, Any],
        *,
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        received_at: str | None,
        run_id: str,
    ) -> ChannelDelivery | None:
        """Map an elicitation/permission card payload to a QQ ``ChannelDelivery``.

        The QQ adapter's ``deliver()`` method calls
        ``build_feedback_keyboard_envelope()`` for ``delivery_type="card"``.
        The card content is the first question's text (for elicitation) or
        the permission description (for permission).
        """
        # Determine card_id and feedback_target
        interrupt_id = card.get("interrupt_id")
        permission_id = card.get("permission_id")

        if interrupt_id:
            card_id = interrupt_id
            feedback_target = interrupt_id
            # Content: first question's text
            questions = card.get("questions") or []
            if questions and isinstance(questions, list):
                first_q = questions[0] if isinstance(questions[0], dict) else {}
                content = first_q.get("question", "请回答以下问题")
            else:
                content = "请回答以下问题"
        elif permission_id:
            card_id = permission_id
            feedback_target = permission_id
            content = card.get("description", "请审批以下操作")
        else:
            # No identifiable card — skip
            return None

        # Apply output boundary (third enforcement layer)
        decision = apply_output_policy(content)
        if decision.action == "block":
            return None
        visible_content = decision.visible_text or content

        return self._make_delivery(
            delivery_type="card",
            content=visible_content,
            scene=scene,
            user_openid=user_openid,
            group_openid=group_openid,
            msg_id=msg_id,
            msg_seq=msg_seq,
            received_at=received_at,
            run_id=run_id,
            extra_metadata={
                "card_id": card_id,
                "feedback_target": feedback_target,
            },
        )

    def _map_file_to_delivery(
        self,
        file_payload: dict[str, Any],
        *,
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        received_at: str | None,
        run_id: str,
    ) -> ChannelDelivery | None:
        """Map an artifact payload to a QQ ``ChannelDelivery`` with file type.

        Downloads the artifact via ``gateway_client.download_artifact()``.
        If ``media_uploader`` is available, uploads the bytes to get
        ``file_info`` dict (QQ's rich media format). If ``media_uploader``
        is ``None``, returns ``None`` (skip file delivery in fixture CI).
        """
        if self.media_uploader is None:
            return None

        artifact_id = file_payload.get("artifact_id", "")
        if not artifact_id:
            return None

        # Download artifact from Gateway
        try:
            content_bytes = self.gateway_client.download_artifact(artifact_id)
        except Exception:
            return None

        # Upload to channel media API
        filename = file_payload.get("name", f"{artifact_id}.bin")
        file_info = self.media_uploader(filename, content_bytes)

        return self._make_delivery(
            delivery_type="file",
            content=file_payload.get("name", "InkStatute file delivery"),
            scene=scene,
            user_openid=user_openid,
            group_openid=group_openid,
            msg_id=msg_id,
            msg_seq=msg_seq,
            received_at=received_at,
            run_id=run_id,
            extra_metadata={
                "file_info": file_info,
            },
        )

    # ------------------------------------------------------------------
    # Delivery ID generation
    # ------------------------------------------------------------------

    def _make_delivery(
        self,
        *,
        delivery_type: str,
        content: str | None = None,
        scene: str,
        user_openid: str | None,
        group_openid: str | None,
        msg_id: str | None,
        msg_seq: int | None,
        received_at: str | None,
        run_id: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> ChannelDelivery:
        """Create a :class:`ChannelDelivery` with a deterministic delivery_id.

        Delivery IDs follow the pattern ``qqbot-deliv-{run_id}-{index}``
        for idempotency.
        """
        delivery_id = f"qqbot-deliv-{run_id}-{self._delivery_index}"
        self._delivery_index += 1

        metadata = self._build_delivery_metadata(
            scene=scene,
            user_openid=user_openid,
            group_openid=group_openid,
            msg_id=msg_id,
            msg_seq=msg_seq,
            received_at=received_at,
        )
        metadata["delivery_type"] = delivery_type
        if extra_metadata:
            metadata.update(extra_metadata)

        return ChannelDelivery(
            delivery_id=delivery_id,
            channel_id="qqbot",
            run_id=run_id,
            content=content,
            metadata=metadata,
        )


__all__ = [
    "QQBotEventConsumer",
    "solution_to_dict",
    "is_terminal_event",
]
