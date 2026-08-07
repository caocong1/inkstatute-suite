"""Three-way cross-validation orchestration/leaf classifier.

Classifies each ``ScannedSkill`` as ``"orchestration"`` or ``"leaf"`` using
three independent signals and extracts parent-child relationships:

1. **Directory structure** — does the skill's directory contain sub-directories
   with their own ``SKILL.md`` files?
2. **plugin.json** — is the skill's path a parent of other paths in the
   ``skills[]`` array (orchestration) or nested under another path (leaf)?
3. **Body text heuristic** — does the body contain ``"编排入口"`` /
   ``"子技能编排顺序"`` (orchestration) or ``"迁移说明"`` (leaf)?

If ANY orchestration signal triggers, the skill is classified as
``"orchestration"``.  Orchestration takes precedence over leaf when a skill
is both nested (has a parent) and has children.

CRITICAL: The classifier is read-only — it inspects ``ScannedSkill`` records
and never writes to the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scanner import ScannedSkill


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Result of classifying a single ``ScannedSkill``.

    Attributes:
        skill_type: ``"orchestration"`` or ``"leaf"``.
        parent_skill: skill_id of the parent for leaf skills nested under an
            orchestration entry; ``None`` for orchestration entries and flat
            skills.
        child_skills: list of child skill_ids for orchestration entries;
            empty list for leaf skills.
        classification_signals: which signals triggered the classification
            (e.g. ``["directory_has_children", "body_text_orchestration"]``).
        warnings: classification warnings.
    """

    skill_type: str
    parent_skill: str | None
    child_skills: list[str] = field(default_factory=list)
    classification_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _skill_dir_path(relative_path: str) -> str:
    """Return the directory portion of a SKILL.md relative path.

    ``"commercial-legal/skills/contract-review/SKILL.md"`` →
    ``"commercial-legal/skills/contract-review/"`` (trailing slash included).
    """
    normalized = relative_path.replace("\\", "/")
    if normalized.endswith("/SKILL.md"):
        return normalized[: -len("SKILL.md")]
    # Fallback: strip the filename component.
    idx = normalized.rfind("/")
    if idx == -1:
        return normalized + "/"
    return normalized[: idx + 1]


def _check_directory_has_children(
    skill: ScannedSkill, all_skills: list[ScannedSkill]
) -> bool:
    """Return True if any other skill is nested directly under *skill*'s directory.

    A child skill's ``relative_path`` starts with the parent's directory path
    (with trailing slash) and has exactly one more path component before
    ``SKILL.md``.
    """
    parent_dir = _skill_dir_path(skill.relative_path)
    for other in all_skills:
        if other.relative_path == skill.relative_path:
            continue
        other_normalized = other.relative_path.replace("\\", "/")
        if not other_normalized.startswith(parent_dir):
            continue
        # Ensure it is a *direct* child (one extra path component).
        remainder = other_normalized[len(parent_dir):]
        # remainder should be ``"<child>/SKILL.md"``
        if remainder.endswith("/SKILL.md"):
            child_name = remainder[: -len("/SKILL.md")]
            if "/" not in child_name:
                return True
    return False


def _check_body_text_orchestration(body: str) -> bool:
    """Return True if *body* contains orchestration-entry markers.

    Detected markers:
    - ``"编排入口"`` (orchestration entry)
    - ``"子技能编排顺序"`` (sub-skill orchestration order)
    - ``"子技能"`` inside a markdown table context (``|`` delimited rows)
    """
    if "编排入口" in body:
        return True
    if "子技能编排顺序" in body:
        return True
    # ``"子技能"`` inside a markdown table — look for table rows mentioning it.
    if "子技能" in body:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "子技能" in stripped:
                return True
    return False


def _check_body_text_leaf(body: str) -> bool:
    """Return True if *body* contains a leaf-skill migration note (``迁移说明``)."""
    return "迁移说明" in body


def _extract_parent_from_path(
    relative_path: str, all_skills: list[ScannedSkill]
) -> str | None:
    """Derive the parent skill_id from a nested relative path.

    For ``"commercial-legal/skills/contract-review/risk-identification/SKILL.md"``
    the parent directory is ``"commercial-legal/skills/contract-review/"`` and
    the parent skill's ``relative_path`` is
    ``"commercial-legal/skills/contract-review/SKILL.md"``.
    """
    normalized = relative_path.replace("\\", "/")
    if not normalized.endswith("/SKILL.md"):
        return None
    # Strip the leaf ``<name>/SKILL.md`` to get the parent directory.
    without_skill = normalized[: -len("/SKILL.md")]
    idx = without_skill.rfind("/")
    if idx == -1:
        return None
    parent_path = without_skill[:idx] + "/SKILL.md"
    for other in all_skills:
        if other.relative_path.replace("\\", "/") == parent_path:
            return other.skill_id
    return None


def _extract_children_from_path(
    skill: ScannedSkill, all_skills: list[ScannedSkill]
) -> list[str]:
    """Return skill_ids of direct child skills nested under *skill*'s directory."""
    parent_dir = _skill_dir_path(skill.relative_path)
    children: list[str] = []
    for other in all_skills:
        if other.relative_path == skill.relative_path:
            continue
        other_normalized = other.relative_path.replace("\\", "/")
        if not other_normalized.startswith(parent_dir):
            continue
        remainder = other_normalized[len(parent_dir):]
        if remainder.endswith("/SKILL.md"):
            child_name = remainder[: -len("/SKILL.md")]
            if "/" not in child_name:
                children.append(other.skill_id)
    return sorted(children)


