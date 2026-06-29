"""inkstatute-solution-loader: default-off SolutionLoader library.

Re-exports the loader, registry, validator, and side-effect declaration
contract. (Plan 13-01 scope; privacy scanner is added by Plan 13-04.)
"""

from platform_runtime import Issue

from .config import (
    DefaultSolutionLoaderConfig,
    SolutionLoaderFeatureFlags,
    load_solution_loader_feature_flags,
)
from .loader import DefaultSolutionLoader
from .manifest_validator import ManifestValidator
from .materializer_registry import MaterializerFn, MaterializerRegistry
from .side_effects import MaterializerSideEffects

# Local Issue alias kept for convenience (mirrors platform_runtime.Issue).
ManifestValidatorIssue = Issue

__all__ = [
    "DefaultSolutionLoader",
    "DefaultSolutionLoaderConfig",
    "Issue",
    "ManifestValidator",
    "ManifestValidatorIssue",
    "MaterializerFn",
    "MaterializerRegistry",
    "MaterializerSideEffects",
    "SolutionLoaderFeatureFlags",
    "load_solution_loader_feature_flags",
]
