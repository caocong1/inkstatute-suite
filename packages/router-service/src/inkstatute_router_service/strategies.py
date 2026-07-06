"""RouterStrategy enum — router-internal routing strategies.

``RouterStrategy`` defines the internal strategy the router uses to classify
a message and produce a ``RouteDecision``.  The three strategies are:

- ``RULE`` — keyword/regex intent classification (``classify_intent``).
- ``SKILL`` — skill registry lookup via ``SkillRegistryPort``.
- ``HYBRID`` — Rule → Skill → Model cascade with confidence thresholds
  and a legal-risk classifier that forces high-risk queries to Hermes.

These are **router-internal strategies** that map onto the frozen
``RouteMode`` outcome values (``matched``, ``simple_qa``, ``skipped``,
``zero_match``).  They are NOT new ``RouteMode`` enum values and must never
be added to the frozen ``RouteMode`` enum in ``platform-contract``
(SAFETY-06 contract freeze).
"""

from __future__ import annotations

from enum import StrEnum


class RouterStrategy(StrEnum):
    """Router-internal strategy enum.

    Values map onto frozen ``RouteMode`` outcomes, NOT onto ``RouteMode``
    itself.  Adding ``RULE``/``SKILL``/``HYBRID`` to ``RouteMode`` would
    violate SAFETY-06.
    """

    RULE = "rule"
    SKILL = "skill"
    HYBRID = "hybrid"
