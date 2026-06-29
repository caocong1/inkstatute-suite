"""inkstatute-solutions-demo_non_legal: backend-neutral education demo pack."""

from platform_runtime import SolutionPackageManifest

from .hermes_materializer import (
    DEMO_NON_LEGAL_SOLUTION_ID,
    DEMO_NON_LEGAL_VERSION,
    DemoNonLegalHermesMaterializer,
)


__all__ = [
    "DEMO_NON_LEGAL_SOLUTION_ID",
    "DEMO_NON_LEGAL_VERSION",
    "DemoNonLegalHermesMaterializer",
    "SolutionPackageManifest",
]