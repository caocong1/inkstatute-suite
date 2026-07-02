"""Policy-driven rolling summary pipeline for safe, reference-first session summaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .context_assembler import RollingSummaryRecord
from .session_resolver import SessionScope, _json_clone, _sha16, _timestamp


class SummaryPrivacyError(ValueError):
    """Raised when the summary pipeline is asked to embed or accept unsafe payload material."""


# Forbidden top-level and recursive metadata keys — same vocabulary as memory.py.
_FORBIDDEN_SUMMARY_KEYS = {
    "callback_body",
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "message_text",
    "payload_text",
    "raw_payload",
    "raw_text",
}
_SUMMARY_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|encoding[_-]?aes[_-]?key)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RollingSummaryPolicy:
    """Threshold and safety configuration for rolling summary pipeline behaviour."""

    max_turn_count_trigger: int = 20
    """Trigger when the conversation reaches this many turns."""

    budget_pressure_threshold: float = 0.80
    """Trigger when estimated_tokens / budget_tokens >= this fraction."""

    require_source_refs: bool = True
    """Fail closed when the producer is called with empty source_refs."""

    allow_raw_text_in_metadata: bool = False
    """Must always remain False; enforced by RollingSummaryProducer."""

    min_summary_ref_prefix: str = "summary://"
    """Producer rejects any summary_ref that does not start with this prefix."""


@dataclass(frozen=True, slots=True)
class RollingSummaryTrigger:
    """Stateless evaluator that decides whether a summary should be produced."""

    policy: RollingSummaryPolicy = field(default_factory=RollingSummaryPolicy)

    def should_trigger(
        self,
        *,
        turn_count: int = 0,
        estimated_tokens: int = 0,
        budget_tokens: int = 0,
        task_completed: bool = False,
        explicit_request: bool = False,
    ) -> tuple[bool, str]:
        """Return ``(should_trigger, reason_code)``.

        ``reason_code`` is one of: ``explicit_request``, ``task_completion``,
        ``budget_pressure``, ``turn_count``, ``none``.
        """
        if explicit_request:
            return (True, "explicit_request")
        if task_completed:
            return (True, "task_completion")
        if budget_tokens > 0 and estimated_tokens / budget_tokens >= self.policy.budget_pressure_threshold:
            return (True, "budget_pressure")
        if turn_count >= self.policy.max_turn_count_trigger:
            return (True, "turn_count")
        return (False, "none")


class RollingSummaryProducer:
    """Create or update a ``RollingSummaryRecord`` from safe source refs.

    Fails closed when:
    - ``summary_ref`` does not start with ``policy.min_summary_ref_prefix``
    - ``policy.require_source_refs`` is True and ``source_refs`` is empty
    - ``metadata`` contains forbidden payload keys or secret-like key names
    """

    def __init__(
        self,
        policy: RollingSummaryPolicy | None = None,
        *,
        clock: Any | None = None,
    ) -> None:
        self._policy = policy or RollingSummaryPolicy()
        self._clock = clock

    def produce(
        self,
        *,
        scope: SessionScope,
        session_id: str,
        summary_ref: str,
        source_refs: tuple[str, ...] = (),
        task_intent_refs: tuple[str, ...] = (),
        user_constraint_refs: tuple[str, ...] = (),
        unanswered_question_refs: tuple[str, ...] = (),
        artifact_refs: tuple[str, ...] = (),
        outcome_refs: tuple[str, ...] = (),
        text_sha256_16: str | None = None,
        text_length: int = 0,
        metadata: dict[str, Any] | None = None,
        existing: RollingSummaryRecord | None = None,
    ) -> RollingSummaryRecord:
        """Produce a safe ``RollingSummaryRecord``.

        Args:
            scope: Session scope providing tenant/workspace/user/session isolation.
            session_id: The session this summary covers.
            summary_ref: A reference URI for the summary content (e.g. ``summary://...``).
            source_refs: Source evidence refs the summary was derived from.
            task_intent_refs: Task intent reference URIs.
            user_constraint_refs: User constraint reference URIs.
            unanswered_question_refs: Open question reference URIs.
            artifact_refs: Artifact reference URIs.
            outcome_refs: Outcome reference URIs.
            text_sha256_16: First 16 hex chars of the summary SHA-256 (hash only, no raw text).
            text_length: Character length of the summary text (count only, no raw text).
            metadata: Optional safe metadata dict (no raw payload keys allowed).
            existing: If provided, ``created_at`` is preserved from this record.

        Returns:
            A new frozen ``RollingSummaryRecord`` — no raw text embedded.

        Raises:
            SummaryPrivacyError: If ``summary_ref`` has wrong prefix, ``source_refs``
                is empty when ``require_source_refs=True``, or ``metadata`` contains
                forbidden keys.
        """
        if not isinstance(summary_ref, str) or not summary_ref.startswith(self._policy.min_summary_ref_prefix):
            raise SummaryPrivacyError(
                f"summary_ref must start with '{self._policy.min_summary_ref_prefix}', got: {summary_ref!r}"
            )
        if self._policy.require_source_refs and not source_refs:
            raise SummaryPrivacyError("source_refs must not be empty when require_source_refs=True")

        safe_metadata = _validate_summary_metadata(metadata or {})

        now_str = _timestamp(_clock_now(self._clock))
        created_at = existing.created_at if existing is not None else now_str
        updated_at = now_str

        return RollingSummaryRecord(
            scope=scope,
            session_id=session_id,
            summary_ref=summary_ref,
            task_intent_refs=tuple(task_intent_refs),
            user_constraint_refs=tuple(user_constraint_refs),
            unanswered_question_refs=tuple(unanswered_question_refs),
            artifact_refs=tuple(artifact_refs),
            outcome_refs=tuple(outcome_refs),
            text_sha256_16=text_sha256_16,
            text_length=text_length,
            created_at=created_at,
            updated_at=updated_at,
            metadata=_json_clone(
                {
                    "source_refs": list(source_refs),
                    "privacy": "no_raw_payload_or_legal_text_stored",
                    **safe_metadata,
                }
            ),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clock_now(clock: Any | None) -> str:
    if clock is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if callable(clock):
        result = clock()
        if isinstance(result, str):
            return result
        if isinstance(result, datetime):
            return result.isoformat()
        return str(result)
    if isinstance(clock, str):
        return clock
    return str(clock)


def _validate_summary_metadata(metadata: Any, path: str = "$") -> dict[str, Any]:
    """Recursively validate metadata, raising SummaryPrivacyError on forbidden keys."""
    if isinstance(metadata, Mapping):
        output: dict[str, Any] = {}
        for key, child in metadata.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _FORBIDDEN_SUMMARY_KEYS:
                raise SummaryPrivacyError(
                    f"summary metadata contains forbidden field '{key_text}' at {child_path}"
                )
            if _SUMMARY_SECRET_KEY_PATTERN.search(key_text):
                raise SummaryPrivacyError(
                    f"summary metadata contains secret-like key '{key_text}' at {child_path}"
                )
            output[key_text] = _validate_summary_metadata(child, child_path)
        return output
    if isinstance(metadata, list):
        return [_validate_summary_metadata(item, f"{path}[{i}]") for i, item in enumerate(metadata)]  # type: ignore[return-value]
    if metadata is None:
        return {}  # type: ignore[return-value]
    return metadata  # type: ignore[return-value]


__all__ = [
    "RollingSummaryPolicy",
    "RollingSummaryProducer",
    "RollingSummaryTrigger",
    "SummaryPrivacyError",
]
