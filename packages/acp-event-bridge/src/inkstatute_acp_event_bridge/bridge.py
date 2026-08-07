"""EventBridge — bidirectional ACP ↔ unified event mapping with request_id correlation.

The :class:`EventBridge` integrates:

- **Forward mapping** (ACP → unified) via ``map_acp_update_to_run_event``
  from ``acp-client``.
- **Reverse mapping** (unified → ACP) via the functions in
  :mod:`inkstatute_acp_event_bridge.reverse_mapping`.
- **Request ID correlation** — stores the original ACP request IDs from
  ``elicitation/create`` and ``session/request_permission`` notifications
  so user responses can be correlated back to the correct JSON-RPC
  response.

The bridge is V3-events-only (Key Decision #4 from CONTEXT.md) — it does
not handle V2 legacy event types.  The bridge must NOT auto-approve any
permission — it only constructs the response envelope; the caller
decides the outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone

from platform_contract.enums import RunEventType
from platform_runtime.protocols import RunEvent

from inkstatute_acp_client.event_mapping import map_acp_update_to_run_event

from .reverse_mapping import map_run_cancel_to_acp, map_unified_event_to_acp_response


class EventBridge:
    """Bidirectional ACP ↔ unified event bridge with request_id correlation.

    The bridge sits between the ACP client (which handles transport and
    session lifecycle) and the platform runtime (which consumes unified
    events).  It transforms events in both directions and maintains the
    ``request_id`` → unified event correlation needed for JSON-RPC
    response routing.
    """

    def __init__(self, run_id: str) -> None:
        """Initialize the bridge.

        Parameters
        ----------
        run_id
            The platform run identifier to attach to all mapped events.
        """
        self._run_id = run_id
        self._seq_counter: int = 0
        self._request_id_map: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Forward mapping (ACP → unified)
    # ------------------------------------------------------------------

    def ingest_acp_notification(
        self,
        notification: dict,
        occurred_at: str | None = None,
    ) -> RunEvent | None:
        """Map an ACP notification to a unified :class:`RunEvent`.

        Calls :func:`map_acp_update_to_run_event` from ``acp-client``.
        Before returning the event, if the notification is an
        ``elicitation/create`` or ``session/request_permission`` request,
        records the ``request_id`` in the internal map for later
        correlation with user responses.

        Parameters
        ----------
        notification
            The raw ACP JSON-RPC notification dict.
        occurred_at
            ISO-8601 timestamp string.  If ``None``, uses the current
            UTC time.

        Returns
        -------
        RunEvent | None
            The mapped event, or ``None`` if the notification type is
            unrecognized.
        """
        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self._seq_counter += 1
        event = map_acp_update_to_run_event(
            notification,
            run_id=self._run_id,
            seq=self._seq_counter,
            occurred_at=occurred_at,
        )

        if event is None:
            # Unrecognized notification — roll back the seq increment
            self._seq_counter -= 1
            return None

        # Record request_id for elicitation and permission notifications
        method = notification.get("method", "")
        if method == "elicitation/create":
            request_id = notification.get("id") or notification.get("params", {}).get("id", "")
            if request_id:
                self._request_id_map[request_id] = {
                    "request_id": request_id,
                    "type": "elicitation",
                    "event_type": RunEventType.ELICITATION_REQUESTED.value,
                }
        elif method == "session/request_permission":
            request_id = notification.get("id") or notification.get("params", {}).get("id", "")
            if request_id:
                self._request_id_map[request_id] = {
                    "request_id": request_id,
                    "type": "permission",
                    "event_type": RunEventType.PERMISSION_REQUESTED.value,
                }

        return event

    # ------------------------------------------------------------------
    # Reverse mapping (unified → ACP)
    # ------------------------------------------------------------------

    def build_acp_response(
        self,
        unified_event_type: str,
        response_payload: dict,
    ) -> dict | None:
        """Construct an ACP JSON-RPC response for a user response.

        Looks up the original ``request_id`` from the internal map based
        on the unified event type, then delegates to
        :func:`map_unified_event_to_acp_response`.

        Parameters
        ----------
        unified_event_type
            The unified event type string (e.g. ``"elicitation.requested"``).
        response_payload
            The response payload dict containing ``action``/``outcome``
            and ``content``/``option_id`` fields.

        Returns
        -------
        dict | None
            The ACP JSON-RPC response dict, or ``None`` if no matching
            request_id is found or the event type is unrecognized.
        """
        # Find the most recent matching request_id
        request_id = self._find_request_id(unified_event_type)
        if request_id is None:
            return None

        return map_unified_event_to_acp_response(
            unified_event_type,
            response_payload,
            request_id,
        )

    def build_cancel_request(self, session_id: str) -> dict:
        """Construct a ``session/cancel`` JSON-RPC request.

        Delegates to :func:`map_run_cancel_to_acp`.

        Parameters
        ----------
        session_id
            The ACP session id to cancel.

        Returns
        -------
        dict
            The ``session/cancel`` JSON-RPC request dict.
        """
        return map_run_cancel_to_acp(session_id)

    # ------------------------------------------------------------------
    # Request tracking
    # ------------------------------------------------------------------

    def get_pending_requests(self) -> list[dict]:
        """Return a list of pending request metadata.

        Returns
        -------
        list[dict]
            A list of dicts, each containing ``request_id``, ``type``
            (elicitation/permission), and ``event_type``.
        """
        return list(self._request_id_map.values())

    def mark_request_responded(self, request_id: str) -> None:
        """Mark a request as responded by removing it from the pending map.

        Parameters
        ----------
        request_id
            The ACP JSON-RPC request id to remove.
        """
        self._request_id_map.pop(request_id, None)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def seq(self) -> int:
        """Return the current sequence counter value."""
        return self._seq_counter

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_request_id(self, unified_event_type: str) -> str | None:
        """Find the most recent request_id for the given unified event type.

        Searches the ``_request_id_map`` for entries whose ``event_type``
        matches the given ``unified_event_type``.  Returns the last
        matching entry's ``request_id``, or ``None`` if no match is found.
        """
        matching = [
            entry
            for entry in self._request_id_map.values()
            if entry.get("event_type") == unified_event_type
        ]
        if not matching:
            return None
        return matching[-1]["request_id"]


__all__ = ["EventBridge"]
