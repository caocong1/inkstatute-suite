"""Three-separation routing manifest producer.

Given a ``skill-index.json``, produces a metadata-only routing manifest (JSON)
containing only index-level fields needed for routing. No skill body text is
included. This enforces the metadata/body/tools separation principle.

Stub — full implementation in Task 97-01-05.
"""

from __future__ import annotations

from pathlib import Path


def produce_routing_manifest(
    index_path: str | Path,
    output_path: str | Path,
) -> None:
    """Produce a metadata-only routing manifest from a skill-index.json.

    Stub — implemented in Task 97-01-05.
    """
    raise NotImplementedError("Three-separation routing manifest not yet implemented")
