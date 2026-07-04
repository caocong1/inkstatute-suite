"""Read-only Skill Registry with list, get, and search operations.

The registry is constructed with a pre-loaded list of
:class:`NeutralSkillDescriptor` records and exposes only query methods.
No write, update, or delete operations are provided — read-only enforcement
is structural.
"""

from __future__ import annotations

from typing import Protocol

from platform_contract import NeutralSkillDescriptor


class SkillRegistryPort(Protocol):
    """Read-only Skill Registry protocol — no write methods."""

    def list_skills(self) -> list[NeutralSkillDescriptor]: ...

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]: ...


class SkillRegistry:
    """Concrete read-only Skill Registry backed by solution-pack manifests.

    The registry stores a copy of the descriptor list at construction time
    and never mutates it.  All public methods are query-only.
    """

    def __init__(self, skills: list[NeutralSkillDescriptor]) -> None:
        self._skills = list(skills)
        self._by_id = {s.skill_id: s for s in self._skills}

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        """Return a copy of all skill descriptors."""
        return list(self._skills)

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        """Return the descriptor for *skill_id*, or ``None`` if not found."""
        return self._by_id.get(skill_id)

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]:
        """Search skills by tag, category, and/or name substring.

        Filters apply AND logic when multiple are supplied:

        - *tag* — matches ``metadata["risk_level"] == tag`` or ``tag`` in
          ``metadata["tags"]``.
        - *category* — matches ``metadata["intent"] == category``.
        - *name_substring* — case-insensitive substring match on ``name``.
        """
        results = self._skills
        if tag is not None:
            results = [
                s
                for s in results
                if s.metadata.get("risk_level") == tag
                or tag in s.metadata.get("tags", [])
            ]
        if category is not None:
            results = [s for s in results if s.metadata.get("intent") == category]
        if name_substring is not None:
            needle = name_substring.lower()
            results = [s for s in results if needle in s.name.lower()]
        return list(results)
