"""PracticeProfile data model — structured JSON with plugin-specific sections.

The model has a common header (identity, role, integrations, escalation
matrix, document style, shared guardrails) plus a ``plugin_configs`` map
where each key is a plugin name and the value is that plugin's
domain-specific practice profile data as a :type:`JsonObject`.

This accommodates the fact that each plugin has a different CLAUDE.md
structure (commercial-legal has review-stance with 7 dimensions × 2
sides, litigation-legal has risk calibration and settlement strategy,
etc.) without hardcoding any single plugin's schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_contract.events import JsonObject


@dataclass(frozen=True, slots=True)
class PracticeProfile:
    """Multi-tenant practice profile for a single plugin.

    A profile is per-plugin per-tenant: ``tenant_id`` + ``plugin`` form
    the composite key in :class:`PracticeProfileStore`.

    Common header fields
    --------------------
    identity
        Org identity: org_name, entity_type, team_size,
        escalation_contact, monthly_volume, counterparty_type,
        practice_environment.
    user_role
        User role: role (律师/非律师), lawyer_contact.
    integrations
        Available integrations: contract_mgmt, e_signature,
        doc_storage, wecom_dingtalk.
    escalation_matrix
        Approval table, amount thresholds, auto-escalation triggers.
    document_style
        Revision tone, stakeholder summary, work-product location,
        renewal reminder recipient.
    shared_guardrails
        No-silent-fill, timeliness trigger, legal fact verification,
        source labels, destination check, dual severity, jurisdiction
        identification.

    Plugin-specific fields
    ----------------------
    plugin_configs
        Maps plugin name → domain-specific config JsonObject.
        e.g. ``{"commercial-legal": {"审查立场": {...}, "升级矩阵": {...}}}``

    Flags
    -----
    temporary_mode
        ``True`` when the profile was generated from temporary mode
        defaults (no real configuration yet).
    updated_at
        ISO-8601 timestamp of the last write, or ``None``.
    """

    tenant_id: str
    plugin: str
    identity: JsonObject = field(default_factory=dict)
    user_role: JsonObject = field(default_factory=dict)
    integrations: JsonObject = field(default_factory=dict)
    escalation_matrix: JsonObject = field(default_factory=dict)
    document_style: JsonObject = field(default_factory=dict)
    shared_guardrails: JsonObject = field(default_factory=dict)
    plugin_configs: dict[str, JsonObject] = field(default_factory=dict)
    temporary_mode: bool = False
    updated_at: str | None = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> JsonObject:
        """Serialize all fields to a flat :type:`JsonObject`.

        The output is a plain dict suitable for JSON encoding.
        """
        return {
            "tenant_id": self.tenant_id,
            "plugin": self.plugin,
            "identity": dict(self.identity),
            "user_role": dict(self.user_role),
            "integrations": dict(self.integrations),
            "escalation_matrix": dict(self.escalation_matrix),
            "document_style": dict(self.document_style),
            "shared_guardrails": dict(self.shared_guardrails),
            "plugin_configs": {
                k: dict(v) for k, v in self.plugin_configs.items()
            },
            "temporary_mode": self.temporary_mode,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, data: JsonObject) -> PracticeProfile:
        """Deserialize a :type:`JsonObject` back to :class:`PracticeProfile`.

        Round-trip is lossless: ``from_json(p.to_json()) == p``.
        """
        plugin_configs_raw = data.get("plugin_configs", {})
        plugin_configs: dict[str, JsonObject] = {}
        if isinstance(plugin_configs_raw, dict):
            for k, v in plugin_configs_raw.items():
                plugin_configs[k] = dict(v) if isinstance(v, dict) else {}

        return cls(
            tenant_id=str(data.get("tenant_id", "")),
            plugin=str(data.get("plugin", "")),
            identity=dict(data.get("identity", {})) if isinstance(data.get("identity"), dict) else {},
            user_role=dict(data.get("user_role", {})) if isinstance(data.get("user_role"), dict) else {},
            integrations=dict(data.get("integrations", {})) if isinstance(data.get("integrations"), dict) else {},
            escalation_matrix=dict(data.get("escalation_matrix", {})) if isinstance(data.get("escalation_matrix"), dict) else {},
            document_style=dict(data.get("document_style", {})) if isinstance(data.get("document_style"), dict) else {},
            shared_guardrails=dict(data.get("shared_guardrails", {})) if isinstance(data.get("shared_guardrails"), dict) else {},
            plugin_configs=plugin_configs,
            temporary_mode=bool(data.get("temporary_mode", False)),
            updated_at=data.get("updated_at"),  # type: ignore[arg-type]
        )


__all__ = ["PracticeProfile"]