def _check_plugin_json_parent(
    skill: ScannedSkill,
    plugin_json_skills: dict[str, list[dict[str, Any]]] | None,
) -> bool:
    """Return True if the skill's path is a parent of other plugin.json paths.

    *plugin_json_skills* maps plugin name → ``skills[]`` list (each entry has a
    ``path`` field relative to the plugin root).
    """
    if plugin_json_skills is None:
        return False
    if skill.plugin is None or skill.plugin == "shared":
        return False
    entries = plugin_json_skills.get(skill.plugin)
    if not entries:
        return False
    # Derive the skill's path relative to its plugin root.
    # ``relative_path`` looks like ``"<plugin>/skills/<name>/SKILL.md"``;
    # plugin.json ``path`` is ``"skills/<name>/SKILL.md"``.
    normalized = skill.relative_path.replace("\\", "/")
    prefix = f"{skill.plugin}/"
    if not normalized.startswith(prefix):
        return False
    skill_path_in_plugin = normalized[len(prefix):]
    skill_dir = _skill_dir_path(skill_path_in_plugin)
    for entry in entries:
        entry_path = entry.get("path", "")
        if entry_path == skill_path_in_plugin:
            continue
        if entry_path.replace("\\", "/").startswith(skill_dir):
            return True
    return False


def _check_plugin_json_leaf_parent(
    skill: ScannedSkill,
    plugin_json_skills: dict[str, list[dict[str, Any]]] | None,
    all_skills: list[ScannedSkill],
) -> str | None:
    """Return the parent skill_id if plugin.json indicates *skill* is nested.

    Looks for another skill whose plugin.json path is a prefix of this skill's
    path.  Falls back to ``_extract_parent_from_path`` for resolution.
    """
    if plugin_json_skills is None:
        return None
    if skill.plugin is None or skill.plugin == "shared":
        return None
    entries = plugin_json_skills.get(skill.plugin)
    if not entries:
        return None
    normalized = skill.relative_path.replace("\\", "/")
    prefix = f"{skill.plugin}/"
    if not normalized.startswith(prefix):
        return None
    skill_path_in_plugin = normalized[len(prefix):]
    for entry in entries:
        entry_path = entry.get("path", "").replace("\\", "/")
        if entry_path == skill_path_in_plugin:
            continue
        entry_dir = _skill_dir_path(entry_path)
        if skill_path_in_plugin.startswith(entry_dir):
            # Found a candidate parent; resolve to a skill_id via all_skills.
            parent_relative = f"{skill.plugin}/{entry_path}"
            for other in all_skills:
                if other.relative_path.replace("\\", "/") == parent_relative:
                    return other.skill_id
    return None


def classify_skill(
    skill: ScannedSkill,
    all_skills: list[ScannedSkill],
    plugin_json_skills: dict[str, list[dict[str, Any]]] | None = None,
) -> ClassificationResult:
    """Classify a single ``ScannedSkill`` as orchestration or leaf.

    Uses three-way cross-validation (directory + plugin.json + body text).
    Orchestration takes precedence: if ANY orchestration signal triggers the
    skill is ``"orchestration"`` even when it is also nested under a parent.
    """
    signals: list[str] = []
    warnings: list[str] = []

    # --- Signal 1: directory structure ---
    has_children = _check_directory_has_children(skill, all_skills)
    if has_children:
        signals.append("directory_has_children")

    # --- Signal 2: plugin.json ---
    plugin_parent = _check_plugin_json_parent(skill, plugin_json_skills)
    if plugin_parent:
        signals.append("plugin_json_parent")

    # --- Signal 3: body text ---
    body_orchestration = _check_body_text_orchestration(skill.body)
    if body_orchestration:
        signals.append("body_text_orchestration")
    body_leaf = _check_body_text_leaf(skill.body)

    # --- Classification decision ---
    is_orchestration = bool(signals)
    # A nested skill (depth >= 1) is normally a leaf, but orchestration signals
    # take precedence (a skill can be both nested and have children).
    if not is_orchestration and skill.depth >= 1:
        is_orchestration = False  # leaf with parent

    if is_orchestration:
        child_skills = _extract_children_from_path(skill, all_skills)
        # If directory has no children but plugin.json/body text say
        # orchestration, child_skills may be empty — that is acceptable.
        parent_skill: str | None = None
        # An orchestration entry that is itself nested (rare) keeps its parent.
        if skill.depth >= 1:
            parent_skill = _extract_parent_from_path(skill.relative_path, all_skills)
        return ClassificationResult(
            skill_type="orchestration",
            parent_skill=parent_skill,
            child_skills=child_skills,
            classification_signals=signals,
            warnings=warnings,
        )

    # Leaf classification.
    parent_skill = None
    if skill.depth >= 1:
        parent_skill = _extract_parent_from_path(skill.relative_path, all_skills)
        if parent_skill is None:
            # Fall back to plugin.json leaf-parent detection.
            parent_skill = _check_plugin_json_leaf_parent(
                skill, plugin_json_skills, all_skills
            )
        if parent_skill is None:
            warnings.append("parent_not_found")
    leaf_signals: list[str] = []
    if body_leaf:
        leaf_signals.append("body_text_leaf")
    if skill.depth >= 1:
        leaf_signals.append("directory_nested")
    return ClassificationResult(
        skill_type="leaf",
        parent_skill=parent_skill,
        child_skills=[],
        classification_signals=leaf_signals,
        warnings=warnings,
    )


def classify_all_skills(
    skills: list[ScannedSkill],
    plugin_json_skills: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, ClassificationResult]:
    """Classify every skill and return a mapping ``skill_id → ClassificationResult``.

    Handles the case where a skill is both a leaf (has a parent) and has
    children (orchestration) — orchestration takes precedence.
    """
    results: dict[str, ClassificationResult] = {}
    for skill in skills:
        results[skill.skill_id] = classify_skill(
            skill, skills, plugin_json_skills
        )
    return results
