"""CSV and JSON export serializers for conversation-read-view query results.

Uses only stdlib modules (``csv``, ``io``, ``json``, ``typing``) so the
package stays dependency-light (``dependencies = []``).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any


CONVERSATION_CSV_COLUMNS = ["conversation_id", "turn_count", "user_ids", "occurred_at"]
TASK_CSV_COLUMNS = ["task_id", "turn_id", "conversation_id", "trace_id", "status", "occurred_at"]


def export_json(items: list[dict[str, Any]]) -> str:
    """Serialize scrubbed items as a JSON string with count and metadata."""

    return json.dumps(
        {
            "items": items,
            "count": len(items),
            "metadata": {
                "derived_from_contract_log": True,
                "format": "json",
            },
        },
        indent=2,
        sort_keys=True,
    )


def _project_conversation_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "conversation_id": item.get("conversation_id", ""),
        "turn_count": item.get("turn_count", ""),
        "user_ids": ",".join(str(uid) for uid in item.get("user_ids", [])),
        "occurred_at": item.get("occurred_at", ""),
    }


def _project_task_row(item: dict[str, Any]) -> dict[str, Any]:
    trace_id = item.get("trace_id")
    return {
        "task_id": item.get("task_id", ""),
        "turn_id": item.get("turn_id", ""),
        "conversation_id": item.get("conversation_id", ""),
        "trace_id": trace_id if trace_id is not None else "",
        "status": item.get("status", ""),
        "occurred_at": item.get("occurred_at", ""),
    }


def export_csv(items: list[dict[str, Any]], resource: str) -> str:
    """Serialize scrubbed items as a flat CSV string using stdlib ``csv``.

    Nested fields (``agent_result``, ``route_decision``, ``execution_trace``,
    ``turns``, ``feedback_events``) are omitted to keep rows flat.
    """

    columns = CONVERSATION_CSV_COLUMNS if resource == "conversations" else TASK_CSV_COLUMNS
    project = _project_conversation_row if resource == "conversations" else _project_task_row

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(project(item))
    return buffer.getvalue()


def csv_metadata(resource: str) -> dict[str, Any]:
    """Return metadata describing the CSV projection for the given resource."""

    return {
        "derived_from_contract_log": True,
        "format": "csv",
        "resource": resource,
        "csv_projection": CONVERSATION_CSV_COLUMNS if resource == "conversations" else TASK_CSV_COLUMNS,
    }


__all__ = [
    "CONVERSATION_CSV_COLUMNS",
    "TASK_CSV_COLUMNS",
    "csv_metadata",
    "export_csv",
    "export_json",
]
