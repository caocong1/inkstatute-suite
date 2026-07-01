"""Privacy-safe long-term memory support for embedded runtimes."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
import re
from typing import Any

from platform_contract.events import JsonObject, MemoryRecord


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
_SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret|password|encoding[_-]?aes[_-]?key)", re.IGNORECASE)
_SECRET_VALUE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


__all__ = [
    "InMemoryMemoryStore",
    "MemoryPrivacyError",
    "MemoryQuery",
    "MemorySearchResult",
    "MemoryStorePolicy",
]
