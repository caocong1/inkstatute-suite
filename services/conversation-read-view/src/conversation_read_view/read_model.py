"""Contract log read model for read-only conversation views."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import (
    ConversationTurnView,
    ConversationView,
    EventReference,
    JsonObject,
    ReadModelIssue,
    TaskView,
)
from .privacy import scrub_contract_payload


def load_records_from_jsonl(path: str | Path) -> list[Any]:
    """Load schema-validated contract event records from a JSONL file."""

    from contract_test_suite.event_stream_replay import load_event_stream

    return load_event_stream(Path(path))


class ContractLogReadModel:
    """Derived indexes over contract event records."""

    def __init__(
        self,
        *,
        conversations: dict[str, ConversationView],
        tasks: dict[str, TaskView],
        trace_to_task_id: dict[str, str],
        issues: list[ReadModelIssue],
        trace_events: dict[str, list["_Record"]] | None = None,
        turn_to_trace: dict[str, str] | None = None,
        all_records: list["_Record"] | None = None,
    ) -> None:
        self._conversations = dict(conversations)
        self._tasks = dict(tasks)
        self._trace_to_task_id = dict(trace_to_task_id)
        self._trace_events = dict(trace_events) if trace_events else {}
        self._turn_to_trace = dict(turn_to_trace) if turn_to_trace else {}
        self._all_records = list(all_records) if all_records else []
        self.issues = list(issues)

    @classmethod
    def from_records(cls, records: Iterable[Any]) -> "ContractLogReadModel":
        normalized = sorted((_coerce_record(record) for record in records), key=_record_sort_key)
        events_by_turn: dict[str, dict[str, list[tuple[_Record, JsonObject]]]] = defaultdict(lambda: defaultdict(list))
        feedback_by_turn: dict[str, list[tuple[_Record, JsonObject]]] = defaultdict(list)
        issues: list[ReadModelIssue] = []

        for record in normalized:
            event = scrub_contract_payload(record.event)
            turn_id = _string(event.get("turn_id"))
            if turn_id is None:
                issues.append(
                    ReadModelIssue(
                        code="missing_turn_id",
                        message=f"{record.event_key} record has no turn_id",
                        event_key=record.event_key,
                    )
                )
                continue
            if record.event_key == "feedback_event":
                feedback_by_turn[turn_id].append((record, event))
            else:
                events_by_turn[turn_id][record.event_key].append((record, event))

        turns_by_conversation: dict[str, list[ConversationTurnView]] = defaultdict(list)
        tasks: dict[str, TaskView] = {}
        trace_to_task_id: dict[str, str] = {}
        trace_id_by_turn: dict[str, str] = {}

        for turn_id, event_groups in events_by_turn.items():
            agent_turn_items = event_groups.get("agent_turn", [])
            if not agent_turn_items:
                issues.append(
                    ReadModelIssue(
                        code="missing_agent_turn",
                        message="events for turn have no AgentTurn anchor",
                        turn_id=turn_id,
                    )
                )
                continue

            turn_record, agent_turn = agent_turn_items[0]
            route_record, route_decision = _first_event(event_groups, "route_decision")
            trace_record, execution_trace = _first_event(event_groups, "execution_trace")
            result_record, agent_result = _first_event(event_groups, "agent_result")
            feedback_events = [event for _, event in feedback_by_turn.get(turn_id, [])]
            task_id, fallback_source = _task_id_for(agent_turn, execution_trace, agent_result, turn_id)
            missing = _missing_associations(route_decision, execution_trace, agent_result)
            event_refs = [
                _event_reference(record)
                for record in (turn_record, route_record, trace_record, result_record)
                if record is not None
            ]
            event_refs.extend(_event_reference(record) for record, _ in feedback_by_turn.get(turn_id, []))

            conversation_id = _string(agent_turn.get("conversation_id")) or "unknown-conversation"
            turn_view = ConversationTurnView(
                turn_id=turn_id,
                conversation_id=conversation_id,
                task_id=task_id,
                agent_turn=agent_turn,
                route_decision=route_decision,
                execution_trace=execution_trace,
                agent_result=agent_result,
                feedback_events=feedback_events,
                event_refs=event_refs,
                missing_associations=missing,
                fallback_source=fallback_source,
            )
            turns_by_conversation[conversation_id].append(turn_view)
            task_view = TaskView(task_id=task_id, turn=turn_view)
            tasks[task_id] = task_view
            tasks[turn_id] = task_view

            trace_id = _string((execution_trace or {}).get("trace_id"))
            if trace_id is None and isinstance((agent_result or {}).get("metadata"), Mapping):
                trace_id = _string(agent_result["metadata"].get("trace_id"))  # type: ignore[index]
            if trace_id is not None:
                trace_to_task_id[trace_id] = task_id
                trace_id_by_turn[turn_id] = trace_id

        conversations = {
            conversation_id: ConversationView(conversation_id=conversation_id, turns=turns, issues=issues)
            for conversation_id, turns in turns_by_conversation.items()
        }

        trace_events: dict[str, list[_Record]] = defaultdict(list)
        turn_to_trace: dict[str, str] = {}
        for record in normalized:
            event = record.event
            turn_id = _string(event.get("turn_id"))
            if turn_id is None:
                continue
            resolved_trace_id = trace_id_by_turn.get(turn_id)
            if resolved_trace_id is not None:
                trace_events[resolved_trace_id].append(record)
                turn_to_trace[turn_id] = resolved_trace_id

        return cls(
            conversations=conversations,
            tasks=tasks,
            trace_to_task_id=trace_to_task_id,
            issues=issues,
            trace_events=dict(trace_events),
            turn_to_trace=turn_to_trace,
            all_records=normalized,
        )

    def get_conversation(self, conversation_id: str) -> JsonObject | None:
        conversation = self._conversations.get(conversation_id)
        return conversation.to_dict() if conversation is not None else None

    def get_task(self, task_id: str) -> JsonObject | None:
        task = self._tasks.get(task_id)
        return task.to_dict() if task is not None else None

    def get_task_by_trace_id(self, trace_id: str) -> JsonObject | None:
        task_id = self._trace_to_task_id.get(trace_id)
        return self.get_task(task_id) if task_id is not None else None

    def get_trace_reconstruction(self, trace_id: str) -> JsonObject | None:
        """Reconstruct all events sharing ``trace_id`` in occurrence order.

        Returns ``None`` when no events are found for the given ``trace_id``.
        The response includes ``metadata.reconstruction_complete=True`` when an
        ``execution_trace`` event is present in the reconstructed set.
        """

        records = self._trace_events.get(trace_id)
        if not records:
            task_id = self._trace_to_task_id.get(trace_id)
            if task_id is None:
                return None
            resolved_trace_id = self._turn_to_trace.get(task_id)
            if resolved_trace_id is not None:
                records = self._trace_events.get(resolved_trace_id)
            if not records:
                return None

        ordered = sorted(records, key=_record_sort_key)
        turn_id = ""
        task_id = ""
        conversation_id = ""
        agent_turn_record = next((r for r in ordered if r.event_key == "agent_turn"), None)
        if agent_turn_record is not None:
            turn_id = _string(agent_turn_record.event.get("turn_id")) or ""
            conversation_id = _string(agent_turn_record.event.get("conversation_id")) or ""
            task_id = self._trace_to_task_id.get(trace_id, turn_id)
        else:
            first = ordered[0]
            turn_id = _string(first.event.get("turn_id")) or ""
            task_id = self._trace_to_task_id.get(trace_id, turn_id)
            conversation_id = _string(first.event.get("conversation_id")) or ""

        has_execution_trace = any(r.event_key == "execution_trace" for r in ordered)
        return {
            "trace_id": trace_id,
            "turn_id": turn_id,
            "task_id": task_id,
            "conversation_id": conversation_id,
            "events": [
                {
                    "event_key": record.event_key,
                    "occurred_at": record.occurred_at,
                    "seq": record.seq,
                    "event": record.event,
                }
                for record in ordered
            ],
            "metadata": {
                "derived_from_contract_log": True,
                "event_count": len(ordered),
                "reconstruction_complete": has_execution_trace,
            },
        }

    def list_conversations(
        self,
        *,
        time_from: str | None = None,
        time_to: str | None = None,
        user_id: str | None = None,
        channel: str | None = None,
    ) -> list[tuple[str, str, JsonObject]]:
        """Return filtered, sorted conversations as ``(sort_key, occurred_at, dict)`` tuples.

        Filters combine with AND semantics. Time-range filters are inclusive on
        both ends. Sort key is ``conversation_id`` for deterministic ordering.
        """

        results: list[tuple[str, str, JsonObject]] = []
        for conversation in self._conversations.values():
            occurred_at = _conversation_occurred_at(conversation)
            if time_from is not None and occurred_at < time_from:
                continue
            if time_to is not None and occurred_at > time_to:
                continue
            if user_id is not None and not _conversation_has_user(conversation, user_id):
                continue
            if channel is not None and not _conversation_has_channel(conversation, channel):
                continue
            results.append((conversation.conversation_id, occurred_at, conversation.to_dict()))
        results.sort(key=lambda entry: (entry[0], entry[1]))
        return results

    def list_tasks(
        self,
        *,
        time_from: str | None = None,
        time_to: str | None = None,
        user_id: str | None = None,
        channel: str | None = None,
        status: str | None = None,
    ) -> list[tuple[str, str, JsonObject]]:
        """Return filtered, sorted, deduplicated tasks as ``(sort_key, occurred_at, dict)`` tuples.

        The internal ``_tasks`` dict is keyed by both ``task_id`` and ``turn_id``
        (aliases). This method emits each unique task once (keyed by
        ``task_id``). Filters combine with AND semantics.
        """

        seen: set[str] = set()
        results: list[tuple[str, str, JsonObject]] = []
        for task in self._tasks.values():
            if task.task_id in seen:
                continue
            seen.add(task.task_id)
            occurred_at = _task_occurred_at(task)
            if time_from is not None and occurred_at < time_from:
                continue
            if time_to is not None and occurred_at > time_to:
                continue
            task_dict = task.to_dict()
            if user_id is not None and not _task_has_user(task, user_id):
                continue
            if channel is not None and not _task_has_channel(task, channel):
                continue
            if status is not None and task_dict.get("status") != status:
                continue
            results.append((task.task_id, occurred_at, task_dict))
        results.sort(key=lambda entry: (entry[0], entry[1]))
        return results

    def list_audit_events(
        self,
        *,
        event_type: str | None = None,
        tenant_filter: Any = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Return AgentTurn and FeedbackEvent records as ``(sort_key, occurred_at, item)`` tuples.

        Sorted reverse-chronologically (occurred_at descending, then seq
        descending).  ``event_type`` filters to ``"agent_turn"`` or
        ``"feedback_event"``; ``None`` returns both.  ``tenant_filter`` is
        applied by checking ``record.event.get("tenant_id")`` when active.
        Each item dict contains: ``timestamp``, ``event_type``,
        ``session_id``, ``trace_id``, ``turn_id``, and ``event`` (scrubbed
        payload).  Records with forbidden keys are excluded (fail-closed).
        """

        audit_keys = {"agent_turn", "feedback_event"}
        results: list[tuple[str, str, dict[str, Any]]] = []
        for record in self._all_records:
            if record.event_key not in audit_keys:
                continue
            if event_type is not None and record.event_key != event_type:
                continue
            if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
                record_tenant = record.event.get("tenant_id")
                if record_tenant != tenant_filter.tenant_id:
                    continue
            turn_id = _string(record.event.get("turn_id")) or ""
            conversation_id = _string(record.event.get("conversation_id")) or ""
            trace_id = self._turn_to_trace.get(turn_id, "")
            try:
                scrubbed_event = scrub_contract_payload(record.event)
            except ValueError:
                # Fail-closed: forbidden key present, exclude the record.
                continue
            item = {
                "timestamp": record.occurred_at,
                "event_type": record.event_key,
                "session_id": conversation_id,
                "trace_id": trace_id,
                "turn_id": turn_id,
                "event": scrubbed_event,
            }
            sort_key = f"{record.occurred_at}|{record.seq}"
            results.append((sort_key, record.occurred_at, item))
        # Reverse-chronological: occurred_at descending, then seq descending.
        results.sort(key=lambda entry: (entry[1], entry[0]), reverse=True)
        return results


