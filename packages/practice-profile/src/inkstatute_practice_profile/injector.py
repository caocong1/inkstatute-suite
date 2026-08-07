"""PracticeProfileInjector — renders a tenant's practice profile as a
``## 执业配置`` context section prepended to the skill body.

The injector runs **before** the :class:`SkillBodyInjector` (Phase 97).
Its output (``context_section``) is prepended to the skill body text so
that the body injector's token-budget trim algorithm can treat the
combined text as a single unit.

Flow:

1. Check the skill's ``practice_profile_dependency`` flag in the
   skill-index.json — if ``False``, return a no-injection result.
2. Determine the plugin (from the skill's index record ``plugin`` field,
   or from the ``plugin`` parameter which overrides the index value).
3. Fetch the tenant's profile from :class:`PracticeProfileStore`.
4. If no profile exists, generate a temporary profile via
   :func:`create_temporary_profile`.
5. Render the profile as a markdown context section starting with
   ``## 执业配置``.  In temporary mode, prepend the
   :data:`TEMPORARY_MODE_TAG`.
6. Return a :class:`ProfileInjectionResult`.

**Runtime-only**: The injector does **not** create any ``RunEvent``.
Profile data is injected as execution-time context and never serialized
into the contract event log (binding constraint #6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platform_contract.events import JsonObject

from .defaults import TEMPORARY_MODE_TAG, create_temporary_profile
from .model import PracticeProfile
from .store import PracticeProfileStore


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SkillNotFoundError(KeyError):
    """Raised when a *skill_id* is not found in the skill index."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProfileInjectionResult:
    """Result of a practice profile injection.

    Attributes
    ----------
    context_section
        The rendered markdown context section (starts with ``## 执业配置``
        or the ``[临时模式]`` tag).  Empty string when no profile was
        injected (skill has no ``practice_profile_dependency``).
    profile_injected
        ``True`` when any profile (real or temporary) was injected.
        ``False`` when the skill has no ``practice_profile_dependency``.
    temporary_mode
        ``True`` when a temporary profile was used (no real profile in
        the store).  ``False`` when a real profile was used or no
        injection happened.
    plugin
        The plugin name used for the injection, or ``None`` when no
        injection happened.
    """

    context_section: str
    profile_injected: bool
    temporary_mode: bool
    plugin: str | None


# ---------------------------------------------------------------------------
# Section rendering helpers
# ---------------------------------------------------------------------------


def _render_kv_block(data: JsonObject, indent: str = "") -> str:
    """Render a flat key-value dict as markdown bullet lines.

    Each entry becomes ``- **key：** value``.  Non-string values are
    rendered via ``str()``.  Empty-string values are rendered as
    ``[未配置]``.
    """
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, bool):
            display = "是" if value else "否"
        elif isinstance(value, list):
            if value:
                display = "、".join(str(v) for v in value)
            else:
                display = "[未配置]"
        elif isinstance(value, dict):
            # Nested dict — render sub-items
            lines.append(f"{indent}- **{key}：**")
            lines.append(_render_kv_block(value, indent=indent + "  "))
            continue
        else:
            display = str(value) if value else "[未配置]"
        lines.append(f"{indent}- **{key}：** {display}")
    return "\n".join(lines)


def _render_subsection(title: str, data: JsonObject) -> str:
    """Render a ``### <title>`` subsection if *data* is non-empty.

    Returns an empty string if *data* is empty (so the caller can skip
    the section entirely).
    """
    if not data:
        return ""
    body = _render_kv_block(data)
    return f"### {title}\n\n{body}\n"


def _render_plugin_config_subsection(plugin: str, config: JsonObject) -> str:
    """Render the plugin-specific config as a ``### <plugin> 配置`` subsection."""
    if not config:
        return ""
    body = _render_kv_block(config)
    return f"### {plugin} 配置\n\n{body}\n"


def _render_profile(profile: PracticeProfile) -> str:
    """Render a :class:`PracticeProfile` as the ``## 执业配置`` section.

    Only subsections with non-empty data are included.  The section
    always starts with ``## 执业配置``.
    """
    parts: list[str] = ["## 执业配置", ""]

    # --- Identity ---
    identity_section = _render_subsection("身份信息", profile.identity)
    if identity_section:
        parts.append(identity_section)

    # --- User role ---
    role_section = _render_subsection("使用者角色", profile.user_role)
    if role_section:
        parts.append(role_section)

    # --- Integrations ---
    integrations_section = _render_subsection("可用集成", profile.integrations)
    if integrations_section:
        parts.append(integrations_section)

    # --- Review stance (plugin-specific) ---
    plugin_config = profile.plugin_configs.get(profile.plugin, {})
    stance_section = _render_plugin_config_subsection(
        profile.plugin, plugin_config
    )
    if stance_section:
        parts.append(stance_section)

    # --- Escalation matrix ---
    escalation_section = _render_subsection("升级矩阵", profile.escalation_matrix)
    if escalation_section:
        parts.append(escalation_section)

    # --- Document style ---
    doc_section = _render_subsection("文书风格", profile.document_style)
    if doc_section:
        parts.append(doc_section)

    # --- Shared guardrails ---
    guardrails_section = _render_subsection(
        "共享护栏", profile.shared_guardrails
    )
    if guardrails_section:
        parts.append(guardrails_section)

    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# PracticeProfileInjector
