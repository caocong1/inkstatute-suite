"""inkstatute-skill-registry: read-only Skill Registry library.

Re-exports the manifest-to-descriptor mapper and the read-only SkillRegistry.
"""

from .mapper import load_skills_from_manifests, manifest_skill_to_descriptor

__all__ = [
    "load_skills_from_manifests",
    "manifest_skill_to_descriptor",
]
