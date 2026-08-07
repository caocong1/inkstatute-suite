"""Decision logging — JSONL append per session.

Ports the JSONL decision logging pattern from
``lawfirm-profile/scripts/router.py`` (lines 299-337) into a reusable
module with configurable log directory.

Two public functions:

- :func:`append_decision_log` — appends a :class:`RouteDecision` as a
  JSON line to ``{log_dir}/{session_id}.jsonl``.  No-op when
  ``session_id`` is empty (callers can opt out).
- :func:`record_routing_error` — appends a routing-error record to the
  error log for ``route_mismatch`` feedback association.

Both functions write JSON with ``ensure_ascii=False`` to preserve
Chinese text.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_contract import RouteDecision


def _serialize_decision(decision: RouteDecision) -> dict[str, Any]:
    """Serialize a :class:`RouteDecision` to a plain dict.

    Uses ``dataclasses.asdict`` and converts any enum values to their
    string form so the result is JSON-serializable.
    """
    record = asdict(decision)
    # RouteMode (StrEnum) → str is handled by asdict, but ensure mode
    # is a plain string for JSON serialization.
    if hasattr(record.get("mode"), "value"):
        record["mode"] = str(record["mode"])
    return record


def append_decision_log(
    decision: RouteDecision,
    user_msg: str,
    log_dir: Path,
    session_id: str,
) -> None:
    """Append a decision record to the session's JSONL log.

    The log file is ``{log_dir}/{session_id}.jsonl``.  Each line is a
    JSON object containing all :class:`RouteDecision` fields plus
    ``timestamp`` (ISO-8601 UTC) and ``user_msg``.

    No-op when *session_id* is empty — callers can opt out of logging
    by passing an empty string.

    The log directory is created if it does not exist
    (``mkdir(parents=True, exist_ok=True)``).

    Args:
        decision: The :class:`RouteDecision` to log.
        user_msg: The user message that produced this decision.
        log_dir: Directory for per-session JSONL log files.
        session_id: Session identifier; empty string → no-op.
    """
    if not session_id:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{session_id}.jsonl"
    record = _serialize_decision(decision)
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    record["user_msg"] = user_msg
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_routing_error(
    decision: RouteDecision,
    user_msg: str,
    actual_skill: str,
    error_log: Path,
) -> None:
    """Append a routing-error record to the error log.

    Called when user feedback indicates the routed ``primary_skill``
    was wrong and the user/agent ended up using a different skill
    (*actual_skill*).  This is the ``route_mismatch`` feedback
    association pattern.

    The error log file is *error_log* (a single JSONL file, not
    per-session).  Each line is a JSON object with:

    - ``timestamp`` — ISO-8601 UTC
    - ``session_id`` — from ``decision.metadata["session_id"]``
    - ``user_msg`` — the original user message
    - ``router_primary`` — the router's ``primary_skill``
    - ``router_confidence`` — the router's ``confidence``
    - ``router_matched_rule`` — the router's ``matched_rule``
    - ``actual_skill`` — the skill the user/agent actually used

    The parent directory is created if it does not exist.

    Args:
        decision: The original :class:`RouteDecision` that was wrong.
        user_msg: The user message that was mis-routed.
        actual_skill: The skill the user/agent actually used.
        error_log: Path to the JSONL error log file.
    """
    error_log.parent.mkdir(parents=True, exist_ok=True)
    session_id = decision.metadata.get("session_id", "")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_msg": user_msg,
        "router_primary": decision.primary_skill,
        "router_confidence": decision.confidence,
        "router_matched_rule": decision.matched_rule,
        "actual_skill": actual_skill,
    }
    with error_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
