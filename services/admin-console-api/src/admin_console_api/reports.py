"""Reports dashboard handler — bounded aggregation from contract log + feedback queue.

``handle_reports`` validates the ``window`` query parameter, resolves the
time range in UTC, calls ``ReportsAggregator.build``, and merges the gate
summary from ``admin_console_api.gates``.  The response is scrubbed via
``scrub_contract_payload`` before serialization (T-81-06).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from conversation_read_view.privacy import scrub_contract_payload

from .gates import run_gate_summary

_VALID_WINDOWS = ("today", "7d", "30d", "custom")


def _load_zone(tz_name: str) -> timezone:
    """Return a timezone from a name, falling back to UTC on unknown names."""

    if not tz_name or tz_name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def _resolve_window(
    window: str,
    query: Mapping[str, str],
    display_tz: str,
) -> tuple[datetime, datetime]:
    """Resolve ``time_from``/``time_to`` in UTC for the requested window."""

    now_utc = datetime.now(timezone.utc)
    if window == "today":
        zone = _load_zone(display_tz)
        now_local = now_utc.astimezone(zone)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        time_from = start_local.astimezone(timezone.utc)
        time_to = now_utc
        return time_from, time_to
    if window == "7d":
        return now_utc - timedelta(days=7), now_utc
    if window == "30d":
        return now_utc - timedelta(days=30), now_utc
    # custom
    time_from = _parse_iso(query.get("from"))
    time_to = _parse_iso(query.get("to"))
    if time_from is None:
        time_from = now_utc - timedelta(days=7)
    if time_to is None:
        time_to = now_utc
    if time_from > time_to:
        time_from, time_to = time_to, time_from
    return time_from, time_to


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def handle_reports(
    query: Mapping[str, str],
    reports_aggregator: Any,
    feedback_queue: Any,
    feature_flags: Any,
    tenant_filter: Any = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``GET /reports`` — return aggregate report statistics.

    Returns ``200`` with the aggregate payload, ``400`` for unknown windows,
    or ``500`` on aggregator errors.
    """

    source = env if env is not None else {}
    window = str(query.get("window", "7d")).lower()
    if window not in _VALID_WINDOWS:
        return 400, {
            "error": {
                "code": "invalid_window",
                "message": f"window must be one of {list(_VALID_WINDOWS)}",
            },
            "metadata": {"admin_api": True, "read_only": True},
        }

    display_tz = str(source.get("INKSTATUTE_REPORT_DISPLAY_TZ", "UTC"))
    time_from, time_to = _resolve_window(window, query, display_tz)

    if reports_aggregator is None:
        return 500, {
            "error": {
                "code": "reports_not_configured",
                "message": "reports aggregator is not available",
            },
            "metadata": {"admin_api": True, "read_only": True},
        }

    try:
        aggregate = reports_aggregator.build(
            time_from,
            time_to,
            feedback_queue,
            tenant_filter=tenant_filter,
        )
    except ValueError:
        return 500, {
            "error": {
                "code": "reports_aggregation_failed",
                "message": "failed to aggregate report data",
            },
            "metadata": {"admin_api": True, "read_only": True},
        }

    # Merge gate summary (subprocess-isolated, never raises).
    gate_summary = run_gate_summary()
    gates_payload: dict[str, Any] = {
        "passed": gate_summary.get("passed", False),
        "gate_count": len(gate_summary.get("gates", [])),
    }
    if "error" in gate_summary:
        gates_payload["error"] = gate_summary["error"]

    aggregate["gates"] = gates_payload
    aggregate["metadata"]["window"] = window

    # Scrub the final payload (T-81-06) — fail closed on forbidden keys.
    scrubbed = scrub_contract_payload(aggregate)
    scrubbed["metadata"] = aggregate["metadata"]
    scrubbed["gates"] = gates_payload

    return 200, scrubbed


__all__ = ["handle_reports"]
