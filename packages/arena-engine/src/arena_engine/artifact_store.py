"""ArtifactStore — reference-first structured output persistence (ENGINE-07).

Every agent's structured output per round is persisted to disk as a JSON
file.  The returned ``RoundArtifact`` carries ``raw_payload_ref`` as a
file path reference (not the full content), honouring the project rule
that contract logs prefer references over sensitive full text.

The store is file-based and per-arena: artifacts are organised as
``{storage_dir}/{arena_id}/{agent_slot}/round_{round}.json``.  All file
operations use ``pathlib.Path`` and ``json`` — no external dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RoundArtifact:
    """A single agent's structured output for one arena round.

    ``raw_payload_ref`` is a file path reference to the persisted JSON
    file — NOT the content itself.  This honours the reference-first
    logging rule (AGENTS.md: "Contract logs prefer references such as
    ``raw_payload_ref``").
    """

    arena_id: str
    agent_slot: str
    round: int
    content: str
    raw_payload_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)
    stored_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ArtifactStore:
    """File-based persistence for arena round outputs.

    Writes one JSON file per ``(arena_id, agent_slot, round)`` tuple.
    The returned ``RoundArtifact.raw_payload_ref`` is the on-disk file
    path, so downstream consumers and contract logs reference the file
    rather than embedding the full content.
    """

    def __init__(self, storage_dir: str | Path) -> None:
        self._storage_dir = Path(storage_dir)

    def store_round_output(
        self,
        *,
        arena_id: str,
        agent_slot: str,
        round: int,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoundArtifact:
        """Persist a round output to disk and return a ``RoundArtifact``.

        The JSON file at ``{storage_dir}/{arena_id}/{agent_slot}/round_{round}.json``
        contains keys ``arena_id``, ``agent_slot``, ``round``, ``content``,
        ``metadata``, and ``stored_at``.  The returned ``RoundArtifact``
        has ``raw_payload_ref`` set to the file path string.
        """
        metadata = dict(metadata) if metadata is not None else {}
        stored_at = datetime.now(UTC).isoformat()

        arena_dir = self._storage_dir / arena_id / agent_slot
        arena_dir.mkdir(parents=True, exist_ok=True)
        file_path = arena_dir / f"round_{round}.json"

        payload = {
            "arena_id": arena_id,
            "agent_slot": agent_slot,
            "round": round,
            "content": content,
            "metadata": metadata,
            "stored_at": stored_at,
        }
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return RoundArtifact(
            arena_id=arena_id,
            agent_slot=agent_slot,
            round=round,
            content=content,
            raw_payload_ref=str(file_path),
            metadata=metadata,
            stored_at=stored_at,
        )

    def get_artifact(
        self,
        *,
        arena_id: str,
        agent_slot: str,
        round: int,
    ) -> RoundArtifact | None:
        """Read and reconstruct a ``RoundArtifact`` from disk.

        Returns ``None`` when no file exists for the given tuple.
        """
        file_path = (
            self._storage_dir / arena_id / agent_slot / f"round_{round}.json"
        )
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return RoundArtifact(
            arena_id=data["arena_id"],
            agent_slot=data["agent_slot"],
            round=data["round"],
            content=data["content"],
            raw_payload_ref=str(file_path),
            metadata=data.get("metadata", {}),
            stored_at=data.get("stored_at", ""),
        )

    def list_round_artifacts(
        self,
        *,
        arena_id: str,
        round: int,
    ) -> list[RoundArtifact]:
        """List all ``RoundArtifact`` entries for a given arena round.

        Globs ``{storage_dir}/{arena_id}/*/round_{round}.json`` and
        returns the reconstructed artifacts.
        """
        arena_dir = self._storage_dir / arena_id
        if not arena_dir.exists():
            return []
        artifacts: list[RoundArtifact] = []
        for file_path in sorted(arena_dir.glob(f"*/round_{round}.json")):
            data = json.loads(file_path.read_text(encoding="utf-8"))
            artifacts.append(
                RoundArtifact(
                    arena_id=data["arena_id"],
                    agent_slot=data["agent_slot"],
                    round=data["round"],
                    content=data["content"],
                    raw_payload_ref=str(file_path),
                    metadata=data.get("metadata", {}),
                    stored_at=data.get("stored_at", ""),
                )
            )
        return artifacts


__all__ = [
    "ArtifactStore",
    "RoundArtifact",
]
