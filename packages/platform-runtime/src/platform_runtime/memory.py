"""Privacy-safe long-term memory support for embedded runtimes."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from platform_contract.events import JsonObject, MemoryCandidate, MemoryRecord, MemoryUse


class MemoryPrivacyError(ValueError):
    """Raised when memory support is asked to store unsafe payload material."""


@dataclass(frozen=True, slots=True)
class MemoryStorePolicy:
    max_results: int = 8
    minimum_confidence: float = 0.0
    allowed_sensitivities: tuple[str, ...] = ("public", "internal", "confidential")
    active_statuses: tuple[str, ...] = ("active",)
    chars_per_token: int = 4


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    tenant_id: str
    workspace_id: str
    session_id: str | None = None
    user_id: str | None = None
    text: str | None = None
    labels: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    now: str | datetime | None = None
    max_results: int | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    record: MemoryRecord
    relevance_score: float
    matched_terms: tuple[str, ...] = ()
    policy_result: str = "selected"
    metadata: JsonObject = field(default_factory=dict)

    def to_memory_use_ref(self) -> str:
        return f"memory://{self.record.memory_id}"


class InMemoryMemoryStore:
    """Copy-safe, scoped memory store for tests and embedded hosts."""

    def __init__(self, *, clock: Callable[[], datetime | str] | Any | None = None) -> None:
        self._clock = clock
        self._records: dict[str, MemoryRecord] = {}

    def upsert(self, record: MemoryRecord) -> None:
        _validate_record(record)
        self._records[record.memory_id] = _copy_record(record)

    def get(self, memory_id: str) -> MemoryRecord | None:
        record = self._records.get(memory_id)
        return _copy_record(record) if record is not None else None

    def list_for_query(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemoryRecord, ...]:
        cfg = policy or MemoryStorePolicy()
        _validate_query(query)
        now = _query_now(query, self._clock)
        return tuple(
            _copy_record(record)
            for record in self._records.values()
            if _record_visible(record, query, cfg, now)
        )

    def search(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemorySearchResult, ...]:
        cfg = policy or MemoryStorePolicy()
        query_terms = _terms_from_query(query)
        results = [
            _search_result(record, query_terms)
            for record in self.list_for_query(query, policy=cfg)
        ]
        if query_terms:
            results = [result for result in results if result.matched_terms]
        results.sort(
            key=lambda item: (
                -item.relevance_score,
                -float(item.record.confidence if item.record.confidence is not None else 0.0),
                _reverse_timestamp_key(item.record.updated_at),
                item.record.memory_id,
            )
        )
        limit = max(0, int(query.max_results if query.max_results is not None else cfg.max_results))
        return tuple(results[:limit])

    def mark_deleted(self, memory_id: str, *, deleted_at: str | datetime | None = None, reason: str = "") -> MemoryRecord:
        record = self._records[memory_id]
        timestamp = _timestamp(deleted_at or _clock_now(self._clock))
        deleted = replace(
            record,
            status="deleted",
            deleted_at=timestamp,
            deletion_reason=reason or "deleted_by_policy",
            updated_at=timestamp,
        )
        self.upsert(deleted)
        return _copy_record(deleted)


@dataclass(frozen=True, slots=True)
class FeedbackLearningInput:
    tenant_id: str
    workspace_id: str
    session_id: str
    user_id: str
    feedback_events: tuple[JsonObject, ...]
    context_bundle_id: str | None = None
    run_id: str | None = None
    turn_id: str | None = None
    selected_memory_ids: tuple[str, ...] = ()
    now: str | datetime | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeedbackLearningResult:
    feedback_correction_refs: tuple[str, ...] = ()
    memory_candidates: tuple[MemoryCandidate, ...] = ()
    routing_candidates: tuple[MemoryCandidate, ...] = ()
    memory_uses: tuple[MemoryUse, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeedbackLearningPolicy:
    repeated_negative_threshold: int = 2
    default_candidate_scope: str = "session"
    default_candidate_sensitivity: str = "confidential"
    correction_categories: tuple[str, ...] = (
        "correction",
        "fact_missing",
        "citation_error",
        "format_issue",
        "compliance_issue",
    )

    def learn(self, input: FeedbackLearningInput) -> FeedbackLearningResult:
        _safe_metadata(input.metadata)
        now = _timestamp(input.now or _clock_now(None))
        events = tuple(_safe_event(event) for event in input.feedback_events)
        correction_refs: list[str] = []
        metadata_events: list[JsonObject] = []
        negative_groups: dict[tuple[str, str, str], list[JsonObject]] = {}
        routing_candidates: list[MemoryCandidate] = []

        for event in events:
            feedback_id = _event_text(event, "feedback_id") or f"feedback-{_sha16(json.dumps(event, sort_keys=True))}"
            category = _feedback_category(event)
            route_or_skill = _requires_route_or_skill_review(event, category)
            if not route_or_skill and category in self.correction_categories:
                correction_refs.append(f"feedback://{feedback_id}/correction")
            if _negative_feedback(event, category):
                key = (
                    _event_text(event, "feedback_target") or _event_text(event, "result_id") or "unknown-target",
                    _event_text(event, "user_id") or input.user_id,
                    category,
                )
                negative_groups.setdefault(key, []).append(event)
            if route_or_skill:
                routing_candidates.append(
                    self._candidate_from_events(
                        input=input,
                        events=(event,),
                        now=now,
                        category=category,
                        proposed_action="review_route_or_skill_candidate",
                        requires_human_review=True,
                        no_auto_modify=True,
                    )
                )
            metadata_events.append(_feedback_event_metadata(event, category))

        memory_candidates: list[MemoryCandidate] = []
        for (_target, _user, category), grouped in negative_groups.items():
            if len(grouped) < max(1, self.repeated_negative_threshold):
                continue
            if _requires_route_or_skill_review(grouped[0], category):
                continue
            memory_candidates.append(
                self._candidate_from_events(
                    input=input,
                    events=tuple(grouped),
                    now=now,
                    category=category,
                    proposed_action="create_memory_candidate",
                    requires_human_review=True,
                    no_auto_modify=False,
                )
            )

        memory_uses = tuple(
            MemoryUse(
                use_id=f"memory-use-{_sha16(f'{input.context_bundle_id}:{memory_id}')}",
                memory_id=memory_id,
                context_bundle_id=input.context_bundle_id,
                used_at=now,
                purpose="feedback_learning_context",
                run_id=input.run_id,
                turn_id=input.turn_id,
                relevance_score=None,
                policy_result="selected",
                source_refs=[f"memory://{memory_id}"],
                metadata={"privacy": "refs_hashes_lengths_statuses_only"},
            )
            for memory_id in input.selected_memory_ids
            if input.context_bundle_id is not None
        )

        return FeedbackLearningResult(
            feedback_correction_refs=tuple(dict.fromkeys(correction_refs)),
            memory_candidates=tuple(memory_candidates),
            routing_candidates=tuple(routing_candidates),
            memory_uses=memory_uses,
            metadata=_safe_metadata(
                {
                    "privacy": "refs_hashes_lengths_statuses_only",
                    "feedback_events": metadata_events,
                    "repeated_negative_threshold": self.repeated_negative_threshold,
                }
            ),
        )

    def _candidate_from_events(
        self,
        *,
        input: FeedbackLearningInput,
        events: tuple[JsonObject, ...],
        now: str,
        category: str,
        proposed_action: str,
        requires_human_review: bool,
        no_auto_modify: bool,
    ) -> MemoryCandidate:
        feedback_ids = [_event_text(event, "feedback_id") for event in events]
        feedback_ids = [item for item in feedback_ids if item is not None]
        raw_refs = [_event_text(event, "raw_payload_ref") for event in events]
        raw_refs = [item for item in raw_refs if item is not None]
        source_refs = list(dict.fromkeys([*(f"feedback://{item}" for item in feedback_ids), *raw_refs]))
        target_refs = [_event_text(event, "feedback_target") for event in events]
        target_refs = [item for item in target_refs if item is not None]
        confidence = min(1.0, 0.5 + (0.1 * len(events)))
        candidate_id = f"memory-candidate-{_sha16('|'.join(source_refs) + proposed_action + category)}"
        return MemoryCandidate(
            candidate_id=candidate_id,
            tenant_id=input.tenant_id,
            workspace_id=input.workspace_id,
            status="pending",
            source_refs=source_refs or [f"feedback://candidate/{candidate_id}"],
            created_at=now,
            proposed_scope=self.default_candidate_scope,
            proposed_sensitivity=self.default_candidate_sensitivity,
            proposed_action=proposed_action,
            proposed_record_ref=f"memory://candidates/{candidate_id}",
            reason=f"{category} feedback learning candidate",
            confidence=round(confidence, 6),
            requires_human_review=requires_human_review,
            raw_payload_ref=raw_refs[0] if raw_refs else None,
            metadata=_safe_metadata(
                {
                    "category": category,
                    "feedback_ids": feedback_ids,
                    "feedback_targets": target_refs,
                    "feedback_count": len(events),
                    "no_auto_modify": no_auto_modify,
                    "privacy": "refs_hashes_lengths_statuses_only",
                }
            ),
        )


def _validate_record(record: MemoryRecord) -> None:
    _safe_metadata(record.metadata)
    _safe_metadata(record.industry_context)
    for ref in record.source_refs:
        _validate_ref(ref, field="source_refs")
    if record.raw_payload_ref is not None:
        _validate_ref(record.raw_payload_ref, field="raw_payload_ref")


def _validate_query(query: MemoryQuery) -> None:
    _safe_metadata(query.metadata)
    for ref in query.source_refs:
        _validate_ref(ref, field="source_refs")


def _record_visible(
    record: MemoryRecord,
    query: MemoryQuery,
    policy: MemoryStorePolicy,
    now: datetime,
) -> bool:
    if record.tenant_id != query.tenant_id or record.workspace_id != query.workspace_id:
        return False
    if str(record.status) not in policy.active_statuses:
        return False
    if record.deleted_at is not None:
        return False
    if str(record.sensitivity) not in policy.allowed_sensitivities:
        return False
    if float(record.confidence if record.confidence is not None else 0.0) < policy.minimum_confidence:
        return False
    if record.ttl_expires_at is not None and _parse_timestamp(record.ttl_expires_at) <= now:
        return False
    return _scope_allows(record, query)


def _scope_allows(record: MemoryRecord, query: MemoryQuery) -> bool:
    scope = str(record.scope)
    if scope == "session":
        return bool(record.session_id and query.session_id and record.session_id == query.session_id)
    if scope == "user":
        return bool(record.related_user_id and query.user_id and record.related_user_id == query.user_id)
    if scope == "workspace":
        return True
    if scope == "tenant":
        return True
    return False


def _search_result(record: MemoryRecord, query_terms: set[str]) -> MemorySearchResult:
    record_terms = _terms_from_record(record)
    matched = tuple(sorted(query_terms & record_terms))
    if not query_terms:
        score = float(record.confidence if record.confidence is not None else 0.0)
    else:
        score = len(matched) / max(1, len(query_terms))
    return MemorySearchResult(
        record=_copy_record(record),
        relevance_score=round(score, 6),
        matched_terms=matched,
        metadata={
            "privacy": "refs_hashes_lengths_statuses_only",
            "matched_term_count": len(matched),
        },
    )


def _terms_from_query(query: MemoryQuery) -> set[str]:
    terms = _tokenize(query.text)
    terms.update(_normalize_token(label) for label in query.labels if _normalize_token(label))
    terms.update(_ref_terms(query.source_refs))
    return terms


def _terms_from_record(record: MemoryRecord) -> set[str]:
    terms = _tokenize(record.subject)
    terms.update(_tokenize(record.summary))
    terms.update(_ref_terms(record.source_refs))
    metadata = record.metadata if isinstance(record.metadata, Mapping) else {}
    for key in ("labels", "tags", "categories", "category", "subject"):
        value = metadata.get(key)
        if isinstance(value, list | tuple):
            terms.update(_normalize_token(item) for item in value if _normalize_token(item))
        elif value is not None:
            terms.update(_tokenize(str(value)))
    return {term for term in terms if term}


def _tokenize(text: Any) -> set[str]:
    if text is None:
        return set()
    return {
        token
        for token in (_normalize_token(part) for part in re.split(r"[^0-9A-Za-z_\u4e00-\u9fff]+", str(text)))
        if token
    }


def _normalize_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _ref_terms(refs: Sequence[str]) -> set[str]:
    terms: set[str] = set()
    for ref in refs:
        terms.update(_tokenize(ref.rsplit("/", 1)[-1]))
        terms.update(_tokenize(ref.rsplit(":", 1)[-1]))
    return terms


def _query_now(query: MemoryQuery, clock: Callable[[], datetime | str] | Any | None) -> datetime:
    if query.now is not None:
        return _parse_timestamp(query.now)
    return _parse_timestamp(_clock_now(clock))


def _clock_now(clock: Callable[[], datetime | str] | Any | None) -> datetime | str:
    if clock is None:
        return datetime.now(timezone.utc)
    if callable(clock):
        return clock()
    now = getattr(clock, "now", None)
    if callable(now):
        return now()
    raise TypeError("clock must be callable or provide now()")


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if value.endswith("+00:00"):
        return value[:-6] + "Z"
    return str(value)


def _parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _reverse_timestamp_key(value: str) -> float:
    try:
        return -_parse_timestamp(value).timestamp()
    except ValueError:
        return 0.0


def _safe_metadata(value: Any, path: str = "$") -> JsonObject:
    if isinstance(value, Mapping):
        output: JsonObject = {}
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _FORBIDDEN_KEYS or _SECRET_KEY_PATTERN.search(key_text):
                raise MemoryPrivacyError(f"memory metadata contains forbidden field at {child_path}")
            output[key_text] = _safe_value(child, child_path)
        return _json_clone(output)
    if value is None:
        return {}
    raise MemoryPrivacyError(f"memory metadata must be an object at {path}")


def _safe_value(value: Any, path: str) -> Any:
    if isinstance(value, Mapping):
        return _safe_metadata(value, path)
    if isinstance(value, list):
        return [_safe_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, tuple):
        return [_safe_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.search(value):
        raise MemoryPrivacyError(f"memory metadata contains secret-like value at {path}")
    return value


def _safe_event(event: Mapping[str, Any]) -> JsonObject:
    found = _find_forbidden_key(event)
    if found is not None:
        raise MemoryPrivacyError(f"feedback event contains forbidden field at {found}")
    return _json_clone(event)


def _find_forbidden_key(value: Any, path: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in _FORBIDDEN_EVENT_KEYS:
                return child_path
            found = _find_forbidden_key(child, child_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden_key(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _feedback_category(event: Mapping[str, Any]) -> str:
    labels = _event_labels(event)
    event_type = _event_text(event, "event_type")
    if bool(event.get("route_mismatch")) or event_type == "route_mismatch" or "route_mismatch" in labels:
        return "route_mismatch"
    if event_type == "skill_candidate" or "skill_candidate" in labels or isinstance(event.get("skill_candidate"), Mapping):
        return "skill_candidate"
    for label in labels:
        normalized = label.replace("-", "_")
        if normalized in {
            "correction",
            "fact_missing",
            "citation_error",
            "format_issue",
            "compliance_issue",
            "rating",
        }:
            return normalized
    if event_type in {"correction", "fact_missing", "citation_error", "format_issue", "compliance_issue", "rating"}:
        return event_type
    action = _event_text(event, "action")
    if action == "up":
        return "rating"
    return "correction"


def _event_labels(event: Mapping[str, Any]) -> set[str]:
    labels = event.get("labels")
    if not isinstance(labels, list):
        return set()
    return {_normalize_token(label).replace("-", "_") for label in labels if _normalize_token(label)}


def _event_text(event: Mapping[str, Any], key: str) -> str | None:
    value = event.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _requires_route_or_skill_review(event: Mapping[str, Any], category: str) -> bool:
    return category in {"route_mismatch", "skill_candidate"} or isinstance(event.get("skill_candidate"), Mapping)


def _negative_feedback(event: Mapping[str, Any], category: str) -> bool:
    action = _event_text(event, "action")
    return category != "rating" or action in {"down", "needs_fix", "route_wrong"}


def _feedback_event_metadata(event: Mapping[str, Any], category: str) -> JsonObject:
    message = _event_text(event, "message")
    metadata: JsonObject = {
        "feedback_id": _event_text(event, "feedback_id"),
        "feedback_target": _event_text(event, "feedback_target"),
        "category": category,
        "action": _event_text(event, "action"),
        "raw_payload_ref": _event_text(event, "raw_payload_ref"),
    }
    if message is not None:
        metadata["message_sha256_16"] = _sha16(message)
        metadata["message_length"] = len(message)
    return _safe_metadata({key: value for key, value in metadata.items() if value is not None})


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _validate_ref(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise MemoryPrivacyError(f"{field} must contain non-empty refs")
    if _SECRET_VALUE_PATTERN.search(value):
        raise MemoryPrivacyError(f"{field} contains secret-like value")


def _copy_record(record: MemoryRecord) -> MemoryRecord:
    return MemoryRecord(
        memory_id=record.memory_id,
        tenant_id=record.tenant_id,
        workspace_id=record.workspace_id,
        scope=str(record.scope),
        status=str(record.status),
        sensitivity=str(record.sensitivity),
        created_at=record.created_at,
        updated_at=record.updated_at,
        source_refs=list(record.source_refs),
        summary=record.summary,
        subject=record.subject,
        related_user_id=record.related_user_id,
        session_id=record.session_id,
        raw_payload_ref=record.raw_payload_ref,
        confidence=record.confidence,
        ttl_expires_at=record.ttl_expires_at,
        deleted_at=record.deleted_at,
        deletion_reason=record.deletion_reason,
        industry_context=_safe_metadata(record.industry_context),
        metadata=_safe_metadata(record.metadata),
    )


def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


_FORBIDDEN_KEYS = {
    "callback_body",
    "case_facts",
    "customer_document_text",
    "document_text",
    "feedback_message_text",
    "full_text",
    "message_text",
    "payload_text",
    "raw_payload",
    "raw_text",
}
_FORBIDDEN_EVENT_KEYS = _FORBIDDEN_KEYS | {"raw_payload"}
_SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret|password|encoding[_-]?aes[_-]?key)", re.IGNORECASE)
_SECRET_VALUE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


__all__ = [
    "FeedbackLearningInput",
    "FeedbackLearningPolicy",
    "FeedbackLearningResult",
    "InMemoryMemoryStore",
    "MemoryPrivacyError",
    "MemoryQuery",
    "MemorySearchResult",
    "MemoryStorePolicy",
]
