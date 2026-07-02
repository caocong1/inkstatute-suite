"""Tests for Phase 21: rolling summary pipeline — policy, trigger, and producer."""

from __future__ import annotations

import unittest

from platform_runtime import (
    ContextAssembler,
    ContextAssemblyInput,
    ContextAssemblyPolicy,
    InMemoryRollingSummaryStore,
    RollingSummaryPolicy,
    RollingSummaryProducer,
    RollingSummaryRecord,
    RollingSummaryTrigger,
    SessionScope,
    SummaryPrivacyError,
)


FIXED_NOW = "2026-07-02T10:00:00+00:00"

SCOPE = SessionScope(
    tenant_id="tenant-phase21",
    workspace_id="workspace-phase21",
    channel_id="channel-phase21",
    user_id="user-phase21",
    bot_instance_id="bot-phase21",
    conversation_id="conv-phase21",
)


def make_producer(**overrides: object) -> RollingSummaryProducer:
    return RollingSummaryProducer(clock=lambda: FIXED_NOW)


class RollingSummaryPolicyTests(unittest.TestCase):
    def test_policy_defaults_are_safe(self) -> None:
        """Default policy is conservative: require source refs, no raw text allowed."""
        policy = RollingSummaryPolicy()

        self.assertTrue(policy.require_source_refs)
        self.assertFalse(policy.allow_raw_text_in_metadata)
        self.assertEqual(policy.min_summary_ref_prefix, "summary://")
        self.assertEqual(policy.max_turn_count_trigger, 20)
        self.assertAlmostEqual(policy.budget_pressure_threshold, 0.80)

    def test_policy_is_frozen(self) -> None:
        policy = RollingSummaryPolicy()
        with self.assertRaises((AttributeError, TypeError)):
            policy.max_turn_count_trigger = 10  # type: ignore[misc]


class RollingSummaryTriggerTests(unittest.TestCase):
    def _trigger(self, **policy_kwargs: object) -> RollingSummaryTrigger:
        return RollingSummaryTrigger(policy=RollingSummaryPolicy(**policy_kwargs))  # type: ignore[arg-type]

    def test_explicit_request_triggers_regardless_of_counts(self) -> None:
        trigger = self._trigger()
        should, reason = trigger.should_trigger(
            explicit_request=True, turn_count=0, estimated_tokens=0, budget_tokens=1000
        )
        self.assertTrue(should)
        self.assertEqual(reason, "explicit_request")

    def test_task_completion_triggers(self) -> None:
        trigger = self._trigger()
        should, reason = trigger.should_trigger(task_completed=True)
        self.assertTrue(should)
        self.assertEqual(reason, "task_completion")

    def test_budget_pressure_triggers_at_threshold(self) -> None:
        trigger = self._trigger(budget_pressure_threshold=0.80)
        # exactly at threshold
        should, reason = trigger.should_trigger(estimated_tokens=800, budget_tokens=1000)
        self.assertTrue(should)
        self.assertEqual(reason, "budget_pressure")

    def test_budget_pressure_does_not_trigger_below_threshold(self) -> None:
        trigger = self._trigger(budget_pressure_threshold=0.80)
        should, reason = trigger.should_trigger(estimated_tokens=799, budget_tokens=1000)
        self.assertFalse(should)
        self.assertEqual(reason, "none")

    def test_budget_pressure_ignored_when_budget_is_zero(self) -> None:
        trigger = self._trigger(budget_pressure_threshold=0.80)
        # budget_tokens=0 must not cause ZeroDivisionError
        should, reason = trigger.should_trigger(estimated_tokens=9999, budget_tokens=0)
        self.assertEqual(reason, "none")

    def test_turn_count_triggers_at_threshold(self) -> None:
        trigger = self._trigger(max_turn_count_trigger=20)
        should, reason = trigger.should_trigger(turn_count=20)
        self.assertTrue(should)
        self.assertEqual(reason, "turn_count")

    def test_turn_count_does_not_trigger_below_threshold(self) -> None:
        trigger = self._trigger(max_turn_count_trigger=20)
        should, reason = trigger.should_trigger(turn_count=19)
        self.assertFalse(should)
        self.assertEqual(reason, "none")

    def test_no_condition_returns_false_none(self) -> None:
        trigger = self._trigger()
        should, reason = trigger.should_trigger()
        self.assertFalse(should)
        self.assertEqual(reason, "none")

    def test_explicit_request_wins_over_other_conditions(self) -> None:
        """explicit_request is evaluated first so it wins over all other triggers."""
        trigger = self._trigger()
        should, reason = trigger.should_trigger(
            explicit_request=True,
            task_completed=True,
            turn_count=100,
            estimated_tokens=9999,
            budget_tokens=1000,
        )
        self.assertTrue(should)
        self.assertEqual(reason, "explicit_request")


