"""Hermes materializer — symlink-first, copy for scripts/.

Produces a Hermes profile layout under
``output_dir/profiles/<profile>/skills/<skill-name>/`` from a
``skill-index.json``.

Stub — full implementation in Task 97-01-02.
"""

from __future__ import annotations

from pathlib import Path


def materialize_hermes(
    index_path: str | Path,
    output_dir: str | Path,
    profile_name: str = "lawfirm",
) -> object:
    """Materialize skills to a Hermes profile layout.

    Stub — implemented in Task 97-01-02.
    """
    raise NotImplementedError("Hermes materializer not yet implemented")


class HermesMaterializer:
    """Hermes profile materializer (symlink-first, copy for scripts/).

    Stub — full implementation in Task 97-01-02.
    """

    def materialize(
        self,
        index_path: str | Path,
        output_dir: str | Path,
        profile_name: str = "lawfirm",
    ) -> object:
        raise NotImplementedError("Hermes materializer not yet implemented")
