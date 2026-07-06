"""inkstatute-skill-registry: Skill Registry library.

Re-exports the manifest-to-descriptor mapper, the read-only SkillRegistry,
the discovery index builder, the API route handler, and the
WritableSkillRegistry with CRUD, immutable versioning, rollback,
two-person rule, and per-tenant namespaces.
"""

from .api import handle_get
from .discovery import build_discovery_index
from .mapper import load_skills_from_manifests, manifest_skill_to_descriptor
from .registry import SkillRegistry, SkillRegistryPort
from .write import (
    HumanReviewRecord,
    SkillRegistryWriteError,
    SkillRegistryWritePort,
    SkillVersion,
    WritableSkillRegistry,
    WriteRequest,
)
from .write_api import handle_delete, handle_post, handle_put

__all__ = [
    "HumanReviewRecord",
    "SkillRegistry",
    "SkillRegistryPort",
    "SkillRegistryWriteError",
    "SkillRegistryWritePort",
    "SkillVersion",
    "WritableSkillRegistry",
    "WriteRequest",
    "build_discovery_index",
    "handle_delete",
    "handle_get",
    "handle_post",
    "handle_put",
    "load_skills_from_manifests",
    "manifest_skill_to_descriptor",
]