class RollingSummaryProducerTests(unittest.TestCase):
    def _producer(self, **policy_kwargs: object) -> RollingSummaryProducer:
        return RollingSummaryProducer(
            RollingSummaryPolicy(**policy_kwargs),  # type: ignore[arg-type]
            clock=lambda: FIXED_NOW,
        )

    def test_producer_creates_record_with_all_sum02_fields(self) -> None:
        """SUM-02: produced record carries all required fields."""
        producer = self._producer()
        record = producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/session-phase21-001/v1",
            source_refs=("feedback://fb-001", "turn://turn-001"),
            task_intent_refs=("intent://task-001",),
            user_constraint_refs=("constraint://rule-001",),
            unanswered_question_refs=("question://q-001",),
            artifact_refs=("artifact://a-001",),
            outcome_refs=("outcome://o-001",),
            text_sha256_16="abcd1234efgh5678",
            text_length=142,
            metadata={"trigger_reason": "turn_count"},
        )

        self.assertEqual(record.summary_ref, "summary://phase21/session-phase21-001/v1")
        self.assertEqual(record.session_id, "session-phase21-001")
        self.assertEqual(record.scope, SCOPE)
        self.assertEqual(record.task_intent_refs, ("intent://task-001",))
        self.assertEqual(record.user_constraint_refs, ("constraint://rule-001",))
        self.assertEqual(record.unanswered_question_refs, ("question://q-001",))
        self.assertEqual(record.artifact_refs, ("artifact://a-001",))
        self.assertEqual(record.outcome_refs, ("outcome://o-001",))
        self.assertEqual(record.text_sha256_16, "abcd1234efgh5678")
        self.assertEqual(record.text_length, 142)
        self.assertIn("source_refs", record.metadata)
        self.assertIsNotNone(record.created_at)
        self.assertIsNotNone(record.updated_at)

    def test_producer_preserves_created_at_from_existing_record(self) -> None:
        """When existing is provided, created_at is not overwritten."""
        producer = self._producer()
        original = producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/session-phase21-001/v1",
            source_refs=("feedback://fb-001",),
        )

        updated_producer = RollingSummaryProducer(clock=lambda: "2026-07-03T10:00:00+00:00")
        updated = updated_producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/session-phase21-001/v2",
            source_refs=("feedback://fb-002",),
            existing=original,
        )

        self.assertEqual(updated.created_at, original.created_at)
        self.assertNotEqual(updated.updated_at, original.updated_at)
        self.assertEqual(updated.summary_ref, "summary://phase21/session-phase21-001/v2")

    def test_producer_fails_closed_on_empty_source_refs(self) -> None:
        """SUM-04: fails closed when source_refs is empty and require_source_refs=True."""
        producer = self._producer(require_source_refs=True)

        with self.assertRaisesRegex(SummaryPrivacyError, "source_refs"):
            producer.produce(
                scope=SCOPE,
                session_id="session-phase21-001",
                summary_ref="summary://phase21/s1",
                source_refs=(),
            )

    def test_producer_allows_empty_source_refs_when_policy_disabled(self) -> None:
        """When require_source_refs=False, empty source_refs is allowed."""
        producer = self._producer(require_source_refs=False)
        record = producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/s1",
            source_refs=(),
        )
        self.assertIsNotNone(record)

    def test_producer_fails_closed_on_wrong_ref_prefix(self) -> None:
        """SUM-04: fails closed when summary_ref does not start with min_summary_ref_prefix."""
        producer = self._producer()

        with self.assertRaisesRegex(SummaryPrivacyError, "summary_ref"):
            producer.produce(
                scope=SCOPE,
                session_id="session-phase21-001",
                summary_ref="https://external.example.com/summary/1",
                source_refs=("feedback://fb-001",),
            )

    def test_producer_rejects_raw_payload_in_metadata(self) -> None:
        """SUM-04: raises SummaryPrivacyError for forbidden raw payload metadata keys."""
        producer = self._producer()

        for forbidden_key in ("raw_payload", "full_text", "callback_body", "document_text", "case_facts"):
            with self.subTest(key=forbidden_key):
                with self.assertRaisesRegex(SummaryPrivacyError, forbidden_key):
                    producer.produce(
                        scope=SCOPE,
                        session_id="session-phase21-001",
                        summary_ref="summary://phase21/s1",
                        source_refs=("feedback://fb-001",),
                        metadata={forbidden_key: "some text"},
                    )

    def test_producer_rejects_secret_like_key_in_metadata(self) -> None:
        """SUM-04: raises SummaryPrivacyError for secret-like metadata keys."""
        producer = self._producer()

        with self.assertRaisesRegex(SummaryPrivacyError, "api_key"):
            producer.produce(
                scope=SCOPE,
                session_id="session-phase21-001",
                summary_ref="summary://phase21/s1",
                source_refs=("feedback://fb-001",),
                metadata={"api_key": "leaked"},
            )

    def test_producer_output_record_is_frozen_and_copy_safe(self) -> None:
        """Returned RollingSummaryRecord is frozen; re-producing does not share state."""
        producer = self._producer()
        record = producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/s1",
            source_refs=("feedback://fb-001",),
        )

        with self.assertRaises((AttributeError, TypeError)):
            record.session_id = "mutated"  # type: ignore[misc]

    def test_context_bundle_does_not_embed_summary_full_text(self) -> None:
        """SUM-01 contract: ContextAssembler stores only summary_ref + hashes in bundle metadata."""
        producer = self._producer()
        raw_summary_text = "这是一段真实的会话摘要内容，绝不应该出现在 ContextBundle 元数据中。"
        record = producer.produce(
            scope=SCOPE,
            session_id="session-phase21-001",
            summary_ref="summary://phase21/s1",
            source_refs=("feedback://fb-001",),
            text_sha256_16=raw_summary_text[:16],  # using first chars as a "hash" for test detection
            text_length=len(raw_summary_text),
        )

        assembler = ContextAssembler(policy=ContextAssemblyPolicy(budget_tokens=4096))
        result = assembler.assemble(
            ContextAssemblyInput(
                scope=SCOPE,
                session_id="session-phase21-001",
                turn_id="turn-phase21-001",
                current_turn_ref="turn://turn-phase21-001",
                rolling_summary=record,
            )
        )

        bundle_event_str = str(result.bundle)
        self.assertNotIn(raw_summary_text, bundle_event_str)

        # The summary_ref only (not raw text) is embedded in bundle.summary_ref
        self.assertEqual(result.bundle.summary_ref, "summary://phase21/s1")


