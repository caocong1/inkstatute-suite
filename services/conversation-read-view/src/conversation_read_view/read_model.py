"""Contract log read model for read-only conversation views."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from platform_contract.utils import coerce_str

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
    ) -> None:
        self._conversations = dict(conversations)
        self._tasks = dict(tasks)
        self._trace_to_task_id = dict(trace_to_task_id)
        self.issues = list(issues)

    @classmethod
    def from_records(cls, records: Iterable[Any]) -> "ContractLogReadModel":
        normalized = sorted((_coerce_record(record) for record in records), key=_record_sort_key)
        events_by_turn: dict[str, dict[str, list[tuple[_Record, JsonObject]]]] = defaultdict(lambda: defaultdict(list))
        feedback_by_turn: dict[str, list[tuple[_Record, JsonObject]]] = defaultdict(list)
        issues: list[ReadModelIssue] = []

        for record in normalized:
            event = scrub_contract_payload(record.event)
            turn_id = coerce_str(event.get("turn_id"))
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

            conversation_id = coerce_str(agent_turn.get("conversation_id")) or "unknown-conversation"
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

            trace_id = coerce_str((execution_trace or {}).get("trace_id"))
            if trace_id is None and isinstance((agent_result or {}).get("metadata"), Mapping):
                trace_id = coerce_str(agent_result["metadata"].get("trace_id"))  # type: ignore[index]
            if trace_id is not None:
                trace_to_task_id[trace_id] = task_id

        conversations = {
            conversation_id: ConversationView(conversation_id=conversation_id, turns=turns, issues=issues)
            for conversation_id, turns in turns_by_conversation.items()
        }
        return cls(conversations=conversations, tasks=tasks, trace_to_task_id=trace_to_task_id, issues=issues)

    def get_conversation(self, conversation_id: str) -> JsonObject | None:
        conversation = self._conversations.get(conversation_id)
        return conversation.to_dict() if conversation is not None else None

    def get_task(self, task_id: str) -> JsonObject | None:
        task = self._tasks.get(task_id)
        return task.to_dict() if task is not None else None

    def get_task_by_trace_id(self, trace_id: str) -> JsonObject | None:
        task_id = self._trace_to_task_id.get(trace_id)
        return self.get_task(task_id) if task_id is not None else None


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
            source_path=coerce_str(record.get("source_path")),
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
            task_id = coerce_str(metadata.get("task_id"))
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



def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


__all__ = [
    "ContractLogReadModel",
    "build_read_model",
    "load_records_from_jsonl",
]
