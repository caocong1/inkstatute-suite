"""Tests for privacy scanning & secrets detection — privacy_scan module.

Tests cover:
- Clean events (legitimate Chinese legal content) produce no findings
- API key / access token / secret assignment detection
- ACP-specific patterns: HERMES_HOME paths, ACP env vars, agent env vars
- Provider leak detection
- ACP debug content detection
- Nested dict scanning with field path tracking
- List value scanning with indexed field paths
- No original secret text in any finding (reference-first audit)
- Batch scanning (scan_events)
- Reference-first compliance: compliant events, violations, exempt types
- assert_all_reference_first with clean and violating event lists
- Audit metadata structure (hash prefix, length, privacy marker)
"""

from __future__ import annotations

import json
import unittest
import uuid

from platform_runtime.protocols import RunEvent

from inkstatute_acp_event_bridge.privacy_scan import (
    EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF,
    ScanResult,
    assert_all_reference_first,
    assert_reference_first,
    scan_event,
    scan_events,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_event(
    event_type: str = "message.delta",
    payload: dict | None = None,
    metadata: dict | None = None,
) -> RunEvent:
    """Create a RunEvent with sensible defaults for testing."""
    return RunEvent(
        event_id=str(uuid.uuid4()),
        run_id="run-test",
        event_type=event_type,
        occurred_at="2026-01-01T00:00:00Z",
        seq=1,
        payload=payload if payload is not None else {},
        metadata=metadata if metadata is not None else {},
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestPrivacyScan(unittest.TestCase):
    """Comprehensive tests for secret detection and reference-first enforcement."""

    # ------------------------------------------------------------------
    # Clean event tests
    # ------------------------------------------------------------------

    def test_clean_event_no_findings(self) -> None:
        """A clean event with legitimate content produces no findings."""
        event = _make_event(
            event_type="message.delta",
            payload={"delta": "合同审查已完成"},
        )
        result = scan_event(event)
        self.assertTrue(result.clean)
        self.assertEqual(result.findings, [])

    def test_legitimate_chinese_content_clean(self) -> None:
        """Chinese legal content must not trigger false positives."""
        event = _make_event(
            payload={"content": "根据《民法典》第一编第一章的规定，民事主体从事民事活动应当遵循自愿原则。"},
        )
        result = scan_event(event)
        self.assertTrue(result.clean)
        self.assertEqual(result.findings, [])

    # ------------------------------------------------------------------
    # Secret pattern detection tests
    # ------------------------------------------------------------------

    def test_api_key_detected(self) -> None:
        """API key patterns are detected."""
        event = _make_event(payload={"content": "api_key=abc123"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        rule_ids = [f["rule_id"] for f in result.findings]
        self.assertTrue(
            "secret_assignment" in rule_ids or "secret_like" in rule_ids,
            f"Expected secret_assignment or secret_like, got {rule_ids}",
        )

    def test_access_token_detected(self) -> None:
        """Access token patterns are detected."""
        event = _make_event(payload={"content": "access_token:Bearer xyz123"})
        result = scan_event(event)
        self.assertFalse(result.clean)

    def test_hermes_home_path_detected(self) -> None:
        """ACP-specific HERMES_HOME path is detected."""
        event = _make_event(payload={"content": "/home/user/.hermes/config.json"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        rule_ids = [f["rule_id"] for f in result.findings]
        self.assertTrue(
            "hermes_home_path" in rule_ids or "hermes_dot_path" in rule_ids,
            f"Expected hermes_home_path or hermes_dot_path, got {rule_ids}",
        )

    def test_acp_env_secret_detected(self) -> None:
        """ACP env var secrets are detected."""
        event = _make_event(payload={"content": "HERMES_HOME=/opt/hermes"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        rule_ids = [f["rule_id"] for f in result.findings]
        self.assertIn("acp_env_secret", rule_ids)

    def test_agent_env_secret_detected(self) -> None:
        """AGENT_ env var secrets are detected."""
        event = _make_event(payload={"content": "AGENT_API_KEY=sk-12345"})
        result = scan_event(event)
        self.assertFalse(result.clean)

    def test_provider_leak_detected(self) -> None:
        """Provider leak patterns are detected."""
        event = _make_event(payload={"content": "model: gpt-4, provider: openai"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        rule_ids = [f["rule_id"] for f in result.findings]
        self.assertIn("provider_leak", rule_ids)

    def test_acp_debug_detected(self) -> None:
        """ACP debug content is detected."""
        event = _make_event(payload={"content": "acp: session/update debug info"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        rule_ids = [f["rule_id"] for f in result.findings]
        self.assertIn("acp_debug", rule_ids)

    # ------------------------------------------------------------------
    # Nested structure scanning
    # ------------------------------------------------------------------

    def test_nested_dict_scanned(self) -> None:
        """Nested dict values are scanned with correct field paths."""
        event = _make_event(
            payload={"metadata": {"inner": {"secret": "api_key=xyz"}}},
        )
        result = scan_event(event)
        self.assertFalse(result.clean)
        field_paths = [f["field_path"] for f in result.findings]
        self.assertTrue(
            any("metadata.inner.secret" in p for p in field_paths),
            f"Expected field_path containing 'metadata.inner.secret', got {field_paths}",
        )

    def test_list_values_scanned(self) -> None:
        """List values are scanned with indexed field paths."""
        event = _make_event(
            payload={"items": ["safe text", "token=abc123"]},
        )
        result = scan_event(event)
        self.assertFalse(result.clean)
        field_paths = [f["field_path"] for f in result.findings]
        self.assertTrue(
            any("items[1]" in p for p in field_paths),
            f"Expected field_path containing 'items[1]', got {field_paths}",
        )

    # ------------------------------------------------------------------
    # No original text in findings
    # ------------------------------------------------------------------

    def test_no_original_text_in_findings(self) -> None:
        """Findings must NOT contain the original secret text."""
        event = _make_event(payload={"content": "api_key=abc123def"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        for finding in result.findings:
            serialized = json.dumps(finding)
            self.assertNotIn(
                "abc123def",
                serialized,
                f"Original text found in finding: {serialized}",
            )
            # Audit should contain hash prefix and length
            audit = finding["audit"]
            self.assertIn("input_hash_prefix", audit)
            self.assertIn("input_length", audit)

    # ------------------------------------------------------------------
    # Batch scanning
    # ------------------------------------------------------------------

    def test_scan_events_batch(self) -> None:
        """scan_events processes a batch of events correctly."""
        events = [
            _make_event(payload={"delta": "合法内容"}),
            _make_event(payload={"content": "api_key=xyz"}),
            _make_event(payload={"delta": "更多合法内容"}),
        ]
        results = scan_events(events)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].clean)
        self.assertFalse(results[1].clean)
        self.assertTrue(results[2].clean)

    # ------------------------------------------------------------------
    # Reference-first enforcement
    # ------------------------------------------------------------------

    def test_reference_first_compliant(self) -> None:
        """A message.completed event with raw_payload_ref is compliant."""
        event = _make_event(
            event_type="message.completed",
            payload={"content": "review done"},
            metadata={"raw_payload_ref": "sha256:abc123:11"},
        )
        self.assertTrue(assert_reference_first(event))

    def test_reference_first_violation(self) -> None:
        """A message.completed event without raw_payload_ref is a violation."""
        event = _make_event(
            event_type="message.completed",
            payload={"content": "review done"},
            metadata={},
        )
        self.assertFalse(assert_reference_first(event))

    def test_reference_first_exempt_type(self) -> None:
        """Delta events are exempt from reference-first requirement."""
        event = _make_event(
            event_type="message.delta",
            payload={"delta": "streaming..."},
            metadata={},
        )
        self.assertTrue(assert_reference_first(event))

    def test_reference_first_elicitation_exempt(self) -> None:
        """Elicitation events are exempt (content needed for user interaction)."""
        event = _make_event(
            event_type="elicitation.requested",
            payload={"intro": "Please answer"},
            metadata={},
        )
        self.assertTrue(assert_reference_first(event))

    def test_assert_all_reference_first_clean(self) -> None:
        """All compliant events return an empty violation list."""
        events = [
            _make_event(
                event_type="message.completed",
                payload={"content": "done"},
                metadata={"raw_payload_ref": "sha256:abc:4"},
            ),
            _make_event(
                event_type="message.delta",
                payload={"delta": "streaming"},
                metadata={},
            ),
        ]
        violations = assert_all_reference_first(events)
        self.assertEqual(violations, [])

    def test_assert_all_reference_first_with_violation(self) -> None:
        """Non-compliant events are listed in violations."""
        compliant = _make_event(
            event_type="message.completed",
            payload={"content": "done"},
            metadata={"raw_payload_ref": "sha256:abc:4"},
        )
        violating = _make_event(
            event_type="message.completed",
            payload={"content": "not done"},
            metadata={},
        )
        violations = assert_all_reference_first([compliant, violating])
        self.assertEqual(len(violations), 1)
        self.assertIn(violating.event_id, violations)

    # ------------------------------------------------------------------
    # Audit metadata structure
    # ------------------------------------------------------------------

    def test_finding_audit_metadata_structure(self) -> None:
        """Audit metadata has correct reference-first structure."""
        event = _make_event(payload={"content": "api_key=secret123"})
        result = scan_event(event)
        self.assertFalse(result.clean)
        for finding in result.findings:
            audit = finding["audit"]
            # input_hash_prefix should be 16-char hex
            self.assertIn("input_hash_prefix", audit)
            self.assertEqual(len(audit["input_hash_prefix"]), 16)
            # input_length should be a positive int
            self.assertIn("input_length", audit)
            self.assertIsInstance(audit["input_length"], int)
            self.assertGreater(audit["input_length"], 0)
            # privacy marker
            self.assertEqual(audit["privacy"], "no_original_text_stored")
            # rule_id present
            self.assertIn("rule_id", audit)


if __name__ == "__main__":
    unittest.main()
