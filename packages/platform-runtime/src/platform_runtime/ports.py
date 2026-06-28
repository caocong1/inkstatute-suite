"""Injected runtime support ports for embeddable platform hosts.

These Protocols keep runtime support library-only: hosts provide clocks, ID
generation, contract-log persistence, and output-boundary policy explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from platform_contract.events import JsonObject


@dataclass(frozen=True, slots=True)
class AssistantOutputDecision:
    action: str
    visible_text: str | None = None
    audit_metadata: JsonObject = field(default_factory=dict)


class RuntimeClock(Protocol):
    def now(self) -> str: ...


class IdFactory(Protocol):
    def new_id(self, prefix: str) -> str: ...


class ContractLogStore(Protocol):
    def append(self, event_key: str, event: Mapping[str, object]) -> object: ...


class AssistantOutputBoundary(Protocol):
    def apply(
        self,
        visibility_target: str,
        text: str | None = None,
        event_metadata: Mapping[str, object] | None = None,
    ) -> AssistantOutputDecision: ...


__all__ = [
    "AssistantOutputBoundary",
    "AssistantOutputDecision",
    "ContractLogStore",
    "IdFactory",
    "RuntimeClock",
]
