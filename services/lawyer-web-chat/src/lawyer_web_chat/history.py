"""In-memory message history for Lawyer Web Chat.

Stores message references only — no raw legal payloads are persisted.
Each message records the conversation_id, sender, content (boundary-filtered),
and a reference to the original payload.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .boundary import ChatBoundary
from platform_runtime.output_boundary import BoundaryAction


@dataclass
class ChatMessage:
    """A chat message in history (reference-only)."""

    message_id: str
    conversation_id: str
    sender: str  # "lawyer" or "assistant"
    content: str  # boundary-filtered, HTML-escaped
    payload_ref: str  # reference to original payload (no raw text)
    timestamp: int
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageHistory:
    """In-memory message history store.

    Messages are stored per conversation_id. Content is filtered through the
    output boundary before storage — no backend noise is persisted.
    """

    def __init__(self, boundary: ChatBoundary | None = None) -> None:
        self._boundary = boundary or ChatBoundary()
        self._messages: dict[str, list[ChatMessage]] = {}
        self._counter = 0

    def add_message(
        self,
        *,
        conversation_id: str,
        sender: str,
        content: str,
        payload_ref: str,
        timestamp: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """Add a message to history. Content is boundary-filtered before storage."""
        ts = int(timestamp if timestamp is not None else time.time())
        self._counter += 1
        message_id = f"msg-{self._counter}"

        # Apply output boundary to content
        decision = self._boundary.apply(content)
        if decision.action == BoundaryAction.BLOCK:
            filtered_content = "[content filtered]"
        elif decision.action == BoundaryAction.REWRITE and decision.visible_text is not None:
            filtered_content = decision.visible_text
        elif decision.visible_text is not None:
            filtered_content = decision.visible_text
        else:
            filtered_content = ""

        message = ChatMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            sender=sender,
            content=filtered_content,
            payload_ref=payload_ref,
            timestamp=ts,
            metadata=metadata or {},
        )
        self._messages.setdefault(conversation_id, []).append(message)
        return message

    def get_history(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        tenant_filter: Any = None,
    ) -> dict[str, Any]:
        """Get message history for a conversation.

        Returns a dict with ``items``, ``count``, ``has_more``, and ``next_cursor``.

        When ``tenant_filter`` is active, messages are additionally filtered by
        ``msg.metadata.get("tenant_id") == tenant_filter.tenant_id``.  Messages
        without a ``tenant_id`` in metadata are excluded when the filter is
        active (fail-safe).
        """
        messages = self._messages.get(conversation_id, [])
        if tenant_filter is not None and getattr(tenant_filter, "is_active", False):
            messages = [
                msg for msg in messages
                if msg.metadata.get("tenant_id") == tenant_filter.tenant_id
            ]
        start_idx = 0
        if cursor is not None:
            for i, msg in enumerate(messages):
                if msg.message_id == cursor:
                    start_idx = i + 1
                    break
        page = messages[start_idx:start_idx + limit]
        has_more = start_idx + limit < len(messages)
        next_cursor = page[-1].message_id if page and has_more else None

        return {
            "items": [
                {
                    "message_id": msg.message_id,
                    "conversation_id": msg.conversation_id,
                    "sender": msg.sender,
                    "content": msg.content,
                    "payload_ref": msg.payload_ref,
                    "timestamp": msg.timestamp,
                }
                for msg in page
            ],
            "count": len(page),
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    def clear(self, conversation_id: str) -> int:
        """Clear history for a conversation. Returns count of removed messages."""
        messages = self._messages.pop(conversation_id, [])
        return len(messages)


__all__ = ["ChatMessage", "MessageHistory"]
