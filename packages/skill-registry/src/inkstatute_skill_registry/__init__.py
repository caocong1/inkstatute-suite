"""inkstatute-skill-registry: read-only Skill Registry library.

Re-exports the manifest-to-descriptor mapper, the read-only SkillRegistry,
the discovery index builder, and the API route handler.
"""

from .api import handle_get
from .discovery import build_discovery_index
from .mapper import load_skills_from_manifests, manifest_skill_to_descriptor
from .registry import SkillRegistry, SkillRegistryPort

__all__ = [
    "SkillRegistry",
    "SkillRegistryPort",
    "build_discovery_index",
    "handle_get",
    "load_skills_from_manifests",
    "manifest_skill_to_descriptor",
]