# ---------------------------------------------------------------------------


class PracticeProfileInjector:
    """Injects a tenant's practice profile as a context section.

    The injector checks the skill index for ``practice_profile_dependency``,
    fetches the tenant's profile from the store (or generates a temporary
    one), and renders it as a ``## 执业配置`` markdown section.

    Args
    ----
    store
        The :class:`PracticeProfileStore` to fetch profiles from.
    skill_index_path
        Path to ``skill-index.json``.  Used to check
        ``practice_profile_dependency`` and resolve the skill's plugin.
    """

    def __init__(
        self,
        store: PracticeProfileStore,
        skill_index_path: str | Path | None = None,
    ) -> None:
        self._store = store
        self._skill_index_path = (
            Path(skill_index_path) if skill_index_path is not None else None
        )
        # Lazy-loaded index cache
        self._index_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, Any]:
        """Load and cache the skill-index.json."""
        if self._index_data is not None:
            return self._index_data
        if self._skill_index_path is None:
            raise FileNotFoundError(
                "skill_index_path was not provided to PracticeProfileInjector; "
                "a valid path to skill-index.json is required."
            )
        if not self._skill_index_path.exists():
            raise FileNotFoundError(
                f"skill-index.json not found: {self._skill_index_path}"
            )
        self._index_data = json.loads(
            self._skill_index_path.read_text(encoding="utf-8")
        )
        return self._index_data

    def _find_skill_record(self, skill_id: str) -> dict[str, Any]:
        """Find a skill record by *skill_id* in the index.

        Raises :class:`SkillNotFoundError` if not found.
        """
        index = self._load_index()
        skills = index.get("skills", [])
        for record in skills:
            if record.get("skill_id") == skill_id:
                return record
        raise SkillNotFoundError(
            f"Skill '{skill_id}' not found in index: {self._skill_index_path}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject(
        self,
        skill_id: str,
        tenant_id: str,
        plugin: str | None = None,
    ) -> ProfileInjectionResult:
        """Inject the practice profile for a skill execution.

        Args
        ----
        skill_id
            The skill ID to look up in the index.
        tenant_id
            The tenant whose profile should be injected.
        plugin
            Override for the plugin name.  When ``None``, the plugin is
            read from the skill's index record ``plugin`` field.

        Returns
        -------
        ProfileInjectionResult
            The injection result with the rendered context section.

        Raises
        ------
        FileNotFoundError
            If the skill-index.json is missing or no path was provided.
        SkillNotFoundError
            If *skill_id* is not found in the index.
        """
        # Step 1: Check practice_profile_dependency in the index
        record = self._find_skill_record(skill_id)
        has_dependency = bool(
            record.get("practice_profile_dependency", False)
        )

        if not has_dependency:
            return ProfileInjectionResult(
                context_section="",
                profile_injected=False,
                temporary_mode=False,
                plugin=None,
            )

        # Step 2: Determine the plugin
        resolved_plugin = plugin if plugin is not None else record.get("plugin")
        if resolved_plugin is None:
            # Skill has dependency but no plugin in index and no override.
            # Use a fallback — should not happen in practice.
            resolved_plugin = "default"

        # Step 3: Fetch the tenant's profile
        profile = self._store.get(tenant_id, resolved_plugin)

        # Step 4: Generate temporary profile if none exists
        temporary_mode = False
        if profile is None:
            profile = create_temporary_profile(tenant_id, resolved_plugin)
            temporary_mode = True

        # Step 5: Render the context section
        context_section = _render_profile(profile)
        if temporary_mode:
            context_section = (
                f"{TEMPORARY_MODE_TAG}\n\n{context_section}"
            )

        # Step 6: Return result
        return ProfileInjectionResult(
            context_section=context_section,
            profile_injected=True,
            temporary_mode=temporary_mode,
            plugin=resolved_plugin,
        )


__all__ = [
    "PracticeProfileInjector",
    "ProfileInjectionResult",
    "SkillNotFoundError",
]
