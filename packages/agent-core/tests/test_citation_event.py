"""Tests for citation.recorded event emission via EventEmitter.

Tests that ``emit_citation_recorded()`` produces a ``RunEvent`` with
``event_type="citation.recorded"`` and a ``CitationRecordedPayload``,
and that it uses the side-channel buffer (same pattern as
``emit_artifact_created``).
"""

from __future__ import annotations

import unittest

from platform_contract.enums import RunEventType

from inkstatute_agent_core.citations import CitationAuditItem, CitationKind
from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter


def _make_audit_item(
    kind: CitationKind = CitationKind.LAW,
    source: str = "民法典",
    reference: str = "第五百八十五条",
    status: str = "verified",
) -> CitationAuditItem:
    """Build a CitationAuditItem for testing."""
    return CitationAuditItem(
        kind=kind,
        source=source,
        reference=reference,
        status=status,
    )


class TestEmitCitationRecorded(unittest.TestCase):
    """Tests for emit_citation_recorded()."""

    def test_produces_run_event_with_correct_event_type(self) -> None:
        """emit_citation_recorded() produces RunEvent with event_type='citation.recorded'."""
        emitter = EventEmitter("run-1")
        items = [_make_audit_item(status="verified")]
        event = emitter.emit_citation_recorded(items)
        self.assertEqual(event.event_type, RunEventType.CITATION_RECORDED.value)
        self.assertEqual(event.run_id, "run-1")

    def test_payload_contains_citation_records(self) -> None:
        """Payload contains CitationRecord objects with source and status."""
        emitter = EventEmitter("run-1")
        items = [
            _make_audit_item(source="民法典", reference="第五百八十五条", status="verified"),
            _make_audit_item(source="", reference="（2024）渝01民初1234号", status="retrieved"),
        ]
        event = emitter.emit_citation_recorded(items)
        payload = event.payload
        citations = payload.get("citations", [])
        self.assertEqual(len(citations), 2)
        # First citation: source from source field
        self.assertEqual(citations[0]["source"], "民法典")
        self.assertEqual(citations[0]["status"], "verified")
        # Second citation: source empty → uses reference as source
        self.assertEqual(citations[1]["source"], "（2024）渝01民初1234号")
        self.assertEqual(citations[1]["status"], "retrieved")

    def test_uses_side_channel_buffer(self) -> None:
        """emit_citation_recorded() appends to side-channel buffer."""
        emitter = EventEmitter("run-1")
        items = [_make_audit_item()]
        event = emitter.emit_citation_recorded(items)
        drained = emitter.drain_side_channel_events()
        self.assertEqual(len(drained), 1)
        self.assertIs(drained[0], event)

    def test_side_channel_buffer_cleared_after_drain(self) -> None:
        """Side-channel buffer is cleared after draining."""
        emitter = EventEmitter("run-1")
        emitter.emit_citation_recorded([_make_audit_item()])
        emitter.drain_side_channel_events()
        self.assertEqual(emitter.drain_side_channel_events(), [])

    def test_empty_citations_list(self) -> None:
        """Empty citations list → event with empty citations payload."""
        emitter = EventEmitter("run-1")
        event = emitter.emit_citation_recorded([])
        payload = event.payload
        self.assertEqual(payload.get("citations", []), [])

    def test_seq_increments(self) -> None:
        """emit_citation_recorded() increments seq like other emit methods."""
        emitter = EventEmitter("run-1")
        event1 = emitter.emit_thought_delta("thinking")
        event2 = emitter.emit_citation_recorded([_make_audit_item()])
        self.assertEqual(event1.seq, 0)
        self.assertEqual(event2.seq, 1)

    def test_metadata_preserved(self) -> None:
        """Metadata is preserved in the emitted event."""
        emitter = EventEmitter("run-1")
        metadata = {"audit_total": 3, "phase": "post-response"}
        event = emitter.emit_citation_recorded([_make_audit_item()], metadata=metadata)
        self.assertEqual(event.metadata["audit_total"], 3)
        self.assertEqual(event.metadata["phase"], "post-response")

    def test_all_three_statuses(self) -> None:
        """All three verification statuses appear in citation records."""
        emitter = EventEmitter("run-1")
        items = [
            _make_audit_item(source="民法典", status="verified"),
            _make_audit_item(source="刑法", status="retrieved"),
            _make_audit_item(source="行政法", status="unverified"),
        ]
        event = emitter.emit_citation_recorded(items)
        citations = event.payload.get("citations", [])
        statuses = [c["status"] for c in citations]
        self.assertEqual(statuses, ["verified", "retrieved", "unverified"])


if __name__ == "__main__":
    unittest.main()
