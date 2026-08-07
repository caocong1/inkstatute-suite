"""inkstatute-router-service: standalone router library.

Re-exports the RouterPort Protocol, RouterService class, RouterStrategy enum,
the classify_intent classifier function, the tool-resolution join helpers,
the legal-risk classifier, and the model classifier port.
"""

from .classifier import classify_intent
from .decision_log import append_decision_log, record_routing_error
from .legal_risk import (
    KeywordLegalRiskClassifier,
    LegalRiskAssessment,
    LegalRiskClassifierPort,
    LegalRiskLevel,
)
from .model_classifier import ModelClassificationResult, ModelClassifierPort
from .mode_classifier import (
    AgentMode,
    ClassifyContext,
    ClassifyResult,
    ModeClassifierPort,
)
from .port import RouterPort
from .service import RouterService
from .soft_matcher import (
    SOFT_MATCH_THRESHOLD,
    SKIP_CLARIFICATION_THRESHOLD,
    best_soft_match,
    score_skill,
)
from .strategies import RouterStrategy
from .strong_signal import (
    StrongSignalRule,
    build_strong_signal_rules,
    is_simple_factual,
    match_strong_signal,
)
from .tool_resolver import ToolResolutionMap, resolve_all_tool_refs, resolve_tool_refs

__all__ = [
    "AgentMode",
    "ClassifyContext",
    "ClassifyResult",
    "KeywordLegalRiskClassifier",
    "append_decision_log",
    "LegalRiskAssessment",
    "LegalRiskClassifierPort",
    "LegalRiskLevel",
    "ModeClassifierPort",
    "ModelClassificationResult",
    "ModelClassifierPort",
    "RouterPort",
    "RouterService",
    "RouterStrategy",
    "SOFT_MATCH_THRESHOLD",
    "SKIP_CLARIFICATION_THRESHOLD",
    "StrongSignalRule",
    "ToolResolutionMap",
    "best_soft_match",
    "build_strong_signal_rules",
    "classify_intent",
    "is_simple_factual",
    "match_strong_signal",
    "record_routing_error",
    "resolve_all_tool_refs",
    "resolve_tool_refs",
    "score_skill",
]
