"""Dataclasses for contract-log-derived read views."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class EventReference:
    event_key: str
    occurred_at: str
    ingested_at: str
    seq: int
    source_path: str | None = None

    def to_dict(self) -> JsonObject:
        data: JsonObject = {
            "event_key": self.event_key,
            "occurred_at": self.occurred_at,
            "ingested_at": self.ingested_at,
            "seq": self.seq,
        }
        if self.source_path is not None:
            data["source_path"] = self.source_path
        return data


@dataclass(frozen=True, slots=True)
class ReadModelIssue:
    code: str
    message: str
    turn_id: str | None = None
    event_key: str | None = None

    def to_dict(self) -> JsonObject:
        data: JsonObject = {
            "code": self.code,
            "message": self.message,
        }
        if self.turn_id is not None:
            data["turn_id"] = self.turn_id
        if self.event_key is not None:
            data["event_key"] = self.event_key
        return data


@dataclass(frozen=True, slots=True)
class ConversationTurnView:
    turn_id: str
    conversation_id: str
    task_id: str
    agent_turn: JsonObject
    route_decision: JsonObject | None = None
    execution_trace: JsonObject | None = None
    agent_result: JsonObject | None = None
    feedback_events: list[JsonObject] = field(default_factory=list)
    event_refs: list[EventReference] = field(default_factory=list)
    missing_associations: list[str] = field(default_factory=list)
    fallback_source: str | None = None

    def to_dict(self) -> JsonObject:
        data: JsonObject = {
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "task_id": self.task_id,
            "agent_turn": self.agent_turn,
            "route_decision": self.route_decision,
            "execution_trace": self.execution_trace,
            "agent_result": self.agent_result,
            "feedback_events": self.feedback_events,
            "event_refs": [ref.to_dict() for ref in self.event_refs],
            "missing_associations": list(self.missing_associations),
            "source_status": "contract_log_derived",
            "derived_from_contract_log": True,
        }
        if self.fallback_source is not None:
            data["fallback_source"] = self.fallback_source
        return data


@dataclass(frozen=True, slots=True)
class ConversationView:
    conversation_id: str
    turns: list[ConversationTurnView]
    issues: list[ReadModelIssue] = field(default_factory=list)

    def to_dict(self) -> JsonObject:
        user_ids = sorted(
            {
                turn.agent_turn.get("user_id")
                for turn in self.turns
                if isinstance(turn.agent_turn.get("user_id"), str)
            }
        )
        missing = sorted({item for turn in self.turns for item in turn.missing_associations})
        return {
            "conversation_id": self.conversation_id,
            "turn_count": len(self.turns),
            "user_ids": user_ids,
            "turns": [turn.to_dict() for turn in self.turns],
            "metadata": {
                "derived_from_contract_log": True,
                "source_status": "contract_log_derived",
                "missing_associations": missing,
                "issue_count": len(self.issues),
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class TaskView:
    task_id: str
    turn: ConversationTurnView

    def to_dict(self) -> JsonObject:
        trace_id = None
        if self.turn.execution_trace is not None:
            trace_id = self.turn.execution_trace.get("trace_id")
        result = self.turn.agent_result or {}
        trace = self.turn.execution_trace or {}
        return {
            "task_id": self.task_id,
            "turn_id": self.turn.turn_id,
            "conversation_id": self.turn.conversation_id,
            "trace_id": trace_id,
            "status": result.get("status", "unknown"),
            "route_decision": self.turn.route_decision,
            "execution_trace": self.turn.execution_trace,
            "agent_result": self.turn.agent_result,
            "feedback_events": self.turn.feedback_events,
            "artifacts": result.get("artifacts", []),
            "errors": _task_errors(result, trace),
            "lookup_aliases": {
                "task_id": self.task_id,
                "turn_id": self.turn.turn_id,
                "trace_id": trace_id,
            },
            "source_status": "contract_log_derived",
            "derived_from_contract_log": True,
            "fallback_source": self.turn.fallback_source,
            "missing_associations": list(self.turn.missing_associations),
        }


def _task_errors(result: JsonObject, trace: JsonObject) -> list[Any]:
    errors: list[Any] = []
    if isinstance(trace.get("errors"), list):
        errors.extend(trace["errors"])
    if "error" in result:
        errors.append(result["error"])
    return errors


__all__ = [
    "ConversationTurnView",
    "ConversationView",
    "EventReference",
    "JsonObject",
    "ReadModelIssue",
    "TaskView",
]

