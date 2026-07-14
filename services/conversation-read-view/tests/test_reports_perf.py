"""Performance tests for ReportsAggregator bounded scanning."""

from __future__ import annotations

import json
import tempfile
import time
import tracemalloc
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conversation_read_view.reports_aggregator import ReportsAggregator


class ReportsAggregatorPerfTests(unittest.TestCase):
    def _generate_fixture(self, line_count: int) -> str:
        """Generate a JSONL file with ``line_count`` events spread over 14 days."""

        now = datetime.now(timezone.utc)
        lines: list[str] = []
        for i in range(line_count):
            offset = timedelta(seconds=(line_count - i) * 60)  # newer events last
            occurred = now - offset
            iso = occurred.isoformat().replace("+00:00", "Z")
            turn_id = f"turn-{i:08d}"
            record = {
                "event_key": "agent_turn",
                "occurred_at": iso,
                "ingested_at": iso,
                "seq": i,
                "event": {
                    "turn_id": turn_id,
                    "conversation_id": f"conv-{i % 1000:04d}",
                    "channel": "wecom",
                    "user_id": "user-1",
                    "message_type": "text",
                    "received_at": iso,
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        return str(path)

    def test_50k_events_bounded(self) -> None:
        fixture_path = self._generate_fixture(50000)
        agg = ReportsAggregator(fixture_path, default_max_scan_lines=10000)
        now = datetime.now(timezone.utc)
        time_from = now - timedelta(days=7)
        time_to = now

        tracemalloc.start()
        tracemalloc.reset_peak()
        start = time.perf_counter()
        result = agg.build(time_from, time_to, feedback_queue=[], max_scan_lines=10000)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertLess(elapsed, 1.0, f"build() took {elapsed:.3f}s")
        max_allowed = min(25 * 1024 * 1024, 10000 * 4 * 1024)
        self.assertLess(peak, max_allowed, f"peak memory {peak} bytes exceeds {max_allowed} bytes")
        self.assertLessEqual(result["metadata"]["scan_lines"], 10000)
        self.assertGreaterEqual(result["metadata"]["scan_lines"], 0)


if __name__ == "__main__":
    unittest.main()
