"""inkstatute-skill-registry: read-only Skill Registry library.

Re-exports the manifest-to-descriptor mapper, the read-only SkillRegistry,
and the discovery index builder.
"""

from .discovery import build_discovery_index
from .mapper import load_skills_from_manifests, manifest_skill_to_descriptor
from .registry import SkillRegistry, SkillRegistryPort

__all__ = [
    "SkillRegistry",
    "SkillRegistryPort",
    "build_discovery_index",
    "load_skills_from_manifests",
    "manifest_skill_to_descriptor",
]
