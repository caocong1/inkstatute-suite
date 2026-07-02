"""Memory integration policy and helpers for the WeCom session runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from platform_runtime import (
    Memory,
    MemoryCategory,
    MemoryContentClassifier,
    MemoryFocusPolicy,
    MemoryRecallInput,
    MemoryRetentionPolicy,
    MemoryRetainInput,
)


class MemoryFailureMode(StrEnum):
    """How to behave when a memory operation fails."""

    FAIL_OPEN = "fail_open"
    LOG_ONLY = "log_only"
    FAIL_CLOSED = "fail_closed"


class MemoryRetentionScope(StrEnum):
    """What part of a turn to retain as durable memory."""

    USER_TURN = "user_turn"
    AGENT_REPLY = "agent_reply"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class MemoryIntegrationPolicy:
    """Configuration for memory integration in the WeCom session runtime."""

    enabled: bool = True
    failure_mode: MemoryFailureMode = MemoryFailureMode.FAIL_OPEN
    recall_max_results: int = 6
    retention_scope: MemoryRetentionScope = MemoryRetentionScope.BOTH
    retention_policy: MemoryRetentionPolicy | None = None
    focus_policy: MemoryFocusPolicy | None = None


async def recall_for_turn(
    memory: Memory,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    query: str,
    policy: MemoryIntegrationPolicy,
) -> tuple[str, ...]:
    """Recall relevant memory refs for a user turn.

    Returns a tuple of recalled memory text summaries. Never raises;
    failures are handled according to the policy.
    """
    if not policy.enabled:
        return ()
    try:
        focus = policy.focus_policy or MemoryFocusPolicy(max_results=policy.recall_max_results)
        result = await memory.arecall(
            MemoryRecallInput(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id,
                bank_id="default",
                query=query,
                focus_policy=focus,
            )
        )
        return tuple(m.text for m in result.memories)
    except Exception:
        if policy.failure_mode == MemoryFailureMode.FAIL_CLOSED:
            raise
        return ()


async def retain_turn_memory(
    memory: Memory,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    user_turn_text: str,
    agent_reply_text: str,
    policy: MemoryIntegrationPolicy,
) -> int:
    """Retain durable memory after a turn reply is finalized.

    Returns the number of retained memory items. Never raises; failures are
    handled according to the policy.
    """
    if not policy.enabled:
        return 0
    retention_policy = policy.retention_policy or MemoryRetentionPolicy()
    classifier = MemoryContentClassifier()
    retained = 0
    contents: list[str] = []
    if policy.retention_scope in (MemoryRetentionScope.USER_TURN, MemoryRetentionScope.BOTH):
        contents.append(user_turn_text)
    if policy.retention_scope in (MemoryRetentionScope.AGENT_REPLY, MemoryRetentionScope.BOTH):
        contents.append(agent_reply_text)
    for content in contents:
        classification = classifier.classify(content)
        if classification.category not in retention_policy.allowed_categories:
            continue
        try:
            result = await memory.aretain(
                MemoryRetainInput(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    bank_id="default",
                    content=content,
                    retention_policy=retention_policy,
                )
            )
            retained += result.retained_count
        except Exception:
            if policy.failure_mode == MemoryFailureMode.FAIL_CLOSED:
                raise
            continue
    return retained
