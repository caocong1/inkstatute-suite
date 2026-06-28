from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from platform_contract import AsyncTaskState
from wecom_service.task_flow import (
    TASK_STAGE_TO_ASYNC_STATE,
    TaskFlowConfig,
    WeComTaskStage,
    create_task_flow,
    deadline_exceeded,
    progress_notice_due,
    record_stage,
    summarize_task_input,
)


class TaskFlowTests(unittest.TestCase):
    def test_initial_task_creation_records_minimized_turn_ready_event(self) -> None:
        task = create_task_flow(
            conversation_id="conv-1",
            user_id="lawyer-1",
            message_id="msg-1",
            text="审查这份合同。",
            media_types=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            raw_payload_ref="runtime://wecom-live/msg-1",
            now="2026-06-28T10:00:00+00:00",
            config=TaskFlowConfig(progress_interval_seconds=180, timeout_seconds=7200),
        )

        self.assertEqual(task.current_stage, WeComTaskStage.TURN_READY)
        event = task.stage_records[0].as_event()
        self.assertEqual(event["stage"], "turn_ready")
        self.assertEqual(event["metadata"]["file_text_aggregation"], "adjacent_wecom_events_become_one_task")
        self.assertEqual(event["metadata"]["active_task_followup_route"], "fast_control_plane")
        self.assertNotIn("审查", json.dumps(event, ensure_ascii=False))
        self.assertEqual(task.input_summary.media_count, 1)

    def test_stage_transition_order_and_async_state_mapping(self) -> None:
        task = self.task()
        queued = record_stage(task, WeComTaskStage.QUEUED, now="2026-06-28T10:00:01+00:00")
        running = record_stage(task, WeComTaskStage.RUNNING, now="2026-06-28T10:00:02+00:00")
        completed = record_stage(task, WeComTaskStage.COMPLETED, now="2026-06-28T10:00:03+00:00")

        self.assertEqual([record.seq for record in task.stage_records], [1, 2, 3, 4])
        self.assertEqual(queued.async_task_state, AsyncTaskState.QUEUED.value)
        self.assertEqual(running.async_task_state, AsyncTaskState.RUNNING.value)
        self.assertEqual(completed.async_task_state, AsyncTaskState.SUCCEEDED.value)
        self.assertFalse(task.active)
        self.assertIsNone(TASK_STAGE_TO_ASYNC_STATE[WeComTaskStage.TURN_READY])

    def test_recurring_progress_due_calculation(self) -> None:
        task = self.task(progress_interval_seconds=60)
        record_stage(task, WeComTaskStage.RUNNING, now="2026-06-28T10:00:00+00:00")

        self.assertFalse(progress_notice_due(task, now="2026-06-28T10:00:59+00:00"))
        self.assertTrue(progress_notice_due(task, now="2026-06-28T10:01:00+00:00"))

        notice = record_stage(task, WeComTaskStage.PROGRESS_NOTICE_DUE, now="2026-06-28T10:01:00+00:00")
        self.assertEqual(notice.async_task_state, AsyncTaskState.RUNNING.value)
        record_stage(task, WeComTaskStage.RUNNING, now="2026-06-28T10:01:01+00:00")
        self.assertFalse(progress_notice_due(task, now="2026-06-28T10:01:59+00:00"))
        self.assertTrue(progress_notice_due(task, now="2026-06-28T10:02:00+00:00"))

    def test_timeout_classification_maps_to_failed_async_state(self) -> None:
        task = self.task(timeout_seconds=30)
        record_stage(task, WeComTaskStage.RUNNING, now="2026-06-28T10:00:01+00:00")

        self.assertFalse(deadline_exceeded(task, now="2026-06-28T10:00:29+00:00"))
        self.assertTrue(deadline_exceeded(task, now="2026-06-28T10:00:30+00:00"))

        timeout = record_stage(task, WeComTaskStage.TIMEOUT, now="2026-06-28T10:00:30+00:00")
        self.assertEqual(timeout.async_task_state, AsyncTaskState.FAILED.value)
        self.assertFalse(task.active)

    def test_stage_idempotency_key_is_stable_for_same_stage_occurrence(self) -> None:
        task = self.task()
        first = record_stage(task, WeComTaskStage.QUEUED, now="2026-06-28T10:00:01+00:00")
        second = record_stage(task, WeComTaskStage.RUNNING, now="2026-06-28T10:00:02+00:00")

        self.assertEqual(first.idempotency_key, f"wecom-task:{task.task_id}:queued:2")
        self.assertEqual(second.idempotency_key, f"wecom-task:{task.task_id}:running:3")

    def test_summarized_records_never_include_raw_payload_text(self) -> None:
        summary = summarize_task_input(
            text="包含敏感事实的长合同内容",
            media_types=["application/pdf"],
            raw_payload_ref="runtime://private/payload",
        )

        serialized = json.dumps(summary.as_event_metadata(), ensure_ascii=False)
        self.assertIn("text_sha256_16", serialized)
        self.assertIn("text_length", serialized)
        self.assertNotIn("敏感事实", serialized)
        self.assertNotIn("长合同内容", serialized)

    def task(self, *, progress_interval_seconds: float = 180, timeout_seconds: float = 7200):
        return create_task_flow(
            conversation_id="conv-1",
            user_id="lawyer-1",
            message_id="msg-1",
            text="审查这份合同。",
            media_types=["application/pdf"],
            raw_payload_ref="runtime://wecom-live/msg-1",
            now=datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc),
            config=TaskFlowConfig(
                progress_interval_seconds=progress_interval_seconds,
                timeout_seconds=timeout_seconds,
            ),
        )


if __name__ == "__main__":
    unittest.main()
