"""Bounded, privacy-safe report aggregator for contract logs."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from platform_runtime.privacy_keys import ALL_FORBIDDEN_KEYS

from .privacy import scrub_contract_payload


JSONL_CHUNK_SIZE = 64 * 1024

_COMPLETED_STATUSES = {"success", "partial"}
_FAILED_STATUSES = {"failed", "blocked", "needs_clarification"}


def _parse_iso(value: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Naive strings are interpreted as UTC.  Datetime objects are converted to
    UTC when they carry a timezone; naive datetimes are treated as UTC.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_zone(tz_name: str) -> timezone:
    """Return a timezone from a name, falling back to UTC on unknown names."""

    if not tz_name or tz_name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def _reverse_line_reader(path: str | Path, *, chunk_size: int = JSONL_CHUNK_SIZE):
    """Yield non-empty lines of a file from EOF to start."""

    with open(path, "rb") as fh:
        segment: bytes | None = None
        total = fh.seek(0, 2)
        while total > 0:
            offset = min(chunk_size, total)
            fh.seek(total - offset)
            buffer = fh.read(offset)
            total -= offset
            if not buffer:
                continue
            lines = buffer.split(b"\n")
            if segment is not None:
                if buffer[-1:] != b"\n":
                    lines[-1] = lines[-1] + segment
                else:
                    lines.append(segment)
            segment = lines[0]
            for line in reversed(lines[1:]):
                if line:
                    yield line.decode("utf-8", errors="replace")
        if segment:
            yield segment.decode("utf-8", errors="replace")


class ReportsAggregator:
    """Aggregate reports by tail-reading a contract JSONL log.

    The scanner reads from EOF backwards in fixed-size chunks, stopping once
    it has processed ``max_scan_lines`` records or the event time falls before
    ``time_from - lookback_seconds``.  It never loads the entire file into the
    read model.
    """

    def __init__(
        self,
        contract_log_path: str | Path | None,
        default_max_scan_lines: int = 10000,
        default_lookback_seconds: float = 86400.0,
        long_task_threshold_seconds: float = 60.0,
        display_tz: str = "UTC",
        env: Mapping[str, str] | None = None,
    ) -> None:
        source = env if env is not None else os.environ
        self.contract_log_path = str(contract_log_path) if contract_log_path else None
        self.default_max_scan_lines = int(
            source.get("REPORTS_MAX_SCAN_LINES", default_max_scan_lines)
        )
        self.default_lookback_seconds = float(
            source.get("REPORTS_SCAN_LOOKBACK_SECONDS", default_lookback_seconds)
        )
        self.long_task_threshold_seconds = float(
            source.get(
                "REPORTS_LONG_TASK_THRESHOLD_SECONDS",
                long_task_threshold_seconds,
            )
        )
        self.display_tz = str(source.get("INKSTATUTE_REPORT_DISPLAY_TZ", display_tz))

    def build(
        self,
        time_from: datetime | str,
        time_to: datetime | str,
        feedback_queue: list[dict[str, Any]] | Any | None,
        tenant_filter: Any = None,
        max_scan_lines: int | None = None,
    ) -> dict[str, Any]:
        """Return a report aggregate for the requested time window."""

        time_from_dt = _parse_iso(time_from)
        time_to_dt = _parse_iso(time_to)
        if time_from_dt is None or time_to_dt is None:
            raise ValueError("invalid time window")

        lookback_seconds = self.default_lookback_seconds
        scan_from = time_from_dt - timedelta(seconds=lookback_seconds)
        cap = int(max_scan_lines if max_scan_lines is not None else self.default_max_scan_lines)
        long_threshold = self.long_task_threshold_seconds

        scan_lines = 0
        records: list[dict[str, Any]] = []

        path = self.contract_log_path
        if path and Path(path).is_file():
            for line in _reverse_line_reader(path):
                if not line.strip():
                    continue
                if scan_lines >= cap:
                    break
                scan_lines += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                occurred_at = _parse_iso(record.get("occurred_at"))
                if occurred_at is None:
                    continue
                if occurred_at < scan_from:
                    break
                if not self._tenant_matches(record, tenant_filter):
                    continue
                scrubbed = scrub_contract_payload(record)
                records.append(scrubbed)

        records.reverse()

        buckets: dict[str, dict[str, Any]] = {}
        for rec in records:
            event = rec.get("event") or {}
            if not isinstance(event, dict):
                continue
            turn_id = event.get("turn_id")
            if not turn_id:
                continue
            event_key = rec.get("event_key")
            if event_key not in ("agent_turn", "execution_trace", "agent_result"):
                continue
            bucket = buckets.setdefault(turn_id, {})
            bucket[event_key] = rec

        sessions: set[str] = set()
        total = 0
        completed = 0
        failed = 0
        long_task_total = 0
        long_task_success = 0

        for turn_id, bucket in buckets.items():
            agent_turn = bucket.get("agent_turn")
            agent_result = bucket.get("agent_result")
            execution_trace = bucket.get("execution_trace")

            if agent_turn is None:
                continue

            turn_time = _parse_iso(agent_turn.get("occurred_at"))
            result_time = _parse_iso(agent_result.get("occurred_at")) if agent_result else None
            in_window = False
            if turn_time is not None and time_from_dt <= turn_time <= time_to_dt:
                in_window = True
            if result_time is not None and time_from_dt <= result_time <= time_to_dt:
                in_window = True
            if not in_window:
                continue

            event = agent_turn.get("event") or {}
            conversation_id = event.get("conversation_id")
            if conversation_id:
                sessions.add(str(conversation_id))

            total += 1

            status: str | None = None
            if agent_result is not None:
                result_event = agent_result.get("event") or {}
                status = str(result_event.get("status", "")).lower() or None
            if status in _COMPLETED_STATUSES:
                completed += 1
            elif status in _FAILED_STATUSES:
                failed += 1

            duration: float | None = None
            if execution_trace is not None:
                trace_event = execution_trace.get("event") or {}
                started = _parse_iso(trace_event.get("started_at"))
                ended = _parse_iso(trace_event.get("ended_at"))
                if started is not None and ended is not None:
                    duration = (ended - started).total_seconds()
            if duration is not None and duration > long_threshold:
                long_task_total += 1
                if status in _COMPLETED_STATUSES:
                    long_task_success += 1

        incomplete = total - completed - failed
        completion_rate = completed / total if total else 0.0
        long_task_success_rate = long_task_success / long_task_total if long_task_total else 0.0

        feedback_counter = Counter({"up": 0, "down": 0, "none": 0})
        queue = feedback_queue or []
        for item in queue:
            if not isinstance(item, dict):
                continue
            created_at = _parse_iso(item.get("created_at"))
            if created_at is None or not (time_from_dt <= created_at <= time_to_dt):
                continue
            action = str(item.get("action", "")).lower() or None
            if action == "up":
                feedback_counter["up"] += 1
            elif action in ("down", "needs_fix", "route_wrong"):
                feedback_counter["down"] += 1
            else:
                feedback_counter["none"] += 1

        feedback_total = feedback_counter["up"] + feedback_counter["down"] + feedback_counter["none"]

        return {
            "sessions": {"count": len(sessions)},
            "tasks": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "incomplete": incomplete,
                "completion_rate": completion_rate,
                "long_task_total": long_task_total,
                "long_task_success": long_task_success,
                "long_task_success_rate": long_task_success_rate,
            },
            "feedback": {
                "up": feedback_counter["up"],
                "down": feedback_counter["down"],
                "none": feedback_counter["none"],
                "total": feedback_total,
            },
            "metadata": {
                "time_from": _format_iso(time_from_dt),
                "time_to": _format_iso(time_to_dt),
                "aggregated_at": _format_iso(datetime.now(timezone.utc)),
                "scan_lines": scan_lines,
                "max_scan_lines": cap,
                "lookback_seconds": lookback_seconds,
                "display_tz": self.display_tz,
            },
        }

    def _tenant_matches(self, record: dict[str, Any], tenant_filter: Any) -> bool:
        """Return True when the record is visible for the active tenant filter."""

        if tenant_filter is None:
            return True
        if not getattr(tenant_filter, "is_active", False):
            return True
        tenant_id = getattr(tenant_filter, "tenant_id", None)
        if tenant_id is None:
            return True
        record_tenant = record.get("tenant_id")
        if record_tenant is None:
            event = record.get("event") or {}
            if isinstance(event, dict):
                record_tenant = event.get("tenant_id")
        return record_tenant == tenant_id


__all__ = ["ReportsAggregator"]
