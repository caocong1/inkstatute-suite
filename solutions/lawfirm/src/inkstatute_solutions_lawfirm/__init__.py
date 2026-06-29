"""inkstatute-solutions-lawfirm: backend-neutral lawyer solution pack.

Public surface: LawfirmHermesMaterializer, LAWFIRM_SOLUTION_ID,
LAWFIRM_VERSION, LAWFIRM_PERSONA_REF, register_into, scan_text, scan_path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from platform_runtime import SolutionPackageManifest

from .hermes_materializer import (
    LAWFIRM_PERSONA_REF,
    LAWFIRM_SOLUTION_ID,
    LAWFIRM_VERSION,
    LawfirmHermesMaterializer,
)
from .sanitize import scan_path, scan_text

if TYPE_CHECKING:
    from inkstatute_solution_loader import MaterializerRegistry


def register_into(
    registry: "MaterializerRegistry",
    output_dir_anchor: Path | None = None,
    backend_id: str = "hermes",
) -> None:
    """Register the lawfirm Hermes materializer into ``registry``.

    ``output_dir_anchor`` is accepted-but-unused: the current materializer
    writes only inside the caller-provided ``materialize_for`` output_dir,
    but Plan 13-04's composability test passes it for forward-compatibility
    with materializers that may need a long-lived base directory.
    """

    del output_dir_anchor
    mat = LawfirmHermesMaterializer()
    registry.register(backend_id, mat.materialize, mat.side_effects())


__all__ = [
    "LAWFIRM_PERSONA_REF",
    "LAWFIRM_SOLUTION_ID",
    "LAWFIRM_VERSION",
    "LawfirmHermesMaterializer",
    "SolutionPackageManifest",
    "register_into",
    "scan_path",
    "scan_text",
]