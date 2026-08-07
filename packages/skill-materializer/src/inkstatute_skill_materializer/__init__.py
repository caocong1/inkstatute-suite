"""inkstatute-skill-materializer: Skill corpus materializer.

Consumes ``skill-index.json`` (produced by Phase 96 ``inkstatute-skill-index``)
and produces per-backend skill layouts:

- **Hermes profile** — symlink-first, copy for skills with ``scripts/``
- **ACP agent skills** — Claude Code plugin format + host assumption rewriting
- **Routing manifest** — metadata-only (three-separation enforcement)

Public API::

    from inkstatute_skill_materializer import (
        materialize_hermes,
        materialize_acp,
        produce_routing_manifest,
        SkillBodyInjector,
        HostAssumptionRewriter,
    )
"""

from .acp_materializer import ACPMaterializer, materialize_acp
from .body_injector import SkillBodyInjector
from .hermes_materializer import HermesMaterializer, materialize_hermes
from .host_assumption_rewriter import HostAssumptionRewriter
from .three_separation import produce_routing_manifest

MATERIALIZER_VERSION = "1.0.0"

__all__ = [
    "MATERIALIZER_VERSION",
    "ACPMaterializer",
    "HermesMaterializer",
    "HostAssumptionRewriter",
    "SkillBodyInjector",
    "materialize_acp",
    "materialize_hermes",
    "produce_routing_manifest",
]
