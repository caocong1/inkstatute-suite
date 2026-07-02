"""Contract tests for memory classification, retention, and focus policies."""

from __future__ import annotations

import unittest

from platform_runtime import (
    FakeMemory,
    MemoryCategory,
    MemoryContentClassifier,
    MemoryFocusPolicy,
    MemoryRecallInput,
    MemoryRetentionPolicy,
    MemoryRetainInput,
)


class MemoryContentClassifierTests(unittest.TestCase):
    def test_user_preference(self) -> None:
        classifier = MemoryContentClassifier()
        result = classifier.classify("User prefers concise answers.")
        self.assertEqual(result.category, MemoryCategory.USER_PREFERENCE)
        self.assertGreater(result.confidence, 0.0)

    def test_project_fact(self) -> None:
        classifier = MemoryContentClassifier()
        result = classifier.classify("User is working on the Acme contract dispute.")
        self.assertEqual(result.category, MemoryCategory.PROJECT_FACT)

    def test_lesson_learned(self) -> None:
        classifier = MemoryContentClassifier()
        result = classifier.classify("Lesson learned: never skip the review clause.")
        self.assertEqual(result.category, MemoryCategory.LESSON_LEARNED)

    def test_transient(self) -> None:
        classifier = MemoryContentClassifier()
        result = classifier.classify("Please send me the latest draft.")
        self.assertEqual(result.category, MemoryCategory.TASK_DETAIL)

    def test_classifier_rejects_non_string(self) -> None:
        classifier = MemoryContentClassifier()
        with self.assertRaises(Exception):
            classifier.classify(123)  # type: ignore[arg-type]


class MemoryRetentionPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_durable_content_is_retained(self) -> None:
        memory = FakeMemory()
        result = await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User prefers concise answers.",
            )
        )
        self.assertEqual(result.retained_count, 1)
        self.assertEqual(result.discarded_count, 0)

    async def test_transient_content_is_discarded_by_default(self) -> None:
        memory = FakeMemory()
        result = await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="Upload the file to temporary storage.",
            )
        )
        self.assertEqual(result.retained_count, 0)
        self.assertEqual(result.discarded_count, 1)

    async def test_policy_can_allow_task_details(self) -> None:
        memory = FakeMemory()
        policy = MemoryRetentionPolicy(
            allowed_categories=(
                MemoryCategory.USER_PREFERENCE,
                MemoryCategory.PROJECT_FACT,
                MemoryCategory.TASK_DETAIL,
            )
        )
        result = await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="Upload the file to temporary storage.",
                retention_policy=policy,
            )
        )
        self.assertEqual(result.retained_count, 1)


class MemoryFocusPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_relevance_threshold_filters_memories(self) -> None:
        memory = FakeMemory()
        await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User prefers concise answers.",
            )
        )
        await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User likes coffee in the morning.",
            )
        )
        result = await memory.arecall(
            MemoryRecallInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                query="concise",
                focus_policy=MemoryFocusPolicy(minimum_relevance_score=0.5),
            )
        )
        self.assertEqual(len(result.memories), 1)
        self.assertIn("concise", result.memories[0].text)

    async def test_required_category_filter(self) -> None:
        memory = FakeMemory()
        await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User prefers concise answers.",
            )
        )
        await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User is working on Acme contract.",
            )
        )
        result = await memory.arecall(
            MemoryRecallInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                query="user",
                focus_policy=MemoryFocusPolicy(required_categories=(MemoryCategory.USER_PREFERENCE,)),
            )
        )
        self.assertEqual(len(result.memories), 1)
        self.assertIn("concise", result.memories[0].text)


if __name__ == "__main__":
    unittest.main()
