"""ProvenanceLogger — per-claim agent → reviewer → source chain (SAFE-07).

Every claim's provenance (agent → reviewer → source) is logged with a
hash reference (``claim_ref``), NOT the full claim text — honouring the
project rule that contract logs prefer references over sensitive full
text.

The logger is file-based and per-arena: provenance entries are appended
to ``{storage_dir}/{arena_id}/provenance.json`` as a JSON array.  Each
entry stores ``claim_ref`` (first 32 chars of the SHA-256 hex digest of
the claim), ``agent_slot``, ``reviewer_slot`` (``None`` for Phase 107 —
cross-review is Phase 108), ``source``, ``tier``, and ``timestamp``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inkstatute_agent_core.citations import CitationAudit


@dataclass(frozen=True, slots=True)
class ProvenanceChain:
    """A single provenance entry for one claim from one agent.

    ``claim_ref`` is a truncated SHA-256 hash reference (first 32 chars),
    NOT the full claim text.  ``reviewer_slot`` is ``None`` for Phase 107
    because cross-review is not implemented until Phase 108.
    """

    claim_ref: str
    agent_slot: str
    reviewer_slot: str | None
    source: str
    tier: str | None
    timestamp: str


def _claim_ref(claim: str) -> str:
    """Return the first 32 chars of the SHA-256 hex digest of *claim*."""
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()[:32]


class ProvenanceLogger:
    """File-based per-claim provenance logging with hash references.

    Appends ``ProvenanceChain`` entries to
    ``{storage_dir}/{arena_id}/provenance.json``.  The stored JSON does
    NOT contain the full claim text — only ``claim_ref`` (a hash).
    """

    def __init__(self, storage_dir: str | Path) -> None:
        self._storage_dir = Path(storage_dir)

    def log_claim(
        self,
        *,
        arena_id: str,
        claim: str,
        agent_slot: str,
        citation_audit: Any | None = None,
        reviewer_slot: str | None = None,
    ) -> ProvenanceChain:
        """Log a provenance entry for a claim and return the ``ProvenanceChain``.

        ``source`` and ``tier`` are populated from the first
        ``citation_audit.items[0]`` if items exist; otherwise ``source``
        is ``""`` and ``tier`` is ``None``.
        """
        source = ""
        tier: str | None = None
        if citation_audit is not None and getattr(citation_audit, "items", None):
            first_item = citation_audit.items[0]
            source = getattr(first_item, "source", "") or ""
            tier = getattr(first_item, "tier", None)

        chain = ProvenanceChain(
            claim_ref=_claim_ref(claim),
            agent_slot=agent_slot,
            reviewer_slot=reviewer_slot,
            source=source,
            tier=tier,
            timestamp=datetime.now(UTC).isoformat(),
        )

        arena_dir = self._storage_dir / arena_id
        arena_dir.mkdir(parents=True, exist_ok=True)
        file_path = arena_dir / "provenance.json"

        entries = self._read_entries(file_path)
        entries.append(
            {
                "claim_ref": chain.claim_ref,
                "agent_slot": chain.agent_slot,
                "reviewer_slot": chain.reviewer_slot,
                "source": chain.source,
                "tier": chain.tier,
                "timestamp": chain.timestamp,
            }
        )
        file_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return chain

    def get_chain(
        self,
        *,
        arena_id: str,
        claim: str,
    ) -> list[ProvenanceChain]:
        """Return all provenance entries for *claim* in insertion order."""
        file_path = self._storage_dir / arena_id / "provenance.json"
        entries = self._read_entries(file_path)
        target_ref = _claim_ref(claim)
        return [
            ProvenanceChain(
                claim_ref=e["claim_ref"],
                agent_slot=e["agent_slot"],
                reviewer_slot=e.get("reviewer_slot"),
                source=e.get("source", ""),
                tier=e.get("tier"),
                timestamp=e.get("timestamp", ""),
            )
            for e in entries
            if e["claim_ref"] == target_ref
        ]

    def get_all_chains(
        self,
        *,
        arena_id: str,
    ) -> list[ProvenanceChain]:
        """Return all provenance entries for *arena_id* in insertion order."""
        file_path = self._storage_dir / arena_id / "provenance.json"
        entries = self._read_entries(file_path)
        return [
            ProvenanceChain(
                claim_ref=e["claim_ref"],
                agent_slot=e["agent_slot"],
                reviewer_slot=e.get("reviewer_slot"),
                source=e.get("source", ""),
                tier=e.get("tier"),
                timestamp=e.get("timestamp", ""),
            )
            for e in entries
        ]

    @staticmethod
    def _read_entries(file_path: Path) -> list[dict[str, Any]]:
        """Read the JSON array from *file_path*, returning ``[]`` if absent."""
        if not file_path.exists():
            return []
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []


__all__ = [
    "ProvenanceChain",
    "ProvenanceLogger",
]
