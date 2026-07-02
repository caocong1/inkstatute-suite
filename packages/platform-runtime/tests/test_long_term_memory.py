"""Contract tests for the backend-agnostic long-term Memory interface."""

from __future__ import annotations

import os
import unittest

from hindsight_client import Hindsight

from platform_runtime import (
    FakeMemory,
    HindsightMemory,
    HindsightMemoryError,
    Memory,
    MemoryPrivacyError,
    MemoryRecallInput,
    MemoryReflectInput,
    MemoryRetainInput,
)


class FakeMemoryContractTest(unittest.IsolatedAsyncioTestCase):
    """Validate FakeMemory satisfies the Memory interface."""

    async def asyncSetUp(self) -> None:
        self.memory: Memory = FakeMemory()
        self.tenant = "tenant-1"
        self.workspace = "workspace-1"
        self.user = "alice"
        self.bank = "default"

    async def test_retain_and_recall(self) -> None:
        await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="Alice prefers concise answers.",
            )
        )
        result = await self.memory.arecall(
            MemoryRecallInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="concise",
            )
        )
        self.assertEqual(result.bank_id, "tenant-1:workspace-1:alice")
        self.assertEqual(len(result.memories), 1)
        self.assertIn("concise", result.memories[0].text.lower())

    async def test_reflect_uses_recall(self) -> None:
        await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="Alice is a lawyer working on contract disputes.",
            )
        )
        result = await self.memory.areflect(
            MemoryReflectInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="What does Alice do?",
            )
        )
        self.assertIn("lawyer", result.text.lower())
        self.assertTrue(result.based_on)

    async def test_isolation_between_users(self) -> None:
        await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="Alice's private note.",
            )
        )
        result = await self.memory.arecall(
            MemoryRecallInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id="bob",
                bank_id=self.bank,
                query="private note",
            )
        )
        self.assertEqual(len(result.memories), 0)

    async def test_retain_rejects_empty_content(self) -> None:
        with self.assertRaises(MemoryPrivacyError):
            await self.memory.aretain(
                MemoryRetainInput(
                    tenant_id=self.tenant,
                    workspace_id=self.workspace,
                    user_id=self.user,
                    bank_id=self.bank,
                    content="   ",
                )
            )

    async def test_retain_rejects_secret_metadata(self) -> None:
        with self.assertRaises(MemoryPrivacyError):
            await self.memory.aretain(
                MemoryRetainInput(
                    tenant_id=self.tenant,
                    workspace_id=self.workspace,
                    user_id=self.user,
                    bank_id=self.bank,
                    content="Public fact.",
                    metadata={"api_key": "secret"},
                )
            )

    async def test_capability_manifest(self) -> None:
        manifest = self.memory.capability_manifest()
        self.assertEqual(manifest["provider"], "test_double")
        self.assertFalse(manifest["network_required"])
        self.assertFalse(manifest["requires_secrets"])


class HindsightMemoryContractTest(unittest.IsolatedAsyncioTestCase):
    """Validate HindsightMemory against a live Hindsight instance when available."""

    async def asyncSetUp(self) -> None:
        self.base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
        self.skip_if_unavailable()
        self.memory: Memory = HindsightMemory(
            client=Hindsight(base_url=self.base_url, api_key=os.environ.get("HINDSIGHT_API_KEY"))
        )
        self.tenant = "tenant-test"
        self.workspace = "workspace-test"
        self.user = f"user-{self.id()}"
        self.bank = "default"

    def skip_if_unavailable(self) -> None:
        import urllib.request

        try:
            urllib.request.urlopen(f"{self.base_url}/health", timeout=2)
        except Exception:
            self.skipTest("Hindsight not available at HINDSIGHT_BASE_URL")

    async def test_retain_recall_reflect(self) -> None:
        retain_result = await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="User is a lawyer named Alice. She is working on a contract dispute with Acme Corp.",
            )
        )
        self.assertGreaterEqual(retain_result.retained_count, 0)

        # Allow Hindsight to consolidate.
        import asyncio

        await asyncio.sleep(2)

        recall_result = await self.memory.arecall(
            MemoryRecallInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="What is Alice working on?",
            )
        )
        self.assertTrue(recall_result.memories)
        texts = " ".join(m.text.lower() for m in recall_result.memories)
        self.assertTrue(
            "acme" in texts or "contract" in texts or "dispute" in texts,
            f"Expected Acme/contract/dispute in recall: {texts}",
        )

        reflect_result = await self.memory.areflect(
            MemoryReflectInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="Summarize Alice's current work.",
            )
        )
        self.assertTrue(reflect_result.text)

    async def test_capability_manifest(self) -> None:
        manifest = self.memory.capability_manifest()
        self.assertEqual(manifest["provider"], "hindsight")
        self.assertTrue(manifest["supports_memory_records"])
        self.assertTrue(manifest["network_required"])


class HindsightMemoryMultiTurnTest(unittest.IsolatedAsyncioTestCase):
    """Live multi-turn validation: preference retention + cross-task recall."""

    async def asyncSetUp(self) -> None:
        self.base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
        self.skip_if_unavailable()
        self.memory: Memory = HindsightMemory(
            client=Hindsight(base_url=self.base_url, api_key=os.environ.get("HINDSIGHT_API_KEY"))
        )
        self.tenant = "tenant-multiturn"
        self.workspace = "workspace-multiturn"
        self.user = f"user-{self.id()}"
        self.bank = "default"

    def skip_if_unavailable(self) -> None:
        import urllib.request

        try:
            urllib.request.urlopen(f"{self.base_url}/health", timeout=2)
        except Exception:
            self.skipTest("Hindsight not available at HINDSIGHT_BASE_URL")

    async def test_multi_turn_preference_retention_and_cross_task_recall(self) -> None:
        import asyncio

        # Turn 1: retain a preference
        await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="User prefers concise contract summaries and dislikes verbose explanations.",
            )
        )

        # Turn 2: retain a project fact
        await self.memory.aretain(
            MemoryRetainInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                content="User is currently handling the Acme Corporation contract dispute.",
            )
        )

        # Allow Hindsight to consolidate.
        await asyncio.sleep(2)

        # Cross-task recall: preference
        preference_result = await self.memory.arecall(
            MemoryRecallInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="How should I format summaries for this user?",
                max_results=4,
            )
        )
        preference_texts = " ".join(m.text.lower() for m in preference_result.memories)
        self.assertTrue(
            "concise" in preference_texts or "verbose" in preference_texts,
            f"Expected preference recall: {preference_texts}",
        )

        # Cross-task recall: project fact
        project_result = await self.memory.arecall(
            MemoryRecallInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="What is the current case about?",
                max_results=4,
            )
        )
        project_texts = " ".join(m.text.lower() for m in project_result.memories)
        self.assertTrue(
            "acme" in project_texts or "contract" in project_texts or "dispute" in project_texts,
            f"Expected project fact recall: {project_texts}",
        )

        # Reflect combines both
        reflect_result = await self.memory.areflect(
            MemoryReflectInput(
                tenant_id=self.tenant,
                workspace_id=self.workspace,
                user_id=self.user,
                bank_id=self.bank,
                query="What should I remember about this user and their current work?",
            )
        )
        reflect_text = reflect_result.text.lower()
        self.assertTrue(
            ("concise" in reflect_text or "verbose" in reflect_text)
            and ("acme" in reflect_text or "contract" in reflect_text),
            f"Expected reflect to combine preference and project: {reflect_result.text}",
        )


if __name__ == "__main__":
    unittest.main()
