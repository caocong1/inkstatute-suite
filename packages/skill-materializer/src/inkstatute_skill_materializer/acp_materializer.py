"""ACP materializer — Claude Code plugin format + host assumption rewriting.

Produces a Claude Code plugin format directory layout from a
``skill-index.json``, applying host assumption rewriting to SKILL.md content.

Stub — full implementation in Task 97-01-04.
"""

from __future__ import annotations

from pathlib import Path


def materialize_acp(
    index_path: str | Path,
    output_dir: str | Path,
) -> object:
    """Materialize skills to an ACP agent skills layout.

    Stub — implemented in Task 97-01-04.
    """
    raise NotImplementedError("ACP materializer not yet implemented")


class ACPMaterializer:
    """ACP agent skills materializer (Claude Code plugin format + rewriting).

    Stub — full implementation in Task 97-01-04.
    """

    def materialize(
        self,
        index_path: str | Path,
        output_dir: str | Path,
    ) -> object:
        raise NotImplementedError("ACP materializer not yet implemented")
