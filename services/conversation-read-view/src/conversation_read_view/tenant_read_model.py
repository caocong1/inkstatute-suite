"""Tenant-scoped wrapper for ContractLogReadModel.

Wraps a ``ContractLogReadModel`` delegate and filters results by ``tenant_id``
when a ``ScopedQueryFilter`` is active.  When the filter is ``None`` or
``active=False`` (disabled mode / ``multi_tenant_enabled=False``), all calls
delegate directly — preserving v1.6 behavior with zero regression.

The ``tenant_id`` is expected at the top level of the ``agent_turn`` event dict
(injected by ``TenantScopedContractLogStore.append()``).  The read model stores
``agent_turn`` as a ``JsonObject`` inside ``ConversationTurnView``, so filtering
checks ``turn["agent_turn"].get("tenant_id")`` for conversations and tasks.
"""

from __future__ import annotations

from typing import Any

from .models import JsonObject
from .read_model import ContractLogReadModel


def _extract_tenant_id_from_conversation(conv: JsonObject) -> str | None:
    """Extract tenant_id from a conversation dict's first turn agent_turn."""
    turns = conv.get("turns")
    if isinstance(turns, list) and turns:
        first_turn = turns[0]
        if isinstance(first_turn, dict):
            agent_turn = first_turn.get("agent_turn")
            if isinstance(agent_turn, dict):
                tid = agent_turn.get("tenant_id")
                if isinstance(tid, str) and tid:
                    return tid
    return None


def _extract_tenant_id_from_task(task: JsonObject) -> str | None:
    """Extract tenant_id from a task dict.

    ``TenantScopedContractLogStore.append()`` injects ``tenant_id`` at the
    top level of every event dict.  ``TaskView.to_dict()`` exposes
    ``route_decision``, ``execution_trace``, and ``agent_result`` (but not
    ``agent_turn`` directly).  We check each of these for a top-level
    ``tenant_id`` field.
    """
    for key in ("agent_result", "execution_trace", "route_decision"):
        event = task.get(key)
        if isinstance(event, dict):
            tid = event.get("tenant_id")
            if isinstance(tid, str) and tid:
                return tid
    return None


class TenantScopedContractLogReadModel:
    """Wraps ``ContractLogReadModel`` with tenant_id filtering.

    When ``tenant_filter`` is ``None`` or not active, all methods delegate
    directly to the wrapped read model (v1.6 behavior).  When active, results
    are filtered by ``tenant_filter.tenant_id`` — non-matching records are
    invisible (returned as ``None`` or excluded from lists).
    """

    def __init__(self, delegate: ContractLogReadModel) -> None:
        self._delegate = delegate

    @property
    def issues(self) -> list[Any]:
        """Delegate issues property."""
        return self._delegate.issues

    def get_conversation(
        self,
        conversation_id: str,
        *,
        tenant_filter: Any = None,
    ) -> JsonObject | None:
        """Get a conversation by ID, filtered by tenant when active."""
        result = self._delegate.get_conversation(conversation_id)
        if result is None:
            return None
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            tid = _extract_tenant_id_from_conversation(result)
            if tid != tenant_filter.tenant_id:
                return None
        return result

    def get_task(
        self,
        task_id: str,
        *,
        tenant_filter: Any = None,
    ) -> JsonObject | None:
        """Get a task by ID, filtered by tenant when active."""
        result = self._delegate.get_task(task_id)
        if result is None:
            return None
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            tid = _extract_tenant_id_from_task(result)
            if tid != tenant_filter.tenant_id:
                return None
        return result

    def get_task_by_trace_id(
        self,
        trace_id: str,
        *,
        tenant_filter: Any = None,
    ) -> JsonObject | None:
        """Get a task by trace ID, filtered by tenant when active."""
        result = self._delegate.get_task_by_trace_id(trace_id)
        if result is None:
            return None
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            tid = _extract_tenant_id_from_task(result)
            if tid != tenant_filter.tenant_id:
                return None
        return result

    def list_conversations(
        self,
        *,
        time_from: str | None = None,
        time_to: str | None = None,
        user_id: str | None = None,
        channel: str | None = None,
        tenant_filter: Any = None,
    ) -> list[tuple[str, str, JsonObject]]:
        """List conversations, filtered by tenant when active."""
        results = self._delegate.list_conversations(
            time_from=time_from,
            time_to=time_to,
            user_id=user_id,
            channel=channel,
        )
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            results = [
                entry for entry in results
                if _extract_tenant_id_from_conversation(entry[2]) == tenant_filter.tenant_id
            ]
        return results

    def list_tasks(
        self,
        *,
        time_from: str | None = None,
        time_to: str | None = None,
        user_id: str | None = None,
        channel: str | None = None,
        status: str | None = None,
        tenant_filter: Any = None,
    ) -> list[tuple[str, str, JsonObject]]:
        """List tasks, filtered by tenant when active."""
        results = self._delegate.list_tasks(
            time_from=time_from,
            time_to=time_to,
            user_id=user_id,
            channel=channel,
            status=status,
        )
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            results = [
                entry for entry in results
                if _extract_tenant_id_from_task(entry[2]) == tenant_filter.tenant_id
            ]
        return results


__all__ = ["TenantScopedContractLogReadModel"]
