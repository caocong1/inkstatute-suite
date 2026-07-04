"""Health/status views with a positive field allowlist.

The allowlist (``HEALTH_ALLOWED_FIELDS``) is a **positive filter** — only fields
in the set are exposed.  This is different from the ``ALL_FORBIDDEN_KEYS``
negative filter used by ``scrub_contract_payload``.  The allowlist approach
prevents accidental exposure of new secret-like fields.

Only ``secrets_configured: true/false`` (a boolean) is exposed to indicate
whether secrets are configured.  Secret reference names, config paths,
``secret_refs_configured`` maps, and ``api_base_url`` values are excluded.
"""

from __future__ import annotations

from typing import Any

from platform_runtime.feature_flags import RuntimeFeatureFlags

from .auth import resolve_admin_token

# Positive allowlist — only these fields are exposed in health responses.
HEALTH_ALLOWED_FIELDS = frozenset({
    "service",
    "status",
    "version",
    "secrets_configured",
    "uptime_seconds",
    "gate_count",
    "gates_passed",
    "gates_failed",
})

# Documented for clarity — the allowlist is the enforcement mechanism, not this
# exclusion list.  These fields must NEVER appear in a projected health response.
HEALTH_EXCLUDED_FIELDS = frozenset({
    "secret_refs_configured",
    "api_base_url",
    "config_path",
    "config_file",
    "secret_ref_names",
    "wecom_token_ref",
    "aes_key_ref",
    "callback_token_ref",
    "encoding_aes_key_ref",
})


def project_health(raw_status: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *raw_status* containing only allowlisted fields.

    Fields not in ``HEALTH_ALLOWED_FIELDS`` are silently dropped — health views
    should not crash on unexpected fields.
    """

    return {key: value for key, value in raw_status.items() if key in HEALTH_ALLOWED_FIELDS}


def collect_raw_health(
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    gate_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gather raw status data before allowlist projection.

    The raw dict intentionally includes secret-related fields
    (``secret_refs_configured``, ``api_base_url``, ``config_path``) to prove
    that ``project_health`` excludes them.  Callers pass the result through
    ``project_health`` before returning it to the API layer.
    """

    raw: dict[str, Any] = {
        "service": "admin-console-api",
        "status": "ok",
        "version": "0.1.0",
        "secrets_configured": bool(resolve_admin_token()),
        "uptime_seconds": None,
    }

    if gate_summary is not None:
        gates = gate_summary.get("gates", [])
        raw["gate_count"] = len(gates)
        raw["gates_passed"] = sum(1 for g in gates if g.get("exit_code") == 0)
        raw["gates_failed"] = sum(1 for g in gates if g.get("exit_code") != 0)
    else:
        raw["gate_count"] = None
        raw["gates_passed"] = None
        raw["gates_failed"] = None

    # Intentionally included raw fields that project_health will filter OUT.
    # These prove the allowlist excludes secret-related data.
    raw["secret_refs_configured"] = {"wecom_token": True, "aes_key": False}
    raw["api_base_url"] = "REDACTED"
    raw["config_path"] = "/etc/inkstatute/config.yaml"

    return raw


def handle_health(
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    gate_summary: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Collect raw health data, project through the allowlist, return 200."""

    raw = collect_raw_health(feature_flags, read_model, gate_summary)
    projected = project_health(raw)
    return 200, projected


__all__ = [
    "HEALTH_ALLOWED_FIELDS",
    "HEALTH_EXCLUDED_FIELDS",
    "project_health",
    "collect_raw_health",
    "handle_health",
]
