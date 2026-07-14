"""Admin API handler for contract event audit trail (Phase 83)."""

from __future__ import annotations

from typing import Any, Mapping

from conversation_read_view.audit import AUDIT_EVENT_TYPES, handle_audit_get


def handle_audit(
    path: str,
    query: Mapping[str, str],
    read_model: Any,
    feature_flags: Any,
    tenant_filter: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``GET /audit`` (paginated audit trail) and ``GET /audit/<trace_id>``.

    ``GET /audit`` returns AgentTurn and FeedbackEvent records in
    reverse-chronological order with cursor pagination and event-type filter.
    ``GET /audit/<trace_id>`` returns the full trace reconstruction with a
    field allowlist applied.
    """
    if not feature_flags.admin_api_enabled:
        return 503, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            }
        }

    if read_model is None:
        return 503, {
            "error": {
                "code": "audit_unavailable",
                "message": "Audit read model is not configured",
            }
        }

    # Validate event_type query param if present (only for list endpoint).
    route_path = path.split("?")[0]
    if not route_path.startswith("/audit/"):
        event_type = query.get("event_type")
        if event_type is not None and event_type not in AUDIT_EVENT_TYPES:
            return 400, {
                "error": {
                    "code": "invalid_event_type",
                    "message": "event_type must be 'agent_turn', 'feedback_event', or absent",
                    "event_type": event_type,
                },
                "metadata": {
                    "admin_api": True,
                    "read_only": True,
                },
            }

    status, body = handle_audit_get(path, query, read_model, tenant_filter=tenant_filter)

    # Merge admin metadata into the response.
    if isinstance(body, dict):
        metadata = body.get("metadata")
        if isinstance(metadata, dict):
            metadata["admin_api"] = True
            metadata["read_only"] = True
        else:
            body["metadata"] = {"admin_api": True, "read_only": True}

    return status, body


__all__ = ["handle_audit"]
