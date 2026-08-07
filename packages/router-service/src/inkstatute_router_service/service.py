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

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from platform_contract import RouteDecision, RouteMode

from .classifier import classify_intent
from .decision_log import append_decision_log
from .legal_risk import LegalRiskAssessment, LegalRiskClassifierPort
from .mode_classifier import ClassifyContext, ModeClassifierPort
from .model_classifier import ModelClassifierPort
from .soft_matcher import (
    SKIP_CLARIFICATION_THRESHOLD,
    SOFT_MATCH_THRESHOLD,
    best_soft_match,
)
from .strategies import RouterStrategy
from .strong_signal import is_simple_factual, match_strong_signal

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

    An optional ``mode_classifier`` (``ModeClassifierPort``) can be injected
    to perform Chat/Draft/Evidence three-mode detection.  When provided,
    the classification result is stored in ``RouteDecision.metadata``
    (keys: ``agent_mode``, ``mode_action``, ``mode_label``, ``mode_source``,
    ``mode_fallback_reason``).  When ``None`` (the default), no mode-related
    metadata keys are present (backward compatible).

    An optional ``log_dir`` (``Path | None``) can be injected to enable
    JSONL decision logging.  When set, ``decide()`` calls
    ``append_decision_log()`` after computing the decision, writing a
    JSON line to ``{log_dir}/{session_id}.jsonl``.  When ``None`` (the
    default), no logging occurs (backward compatible — existing tests
    unaffected).  Logging is a no-op when ``session_id`` is empty.
    """

    def __init__(
        self,
        skill_registry: "SkillRegistryPort | None" = None,
        strategy: RouterStrategy = RouterStrategy.RULE,
        legal_risk_classifier: LegalRiskClassifierPort | None = None,
        model_classifier: ModelClassifierPort | None = None,
        mode_classifier: ModeClassifierPort | None = None,
        log_dir: Path | None = None,
    ) -> None:
        self._registry = skill_registry
        self._strategy = strategy
        self._legal_risk_classifier = legal_risk_classifier
        self._model_classifier = model_classifier
        self._mode_classifier = mode_classifier
        self._log_dir = log_dir

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        """Produce a ``RouteDecision`` from *context* using the active strategy.

        The routing flow includes a pre-router layer that runs BEFORE the
        strategy cascade for ALL strategies:

        1. **Empty/trivially short** (len < 4) → ``None``, confidence 0.9
        2. **Strong-signal rules** (first match wins) → rule's primary_skill,
           confidence 0.95, gates from rule
        3. **Factual short-circuit** → ``None``, confidence 0.85,
           ``matched_rule="factual_short_circuit"``
        4. **Soft trigger-phrase matching** (threshold ≥ 0.4) → best match,
           ``gate_before=["ask-user-enforcement"]`` (unless score ≥ 0.7 →
           skip), ``gate_after=["legal-de-ai-polish"]``
        5. **Fall through** to the existing strategy cascade
           (RULE/SKILL/HYBRID)

        After the routing decision is computed, if a ``mode_classifier`` is
        injected, Chat/Draft/Evidence mode detection runs and the result is
        merged into ``RouteDecision.metadata``.  Mode detection is orthogonal
        to skill routing — it classifies the user's interaction mode, not
        which skill to route to.
        """
        decision = self._decide_core(context)

        # Mode detection runs AFTER the routing decision (orthogonal to skill routing).
        if self._mode_classifier is not None:
            decision = self._merge_mode_metadata(decision, context)

        # Decision logging — JSONL append per session.
        # No-op when log_dir is None or session_id is empty.
        if self._log_dir is not None:
            message = context.get("message")
            user_msg = message if isinstance(message, str) else ""
            session_id = context.get("session_id", "")
            append_decision_log(decision, user_msg, self._log_dir, session_id)

        return decision

    def _decide_core(self, context: Mapping[str, Any]) -> RouteDecision:
        """Core routing logic — pre-router layer + strategy cascade."""
        message = context.get("message")
        message_str = message if isinstance(message, str) else None

        # 1. Empty / trivially short → treat as factual
        if message_str is not None:
            msg = message_str.strip()
            if not msg or len(msg) < 4:
                return self._build_decision(
                    context,
                    mode=RouteMode.SIMPLE_QA,
                    primary_skill=None,
                    confidence=0.9,
                    reason="empty or trivially short message",
                    matched_rule="",
                    metadata_extra={
                        "router_strategy": str(self._strategy),
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "pre_router_layer": "trivially_short",
                    },
                )

        # 2. Strong-signal rules (first match wins)
        if message_str is not None:
            rule = match_strong_signal(message_str.strip())
            if rule is not None:
                gates_before = [rule.gate_before] if rule.gate_before else []
                gates_after = [rule.gate_after] if rule.gate_after else []
                return self._build_decision(
                    context,
                    mode=RouteMode.MATCHED,
                    primary_skill=rule.primary,
                    confidence=rule.confidence,
                    supporting_skills=list(rule.supporting),
                    gates_before=gates_before,
                    gates_after=gates_after,
                    matched_rule=rule.name,
                    reason=rule.reason,
                    metadata_extra={
                        "router_strategy": str(self._strategy),
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "pre_router_layer": "strong_signal",
                        "skip_clarification": rule.skip_clarification,
                    },
                )

        # 3. Simple factual Q? (statute lookup, term definition)
        if message_str is not None and is_simple_factual(message_str.strip()):
            return self._build_decision(
                context,
                mode=RouteMode.SIMPLE_QA,
                primary_skill=None,
                confidence=0.85,
                matched_rule="factual_short_circuit",
                reason="simple_factual_question (statute/term lookup, no skill needed)",
                metadata_extra={
                    "router_strategy": str(self._strategy),
                    "router_service_version": ROUTER_SERVICE_VERSION,
                    "pre_router_layer": "factual_short_circuit",
                },
            )

        # 4. Soft trigger-phrase matching (threshold ≥ 0.4)
        if message_str is not None and self._registry is not None:
            descriptors = self._registry.list_skills()
            best_id, best_score, best_reason = best_soft_match(
                message_str.strip(), descriptors, exclude=set(),
            )
            if best_id is not None and best_score >= SOFT_MATCH_THRESHOLD:
                skip = best_score >= SKIP_CLARIFICATION_THRESHOLD
                gates_before = [] if skip else ["ask-user-enforcement"]
                gates_after = ["legal-de-ai-polish"]
                return self._build_decision(
                    context,
                    mode=RouteMode.MATCHED,
                    primary_skill=best_id,
                    confidence=round(best_score, 3),
                    gates_before=gates_before,
                    gates_after=gates_after,
                    matched_rule="soft_trigger_match",
                    reason=best_reason,
                    metadata_extra={
                        "router_strategy": str(self._strategy),
                        "router_service_version": ROUTER_SERVICE_VERSION,
                        "pre_router_layer": "soft_trigger_match",
                        "skip_clarification": skip,
                        "soft_match_score": round(best_score, 3),
                    },
                )

        # 5. Fall through to the existing strategy cascade
        if self._strategy == RouterStrategy.HYBRID:
            return self._decide_hybrid(context)
        if self._strategy == RouterStrategy.SKILL:
            return self._decide_skill(context)
        return self._decide_rule(context)

    def _merge_mode_metadata(
        self,
        decision: RouteDecision,
        context: Mapping[str, Any],
    ) -> RouteDecision:
        """Run mode classification and merge results into decision metadata.

        Builds a ``ClassifyContext`` from the routing context, calls
        ``mode_classifier.classify()``, and returns a new ``RouteDecision``
        with mode-related keys added to ``metadata``.  No new top-level
        fields are added (contract freeze preserved — SAFETY-06).
        """
        message = context.get("message")
        message_str = message if isinstance(message, str) else ""

        classify_ctx = ClassifyContext(
            user_message=message_str,
            has_directory_ref=bool(context.get("has_directory_ref", False)),
            has_file_ref=bool(context.get("has_file_ref", False)),
            directory_aliases=list(context.get("directory_aliases", [])),
            current_mode=context.get("current_mode"),
            current_task_label=context.get("current_task_label"),
            has_active_document=bool(context.get("has_active_document", False)),
        )

        mode_result = self._mode_classifier.classify(classify_ctx)

        # Merge mode metadata into existing metadata (no new top-level fields).
        merged_metadata = dict(decision.metadata)
        merged_metadata["agent_mode"] = str(mode_result.mode)
        merged_metadata["mode_action"] = mode_result.action
        merged_metadata["mode_label"] = mode_result.label
        merged_metadata["mode_source"] = mode_result.source
        merged_metadata["mode_fallback_reason"] = mode_result.fallback_reason

        return RouteDecision(
            route_decision_id=decision.route_decision_id,
            turn_id=decision.turn_id,
            primary_skill=decision.primary_skill,
            confidence=decision.confidence,
            mode=decision.mode,
            created_at=decision.created_at,
            supporting_skills=list(decision.supporting_skills),
            gates_before=list(decision.gates_before),
            gates_after=list(decision.gates_after),
            required_tools=list(decision.required_tools),
            matched_rule=decision.matched_rule,
            reason=decision.reason,
            route_mismatch=decision.route_mismatch,
            industry_context=dict(decision.industry_context),
            metadata=merged_metadata,
        )

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
        gates_before: list[str] | None = None,
        gates_after: list[str] | None = None,
        metadata_extra: dict[str, Any] | None = None,
    ) -> RouteDecision:
        """Construct a frozen ``RouteDecision`` from context defaults and provided values.

        When *gates_before* or *gates_after* are provided, they override the
        context defaults.  When not provided, the method falls back to
        ``context.get("gates_before", [])`` / ``context.get("gates_after", [])``
        (preserving existing behavior).
        """
        return RouteDecision(
            route_decision_id=context.get("route_decision_id", ""),
            turn_id=context.get("turn_id", ""),
            primary_skill=primary_skill,
            confidence=confidence,
            mode=mode,
            created_at=context.get("created_at", ""),
            supporting_skills=supporting_skills if supporting_skills is not None else list(context.get("supporting_skills", [])),
            gates_before=gates_before if gates_before is not None else list(context.get("gates_before", [])),
            gates_after=gates_after if gates_after is not None else list(context.get("gates_after", [])),
            required_tools=required_tools if required_tools is not None else [],
            matched_rule=matched_rule,
            reason=reason,
            route_mismatch=context.get("route_mismatch"),
            industry_context=dict(context.get("industry_context", {})),
            metadata=metadata_extra if metadata_extra is not None else {},
        )
