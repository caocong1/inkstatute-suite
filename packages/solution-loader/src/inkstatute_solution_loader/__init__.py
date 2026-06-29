"""inkstatute-solution-loader: default-off SolutionLoader library.

Re-exports the loader, registry, validator, side-effect declaration contract,
and the bundle privacy scanner (Plan 13-04).
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
from .privacy_scan import (
    BINARY_REFUSE_EXTENSIONS,
    TEXT_EXTENSIONS,
    scan_bundle_dir,
)
from .side_effects import MaterializerSideEffects

# Local Issue alias kept for convenience (mirrors platform_runtime.Issue).
ManifestValidatorIssue = Issue

__all__ = [
    "BINARY_REFUSE_EXTENSIONS",
    "DefaultSolutionLoader",
    "DefaultSolutionLoaderConfig",
    "Issue",
    "ManifestValidator",
    "ManifestValidatorIssue",
    "MaterializerFn",
    "MaterializerRegistry",
    "MaterializerSideEffects",
    "SolutionLoaderFeatureFlags",
    "TEXT_EXTENSIONS",
    "load_solution_loader_feature_flags",
    "scan_bundle_dir",
]
