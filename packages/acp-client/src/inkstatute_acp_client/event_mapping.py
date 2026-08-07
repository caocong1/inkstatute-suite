"""ACP session/update variants → unified RunEvent mapping.

Maps ACP ``session/update`` notification variants to Phase 88's unified
event vocabulary.  The mapping is isomorphic — the platform stays a thin
relay between ACP backends and client-facing SSE.

See RESEARCH.md §3 for the full mapping table (13 ACP variants → 13
unified event types).
"""

from __future__ import annotations

import uuid
from typing import Any

from platform_contract.enums import RunEventType
from platform_runtime.protocols import RunEvent

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Mapping from ACP update type strings to RunEventType V3 values for
#: the simple (status-independent) cases.
ACP_UPDATE_TYPE_TO_EVENT_TYPE: dict[str, str] = {
    "agent_message_chunk": RunEventType.MESSAGE_DELTA_V3.value,
    "agent_message": RunEventType.MESSAGE_COMPLETED.value,
    "agent_thought_chunk": RunEventType.THOUGHT_DELTA.value,
    "plan": RunEventType.PLAN_UPDATED.value,
    "plan_update": RunEventType.PLAN_UPDATED.value,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_update(notification: dict) -> dict | None:
    """Extract the ``update`` dict from a notification.

    Handles both the ``session/update`` notification format (with
    ``params.update``) and direct update dicts (where the notification
    itself *is* the update).
    """
    params = notification.get("params")
    if isinstance(params, dict):
        update = params.get("update")
        if isinstance(update, dict):
            return update
    # Direct update dict
    update = notification.get("update")
    if isinstance(update, dict):
        return update
    return None


def _make_run_event(
    run_id: str,
    seq: int,
    occurred_at: str,
    event_type: str,
    payload: dict,
    metadata: dict | None = None,
) -> RunEvent:
    """Construct a :class:`RunEvent` with a generated event_id."""
    return RunEvent(
        event_id=str(uuid.uuid4()),
        run_id=run_id,
        event_type=event_type,
        occurred_at=occurred_at,
        seq=seq,
        payload=payload,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------


def map_acp_update_to_run_event(
    acp_notification: dict,
    run_id: str,
    seq: int,
    occurred_at: str,
) -> RunEvent | None:
    """Map an ACP notification to a unified :class:`RunEvent`.

    Parameters
    ----------
    acp_notification
        The raw ACP JSON-RPC notification dict (or a direct update dict).
    run_id
        The platform run identifier to attach.
    seq
        The sequence number for this event.
    occurred_at
        ISO-8601 timestamp string.

    Returns
    -------
    RunEvent | None
        The mapped event, or ``None`` if the notification type is
        unrecognized (caller should skip).
    """
    method = acp_notification.get("method", "")

    # --- JSON-RPC error -------------------------------------------------
    if "error" in acp_notification:
        error = acp_notification["error"]
        if not isinstance(error, dict):
            error = {}
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.ERROR.value,
            {
                "error": {
                    "category": "runtime_error",
                    "code": "acp_error",
                    "message": error.get("message", "Unknown ACP error"),
                }
            },
        )

    # --- elicitation/create ---------------------------------------------
    if method == "elicitation/create":
        params = acp_notification.get("params", {})
        if not isinstance(params, dict):
            params = {}
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.ELICITATION_REQUESTED.value,
            {
                "interrupt_id": params.get("id", ""),
                "intro": params.get("intro", ""),
                "questions": params.get("questions", []),
                "resume_state_ref": params.get("resume_state_ref"),
            },
        )

    # --- session/request_permission -------------------------------------
    if method == "session/request_permission":
        params = acp_notification.get("params", {})
        if not isinstance(params, dict):
            params = {}
        # CRITICAL: must NOT include auto_approve or default_decision
        # (AGENTS.md: Permission requests must never be auto-approved)
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.PERMISSION_REQUESTED.value,
            {
                "permission_id": params.get("id", ""),
                "tool_call_id": params.get("tool_call_id", ""),
                "description": params.get("description", ""),
                "kind": params.get("kind"),
            },
        )

    # --- session/cancel -------------------------------------------------
    if method == "session/cancel":
        params = acp_notification.get("params", {})
        if not isinstance(params, dict):
            params = {}
        update = params.get("update", {})
        status = update.get("status", "cancelled") if isinstance(update, dict) else "cancelled"
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.RUN_STATE_CHANGED.value,
            {"status": status},
        )

    # --- session/update (and direct update dicts) -----------------------
    update = _extract_update(acp_notification)
    if update is None:
        return None

    update_type = update.get("type", "")

    # 1. agent_message_chunk → message.delta
    if update_type == "agent_message_chunk":
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.MESSAGE_DELTA_V3.value,
            {
                "delta": update.get("content", ""),
                "message_id": update.get("messageId"),
            },
        )

    # 2. agent_message → message.completed
    if update_type == "agent_message":
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.MESSAGE_COMPLETED.value,
            {
                "content": update.get("content", ""),
                "message_id": update.get("messageId"),
            },
        )

    # 3. agent_thought_chunk → thought.delta
    if update_type == "agent_thought_chunk":
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.THOUGHT_DELTA.value,
            {"delta": update.get("content", "")},
        )

    # 4. tool_call_update → tool_call.started/delta/completed
    if update_type == "tool_call_update":
        status = update.get("status", "")
        tool_call_id = update.get("toolCallId", update.get("tool_call_id", ""))
        tool_name = update.get("toolName", update.get("tool_name", ""))
        content = update.get("content", "")
        raw_input_ref = update.get("raw_input_ref", update.get("rawInputRef"))
        raw_output_ref = update.get("raw_output_ref", update.get("rawOutputRef"))

        if status in ("pending", "in_progress"):
            # If pending (first seen), map to started; if in_progress, map to delta
            if status == "pending":
                event_type = RunEventType.TOOL_CALL_STARTED_V3.value
            else:
                event_type = RunEventType.TOOL_CALL_DELTA.value
            return _make_run_event(
                run_id,
                seq,
                occurred_at,
                event_type,
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "status": status,
                    "content": content,
                    "raw_input_ref": raw_input_ref,
                    "raw_output_ref": raw_output_ref,
                },
            )
        elif status in ("completed", "failed"):
            return _make_run_event(
                run_id,
                seq,
                occurred_at,
                RunEventType.TOOL_CALL_COMPLETED_V3.value,
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "status": status,
                    "content": content,
                    "raw_input_ref": raw_input_ref,
                    "raw_output_ref": raw_output_ref,
                },
            )
        else:
            # Unknown tool_call_update status — skip
            return None

    # 5. plan / plan_update → plan.updated
    if update_type in ("plan", "plan_update"):
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.PLAN_UPDATED.value,
            {"plan": update.get("plan", [])},
        )

    # 6. elicitation (as session/update variant)
    if update_type == "elicitation":
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.ELICITATION_REQUESTED.value,
            {
                "interrupt_id": update.get("id", ""),
                "intro": update.get("intro", ""),
                "questions": update.get("questions", []),
                "resume_state_ref": update.get("resume_state_ref"),
            },
        )

    # 7. status → run.state_changed
    if update_type == "status":
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.RUN_STATE_CHANGED.value,
            {"status": update.get("status", "")},
        )

    # 8. Artifact content blocks → artifact.created
    if "artifact" in update:
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.ARTIFACT_CREATED_V3.value,
            {"artifact": update.get("artifact")},
        )

    # 9. Citation in _meta → citation.recorded
    meta = update.get("_meta", {})
    if isinstance(meta, dict) and "citation" in meta:
        return _make_run_event(
            run_id,
            seq,
            occurred_at,
            RunEventType.CITATION_RECORDED.value,
            {"citations": meta.get("citation", [])},
        )

    # 10. Unrecognized type — return None (caller skips)
    return None


__all__ = [
    "ACP_UPDATE_TYPE_TO_EVENT_TYPE",
    "map_acp_update_to_run_event",
]