def _conversation_occurred_at(conversation: ConversationView) -> str:
    """Compute the occurred_at timestamp for a conversation from its first turn."""

    if conversation.turns:
        first_turn = conversation.turns[0]
        received_at = _string(first_turn.agent_turn.get("received_at"))
        if received_at is not None:
            return received_at
        ref_times = [ref.occurred_at for ref in first_turn.event_refs if ref.occurred_at]
        if ref_times:
            return min(ref_times)
    return ""


def _conversation_has_user(conversation: ConversationView, user_id: str) -> bool:
    return any(
        _string(turn.agent_turn.get("user_id")) == user_id
        for turn in conversation.turns
    )


def _conversation_has_channel(conversation: ConversationView, channel: str) -> bool:
    return any(
        _string(turn.agent_turn.get("channel")) == channel
        for turn in conversation.turns
    )


def _task_occurred_at(task: TaskView) -> str:
    """Compute the occurred_at timestamp for a task from its turn."""

    turn = task.turn
    if turn.event_refs:
        ref_times = [ref.occurred_at for ref in turn.event_refs if ref.occurred_at]
        if ref_times:
            return min(ref_times)
    received_at = _string(turn.agent_turn.get("received_at"))
    if received_at is not None:
        return received_at
    return ""


def _task_has_user(task: TaskView, user_id: str) -> bool:
    return _string(task.turn.agent_turn.get("user_id")) == user_id


