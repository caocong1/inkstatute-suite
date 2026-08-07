"""Privacy scanning & secrets detection for bridge output events.

This module scans unified :class:`RunEvent` objects produced by the
bridge for secret patterns (API keys, tokens, ACP subprocess credentials,
internal paths, provider leaks) and enforces **reference-first logging**
— all events that carry sensitive content fields must use
``raw_payload_ref`` (hash + length) instead of storing full text.

Secret patterns are derived from two sources:

1. **Existing patterns** from ``output_boundary.py`` (production-validated
   since V2): ``secret_like``, ``secret_assignment``, ``internal_path``,
   ``windows_path``, ``provider_leak``, ``api_error``.
2. **ACP-specific patterns** from RESEARCH.md §4: ``hermes_home_path``,
   ``hermes_dot_path``, ``acp_env_secret``, ``acp_debug``.

Additional patterns from ``channel-core/output_policy.py``:
``profile_path``, ``env_secret_combo``.

The scanner **never** includes the actual matched secret text in any
finding — only the pattern name (``matched_pattern``), the field path,
and audit metadata (hash prefix + length).

Binding constraints (AGENTS.md):

- "Contract logs prefer references such as ``raw_payload_ref`` and must
  not store sensitive full text by default."
- "Never commit secrets, tokens, runtime databases, logs, customer
  documents, or raw legal payloads."
- "ACP subprocess credentials, runtime message payloads must not be
  committed."
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from platform_runtime.protocols import RunEvent


# ---------------------------------------------------------------------------
# ScanResult dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The result of scanning a single event for secret patterns.

    Attributes
    ----------
    clean
        ``True`` if no secret patterns were found, ``False`` otherwise.
    findings
        A list of finding dicts.  Each finding contains ``rule_id``,
        ``matched_pattern`` (the pattern name, NOT the secret text),
        ``field_path``, and ``audit`` (hash prefix + length, no original
        text).
    event_id
        The ``event_id`` from the scanned event.
    event_type
        The ``event_type`` from the scanned event.
    """

    clean: bool
    findings: list[dict[str, Any]] = field(default_factory=list)
    event_id: str = ""
    event_type: str = ""


# ---------------------------------------------------------------------------
# Secret patterns — compiled regex
# ---------------------------------------------------------------------------

#: Compiled regex patterns for secret detection.
#: Reuses pattern categories from ``output_boundary.py`` and adds
#: ACP-specific patterns from RESEARCH.md §4.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern, re.IGNORECASE))
    for rule_id, pattern in (
        # --- From output_boundary.py ---
        ("secret_like", r"\b(?:access|refresh|api|client|encoding)[_-]?(?:token|key|secret)\b"),
        ("secret_assignment", r"\b(?:token|secret|key)\s*[:=]"),
        ("internal_path", r"(?:^|\s)(?:/[^ \n\t]+){2,}"),
        ("windows_path", r"[a-z]:\\[^ \n\t]+"),
        ("provider_leak", r"\b(?:model[:\s]|provider[:\s]|api[_-]?key|quota|token[_\s-]?usage)(?!\w)"),
        ("api_error", r"\b(?:api key invalid|quota exceeded|rate limit retry|insufficient quota)\b"),
        # --- ACP-specific (RESEARCH.md §4) ---
        ("hermes_home_path", r"/home/[^/]+/\.hermes"),
        ("hermes_dot_path", r"\.hermes[^/]"),
        ("acp_env_secret", r"\b(?:HERMES_HOME|ACP_[A-Z_]+|AGENT_[A-Z_]+)\s*[:=]\s*\S+"),
        ("acp_debug", r"\b(?:acp:|agent-client-protocol:)"),
        # --- From channel-core/output_policy.py ---
        ("profile_path", r"\bprofile path\b"),
        ("env_secret_combo", r"\benv\b.*\b(?:secret|token|key)\b"),
    )
)


# ---------------------------------------------------------------------------
# Sensitive field names — must use raw_payload_ref
# ---------------------------------------------------------------------------

#: Field names in event payloads that are considered sensitive and must
#: use ``raw_payload_ref`` instead of full text.
_SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "content",
    "delta",
    "raw_input",
    "raw_output",
    "text",
    "data",
    "body",
})


# ---------------------------------------------------------------------------
# Event types requiring raw_payload_ref
# ---------------------------------------------------------------------------

#: Event types whose payloads contain sensitive content fields and must
#: have ``raw_payload_ref`` in metadata.  Event types like
#: ``message.delta``, ``thought.delta``, ``elicitation.requested``,
#: ``permission.requested`` are exempt because their content is needed
#: for real-time user interaction or is inherently non-sensitive (short
#: deltas).
EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF: frozenset[str] = frozenset({
    "message.completed",
    "tool_call.completed",
    "artifact.created",
    "citation.recorded",
})


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


def _audit_value(value: str, *, rule_id: str, field_path: str) -> dict[str, Any]:
    """Return reference-first audit metadata for a matched value.

    Stores only a hash prefix and length — **no original text**.

    Parameters
    ----------
    value
        The matched string value (used only for hashing, never stored).
    rule_id
        The rule that triggered the finding.
    field_path
        The dotted path to the field containing the match.

    Returns
    -------
    dict
        Audit metadata with ``rule_id``, ``field_path``,
        ``input_hash_prefix`` (16 hex chars), ``input_length``, and
        ``privacy`` marker.
    """
    return {
        "rule_id": rule_id,
        "field_path": field_path,
        "input_hash_prefix": hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
        "input_length": len(value),
        "privacy": "no_original_text_stored",
    }


# ---------------------------------------------------------------------------
# String scanning
# ---------------------------------------------------------------------------