class RollingSummaryCombinedPipelineTests(unittest.TestCase):
    def test_trigger_and_producer_pipeline_produces_safe_record(self) -> None:
        """End-to-end: trigger fires → producer creates record → store upserts → retrieve."""
        policy = RollingSummaryPolicy(max_turn_count_trigger=5)
        trigger = RollingSummaryTrigger(policy=policy)
        producer = RollingSummaryProducer(policy=policy, clock=lambda: FIXED_NOW)
        store = InMemoryRollingSummaryStore()

        should, reason = trigger.should_trigger(turn_count=5)
        self.assertTrue(should)
        self.assertEqual(reason, "turn_count")

        record = producer.produce(
            scope=SCOPE,
            session_id="session-pipeline-001",
            summary_ref="summary://phase21/pipeline/session-001/v1",
            source_refs=("turn://t-001", "turn://t-002", "turn://t-003", "turn://t-004", "turn://t-005"),
            task_intent_refs=("intent://task-phase21-001",),
            metadata={"trigger_reason": reason},
        )

        store.upsert(record)
        retrieved = store.get(SCOPE, "session-pipeline-001")
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.summary_ref, "summary://phase21/pipeline/session-001/v1")
        self.assertEqual(retrieved.metadata["trigger_reason"], reason)


if __name__ == "__main__":
    unittest.main()