def _task_has_channel(task: TaskView, channel: str) -> bool:
    return _string(task.turn.agent_turn.get("channel")) == channel


def build_read_model(records: Iterable[Any]) -> ContractLogReadModel:
    return ContractLogReadModel.from_records(records)


class _Record:
    def __init__(
        self,
        *,
        event_key: str,
        occurred_at: str,
        ingested_at: str,
        seq: int,
        event: JsonObject,
        source_path: str | None = None,
    ) -> None:
        self.event_key = event_key
        self.occurred_at = occurred_at
        self.ingested_at = ingested_at
        self.seq = seq
        self.event = event
        self.source_path = source_path


def _coerce_record(record: Any) -> _Record:
    if isinstance(record, Mapping):
        return _Record(
            event_key=str(record["event_key"]),
            occurred_at=str(record.get("occurred_at", "")),
            ingested_at=str(record.get("ingested_at", "")),
            seq=_int(record.get("seq")),
            event=dict(record["event"]),
            source_path=_string(record.get("source_path")),
        )

    return _Record(
        event_key=str(getattr(record, "event_key")),
        occurred_at=str(getattr(record, "occurred_at")),
        ingested_at=str(getattr(record, "ingested_at")),
        seq=_int(getattr(record, "seq")),
        event=dict(getattr(record, "event")),
        source_path=str(getattr(record, "path")) if getattr(record, "path", None) is not None else None,
    )


