"""In-memory fake implementation of the long-term Memory interface for tests."""

from __future__ import annotations

from platform_contract.events import JsonObject

from .long_term_memory import (
    MemoryRecallInput,
    MemoryRecallResult,
    MemoryReflectInput,
    MemoryReflectResult,
    MemoryRetainInput,
    MemoryRetainResult,
    RecalledMemory,
    _validate_recall_input,
    _validate_reflect_input,
    _validate_retain_input,
)
from .memory_policy import MemoryCategory, MemoryContentClassifier, MemoryFocusPolicy, MemoryRetentionPolicy


class FakeMemory:
    """Deterministic, in-memory test double for the Memory interface.

    This implementation does not use embeddings or LLMs. It stores text verbatim
    and returns it on recall if the query is a substring of any stored memory.
    Reflection returns a canned answer based on recalled memories.

    Supports retention and focus policies via a rule-based classifier.
    """

    def __init__(self, classifier: MemoryContentClassifier | None = None) -> None:
        self._banks: dict[str, list[str]] = {}
        self._classifier = classifier or MemoryContentClassifier()

    def capability_manifest(self) -> JsonObject:
        return {
            "adapter_id": "fake-memory",
            "provider": "test_double",
            "adapter_version": "0.1.0",
            "deployment_model": "in_process",
            "source_refs": ("packages/platform-runtime/src/platform_runtime/fake_memory.py",),
            "supports_memory_records": True,
            "supports_delete": False,
            "supports_export": False,
            "supports_tenant_isolation": True,
            "supports_raw_payload_blocking": True,
            "stores_raw_payloads_by_default": False,
            "network_required": False,
            "requires_secrets": False,
            "data_residency": "process_local",
            "metadata": {"privacy": "test_fixture_only"},
        }

    def _bank_id(self, tenant_id: str, workspace_id: str, user_id: str) -> str:
        return f"{tenant_id}:{workspace_id}:{user_id}"

    async def aretain(self, input: MemoryRetainInput) -> MemoryRetainResult:
        _validate_retain_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        policy = input.retention_policy or MemoryRetentionPolicy()
        classification = self._classifier.classify(input.content)
        if classification.category in policy.allowed_categories and classification.confidence >= policy.min_confidence:
            self._banks.setdefault(bank_id, []).append(input.content)
            return MemoryRetainResult(
                bank_id=bank_id,
                retained_count=1,
                discarded_count=0,
                classifications=(classification,),
                metadata={"scope": {"tenant_id": input.tenant_id, "workspace_id": input.workspace_id, "user_id": input.user_id}},
            )
        return MemoryRetainResult(
            bank_id=bank_id,
            retained_count=0,
            discarded_count=1,
            classifications=(classification,),
            metadata={
                "scope": {"tenant_id": input.tenant_id, "workspace_id": input.workspace_id, "user_id": input.user_id},
                "reason": "category not allowed or confidence too low",
            },
        )

    async def arecall(self, input: MemoryRecallInput) -> MemoryRecallResult:
        _validate_recall_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        memories = self._banks.get(bank_id, [])
        focus = input.focus_policy or MemoryFocusPolicy()
        query_words = {w for w in input.query.lower().split() if len(w) > 2}
        matched = []
        for index, text in enumerate(memories):
            text_words = {w for w in text.lower().split() if len(w) > 2}
            overlap = query_words & text_words
            score = len(overlap) / max(len(query_words), 1)
            if score < focus.minimum_relevance_score:
                continue
            classification = self._classifier.classify(text)
            if focus.required_categories and classification.category not in focus.required_categories:
                continue
            matched.append(
                RecalledMemory(
                    memory_id=f"fake-{bank_id}-{index}",
                    text=text,
                    type="world",
                    relevance_score=score,
                    metadata={"category": classification.category},
                )
            )
        matched.sort(key=lambda m: (m.relevance_score or 0), reverse=True)
        selected = tuple(matched[: focus.max_results])
        return MemoryRecallResult(
            bank_id=bank_id,
            query=input.query,
            memories=selected,
            filtered_count=len(matched) - len(selected),
            metadata={"scope": {"tenant_id": input.tenant_id, "workspace_id": input.workspace_id, "user_id": input.user_id}},
        )

    async def areflect(self, input: MemoryReflectInput) -> MemoryReflectResult:
        _validate_reflect_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        recall = await self.arecall(
            MemoryRecallInput(
                tenant_id=input.tenant_id,
                workspace_id=input.workspace_id,
                user_id=input.user_id,
                bank_id=input.bank_id,
                query=input.query,
                max_results=4,
            )
        )
        text = f"Based on {len(recall.memories)} memories: " + " | ".join(m.text for m in recall.memories) if recall.memories else "No relevant memories found."
        return MemoryReflectResult(
            bank_id=bank_id,
            query=input.query,
            text=text,
            based_on=tuple(m.memory_id for m in recall.memories),
            metadata={"scope": {"tenant_id": input.tenant_id, "workspace_id": input.workspace_id, "user_id": input.user_id}},
        )
