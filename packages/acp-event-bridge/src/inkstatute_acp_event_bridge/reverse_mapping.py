"""Reverse mapping — unified user responses → ACP JSON-RPC responses.

ACP v1 does NOT use separate methods for user responses.  Instead,
responses are JSON-RPC responses to the original request IDs.  This
module constructs those response envelopes for:

- **Elicitation answers** — response to ``elicitation/create``
- **Permission decisions** — response to ``session/request_permission``
- **Run cancellation** — new ``session/cancel`` request

All functions are pure (no side effects, no I/O).  No function produces
``auto_approve``, ``default_decision``, or ``allow_once`` fields — the
caller decides the outcome, not this module.

See RESEARCH.md §1 for the exact ACP v1 response formats.
"""

from __future__ import annotations

from platform_contract.enums import RunEventType

#: Valid actions for elicitation responses.
_ELCITATION_ACTIONS: frozenset[str] = frozenset({"accept", "decline", "cancel"})

#: Valid outcomes for permission responses.
_PERMISSION_OUTCOMES: frozenset[str] = frozenset({"selected", "cancelled"})


# ---------------------------------------------------------------------------
# Elicitation response
# ---------------------------------------------------------------------------


def map_elicitation_response_to_acp(
    original_request_id: str,
    action: str,
    content: dict | None = None,
) -> dict:
    """Construct a JSON-RPC response for an elicitation answer.

    Parameters
    ----------
    original_request_id
        The JSON-RPC ``id`` from the original ``elicitation/create`` request.
    action
        One of ``"accept"``, ``"decline"``, ``"cancel"``.
    content
        User-provided data dict.  Only included when ``action == "accept"``;
        for ``decline`` and ``cancel``, ``content`` is omitted.

    Returns
    -------
    dict
        A JSON-RPC 2.0 response dict::

            {
              "jsonrpc": "2.0",
              "id": "<original_request_id>",
              "result": {
                "action": "accept" | "decline" | "cancel",
                "content": { ... }  # only when action == "accept"
              }
            }

    Raises
    ------
    ValueError
        If ``action`` is not one of the valid values or
        ``original_request_id`` is empty.
    """
    if not original_request_id:
        raise ValueError("original_request_id must be non-empty")
    if action not in _ELCITATION_ACTIONS:
        raise ValueError(
            f"Invalid elicitation action: {action!r}. "
            f"Must be one of {sorted(_ELCITATION_ACTIONS)}"
        )

    result: dict = {"action": action}
    if action == "accept" and content is not None:
        result["content"] = content

    return {
        "jsonrpc": "2.0",
        "id": original_request_id,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Permission decision response
# ---------------------------------------------------------------------------


def map_permission_decision_to_acp(
    original_request_id: str,
    outcome: str,
    option_id: str | None = None,
) -> dict:
    """Construct a JSON-RPC response for a permission decision.

    CRITICAL: This function only constructs the JSON-RPC envelope.  The
    decision of whether to allow/deny is made by the **user**, not by
    this function.  This function must NEVER produce a response that
    auto-approves a dangerous permission.

    Parameters
    ----------
    original_request_id
        The JSON-RPC ``id`` from the original ``session/request_permission``
        request.
    outcome
        One of ``"selected"``, ``"cancelled"``.
    option_id
        The selected option id.  Only included when ``outcome == "selected"``;
        for ``cancelled``, ``optionId`` is omitted.

    Returns
    -------
    dict
        A JSON-RPC 2.0 response dict::

            {
              "jsonrpc": "2.0",
              "id": "<original_request_id>",
              "result": {
                "outcome": {
                  "outcome": "selected" | "cancelled",
                  "optionId": "<option_id>"  # only when outcome == "selected"
                }
              }
            }

    Raises
    ------
    ValueError
        If ``outcome`` is not one of the valid values or
        ``original_request_id`` is empty.
    """
    if not original_request_id:
        raise ValueError("original_request_id must be non-empty")
    if outcome not in _PERMISSION_OUTCOMES:
        raise ValueError(
            f"Invalid permission outcome: {outcome!r}. "
            f"Must be one of {sorted(_PERMISSION_OUTCOMES)}"
        )

    outcome_dict: dict = {"outcome": outcome}
    if outcome == "selected" and option_id is not None:
        outcome_dict["optionId"] = option_id

    return {
        "jsonrpc": "2.0",
        "id": original_request_id,
        "result": {"outcome": outcome_dict},
    }


# ---------------------------------------------------------------------------
# Run cancellation request
# ---------------------------------------------------------------------------


def map_run_cancel_to_acp(session_id: str) -> dict:
    """Construct a ``session/cancel`` JSON-RPC request.

    Unlike elicitation/permission responses, cancellation is a **new**
    request (not a response to an existing request).  The ``id`` field
    is set to ``None`` as a placeholder — the bridge replaces it with
    an actual incrementing id when sending.

    Parameters
    ----------
    session_id
        The ACP session id to cancel.

    Returns
    -------
    dict
        A JSON-RPC 2.0 request dict::

            {
              "jsonrpc": "2.0",
              "id": null,
              "method": "session/cancel",
              "params": { "sessionId": "<session_id>" }
            }
    """
    return {
        "jsonrpc": "2.0",
        "id": None,
        "method": "session/cancel",
        "params": {"sessionId": session_id},
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def map_unified_event_to_acp_response(
    event_type: str,
    payload: dict,
    original_request_id: str,
) -> dict | None:
    """Dispatch to the appropriate reverse mapping function based on event type.

    Parameters
    ----------
    event_type
        The unified event type string (e.g. ``"elicitation.requested"``).
    payload
        The response payload dict containing ``action``/``outcome`` and
        ``content``/``option_id`` fields.
    original_request_id
        The original ACP JSON-RPC request id to correlate the response with.

    Returns
    -------
    dict | None
        The ACP JSON-RPC response dict, or ``None`` if the event type
        is unrecognized.
    """
    if event_type == RunEventType.ELICITATION_REQUESTED.value:
        action = payload.get("action", "")
        content = payload.get("content")
        return map_elicitation_response_to_acp(
            original_request_id, action, content
        )

    if event_type == RunEventType.PERMISSION_REQUESTED.value:
        outcome = payload.get("outcome", "")
        option_id = payload.get("option_id")
        return map_permission_decision_to_acp(
            original_request_id, outcome, option_id
        )

    # Unrecognized event type — caller should skip
    return None


__all__ = [
    "map_elicitation_response_to_acp",
    "map_permission_decision_to_acp",
    "map_run_cancel_to_acp",
    "map_unified_event_to_acp_response",
]
