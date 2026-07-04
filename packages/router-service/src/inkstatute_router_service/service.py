"""RouterService — concrete RouterPort implementation.

The service is stateless with two strategies (RULE, SKILL).  The RULE
strategy uses keyword/regex intent classification via ``classify_intent``.
The SKILL strategy uses the skill registry for stateless skill lookup.

When ``skill_registry`` is ``None``, the RULE strategy falls back to
``SIMPLE_QA`` for matched intents and ``ZERO_MATCH`` for unmatched intents.
The ``None`` default preserves inline inference behavior when no router
is injected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from platform_contract import RouteDecision, RouteMode

from .classifier import classify_intent
from .strategies import RouterStrategy

if TYPE_CHECKING:
    from inkstatute_skill_registry import SkillRegistryPort

ROUTER_SERVICE_VERSION = "0.1.0"


class RouterService:
    """Stateless router with RULE and SKILL strategies.

    The service implements the ``RouterPort`` Protocol via structural
    subtyping.  It produces ``RouteDecision`` records with frozen
    ``RouteMode`` values only; the strategy is recorded in
    ``metadata["router_strategy"]``.
    """

    def __init__(
        self,
        skill_registry: "SkillRegistryPort | None" = None,
        strategy: RouterStrategy = RouterStrategy.RULE,
    ) -> None:
        self._registry = skill_registry
        self._strategy = strategy

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        """Produce a ``RouteDecision`` from *context* using the active strategy."""
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
