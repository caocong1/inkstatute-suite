"""Test fixture helper: load a real skill-index.json and build a SkillRegistry.

Provides a function that loads a ``skill-index.json`` file via
``index_to_descriptors()`` and returns a :class:`SkillRegistry` instance
populated with real descriptors from the 396-skill index.

The default path points to a pre-built index at ``/tmp/skill-index.json``.
Tests that need a real-index registry should call ``build_real_index_registry()``
or ``get_real_index_path()`` to locate the index file.

If the index file is not found, the helper builds it on-the-fly from the
external source repos (``ai-for-china-legal`` and ``legal-skills``).
"""

from __future__ import annotations

from pathlib import Path

from inkstatute_skill_index import build_index, write_index
from inkstatute_skill_registry.mapper import index_to_descriptors
from inkstatute_skill_registry.registry import SkillRegistry

# Default path for the pre-built skill-index.json.
_DEFAULT_INDEX_PATH = Path("/tmp/skill-index.json")

# External repo paths (read-only).
_REPO_CONFIGS = [
    {"name": "ai-for-china-legal", "path": "/home/sorawatcher/workspace/ai-for-china-legal"},
    {"name": "legal-skills", "path": "/home/sorawatcher/workspace/legal-skills"},
]


def get_real_index_path() -> str:
    """Return the path to a usable ``skill-index.json``.

    If the default path exists, return it.  Otherwise, build the index
    on-the-fly from the external source repos and write it to the default
    path.
    """
    if _DEFAULT_INDEX_PATH.is_file():
        return str(_DEFAULT_INDEX_PATH)
    # Build on-the-fly
    index = build_index(_REPO_CONFIGS)
    write_index(index, str(_DEFAULT_INDEX_PATH))
    return str(_DEFAULT_INDEX_PATH)


def build_real_index_registry(index_path: str | None = None) -> SkillRegistry:
    """Build a :class:`SkillRegistry` from a real ``skill-index.json``.

    Args:
        index_path: Optional path to a ``skill-index.json`` file.
            Defaults to :func:`get_real_index_path`.

    Returns:
        A :class:`SkillRegistry` populated with real
        :class:`NeutralSkillDescriptor` records from the index.
    """
    path = index_path or get_real_index_path()
    descriptors = index_to_descriptors(path)
    return SkillRegistry(descriptors)
