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

from dataclasses import fields as dataclass_fields
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
    "gate_pass_rate",
    "services",
    "feature_flags",
    "carried_human_gates",
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

# Static, read-only list of human gates that this console never auto-closes.
# Rendered with a distinct non-green visual state in the dashboard.
# No API endpoint or UI control can mutate this list.
CARRIED_HUMAN_GATES: tuple[dict[str, Any], ...] = (
    {"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False},
    {"name": "Phase 8 lawyer trial", "status": "carried", "auto_closed": False},
    {"name": "QQ live acceptance", "status": "carried", "auto_closed": False},
)


def project_health(raw_status: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *raw_status* containing only allowlisted fields.

    Fields not in ``HEALTH_ALLOWED_FIELDS`` are silently dropped — health views
    should not crash on unexpected fields.
    """

    return {key: value for key, value in raw_status.items() if key in HEALTH_ALLOWED_FIELDS}


def collect_service_health(
    process_supervisor: Any,
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
) -> list[dict[str, Any]]:
    """Build a list of service health dicts for the unified health view.

    Includes the admin-console-api itself plus WeCom and QQBot host
    processes.  Only name, status, ok, host, and port are exposed —
    the raw metadata.health payload from child probes is NOT included.
    """
    # Build the admin-console-api own entry inline to avoid recursion with
    # collect_raw_health (which calls collect_service_health).
    own_raw: dict[str, Any] = {
        "service": "admin-console-api",
        "status": "ok",
        "version": "0.1.0",
        "secrets_configured": bool(resolve_admin_token()),
        "uptime_seconds": None,
    }
    own_projected = project_health(own_raw)
    services: list[dict[str, Any]] = [{
        "name": "admin-console-api",
        "status": own_projected.get("status", "ok"),
        "ok": own_projected.get("status") == "ok",
        "host": None,
        "port": None,
    }]

    if process_supervisor is not None:
        for record in process_supervisor.status_all():
            services.append({
                "name": record.name,
                "status": record.status,
                "ok": record.status == "running",
                "host": record.host,
                "port": record.port,
            })
    else:
        for name in ("wecom", "qqbot"):
            services.append({
                "name": name,
                "status": "unknown",
                "ok": False,
                "host": None,
                "port": None,
            })

    return services


def collect_feature_flag_states(
    feature_flags: RuntimeFeatureFlags,
) -> list[dict[str, Any]]:
    """Return a list of {name, enabled} dicts for every RuntimeFeatureFlags field."""
    return [
        {"name": field.name, "enabled": bool(getattr(feature_flags, field.name))}
        for field in dataclass_fields(RuntimeFeatureFlags)
    ]


def collect_raw_health(
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    gate_summary: dict[str, Any] | None = None,
    process_supervisor: Any = None,
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
        total = len(gates)
        passed = sum(1 for g in gates if g.get("exit_code") == 0)
        raw["gate_pass_rate"] = (passed / total) if total > 0 else None
    else:
        raw["gate_count"] = None
        raw["gates_passed"] = None
        raw["gates_failed"] = None
        raw["gate_pass_rate"] = None

    # Intentionally included raw fields that project_health will filter OUT.
    # These prove the allowlist excludes secret-related data.
    raw["secret_refs_configured"] = {"wecom_token": True, "aes_key": False}
    raw["api_base_url"] = "REDACTED"
    raw["config_path"] = "/etc/inkstatute/config.yaml"

    raw["services"] = collect_service_health(process_supervisor, feature_flags, read_model)
    raw["feature_flags"] = collect_feature_flag_states(feature_flags)
    raw["carried_human_gates"] = list(CARRIED_HUMAN_GATES)

    return raw


def handle_health(
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    gate_summary: dict[str, Any] | None = None,
    process_supervisor: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Collect raw health data, project through the allowlist, return 200."""

    raw = collect_raw_health(
        feature_flags,
        read_model,
        gate_summary,
        process_supervisor=process_supervisor,
    )
    projected = project_health(raw)
    return 200, projected


__all__ = [
    "HEALTH_ALLOWED_FIELDS",
    "HEALTH_EXCLUDED_FIELDS",
    "CARRIED_HUMAN_GATES",
    "project_health",
    "collect_service_health",
    "collect_feature_flag_states",
    "collect_raw_health",
    "handle_health",
]
