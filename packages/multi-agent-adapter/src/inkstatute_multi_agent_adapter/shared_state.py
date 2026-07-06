"""Copy-on-write shared state store for multi-agent orchestration.

``SharedStateStore`` maintains per-``parent_run_id`` shared state with
copy-on-write isolation.  Each agent reads a snapshot of the shared state;
writes create a per-agent COW copy that does not mutate the shared state.
In sequential mode, after an agent completes, its COW copy is committed
to the shared state for the next agent.  In parallel mode, each agent gets
the same snapshot and writes are isolated — no cross-agent mutation.
"""

from __future__ import annotations

import copy
from typing import Any


class SharedStateStore:
    """Copy-on-write shared state scoped by ``parent_run_id``.

    Internal structure:
    - ``_shared``: ``dict[parent_run_id, dict[str, Any]]`` — the shared state.
    - ``_copies``: ``dict[parent_run_id, dict[agent_id, dict[str, Any]]]`` —
      per-agent COW copies.

    All reads return deep copies to prevent external mutation.  All writes
    create a deep-copied COW snapshot for the agent if one does not already
    exist, then mutate only that copy — the shared state is never directly
    mutated by ``write``.
    """

    def __init__(self) -> None:
        self._shared: dict[str, dict[str, Any]] = {}
        self._copies: dict[str, dict[str, dict[str, Any]]] = {}

    def init(self, parent_run_id: str, initial_state: dict[str, Any] | None = None) -> None:
        """Initialize shared state for a parent run.

        Stores a deep copy of ``initial_state`` so the caller's dict is not
        mutated by subsequent writes.
        """
        self._shared[parent_run_id] = copy.deepcopy(initial_state) if initial_state else {}
        self._copies[parent_run_id] = {}

    def snapshot(self, parent_run_id: str) -> dict[str, Any]:
        """Return a deep copy of the shared state for reading.

        Raises ``KeyError`` if the parent run has not been initialized.
        """
        shared = self._shared[parent_run_id]
        return copy.deepcopy(shared)

    def write(self, parent_run_id: str, agent_id: str, key: str, value: Any) -> None:
        """Write a single key into the agent's COW copy.

        Creates a COW copy from the current shared state if the agent does
        not already have one.  The shared state is NOT mutated.
        """
        cow = self._get_or_create_cow(parent_run_id, agent_id)
        cow[key] = copy.deepcopy(value)

    def write_all(self, parent_run_id: str, agent_id: str, updates: dict[str, Any]) -> None:
        """Batch-write multiple keys into the agent's COW copy."""
        cow = self._get_or_create_cow(parent_run_id, agent_id)
        for key, value in updates.items():
            cow[key] = copy.deepcopy(value)

    def commit(self, parent_run_id: str, agent_id: str) -> None:
        """Merge an agent's COW copy into the shared state.

        After commit, subsequent ``snapshot`` calls will reflect the agent's
        writes.  Raises ``KeyError`` if the agent has no COW copy.
        """
        copies = self._copies[parent_run_id]
        if agent_id not in copies:
            raise KeyError(f"no COW copy to commit for agent {agent_id!r} in run {parent_run_id!r}")
        self._shared[parent_run_id].update(copy.deepcopy(copies[agent_id]))

    def agent_state(self, parent_run_id: str, agent_id: str) -> dict[str, Any]:
        """Return the agent's COW copy, or a snapshot if no writes occurred.

        Always returns a deep copy so the caller cannot mutate internal state.
        """
        copies = self._copies[parent_run_id]
        if agent_id in copies:
            return copy.deepcopy(copies[agent_id])
        return self.snapshot(parent_run_id)

    def has_cow_copy(self, parent_run_id: str, agent_id: str) -> bool:
        """Return True if the agent has a COW copy (has written)."""
        return agent_id in self._copies.get(parent_run_id, {})

    def dispose(self, parent_run_id: str) -> None:
        """Remove all shared state and COW copies for a parent run."""
        self._shared.pop(parent_run_id, None)
        self._copies.pop(parent_run_id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_cow(self, parent_run_id: str, agent_id: str) -> dict[str, Any]:
        copies = self._copies[parent_run_id]
        if agent_id not in copies:
            copies[agent_id] = copy.deepcopy(self._shared[parent_run_id])
        return copies[agent_id]


__all__ = ["SharedStateStore"]
