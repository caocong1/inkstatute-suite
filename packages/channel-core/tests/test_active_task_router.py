from __future__ import annotations

import json
import unittest

from channel_core.active_task_router import (
    ActiveTaskRoute,
    ActiveTaskRoutingDecision,
    AdapterTaskCapabilities,
    route_active_task_turn,
)


class ActiveTaskRouterTests(unittest.TestCase):
    def test_status_request_while_running_uses_fast_control_plane(self) -> None:
        decision = route_active_task_turn(
            text="现在进度怎么样了？",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(),
            raw_payload_ref="runtime://followup/msg-2",
        )

        self.assertEqual(decision.route, ActiveTaskRoute.STATUS_REQUEST)
        self.assertTrue(decision.accepted_by_backend)
        self.assertEqual(decision.notice_kind, "status_running")
        self.assertEqual(decision.reason, "status_query_answered_by_fast_control_plane")

    def test_cancel_request_while_running_reflects_capability(self) -> None:
        unsupported = route_active_task_turn(
            text="取消这个任务",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_cancel=False),
        )
        supported = route_active_task_turn(
            text="取消这个任务",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_cancel=True),
        )

        self.assertEqual(unsupported.route, ActiveTaskRoute.CANCEL_REQUEST)
        self.assertFalse(unsupported.accepted_by_backend)
        self.assertEqual(unsupported.notice_kind, "cancel_unsupported")
        self.assertEqual(supported.route, ActiveTaskRoute.CANCEL_REQUEST)
        self.assertTrue(supported.accepted_by_backend)
        self.assertEqual(supported.notice_kind, "cancel_accepted")

    def test_live_update_is_accepted_only_when_adapter_supports_it(self) -> None:
        unsupported = route_active_task_turn(
            text="补充一点：重点看违约责任。",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_live_task_update=False),
        )
        supported = route_active_task_turn(
            text="补充一点：重点看违约责任。",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_live_task_update=True),
        )

        self.assertEqual(unsupported.route, ActiveTaskRoute.UNSUPPORTED_UPDATE_ACK)
        self.assertFalse(unsupported.accepted_by_backend)
        self.assertEqual(unsupported.notice_kind, "update_received_not_applied")
        self.assertEqual(supported.route, ActiveTaskRoute.TASK_UPDATE)
        self.assertTrue(supported.accepted_by_backend)
        self.assertEqual(supported.notice_kind, "update_accepted")

    def test_parallel_new_task_routing_when_supported(self) -> None:
        decision = route_active_task_turn(
            text="另外再帮我检索一下合同解除规则",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_parallel_tasks=True),
        )

        self.assertEqual(decision.route, ActiveTaskRoute.NEW_PARALLEL_TASK)
        self.assertTrue(decision.accepted_by_backend)
        self.assertEqual(decision.notice_kind, "parallel_task_accepted")

    def test_parallel_new_task_is_explicitly_rejected_when_unsupported(self) -> None:
        decision = route_active_task_turn(
            text="另外再帮我检索一下合同解除规则",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(supports_parallel_tasks=False),
        )

        self.assertEqual(decision.route, ActiveTaskRoute.UNSUPPORTED_UPDATE_ACK)
        self.assertFalse(decision.accepted_by_backend)
        self.assertEqual(decision.intent_class, "new_parallel_task")
        self.assertEqual(decision.notice_kind, "parallel_task_unsupported")

    def test_as_event_default_channel_name(self) -> None:
        decision = route_active_task_turn(
            text="进度怎么样了？",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(),
        )
        event = decision.as_event()
        self.assertEqual(event["event"], "channel_active_task_route")

    def test_as_event_custom_wecom_name(self) -> None:
        decision = route_active_task_turn(
            text="进度怎么样了？",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(),
            event_name="wecom_active_task_route",
        )
        event = decision.as_event()
        self.assertEqual(event["event"], "wecom_active_task_route")

    def test_serialized_decision_does_not_store_raw_followup_text(self) -> None:
        decision = route_active_task_turn(
            text="补充一点：客户身份证号是敏感内容",
            active_task=self.active_task,
            capabilities=AdapterTaskCapabilities(),
            raw_payload_ref="runtime://followup/private",
        )

        event = decision.as_event()
        serialized = json.dumps(event, ensure_ascii=False)
        self.assertIn("text_sha256_16", event)
        self.assertIn("text_length", event)
        self.assertNotIn("身份证号", serialized)
        self.assertNotIn("敏感内容", serialized)
        self.assertEqual(event["raw_payload_ref"], "runtime://followup/private")

    @property
    def active_task(self) -> dict[str, str]:
        return {
            "task_id": "task-1",
            "trace_id": "trace-1",
            "stage": "running",
            "async_task_state": "running",
        }


if __name__ == "__main__":
    unittest.main()