def _record_sort_key(record: _Record) -> tuple[str, str, int]:
    return (record.occurred_at, record.ingested_at, record.seq)


def _first_event(
    event_groups: Mapping[str, list[tuple[_Record, JsonObject]]],
    event_key: str,
) -> tuple[_Record | None, JsonObject | None]:
    items = event_groups.get(event_key, [])
    return items[0] if items else (None, None)


def _task_id_for(
    agent_turn: JsonObject,
    execution_trace: JsonObject | None,
    agent_result: JsonObject | None,
    turn_id: str,
) -> tuple[str, str]:
    for source_name, event in (
        ("agent_turn.metadata.task_id", agent_turn),
        ("execution_trace.metadata.task_id", execution_trace or {}),
        ("agent_result.metadata.task_id", agent_result or {}),
    ):
        metadata = event.get("metadata") if isinstance(event, Mapping) else None
        if isinstance(metadata, Mapping):
            task_id = _string(metadata.get("task_id"))
            if task_id is not None:
                return task_id, source_name
    return turn_id, "turn_id"


def _missing_associations(
    route_decision: JsonObject | None,
    execution_trace: JsonObject | None,
    agent_result: JsonObject | None,
) -> list[str]:
    missing = []
    if route_decision is None:
        missing.append("route_decision")
    if execution_trace is None:
        missing.append("execution_trace")
    if agent_result is None:
        missing.append("agent_result")
    return missing


def _event_reference(record: _Record) -> EventReference:
    return EventReference(
        event_key=record.event_key,
        occurred_at=record.occurred_at,
        ingested_at=record.ingested_at,
        seq=record.seq,
        source_path=record.source_path,
    )


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


__all__ = [
    "ContractLogReadModel",
    "build_read_model",
    "load_records_from_jsonl",
]
