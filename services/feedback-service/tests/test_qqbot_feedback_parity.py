"""Wave 0 / Plan 01→02: FEEDBACK-01 QQ contract_feedback_events parity.

Proves QQ-shaped FeedbackEvent dicts dedupe/classify/queue through
feedback-service without wecom_normalizer / wecom_service imports.
"""

from __future__ import annotations

import copy
import inspect
import unittest
from typing import Any

from feedback_service import queue as feedback_queue
from feedback_service.classification import classify_feedback_event
from feedback_service.queue import (
    build_pending_feedback_queue,
    normalize_feedback_inputs,
)


def _qq_feedback_event(
    feedback_id: str,
    *,
    action: str = "up",
    message_id: str = "FIXTURE_CARD_MSG_ID_001",
    button_id: str = "21",
) -> dict[str, Any]:
    event_type = "rating" if action == "up" else "correction"
    if action == "route_wrong":
        event_type = "route_mismatch"
    event: dict[str, Any] = {
        "feedback_id": feedback_id,
        "turn_id": f"turn-{feedback_id}",
        "conversation_id": "qqbot:c2c:FIXTURE_USER:FIXTURE_USER",
        "user_id": "FIXTURE_USER",
        "source": "card_button",
        "event_type": event_type,
        "status": "pending",
        "created_at": "2026-07-09T00:00:00Z",
        "feedback_target": message_id,
        "action": action,
        "raw_payload_ref": f"fixture://qqbot/interaction/{feedback_id}",
        "metadata": {
            "idempotency_key": f"{message_id}:{button_id}",
            "dedupe_strategy": "msg_id + button_identity",
            "msg_id": message_id,
            "source_event": "INTERACTION_CREATE",
            "source_status": "sanitized_callback",
            "no_auto_modify": action == "route_wrong",
            "button_id": button_id,
            "button_data": action,
        },
    }
    if action == "up":
        event["rating"] = 1.0
    if action == "route_wrong":
        event["route_mismatch"] = True
        event["skill_candidate"] = {
            "detected": True,
            "source": "route_mismatch",
            "requires_human_review": True,
            "evidence": [f"fixture://qqbot/interaction/{feedback_id}"],
            "metadata": {"no_auto_modify": True},
        }
    return event


def _assert_no_privacy_leak(self: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        self.assertNotIn("raw_payload", value)
        self.assertNotIn("Authorization", value)
        for key, child in value.items():
            key_l = str(key).lower()
            self.assertNotIn("token", key_l)
            self.assertNotIn("authorization", key_l)
            _assert_no_privacy_leak(self, child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_privacy_leak(self, child)


class TestQqbotFeedbackParity(unittest.TestCase):
    """FEEDBACK-01: QQ dicts through contract_feedback_events without wecom."""

    def test_feedback01_no_wecom_service_import(self) -> None:
        """QQ parity path must not import the WeCom service package."""
        import ast
        from pathlib import Path

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertTrue(
            all(not name.startswith("wecom_service") for name in imported),
            msg=f"unexpected WeCom service imports: {imported}",
        )
        queue_source = inspect.getsource(feedback_queue)
        self.assertNotIn("wecom_service", queue_source)
        # Exercise QQ path only — no wecom_callback_events / compatibility records
        event = _qq_feedback_event("qq-no-wecom-path")
        events = normalize_feedback_inputs(contract_feedback_events=[event])
        self.assertEqual(len(events), 1)

    def test_feedback01_qq_contract_events_dedupe_on_idempotency_key(self) -> None:
        event = _qq_feedback_event("qq-parity-1")
        events = normalize_feedback_inputs(
            contract_feedback_events=[event, copy.deepcopy(event)]
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["metadata"]["idempotency_key"], "FIXTURE_CARD_MSG_ID_001:21"
        )
        self.assertEqual(events[0]["metadata"]["duplicate_count"], 2)
        _assert_no_privacy_leak(self, events[0])

    def test_feedback01_qq_events_classify_and_pending_queue(self) -> None:
        up = _qq_feedback_event("qq-parity-up", action="up")
        route = _qq_feedback_event(
            "qq-parity-route",
            action="route_wrong",
            message_id="FIXTURE_CARD_MSG_ROUTE",
            button_id="24",
        )

        events = normalize_feedback_inputs(contract_feedback_events=[up, route])
        self.assertEqual(len(events), 2)

        up_event = next(e for e in events if e["action"] == "up")
        route_event = next(e for e in events if e["action"] == "route_wrong")
        up_class = classify_feedback_event(up_event)
        route_class = classify_feedback_event(route_event)
        self.assertEqual(up_class.category, "rating")
        self.assertEqual(route_class.category, "route_mismatch")
        self.assertTrue(route_class.requires_human_review)
        self.assertTrue(route_class.no_auto_modify)

        queue = build_pending_feedback_queue(events)
        self.assertEqual(len(queue), 2)
        route_item = next(item for item in queue if item["action"] == "route_wrong")
        self.assertTrue(route_item["no_auto_modify"])
        self.assertTrue(route_item["requires_human_review"])
        _assert_no_privacy_leak(self, queue)

    def test_feedback03_distinct_buttons_do_not_collapse(self) -> None:
        up = _qq_feedback_event("qq-btn-up", action="up", button_id="21")
        down = _qq_feedback_event(
            "qq-btn-down",
            action="down",
            button_id="22",
        )
        # Same card message_id, different button identity → two canonical events
        down["metadata"]["idempotency_key"] = "FIXTURE_CARD_MSG_ID_001:22"
        down["metadata"]["button_id"] = "22"
        down["metadata"]["button_data"] = "down"

        events = normalize_feedback_inputs(contract_feedback_events=[up, down])
        self.assertEqual(len(events), 2)

    def test_feedback01_privacy_raw_payload_rejected(self) -> None:
        event = _qq_feedback_event("qq-raw-payload")
        event["raw_payload"] = {"secret": True}
        with self.assertRaises(ValueError) as ctx:
            normalize_feedback_inputs(contract_feedback_events=[event])
        self.assertIn("raw_payload", str(ctx.exception))

    def test_feedback01_packages_keep_empty_dependencies(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        qqbot = (root / "packages" / "channels" / "qqbot" / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        feedback = (root / "services" / "feedback-service" / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("dependencies = []", qqbot)
        self.assertIn("dependencies = []", feedback)

    def test_feedback01_parity_module_does_not_import_wecom_normalizer(self) -> None:
        import ast
        from pathlib import Path

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertTrue(
            all("wecom_normalizer" not in name for name in imported),
            msg=f"unexpected wecom_normalizer imports: {imported}",
        )


if __name__ == "__main__":
    unittest.main()
