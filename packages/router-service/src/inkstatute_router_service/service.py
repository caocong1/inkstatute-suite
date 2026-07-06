"""RouterService — concrete RouterPort implementation.

The service is stateless with three strategies (RULE, SKILL, HYBRID).  The
RULE strategy uses keyword/regex intent classification via ``classify_intent``.
The SKILL strategy uses the skill registry for stateless skill lookup.  The
HYBRID strategy implements a Rule → Skill → Model cascade with confidence
thresholds and a legal-risk classifier that forces high-risk queries to Hermes.

When ``skill_registry`` is ``None``, the RULE strategy falls back to
``SIMPLE_QA`` for matched intents and ``ZERO_MATCH`` for unmatched intents.
The ``None`` default preserves inline inference behavior when no router
is injected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from platform_contract import RouteDecision, RouteMode

from .classifier import classify_intent
from .legal_risk import LegalRiskAssessment, LegalRiskClassifierPort
from .model_classifier import ModelClassifierPort
from .strategies import RouterStrategy

if TYPE_CHECKING:
    from inkstatute_skill_registry import SkillRegistryPort

ROUTER_SERVICE_VERSION = "0.1.0"

# Confidence thresholds for the HYBRID strategy cascade.
_ROUTE_THRESHOLD = 0.8  # ≥ 0.8 → route directly (matched)
_CLARIFY_THRESHOLD = 0.5  # 0.5–0.8 → clarify (simple_qa); < 0.5 → fallback (zero_match)

# Confidence values for each cascade layer.
_CONFIDENCE_RULE_WITH_REGISTRY = 0.9
_CONFIDENCE_RULE_NO_REGISTRY = 0.6
_CONFIDENCE_SKILL_EXACT = 1.0
_CONFIDENCE_SKILL_SINGLE = 0.85
_CONFIDENCE_SKILL_AMBIGUOUS = 0.6
_CONFIDENCE_NO_MATCH = 0.0

# Hermes skill identifier — the safe-path backend.
_HERMES_SKILL_ID = "hermes"


class RouterService:
    """Stateless router with RULE, SKILL, and HYBRID strategies.

    The service implements the ``RouterPort`` Protocol via structural
    subtyping.  It produces ``RouteDecision`` records with frozen
    ``RouteMode`` values only; the strategy is recorded in
    ``metadata["router_strategy"]``.

    The HYBRID strategy additionally accepts an optional
    ``legal_risk_classifier`` and ``model_classifier``.  Both default to
    ``None``, preserving the ``dependencies = []`` invariant — the actual
    implementations are host-injected.
    """

    def __init__(
        self,
        skill_registry: "SkillRegistryPort | None" = None,
        strategy: RouterStrategy = RouterStrategy.RULE,
        legal_risk_classifier: LegalRiskClassifierPort | None = None,
        model_classifier: ModelClassifierPort | None = None,
    ) -> None:
        self._registry = skill_registry
        self._strategy = strategy
        self._legal_risk_classifier = legal_risk_classifier
        self._model_classifier = model_classifier

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        """Produce a ``RouteDecision`` from *context* using the active strategy."""
        if self._strategy == RouterStrategy.HYBRID:
            return self._decide_hybrid(context)
        if self._strategy == RouterStrategy.SKILL:
            return self._decide_skill(context)
        return self._decide_rule(context)

    def _decide_rule(self, context: Mapping[str, Any]) -> RouteDecision:
        """RULE strategy: keyword/regex intent classification."""
        message = context.get("message")
        intent = classify_intent(message if isinstance(message, str) else None)

        if intent is not None and self._registry is not None:
            results = self._registry.search(category=intent)
            if results:
                descriptor = results[0]
                return self._build_decision(
                    context,
                    mode=RouteMode.MATCHED,
                    primary_skill=descriptor.skill_id,
                    confidence=0.7,
                    required_tools=list(descriptor.required_tool_refs),
                    matched_rule=f"rule:{intent}",
                    metadata_extra={
                        "router_strategy": "rule",
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "classified_intent": intent,
                    },
                )

        if intent is not None:
            return self._build_decision(
                context,
                mode=RouteMode.SIMPLE_QA,
                primary_skill=None,
                confidence=0.5,
                metadata_extra={
                    "router_strategy": "rule",
                    "router_service_version": ROUTER_SERVICE_VERSION,
                    "classified_intent": intent,
                },
            )

        return self._build_decision(
            context,
            mode=RouteMode.ZERO_MATCH,
            primary_skill=None,
            confidence=0.0,
            metadata_extra={
                "router_strategy": "rule",
                "router_service_version": ROUTER_SERVICE_VERSION,
                "classified_intent": intent,
            },
        )

    def _decide_skill(self, context: Mapping[str, Any]) -> RouteDecision:
        """SKILL strategy — stateless Skill Registry lookup.

        Three paths:
        1. Direct ``skill_id`` lookup via ``get_skill()``.
        2. Intent-based ``search(category=<intent>)`` with name-substring
           fallback when no ``skill_id`` is present.
        3. ``zero_match`` when the registry is not configured.
        """
        if self._registry is None:
            return self._build_decision(
                context,
                mode=RouteMode.ZERO_MATCH,
                primary_skill=None,
                confidence=0.0,
                reason="Skill Registry not configured; router cannot perform skill lookup.",
                metadata_extra={
                    "router_strategy": "skill",
                    "router_service_version": ROUTER_SERVICE_VERSION,
                    "registry_not_configured": True,
                },
            )

        skill_id = context.get("skill_id")
        if skill_id is not None:
            descriptor = self._registry.get_skill(skill_id)
            if descriptor is not None:
                return self._build_decision(
                    context,
                    mode=RouteMode.MATCHED,
                    primary_skill=descriptor.skill_id,
                    confidence=1.0,
                    required_tools=list(descriptor.required_tool_refs),
                    matched_rule=f"skill:{descriptor.skill_id}",
                    reason="Skill matched by exact skill_id lookup.",
                    metadata_extra={
                        "router_strategy": "skill",
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "skill_lookup_method": "get_skill",
                    },
                )
            return self._build_decision(
                context,
                mode=RouteMode.ZERO_MATCH,
                primary_skill=None,
                confidence=0.0,
                metadata_extra={
                    "router_strategy": "skill",
                    "router_service_version": ROUTER_SERVICE_VERSION,
                    "skill_lookup_method": "get_skill",
                    "skill_not_found": True,
                },
            )

        message = context.get("message")
        if message is not None and isinstance(message, str):
            results = self._search_by_message(message)
            if len(results) == 1:
                descriptor = results[0]
                return self._build_decision(
                    context,
                    mode=RouteMode.MATCHED,
                    primary_skill=descriptor.skill_id,
                    confidence=0.7,
                    required_tools=list(descriptor.required_tool_refs),
                    matched_rule=f"skill:{descriptor.skill_id}",
                    metadata_extra={
                        "router_strategy": "skill",
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "skill_lookup_method": "search",
                    },
                )
            if len(results) > 1:
                return self._build_decision(
                    context,
                    mode=RouteMode.SIMPLE_QA,
                    primary_skill=None,
                    confidence=0.5,
                    supporting_skills=[r.skill_id for r in results],
                    metadata_extra={
                        "router_strategy": "skill",
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "skill_lookup_method": "search",
                        "ambiguous_matches": len(results),
                    },
                )

        return self._build_decision(
            context,
            mode=RouteMode.ZERO_MATCH,
            primary_skill=None,
            confidence=0.0,
            metadata_extra={
                "router_strategy": "skill",
                "router_service_version": ROUTER_SERVICE_VERSION,
                "skill_lookup_method": "search",
            },
        )

    def _decide_hybrid(self, context: Mapping[str, Any]) -> RouteDecision:
        """HYBRID strategy — Rule → Skill → Model cascade with confidence thresholds.

        The cascade runs three layers in order:
        1. **Rule layer**: ``classify_intent`` + registry lookup.
        2. **Skill layer**: ``get_skill`` or ``search`` by message.
        3. **Model layer**: optional ``ModelClassifierPort.classify``.

        Before the cascade, a legal-risk pre-check runs.  If the query is
        high-risk, routing is forced to Hermes regardless of confidence.

        Confidence thresholds (applied after the cascade, only if not
        high-risk):
        - ≥ 0.8 → ``matched`` (route directly)
        - 0.5–0.8 → ``simple_qa`` (clarify)
        - < 0.5 → ``zero_match`` (fallback to Hermes)
        """
        message = context.get("message")
        message_str = message if isinstance(message, str) else None

        # --- Legal-risk pre-check ---
        risk_assessment = self._classify_legal_risk(message_str)
        legal_risk_metadata: dict[str, Any] = {}
        if risk_assessment is not None:
            legal_risk_metadata["legal_risk_assessment"] = {
                "risk_level": risk_assessment.risk_level,
                "is_high_risk": risk_assessment.is_high_risk,
                "evidence": list(risk_assessment.evidence),
            }

        # --- Run the cascade to compute confidence and matched skill ---
        confidence, primary_skill, required_tools, matched_rule, supporting_skills, \
            cascade_stage, extra_metadata = self._run_cascade(context, message_str)

        # --- Legal-risk override: force high-risk to Hermes ---
        if risk_assessment is not None and risk_assessment.is_high_risk:
            return self._build_decision(
                context,
                mode=RouteMode.MATCHED,
                primary_skill=_HERMES_SKILL_ID,
                confidence=confidence,
                required_tools=required_tools,
                matched_rule=matched_rule,
                supporting_skills=supporting_skills,
                metadata_extra={
                    "router_strategy": "hybrid",
                    "router_service_version": ROUTER_SERVICE_VERSION,
                    "forced_to_hermes": True,
                    "cascade_stage": "legal_risk_override",
                    **legal_risk_metadata,
                    **extra_metadata,
                },
            )

        # --- Apply confidence thresholds ---
        if confidence >= _ROUTE_THRESHOLD:
            mode = RouteMode.MATCHED
            extra_metadata["clarification_needed"] = False
        elif confidence >= _CLARIFY_THRESHOLD:
            mode = RouteMode.SIMPLE_QA
            primary_skill = None
            extra_metadata["clarification_needed"] = True
        else:
            mode = RouteMode.ZERO_MATCH
            primary_skill = None
            extra_metadata["fallback_to_hermes"] = True
            extra_metadata["clarification_needed"] = False

        return self._build_decision(
            context,
            mode=mode,
            primary_skill=primary_skill,
            confidence=confidence,
            required_tools=required_tools,
            matched_rule=matched_rule,
            supporting_skills=supporting_skills,
            metadata_extra={
                "router_strategy": "hybrid",
                "router_service_version": ROUTER_SERVICE_VERSION,
                "cascade_stage": cascade_stage,
                **legal_risk_metadata,
                **extra_metadata,
            },
        )

    def _run_cascade(
        self,
        context: Mapping[str, Any],
        message: str | None,
    ) -> tuple[
        float,  # confidence
        str | None,  # primary_skill
        list[str],  # required_tools
        str | None,  # matched_rule
        list[str] | None,  # supporting_skills
        str,  # cascade_stage
        dict[str, Any],  # extra_metadata
    ]:
        """Run the Rule → Skill → Model cascade and return the best result.

        Returns a tuple of (confidence, primary_skill, required_tools,
        matched_rule, supporting_skills, cascade_stage, extra_metadata).
        """
        # --- Rule layer ---
        intent = classify_intent(message)
        if intent is not None and self._registry is not None:
            results = self._registry.search(category=intent)
            if results:
                descriptor = results[0]
                return (
                    _CONFIDENCE_RULE_WITH_REGISTRY,
                    descriptor.skill_id,
                    list(descriptor.required_tool_refs),
                    f"rule:{intent}",
                    None,
                    "rule",
                    {"classified_intent": intent},
                )
        if intent is not None:
            return (
                _CONFIDENCE_RULE_NO_REGISTRY,
                None,
                [],
                None,
                None,
                "rule",
                {"classified_intent": intent},
            )

        # --- Skill layer ---
        if self._registry is not None:
            skill_id = context.get("skill_id")
            if skill_id is not None:
                descriptor = self._registry.get_skill(skill_id)
                if descriptor is not None:
                    return (
                        _CONFIDENCE_SKILL_EXACT,
                        descriptor.skill_id,
                        list(descriptor.required_tool_refs),
                        f"skill:{descriptor.skill_id}",
                        None,
                        "skill",
                        {"skill_lookup_method": "get_skill"},
                    )

            if message is not None:
                results = self._search_by_message(message)
                if len(results) == 1:
                    descriptor = results[0]
                    return (
                        _CONFIDENCE_SKILL_SINGLE,
                        descriptor.skill_id,
                        list(descriptor.required_tool_refs),
                        f"skill:{descriptor.skill_id}",
                        None,
                        "skill",
                        {"skill_lookup_method": "search"},
                    )
                if len(results) > 1:
                    return (
                        _CONFIDENCE_SKILL_AMBIGUOUS,
                        None,
                        [],
                        None,
                        [r.skill_id for r in results],
                        "skill",
                        {
                            "skill_lookup_method": "search",
                            "ambiguous_matches": len(results),
                        },
                    )

        # --- Model layer ---
        if self._model_classifier is not None:
            result = self._model_classifier.classify(context)
            return (
                result.confidence,
                result.predicted_skill,
                [],
                None,
                None,
                "model",
                {"model_classification": True, **result.metadata},
            )

        # --- No match in any layer ---
        return (
            _CONFIDENCE_NO_MATCH,
            None,
            [],
            None,
            None,
            "no_match",
            {},
        )

    def _classify_legal_risk(self, message: str | None) -> LegalRiskAssessment | None:
        """Classify *message* for legal risk, or return ``None`` if no classifier."""
        if self._legal_risk_classifier is None:
            return None
        return self._legal_risk_classifier.classify(message)

    def _search_by_message(self, message: str) -> list:
        """Search the registry by intent category and name substring.

        Tries ``search(category=<intent>)`` first (if an intent is
        classified), then falls back to ``search(name_substring=<first
        word>)``.  Results are de-duplicated by ``skill_id``.
        """
        results: list = []
        seen: set[str] = set()
        intent = classify_intent(message)
        if intent is not None:
            for descriptor in self._registry.search(category=intent):
                if descriptor.skill_id not in seen:
                    seen.add(descriptor.skill_id)
                    results.append(descriptor)
        first_word = message.split()[0] if message.split() else message
        if first_word:
            for descriptor in self._registry.search(name_substring=first_word):
                if descriptor.skill_id not in seen:
                    seen.add(descriptor.skill_id)
                    results.append(descriptor)
        return results

    def _build_decision(
        self,
        context: Mapping[str, Any],
        mode: RouteMode | str,
        primary_skill: str | None,
        confidence: float,
        required_tools: list[str] | None = None,
        matched_rule: str | None = None,
        reason: str | None = None,
        supporting_skills: list[str] | None = None,
        metadata_extra: dict[str, Any] | None = None,
    ) -> RouteDecision:
        """Construct a frozen ``RouteDecision`` from context defaults and provided values."""
        return RouteDecision(
            route_decision_id=context.get("route_decision_id", ""),
            turn_id=context.get("turn_id", ""),
            primary_skill=primary_skill,
            confidence=confidence,
            mode=mode,
            created_at=context.get("created_at", ""),
            supporting_skills=supporting_skills if supporting_skills is not None else list(context.get("supporting_skills", [])),
            gates_before=list(context.get("gates_before", [])),
            gates_after=list(context.get("gates_after", [])),
            required_tools=required_tools if required_tools is not None else [],
            matched_rule=matched_rule,
            reason=reason,
            route_mismatch=context.get("route_mismatch"),
            industry_context=dict(context.get("industry_context", {})),
            metadata=metadata_extra if metadata_extra is not None else {},
        )
