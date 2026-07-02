"""Derived feedback event normalization and dedupe helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from platform_contract.utils import (
    coerce_str,
    find_forbidden_key,
    json_clone,
    sha256_short,
    timestamp_bucket,
)

from .classification import FeedbackClassification, classify_feedback_event
from .wecom_normalizer import normalize_wecom_feedback_records


@dataclass(frozen=True)
class FeedbackQueueItem:
    event: dict[str, Any]
    classification: FeedbackClassification

    def to_dict(self) -> dict[str, Any]:
        metadata = self.event.get("metadata", {})
        metadata = metadata if isinstance(metadata, Mapping) else {}
        skill_candidate = self.event.get("skill_candidate")
        skill_metadata = skill_candidate.get("metadata", {}) if isinstance(skill_candidate, Mapping) else {}
        skill_metadata = skill_metadata if isinstance(skill_metadata, Mapping) else {}
        requires_human_review = bool(
            self.classification.requires_human_review
            or (isinstance(skill_candidate, Mapping) and skill_candidate.get("requires_human_review"))
        )
        no_auto_modify = bool(
            self.classification.no_auto_modify
            or metadata.get("no_auto_modify")
            or skill_metadata.get("no_auto_modify")
        )
        return {
            "feedback_id": self.event.get("feedback_id"),
            "turn_id": self.event.get("turn_id"),
            "conversation_id": self.event.get("conversation_id"),
            "user_id": self.event.get("user_id"),
            "result_id": self.event.get("result_id"),
            "feedback_target": self.event.get("feedback_target"),
            "source": self.event.get("source"),
            "event_type": self.event.get("event_type"),
            "action": self.event.get("action"),
            "status": self.event.get("status"),
            "created_at": self.event.get("created_at"),
            "classification": self.classification.to_dict(),
            "raw_payload_ref": self.event.get("raw_payload_ref"),
            "related_skill": self.event.get("related_skill"),
            "related_route_decision": self.event.get("related_route_decision"),
            "skill_candidate": skill_candidate,
            "requires_human_review": requires_human_review,
            "no_auto_modify": no_auto_modify,
            "duplicate_count": metadata.get("duplicate_count", 1),
            "idempotency_key": metadata.get("idempotency_key"),
            "source_status": metadata.get("source_status"),
        }


def load_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_feedback_inputs(
    *,
    wecom_callback_events: Iterable[Mapping[str, Any]] | None = None,
    contract_feedback_events: Iterable[Mapping[str, Any]] | None = None,
    compatibility_feedback_records: Iterable[Mapping[str, Any]] | None = None,
    compatibility_preview_records: Iterable[Mapping[str, Any]] | None = None,
    now: str | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event in wecom_callback_events or ():
        events.append(_privacy_checked_clone(event))
    for event in contract_feedback_events or ():
        events.append(_privacy_checked_clone(event))

    if compatibility_feedback_records is not None or compatibility_preview_records is not None:
        batch = normalize_wecom_feedback_records(
            list(compatibility_feedback_records or ()),
            list(compatibility_preview_records or ()),
            now=now,
        )
        if batch.issues:
            first = batch.issues[0]
            raise ValueError(f"could not normalize compatibility feedback: {first.code}")
        events.extend(_privacy_checked_clone(event) for event in batch.events)

    return dedupe_feedback_events(events)


def dedupe_feedback_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for event in events:
        cloned = _privacy_checked_clone(event)
        key = _idempotency_key(cloned)
        if key not in grouped:
            order.append(key)
        grouped.setdefault(key, []).append(cloned)

    return [_canonical_event(key, grouped[key]) for key in order]


def build_pending_feedback_queue(events: Iterable[Mapping[str, Any]], status: str = "pending") -> list[dict[str, Any]]:
    indexed_events = list(enumerate(dedupe_feedback_events(events)))
    filtered = [(index, event) for index, event in indexed_events if event.get("status") == status]
    filtered.sort(key=lambda item: (coerce_str(item[1].get("created_at")) or "", _seq(item[1]), item[0]))
    return [FeedbackQueueItem(event=event, classification=classify_feedback_event(event)).to_dict() for _, event in filtered]


def _canonical_event(idempotency_key: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = json_clone(events[0])
    metadata = dict(canonical.get("metadata", {})) if isinstance(canonical.get("metadata"), Mapping) else {}
    duplicate_count = sum(_duplicate_count(event) for event in events)
    metadata.update(
        {
            "idempotency_key": idempotency_key,
            "canonical_event": True,
            "duplicate_count": duplicate_count,
            "duplicate_feedback_ids": _duplicate_feedback_ids(events),
            "duplicate_callback_refs": _duplicate_callback_refs(events),
        }
    )
    canonical["metadata"] = metadata
    return canonical


def _idempotency_key(event: Mapping[str, Any]) -> str:
    metadata = event.get("metadata")
    if isinstance(metadata, Mapping):
        key = coerce_str(metadata.get("idempotency_key"))
        if key is not None:
            return key

    target = coerce_str(event.get("feedback_target"))
    action = coerce_str(event.get("action"))
    user_id = coerce_str(event.get("user_id"))
    created_at = coerce_str(event.get("created_at"))
    if target is not None and action is not None and user_id is not None and created_at is not None:
        return ":".join((target, action, user_id, timestamp_bucket(created_at)))

    feedback_id = coerce_str(event.get("feedback_id"))
    if feedback_id is not None:
        return feedback_id

    digest = sha256_short(json.dumps(event, sort_keys=True, ensure_ascii=False))
    return f"feedback-event:{digest}"


def _duplicate_count(event: Mapping[str, Any]) -> int:
    metadata = event.get("metadata")
    if isinstance(metadata, Mapping):
        count = metadata.get("duplicate_count")
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            return count
    return 1


def _duplicate_feedback_ids(events: list[Mapping[str, Any]]) -> list[str]:
    return [item for item in (coerce_str(event.get("feedback_id")) for event in events) if item is not None]


def _duplicate_callback_refs(events: list[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for event in events:
        metadata = event.get("metadata")
        if isinstance(metadata, Mapping) and isinstance(metadata.get("duplicate_callback_refs"), list):
            refs.extend(str(item) for item in metadata["duplicate_callback_refs"])
        else:
            ref = coerce_str(event.get("raw_payload_ref") or event.get("feedback_id"))
            if ref is not None:
                refs.append(ref)
    return refs


def _seq(event: Mapping[str, Any]) -> int:
    metadata = event.get("metadata")
    value = metadata.get("seq") if isinstance(metadata, Mapping) else event.get("seq")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _privacy_checked_clone(event: Mapping[str, Any]) -> dict[str, Any]:
    forbidden_path = find_forbidden_key(event, "raw_payload")
    if forbidden_path is not None:
        raise ValueError(f"feedback events must use raw_payload_ref instead of raw_payload at {forbidden_path}")
    return json_clone(event)


__all__ = [
    "FeedbackQueueItem",
    "build_pending_feedback_queue",
    "dedupe_feedback_events",
    "load_jsonl_records",
    "normalize_feedback_inputs",
]
