"""Arena workflow contract dataclasses (Config, Handle, Status, UserAction)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .events import JsonObject


@dataclass(frozen=True, slots=True)
class ArenaWorkflowConfig:
    arena_id: str
    mode: str
    agent_slots: list[str]
    task_instruction: str
    reference_dir: str | None = None
    max_rounds: int = 3
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArenaHandle:
    arena_id: str
    status: str
    created_at: str
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArenaStatus:
    arena_id: str
    mode: str
    status: str
    agent_slots: list[str] = field(default_factory=list)
    current_round: int = 0
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArenaUserAction:
    arena_id: str
    action: str
    selected_slot: str | None = None
    metadata: JsonObject = field(default_factory=dict)


__all__ = [
    "ArenaHandle",
    "ArenaStatus",
    "ArenaUserAction",
    "ArenaWorkflowConfig",
]
