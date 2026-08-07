"""Tests for ACP output boundary enforcement — ACPOutputFilter.

Tests cover:
- All 8 blocked content categories (meta, gateway, system, update,
  command, help, available_commands_update, terminal)
- Legitimate Chinese legal content passes through
- Default-deny for unknown event types
- All allowed event types pass with legitimate content
- None/empty content allowed
- Rewrite for backend lifecycle notices
- Reference-first audit metadata (no original text stored)
- Elicitation and permission notifications always pass through
- Integration with existing DefaultAssistantOutputBoundary (double enforcement)
- ACP pre-filter short-circuits before existing boundary
- No original text in any decision's audit metadata
"""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import asdict

from inkstatute_acp_event_bridge.output_filter import (
    ACP_ALLOWED_EVENT_TYPES,
    ACP_BLOCKED_CONTENT_CATEGORIES,
    ACPOutputFilter,
    FilterDecision,
)
from platform_runtime.output_boundary import DefaultAssistantOutputBoundary


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "backend_noise.json",
)


def _load_fixture() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestACPOutputFilter(unittest.TestCase):
    """Comprehensive tests for ACP output boundary enforcement."""

    def setUp(self) -> None:
        self.fixture = _load_fixture()
        self.filter = ACPOutputFilter()

    # ------------------------------------------------------------------
    # 1. All blocked categories blocked
    # ------------------------------------------------------------------

    def test_all_blocked_categories_blocked(self) -> None:
        """Every sample in every blocked category returns BLOCK."""
        blocked_categories = [
            "meta",
            "gateway",
            "system",
            "update",
            "command",
            "help",
            "available_commands_update",
            "terminal",
        ]
        for category in blocked_categories:
            samples = self.fixture[category]
            for sample in samples:
                with self.subTest(category=category, sample=sample):
                    decision = self.filter.filter_event("message.delta", sample)
                    self.assertEqual(
                        decision.action,
                        "block",
                        f"Category '{category}' sample '{sample}' should be BLOCKED, "
                        f"got {decision.action} (reason={decision.reason})",
                    )

    # ------------------------------------------------------------------
    # 2. Legitimate content allowed
    # ------------------------------------------------------------------

    def test_legitimate_content_allowed(self) -> None:
        """All Chinese legal content returns ALLOW with original text."""
        for content in self.fixture["legitimate_content"]:
            with self.subTest(content=content):
                decision = self.filter.filter_event("message.delta", content)
                self.assertEqual(
                    decision.action,
                    "allow",
                    f"Legitimate content '{content}' should be ALLOWED, "
                    f"got {decision.action}",
                )
                self.assertEqual(decision.visible_content, content)

    # ------------------------------------------------------------------
    # 3. Unknown event type blocked (default-deny)
    # ------------------------------------------------------------------

    def test_unknown_event_type_blocked(self) -> None:
        """Unknown event type is blocked by default-deny policy."""
        decision = self.filter.filter_event("unknown.type", "hello")
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.reason, "event_type_not_allowed")

    # ------------------------------------------------------------------
    # 4. All allowed event types pass
    # ------------------------------------------------------------------

    def test_all_allowed_event_types_pass(self) -> None:
        """All explicitly allowed event types pass with legitimate content."""
        legitimate = "合法内容"
        for event_type in ACP_ALLOWED_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                decision = self.filter.filter_event(event_type, legitimate)
                self.assertEqual(
                    decision.action,
                    "allow",
                    f"Allowed event type '{event_type}' should pass, "
                    f"got {decision.action}",
                )

    # ------------------------------------------------------------------
    # 5. None content allowed
    # ------------------------------------------------------------------

    def test_none_content_allowed(self) -> None:
        """None content returns ALLOW."""
        decision = self.filter.filter_event("message.delta", None)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 6. Empty content allowed
    # ------------------------------------------------------------------

    def test_empty_content_allowed(self) -> None:
        """Empty string content returns ALLOW."""
        decision = self.filter.filter_event("message.delta", "")
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 7. Rewrite for backend lifecycle
    # ------------------------------------------------------------------

    def test_rewrite_for_backend_lifecycle(self) -> None:
        """Backend lifecycle notice is rewritten to business text."""
        decision = self.filter.filter_event(
            "message.delta", "reconnecting to backend, please wait"
        )
        self.assertEqual(decision.action, "rewrite")
        self.assertIn("InkStatute", decision.visible_content)

    # ------------------------------------------------------------------
    # 8. Rewrite for restart
    # ------------------------------------------------------------------

    def test_rewrite_for_restart(self) -> None:
        """Service restart notice is rewritten."""
        decision = self.filter.filter_event(
            "message.delta", "service restarted successfully"
        )
        self.assertEqual(decision.action, "rewrite")

    # ------------------------------------------------------------------
    # 9. Audit metadata reference-first
    # ------------------------------------------------------------------

    def test_audit_metadata_reference_first(self) -> None:
        """Audit metadata contains hash prefix, length, privacy — no original text."""
        test_input = "meta: some backend noise content"
        decision = self.filter.filter_event("message.delta", test_input)

        self.assertIn("input_hash_prefix", decision.audit_metadata)
        self.assertIn("input_length", decision.audit_metadata)
        self.assertIn("privacy", decision.audit_metadata)
        self.assertEqual(
            decision.audit_metadata["privacy"], "no_original_text_stored"
        )

        # Hash prefix should be 16 hex chars
        hash_prefix = decision.audit_metadata["input_hash_prefix"]
        self.assertEqual(len(hash_prefix), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in hash_prefix))

        # Input length should match
        self.assertEqual(decision.audit_metadata["input_length"], len(test_input))

        # Original text must NOT appear in audit metadata
        audit_json = json.dumps(decision.audit_metadata)
        self.assertNotIn(test_input, audit_json)

    # ------------------------------------------------------------------
    # 10. Elicitation notification always allowed
    # ------------------------------------------------------------------

    def test_elicitation_notification_always_allowed(self) -> None:
        """Elicitation/create notification always passes through to user."""
        notification = {
            "method": "elicitation/create",
            "id": "e1",
            "params": {"id": "e1", "intro": "Please answer"},
        }
        decision = self.filter.filter_notification(notification)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 11. Permission notification always allowed
    # ------------------------------------------------------------------

    def test_permission_notification_always_allowed(self) -> None:
        """session/request_permission notification always passes to user."""
        notification = {
            "method": "session/request_permission",
            "id": "p1",
            "params": {"id": "p1", "kind": "terminal"},
        }
        decision = self.filter.filter_notification(notification)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 12. Integration with existing boundary — blocks secrets
    # ------------------------------------------------------------------

    def test_integration_with_existing_boundary_blocks_secrets(self) -> None:
        """ACP filter allows, existing boundary blocks secret pattern."""
        boundary = DefaultAssistantOutputBoundary()
        decision = self.filter.apply_with_existing_boundary(
            "message.delta", "api_key=abc123", boundary
        )
        self.assertEqual(decision.action, "block")

    # ------------------------------------------------------------------
    # 13. Integration with existing boundary — allows legitimate
    # ------------------------------------------------------------------

    def test_integration_with_existing_boundary_allows_legitimate(self) -> None:
        """Both layers allow legitimate Chinese legal content."""
        boundary = DefaultAssistantOutputBoundary()
        decision = self.filter.apply_with_existing_boundary(
            "message.delta", "合同审查已完成", boundary
        )
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 14. ACP filter short-circuits before existing boundary
    # ------------------------------------------------------------------

    def test_integration_acp_filter_short_circuits(self) -> None:
        """ACP pre-filter blocks backend noise before existing boundary is called."""
        boundary = DefaultAssistantOutputBoundary()
        decision = self.filter.apply_with_existing_boundary(
            "message.delta", "meta: backend info", boundary
        )
        self.assertEqual(decision.action, "block")
        # The reason should be from the ACP filter (meta_notice), not
        # from the existing boundary
        self.assertEqual(decision.reason, "meta_notice")

    # ------------------------------------------------------------------
    # 15. No original text in any decision
    # ------------------------------------------------------------------

    def test_no_original_text_in_any_decision(self) -> None:
        """Original input text does not appear in audit metadata for any decision."""
        test_cases = [
            ("message.delta", "meta: blocked backend noise"),       # blocked
            ("message.delta", "reconnecting to backend"),           # rewritten
            ("message.delta", "合法法律内容"),                       # allowed
        ]

        for event_type, content in test_cases:
            with self.subTest(content=content):
                decision = self.filter.filter_event(event_type, content)
                audit_json = json.dumps(decision.audit_metadata)

                # For ALLOW decisions, the original text appears in
                # visible_content (that's legitimate output), but must
                # NOT appear in audit_metadata
                self.assertNotIn(
                    content,
                    audit_json,
                    f"Original text leaked into audit metadata for "
                    f"action={decision.action}",
                )

    # ------------------------------------------------------------------
    # 16. Blocked categories count
    # ------------------------------------------------------------------

    def test_blocked_categories_count(self) -> None:
        """ACP_BLOCKED_CONTENT_CATEGORIES contains exactly 8 categories."""
        self.assertEqual(len(ACP_BLOCKED_CONTENT_CATEGORIES), 8)

    # ------------------------------------------------------------------
    # 17. Allowed event types count
    # ------------------------------------------------------------------

    def test_allowed_event_types_count(self) -> None:
        """ACP_ALLOWED_EVENT_TYPES contains at least 15 event types."""
        self.assertGreaterEqual(len(ACP_ALLOWED_EVENT_TYPES), 15)


if __name__ == "__main__":
    unittest.main()
