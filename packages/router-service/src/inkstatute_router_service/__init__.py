"""inkstatute-router-service: standalone router library.

Re-exports the RouterPort Protocol, RouterService class, RouterStrategy enum,
the classify_intent classifier function, the tool-resolution join helpers,
the legal-risk classifier, and the model classifier port.
"""

from .classifier import classify_intent
from .legal_risk import (
    KeywordLegalRiskClassifier,
    LegalRiskAssessment,
    LegalRiskClassifierPort,
    LegalRiskLevel,
)
from .model_classifier import ModelClassificationResult, ModelClassifierPort
from .port import RouterPort
from .service import RouterService
from .strategies import RouterStrategy
from .strong_signal import (
    StrongSignalRule,
    build_strong_signal_rules,
    is_simple_factual,
    match_strong_signal,
)
from .tool_resolver import ToolResolutionMap, resolve_all_tool_refs, resolve_tool_refs

__all__ = [
    "KeywordLegalRiskClassifier",
    "LegalRiskAssessment",
    "LegalRiskClassifierPort",
    "LegalRiskLevel",
    "ModelClassificationResult",
    "ModelClassifierPort",
    "RouterPort",
    "RouterService",
    "RouterStrategy",
    "StrongSignalRule",
    "ToolResolutionMap",
    "build_strong_signal_rules",
    "classify_intent",
    "is_simple_factual",
    "match_strong_signal",
    "resolve_all_tool_refs",
    "resolve_tool_refs",
]
