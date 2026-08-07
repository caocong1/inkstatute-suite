"""Soft trigger-phrase matching for skill routing.

Ports ``_score_skill()`` and ``_best_soft_match()`` from
``lawfirm-profile/scripts/router.py`` (lines 230-293), adapted to operate
on :class:`NeutralSkillDescriptor` records instead of the lawfirm
dict-based index.

Key adaptations from the source:
- Trigger phrases come from ``metadata["host_assumptions"]`` (replaces the
  lawfirm ``triggers`` field).
- Description bigram bonus uses ``descriptor.description``.
- Only ``leaf``-type skills (from ``metadata["skill_type"]``) are scored —
  orchestration entries are skipped (replaces the lawfirm ``user_facing``
  check).
- ``best_soft_match()`` iterates a list of descriptors instead of a dict.

Public API:
    score_skill(message, descriptor) -> float
    best_soft_match(message, descriptors, exclude) -> tuple[str | None, float, str]
    SOFT_MATCH_THRESHOLD = 0.4
    SKIP_CLARIFICATION_THRESHOLD = 0.7
"""

from __future__ import annotations

import re

from platform_contract import NeutralSkillDescriptor

# Thresholds ported from lawfirm-profile/scripts/router.py route() (line 399).
SOFT_MATCH_THRESHOLD = 0.4
SKIP_CLARIFICATION_THRESHOLD = 0.7


def score_skill(message: str, descriptor: NeutralSkillDescriptor) -> float:
    """Score how well a skill descriptor matches the user message.

    Ports ``_score_skill()`` from ``lawfirm-profile/scripts/router.py``
    (lines 230-265), adapted for :class:`NeutralSkillDescriptor`:

    - Only ``leaf``-type skills are scored (check
      ``metadata.get("skill_type") == "leaf"``); orchestration entries
      return 0.0 (replaces the lawfirm ``user_facing`` check).
    - Trigger phrases come from ``metadata["host_assumptions"]`` (replaces
      the lawfirm ``triggers`` field).
    - Score = fraction of triggers found in message, weighted by phrase
      length (``min(len(trig), 6) / 6.0``).
    - Description bigram bonus: +0.1 per overlapping bigram, capped at 1.0.

    Returns 0.0 - 1.0.
    """
    # Only leaf-type skills are scored (replaces user_facing check)
    if descriptor.metadata.get("skill_type") != "leaf":
        return 0.0

    msg_lower = message.lower()
    triggers = descriptor.metadata.get("host_assumptions", [])
    if not triggers:
        return 0.0

    # Score = fraction of triggers found in msg, weighted by phrase length
    score = 0.0
    max_possible = 0.0
    for trig in triggers:
        weight = min(len(trig), 6) / 6.0  # longer phrases = stronger signal
        max_possible += weight
        if trig in message:
            score += weight

    if max_possible == 0:
        return 0.0
    raw = score / max_possible

    # Description bonus: if the msg contains bigrams from description
    desc = descriptor.description or ""
    bigrams = _extract_bigrams(desc)
    if bigrams:
        overlap = sum(1 for bg in bigrams if bg in message)
        if overlap:
            raw = min(1.0, raw + 0.1 * overlap)

    return raw


def _extract_bigrams(text: str | None) -> set[str]:
    """Extract 2-char sliding windows for fuzzy matching.

    Ports ``_extract_bigrams()`` from ``lawfirm-profile/scripts/router.py``
    (lines 268-271).  Returns a set of 2-character bigrams.

    Handles None/empty description gracefully (returns empty set).
    """
    if not text:
        return set()
    cleaned = re.sub(r"\s+", "", text)
    if len(cleaned) < 2:
        return set()
    return {cleaned[i: i + 2] for i in range(len(cleaned) - 1)}


def best_soft_match(
    message: str,
    descriptors: list[NeutralSkillDescriptor],
    exclude: set[str] | None = None,
) -> tuple[str | None, float, str]:
    """Find the best trigger-phrase match (excluding strong-signal targets).

    Ports ``_best_soft_match()`` from ``lawfirm-profile/scripts/router.py``
    (lines 274-293), adapted for :class:`NeutralSkillDescriptor`.

    Iterates all descriptors, skips excluded skill_ids, returns the
    highest-scoring match.

    Returns:
        A tuple of (best_skill_id, best_score, reason_str).
    """
    if exclude is None:
        exclude = set()

    best_name: str | None = None
    best_score = 0.0
    best_reason = ""
    for descriptor in descriptors:
        if descriptor.skill_id in exclude:
            continue
        s = score_skill(message, descriptor)
        if s > best_score:
            best_score = s
            best_name = descriptor.skill_id
            triggers = descriptor.metadata.get("host_assumptions", [])
            hit_triggers = [t for t in triggers if t in message]
            best_reason = (
                f"trigger-phrase match on {descriptor.skill_id} "
                f"(triggers hit: {hit_triggers})"
            )
    return best_name, best_score, best_reason
