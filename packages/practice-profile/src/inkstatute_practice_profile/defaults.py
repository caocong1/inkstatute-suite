"""Temporary mode (临时模式) default values and profile factory.

When ``PracticeProfileStore.get(tenant_id, plugin)`` returns ``None``
(no profile configured), the system generates a temporary profile from
these defaults.  Every output produced under a temporary profile must
be tagged with :data:`TEMPORARY_MODE_TAG`.

Defaults are sourced from ``practice-profile-schema.md §3.2``:

================  ===========================================
Field             Default
================  ===========================================
风险偏好           平衡型
执业角色           律师
管辖法律           中国大陆法律
甲方/乙方立场      标记常见风险，不偏向任何一方
升级矩阵           不自动升级，提示律师判断
文书风格           半正式，含法条引用，不含案例引用
================  ===========================================
"""

from __future__ import annotations

from platform_contract.events import JsonObject

from .model import PracticeProfile

#: Tag prepended to every output when the practice profile is in
#: temporary mode (no real configuration has been set yet).
TEMPORARY_MODE_TAG = "[临时模式 — 配置你的档案以获得定制输出]"


def _default_user_role() -> JsonObject:
    """Default user role: 律师."""
    return {
        "role": "律师",
        "lawyer_contact": "",
    }


def _default_shared_guardrails() -> JsonObject:
    """Default shared guardrails with jurisdiction identification."""
    return {
        "no_silent_fill": True,
        "timeliness_trigger": True,
        "legal_fact_verification": True,
        "source_labels": True,
        "destination_check": True,
        "dual_severity": True,
        "jurisdiction_identification": "中国大陆法律",
    }


def _default_document_style() -> JsonObject:
    """Default document style: 半正式, 法条引用, no 案例引用."""
    return {
        "revision_tone": "半正式",
        "stakeholder_summary": "",
        "work_product_location": "",
        "renewal_reminder_recipient": "",
        "citation_style": "法条引用",
        "case_citation": False,
    }


def _default_escalation_matrix() -> JsonObject:
    """Default escalation matrix: 不自动升级, 提示律师判断."""
    return {
        "approval_table": [],
        "amount_thresholds": [],
        "auto_escalation_triggers": [],
        "auto_escalation": False,
        "policy": "不自动升级，提示律师判断",
    }


def _default_plugin_config(plugin: str) -> JsonObject:
    """Default plugin-specific config: 风险偏好 + 甲方/乙方立场."""
    return {
        "风险偏好": "平衡型",
        "甲方立场": "标记常见风险，不偏向任何一方",
        "乙方立场": "标记常见风险，不偏向任何一方",
    }


def create_temporary_profile(tenant_id: str, plugin: str) -> PracticeProfile:
    """Construct a temporary-mode :class:`PracticeProfile`.

    The returned profile has ``temporary_mode=True`` and is populated
    with the 6 default values from ``practice-profile-schema.md §3.2``.
    The domain-specific defaults (风险偏好, 甲方/乙方立场) are placed
    in ``plugin_configs[plugin]`` so the function works for any plugin
    name, not just ``commercial-legal``.

    Parameters
    ----------
    tenant_id
        The tenant this profile belongs to.
    plugin
        The plugin name (e.g. ``"commercial-legal"``,
        ``"litigation-legal"``).

    Returns
    -------
    PracticeProfile
        A frozen practice profile with ``temporary_mode=True``.
    """
    return PracticeProfile(
        tenant_id=tenant_id,
        plugin=plugin,
        identity={},
        user_role=_default_user_role(),
        integrations={},
        escalation_matrix=_default_escalation_matrix(),
        document_style=_default_document_style(),
        shared_guardrails=_default_shared_guardrails(),
        plugin_configs={plugin: _default_plugin_config(plugin)},
        temporary_mode=True,
        updated_at=None,
    )


__all__ = [
    "TEMPORARY_MODE_TAG",
    "create_temporary_profile",
]
