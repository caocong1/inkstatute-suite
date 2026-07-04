"""Fast control-plane routing for follow-up turns during active tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import re
from typing import Any, Mapping


JsonObject = dict[str, Any]


class ActiveTaskRoute(StrEnum):
    STATUS_REQUEST = "status_request"
    CANCEL_REQUEST = "cancel_request"
    TASK_UPDATE = "task_update"
    NEW_PARALLEL_TASK = "new_parallel_task"
    UNSUPPORTED_UPDATE_ACK = "unsupported_update_ack"


@dataclass(frozen=True, slots=True)
class AdapterTaskCapabilities:
    supports_live_task_update: bool = False
    supports_cancel: bool = False
    supports_streaming_progress: bool = False
    supports_parallel_tasks: bool = False

    def as_metadata(self) -> JsonObject:
        return {
            "supports_live_task_update": self.supports_live_task_update,
            "supports_cancel": self.supports_cancel,
            "supports_streaming_progress": self.supports_streaming_progress,
            "supports_parallel_tasks": self.supports_parallel_tasks,
        }


@dataclass(frozen=True, slots=True)
class ActiveTaskRoutingDecision:
    route: ActiveTaskRoute
    task_id: str
    accepted_by_backend: bool
    notice_kind: str
    reason: str
    intent_class: str
    text_sha256_16: str
    text_length: int
    raw_payload_ref: str | None = None
    capability_decision: JsonObject = field(default_factory=dict)
    event_name: str = "channel_active_task_route"

    def as_event(self) -> JsonObject:
        return {
            "event": self.event_name,
            "task_id": self.task_id,
            "route": self.route.value,
            "intent_class": self.intent_class,
            "accepted_by_backend": self.accepted_by_backend,
            "notice_kind": self.notice_kind,
            "reason": self.reason,
            "text_sha256_16": self.text_sha256_16,
            "text_length": self.text_length,
            "raw_payload_ref": self.raw_payload_ref,
            "capability_decision": self.capability_decision,
            "privacy": "no_raw_payload_or_legal_text_stored",
        }


def route_active_task_turn(
    *,
    text: str | None,
    active_task: Mapping[str, Any],
    capabilities: AdapterTaskCapabilities,
    raw_payload_ref: str | None = None,
    event_name: str = "channel_active_task_route",
) -> ActiveTaskRoutingDecision:
    """Classify a follow-up turn without blocking on the active task."""

    content = str(text or "")
    task_id = str(active_task.get("task_id") or "unknown-task")
    intent = _classify_intent(content)
    text_sha = _sha16(content)
    capability_metadata = capabilities.as_metadata()

    if intent == ActiveTaskRoute.STATUS_REQUEST:
        return ActiveTaskRoutingDecision(
            route=ActiveTaskRoute.STATUS_REQUEST,
            task_id=task_id,
            accepted_by_backend=True,
            notice_kind="status_running",
            reason="status_query_answered_by_fast_control_plane",
            intent_class=intent.value,
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            capability_decision=capability_metadata,
            event_name=event_name,
        )

    if intent == ActiveTaskRoute.CANCEL_REQUEST:
        return ActiveTaskRoutingDecision(
            route=ActiveTaskRoute.CANCEL_REQUEST,
            task_id=task_id,
            accepted_by_backend=capabilities.supports_cancel,
            notice_kind="cancel_accepted" if capabilities.supports_cancel else "cancel_unsupported",
            reason="cancel_supported" if capabilities.supports_cancel else "adapter_does_not_support_cancel",
            intent_class=intent.value,
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            capability_decision=capability_metadata,
            event_name=event_name,
        )

    if intent == ActiveTaskRoute.NEW_PARALLEL_TASK and capabilities.supports_parallel_tasks:
        return ActiveTaskRoutingDecision(
            route=ActiveTaskRoute.NEW_PARALLEL_TASK,
            task_id=task_id,
            accepted_by_backend=True,
            notice_kind="parallel_task_accepted",
            reason="parallel_task_supported",
            intent_class=intent.value,
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            capability_decision=capability_metadata,
            event_name=event_name,
        )

    if intent == ActiveTaskRoute.NEW_PARALLEL_TASK:
        return ActiveTaskRoutingDecision(
            route=ActiveTaskRoute.UNSUPPORTED_UPDATE_ACK,
            task_id=task_id,
            accepted_by_backend=False,
            notice_kind="parallel_task_unsupported",
            reason="adapter_does_not_support_parallel_tasks",
            intent_class=intent.value,
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            capability_decision=capability_metadata,
            event_name=event_name,
        )

    if capabilities.supports_live_task_update:
        return ActiveTaskRoutingDecision(
            route=ActiveTaskRoute.TASK_UPDATE,
            task_id=task_id,
            accepted_by_backend=True,
            notice_kind="update_accepted",
            reason="live_task_update_supported",
            intent_class=intent.value,
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            capability_decision=capability_metadata,
            event_name=event_name,
        )

    return ActiveTaskRoutingDecision(
        route=ActiveTaskRoute.UNSUPPORTED_UPDATE_ACK,
        task_id=task_id,
        accepted_by_backend=False,
        notice_kind="update_received_not_applied",
        reason="adapter_does_not_support_live_task_update",
        intent_class=intent.value,
        text_sha256_16=text_sha,
        text_length=len(content),
        raw_payload_ref=raw_payload_ref,
        capability_decision=capability_metadata,
        event_name=event_name,
    )


def _classify_intent(text: str) -> ActiveTaskRoute:
    normalized = text.strip().lower()
    if not normalized:
        return ActiveTaskRoute.STATUS_REQUEST
    if _STATUS_RE.search(normalized):
        return ActiveTaskRoute.STATUS_REQUEST
    if _CANCEL_RE.search(normalized):
        return ActiveTaskRoute.CANCEL_REQUEST
    if _NEW_TASK_RE.search(normalized):
        return ActiveTaskRoute.NEW_PARALLEL_TASK
    return ActiveTaskRoute.TASK_UPDATE


_STATUS_RE = re.compile(r"(进度|状态|好了没|完成了吗|还要多久|处理到哪|怎么样了|status|progress|done yet)")
_CANCEL_RE = re.compile(r"(取消|停止|不用处理|先别|算了|cancel|stop)")
_NEW_TASK_RE = re.compile(r"(另外|另一个|新任务|再帮我|同时|顺便|another|new task|separate task)")


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "ActiveTaskRoute",
    "ActiveTaskRoutingDecision",
    "AdapterTaskCapabilities",
    "route_active_task_turn",
]