def _scan_string(value: str, field_path: str) -> list[dict[str, Any]]:
    """Scan a single string value against all secret patterns.

    Parameters
    ----------
    value
        The string to scan.
    field_path
        The dotted path to this field.

    Returns
    -------
    list[dict]
        A list of finding dicts.  Each finding contains ``rule_id``,
        ``matched_pattern`` (the pattern name, NOT the secret text),
        ``field_path``, and ``audit``.  Does NOT include the matched
        text itself.
    """
    findings: list[dict[str, Any]] = []
    for rule_id, pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            findings.append({
                "rule_id": rule_id,
                "matched_pattern": rule_id,
                "field_path": field_path,
                "audit": _audit_value(value, rule_id=rule_id, field_path=field_path),
            })
    return findings


# ---------------------------------------------------------------------------
# Dict scanning (recursive)
# ---------------------------------------------------------------------------


def _scan_dict(obj: dict[str, Any], field_path: str = "") -> list[dict[str, Any]]:
    """Recursively scan all string values in a dict.

    For each key, constructs the field path as
    ``f"{field_path}.{key}"`` (or just ``key`` if ``field_path`` is
    empty).  For nested dicts, recurses.  For lists, scans each element
    with path ``f"{field_path}.{key}[{i}]"``.

    Parameters
    ----------
    obj
        The dict to scan.
    field_path
        The current dotted path prefix (empty for top-level).

    Returns
    -------
    list[dict]
        Aggregated findings from all string values in the dict.
    """
    findings: list[dict[str, Any]] = []
    for key, val in obj.items():
        current_path = f"{field_path}.{key}" if field_path else str(key)
        if isinstance(val, str):
            findings.extend(_scan_string(val, current_path))
        elif isinstance(val, dict):
            findings.extend(_scan_dict(val, current_path))
        elif isinstance(val, list):
            for i, item in enumerate(val):
                item_path = f"{current_path}[{i}]"
                if isinstance(item, str):
                    findings.extend(_scan_string(item, item_path))
                elif isinstance(item, dict):
                    findings.extend(_scan_dict(item, item_path))
                # Other types (int, float, bool, None) are not scanned
    return findings


# ---------------------------------------------------------------------------
# Event scanning
# ---------------------------------------------------------------------------


def scan_event(event: RunEvent) -> ScanResult:
    """Scan a :class:`RunEvent` for secret patterns.

    Scans ``event.payload`` and ``event.metadata`` (all string values
    recursively).

    Parameters
    ----------
    event
        The :class:`RunEvent` to scan.

    Returns
    -------
    ScanResult
        A :class:`ScanResult` with ``clean=True`` if no findings,
        ``clean=False`` if any secrets detected.  The ``event_id`` and
        ``event_type`` are copied from the event.
    """
    findings: list[dict[str, Any]] = []

    # Scan payload
    if isinstance(event.payload, dict):
        findings.extend(_scan_dict(event.payload, "payload"))

    # Scan metadata
    if isinstance(event.metadata, dict):
        findings.extend(_scan_dict(event.metadata, "metadata"))

    return ScanResult(
        clean=len(findings) == 0,
        findings=findings,
        event_id=event.event_id,
        event_type=event.event_type,
    )


def scan_events(events: list[RunEvent]) -> list[ScanResult]:
    """Scan a list of events for secret patterns.

    Parameters
    ----------
    events
        A list of :class:`RunEvent` objects to scan.

    Returns
    -------
    list[ScanResult]
        A list of :class:`ScanResult` objects (one per event).  Events
        with no findings have ``clean=True``.
    """
    return [scan_event(event) for event in events]


# ---------------------------------------------------------------------------
# Reference-first logging enforcement
# ---------------------------------------------------------------------------


def assert_reference_first(event: RunEvent) -> bool:
    """Check that an event uses reference-first logging.

    Returns ``True`` if:

    - The event's metadata contains a ``raw_payload_ref`` key, **or**
    - The event type does not require reference-first logging (e.g.
      elicitation and permission events which need their content for
      user interaction, or delta events which carry short non-sensitive
      deltas).

    Returns ``False`` if a sensitive field (``content``, ``delta``,
    ``text``, ``data``, ``body``) exists in the payload but no
    ``raw_payload_ref`` is present in metadata.

    This enforces the AGENTS.md constraint: "Contract logs prefer
    references such as ``raw_payload_ref`` and must not store sensitive
    full text by default."

    Parameters
    ----------
    event
        The :class:`RunEvent` to check.

    Returns
    -------
    bool
        ``True`` if the event is reference-first compliant, ``False``
        otherwise.
    """
    # Exempt event types — their content is needed for real-time user
    # interaction or is inherently non-sensitive.
    if event.event_type not in EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF:
        return True

    # Check if raw_payload_ref is present in metadata
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    if "raw_payload_ref" in metadata:
        return True

    # Check if any sensitive field exists in payload
    payload = event.payload if isinstance(event.payload, dict) else {}
    has_sensitive_field = any(
        key in _SENSITIVE_FIELD_NAMES for key in payload
    )

    if has_sensitive_field:
        return False

    # No sensitive fields and no raw_payload_ref — still compliant
    # (event may carry only non-sensitive metadata)
    return True


def assert_all_reference_first(events: list[RunEvent]) -> list[str]:
    """Check all events for reference-first compliance.

    Parameters
    ----------
    events
        A list of :class:`RunEvent` objects to check.

    Returns
    -------
    list[str]
        A list of ``event_id`` strings for events that violate the
        reference-first rule.  Empty list if all events are compliant.
    """
    violations: list[str] = []
    for event in events:
        if not assert_reference_first(event):
            violations.append(event.event_id)
    return violations


__all__ = [
    "ScanResult",
    "scan_event",
    "scan_events",
    "assert_reference_first",
    "assert_all_reference_first",
    "EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF",
]
