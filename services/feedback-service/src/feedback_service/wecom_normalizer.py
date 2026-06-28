"""Minimal WeCom feedback normalizer for Phase 5 validation fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Mapping


SUPPORTED_ACTIONS = {"up", "down", "needs_fix", "route_wrong"}


@dataclass(frozen=True)
class FeedbackNormalizationIssue:
    code: str
    message: str
    feedback_ref: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class NormalizedFeedbackBatch:
    events: list[dict[str, Any]]
    issues: list[FeedbackNormalizationIssue]


def normalize_wecom_feedback_records(
    feedback_records: list[Mapping[str, Any]],
    preview_records: list[Mapping[str, Any]],
    *,
    now: str | None = None,
) -> NormalizedFeedbackBatch:
    """Normalize sanitized Hermes feedback records into FeedbackEvent payloads."""

    issues: list[FeedbackNormalizationIssue] = []
    preview_index = _index_previews(preview_records)
    grouped: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any], str, str]]] = {}

    for record in feedback_records:
        feedback_ref = _string(record.get("feedback_id") or record.get("callback_ref") or record.get("raw_payload_ref"))
        raw_payload_path = _find_exact_key(record, "raw_payload")
        if raw_payload_path is not None:
            issues.append(
                FeedbackNormalizationIssue(
                    code="raw_payload_forbidden",
                    message="feedback records must use raw_payload_ref instead of raw_payload",
                    feedback_ref=feedback_ref,
                    path=raw_payload_path,
                )
            )
            continue

        action = _string(record.get("action") or record.get("feedback_action") or record.get("button_action"))
        if action not in SUPPORTED_ACTIONS:
            issues.append(
                FeedbackNormalizationIssue(
                    code="unsupported_action",
                    message=f"unsupported feedback action {action!r}",
                    feedback_ref=feedback_ref,
                    path="action",
                )
            )
            continue

        preview_key = _string(record.get("feedback_target") or record.get("message_id") or record.get("preview_id"))
        preview = preview_index.get(preview_key or "")
        if preview is None:
            issues.append(
                FeedbackNormalizationIssue(
                    code="missing_preview",
                    message="feedback record could not be resolved to a sanitized pending preview",
                    feedback_ref=feedback_ref,
                    path="feedback_target",
                )
            )
            continue

        preview_raw_payload_path = _find_exact_key(preview, "raw_payload")
        if preview_raw_payload_path is not None:
            issues.append(
                FeedbackNormalizationIssue(
                    code="raw_payload_forbidden",
                    message="preview records must use raw_payload_ref instead of raw_payload",
                    feedback_ref=feedback_ref,
                    path=f"preview.{preview_raw_payload_path}",
                )
            )
            continue

        created_at = _string(record.get("created_at") or now)
        if created_at is None:
            issues.append(
                FeedbackNormalizationIssue(
                    code="missing_created_at",
                    message="feedback record has no created_at timestamp and no fallback now value",
                    feedback_ref=feedback_ref,
                    path="created_at",
                )
            )
            continue

        target = _feedback_target(record, preview)
        user_id = _string(record.get("user_id") or preview.get("user_id"))
        turn_id = _string(record.get("turn_id") or preview.get("turn_id"))
        conversation_id = _string(record.get("conversation_id") or preview.get("conversation_id"))
        if target is None or user_id is None or turn_id is None or conversation_id is None:
            issues.append(
                FeedbackNormalizationIssue(
                    code="missing_required_reference",
                    message="feedback target, turn_id, conversation_id, and user_id are required",
                    feedback_ref=feedback_ref,
                )
            )
            continue

        idempotency_key = ":".join((target, action, user_id, _timestamp_bucket(created_at)))
        grouped.setdefault(idempotency_key, []).append((record, preview, action, created_at))

    events = [
        _event_from_group(idempotency_key, records)
        for idempotency_key, records in grouped.items()
    ]
    return NormalizedFeedbackBatch(events=events, issues=issues)


def _index_previews(preview_records: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for record in preview_records:
        for key in ("feedback_target", "message_id", "preview_id"):
            value = _string(record.get(key))
            if value is not None and value not in index:
                index[value] = record
    return index


def _event_from_group(
    idempotency_key: str,
    records: list[tuple[Mapping[str, Any], Mapping[str, Any], str, str]],
) -> dict[str, Any]:
    canonical, preview, action, created_at = records[0]
    target = _feedback_target(canonical, preview)
    assert target is not None

    event: dict[str, Any] = {
        "feedback_id": _string(canonical.get("feedback_id")) or _stable_feedback_id(idempotency_key),
        "turn_id": _required_string(canonical, preview, "turn_id"),
        "conversation_id": _required_string(canonical, preview, "conversation_id"),
        "user_id": _required_string(canonical, preview, "user_id"),
        "source": "card_button",
        "event_type": _event_type(action),
        "status": "pending",
        "created_at": created_at,
        "feedback_target": target,
        "action": action,
        "industry_context": _mapping_or_empty(preview.get("industry_context")),
        "metadata": {
            "idempotency_key": idempotency_key,
            "dedupe_strategy": "feedback_target + action + user_id + created_at_bucket",
            "canonical_event": True,
            "duplicate_callback_refs": _duplicate_callback_refs(records),
            "duplicate_count": len(records),
        },
    }

    optional_fields = {
        "raw_payload_ref": _string(canonical.get("raw_payload_ref") or canonical.get("callback_ref")),
        "result_id": _string(canonical.get("result_id") or preview.get("result_id")),
        "related_skill": _string(canonical.get("related_skill") or preview.get("related_skill")),
        "related_route_decision": _string(
            canonical.get("related_route_decision") or preview.get("related_route_decision")
        ),
        "message": _string(canonical.get("message") or canonical.get("comment")),
    }
    event.update({key: value for key, value in optional_fields.items() if value is not None})

    labels = _string_list(canonical.get("labels"))
    if labels:
        event["labels"] = labels

    if action == "up":
        event["rating"] = 1.0
    if action == "route_wrong":
        evidence = [item for item in (_string(canonical.get("raw_payload_ref")), target) if item is not None]
        event["route_mismatch"] = True
        event["skill_candidate"] = {
            "detected": True,
            "source": "route_mismatch",
            "proposed_name": _string(canonical.get("proposed_skill")) or "lawfirm.route_review_candidate",
            "risk_level": "high",
            "requires_human_review": True,
            "evidence": evidence,
            "metadata": {
                "no_auto_modify": True,
                "source_status": "feedback_callback_sanitized",
            },
        }
        event["metadata"]["no_auto_modify"] = True

    return event


def _event_type(action: str) -> str:
    if action == "up":
        return "rating"
    if action in {"down", "needs_fix"}:
        return "correction"
    return "route_mismatch"


def _feedback_target(record: Mapping[str, Any], preview: Mapping[str, Any]) -> str | None:
    return _string(record.get("feedback_target") or record.get("message_id") or preview.get("feedback_target") or preview.get("message_id"))


def _required_string(record: Mapping[str, Any], preview: Mapping[str, Any], key: str) -> str:
    value = _string(record.get(key) or preview.get(key))
    if value is None:
        raise ValueError(f"missing required field {key}")
    return value


def _duplicate_callback_refs(
    records: list[tuple[Mapping[str, Any], Mapping[str, Any], str, str]],
) -> list[str]:
    refs: list[str] = []
    for record, _, _, _ in records:
        ref = _string(record.get("callback_ref") or record.get("raw_payload_ref") or record.get("feedback_id"))
        if ref is not None:
            refs.append(ref)
    return refs


def _timestamp_bucket(created_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return created_at[:16]
    normalized = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _stable_feedback_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
    return f"feedback-{digest}"


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_string(item) for item in value) if item is not None]


def _find_exact_key(value: Any, needle: str, path: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == needle:
                return child_path
            found = _find_exact_key(child, needle, child_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_exact_key(child, needle, f"{path}[{index}]")
            if found is not None:
                return found
    return None


__all__ = [
    "FeedbackNormalizationIssue",
    "NormalizedFeedbackBatch",
    "normalize_wecom_feedback_records",
]
