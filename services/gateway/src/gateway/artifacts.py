"""Artifact download handler for the InkStatute Gateway.

Provides ``GET /v1/artifacts/{artifact_id}`` with auth + tenant validation.

CRITICAL: Cross-tenant access returns 404 (not 403) to avoid leaking the
existence of artifacts belonging to other tenants. The ``tenant_id`` check
is fail-safe: if the tenant_id doesn't match, the artifact is invisible.

The response does NOT include raw artifact content — only the ``uri_ref``
pointing to the storage location. This satisfies AGENTS.md: "Contract logs
prefer raw_payload_ref" and "Never commit customer documents, or raw legal
payloads."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .auth import AuthContext

JsonObject = dict[str, Any]


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact in the Gateway store.

    Wraps ``ArtifactRecord`` with an explicit ``tenant_id`` field for
    tenant isolation.
    """

    artifact_id: str
    kind: str
    uri_ref: str
    name: str | None = None
    tenant_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)


class GatewayArtifactStore:
    """In-memory artifact store with tenant isolation.

    Artifacts are typically registered by the runtime when an
    ``artifact.created`` event is produced. The store enforces tenant
    isolation: cross-tenant access is invisible (returns ``None``).
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, ArtifactMetadata] = {}

    def register_artifact(self, artifact: ArtifactMetadata) -> None:
        """Register an artifact in the store."""
        self._artifacts[artifact.artifact_id] = artifact

    def get_artifact(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
    ) -> ArtifactMetadata | None:
        """Retrieve an artifact by ID.

        Returns ``None`` if the artifact does not exist OR if the
        artifact's ``tenant_id`` does not match the requesting
        ``tenant_id`` (cross-tenant access denied, fail-safe: invisible
        to other tenants).
        """
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None
        if artifact.tenant_id != tenant_id:
            return None
        return artifact

    def list_artifacts(
        self,
        run_id: str,
        *,
        tenant_id: str,
    ) -> list[ArtifactMetadata]:
        """List artifacts for a run, filtered by tenant_id."""
        return [
            a for a in self._artifacts.values()
            if a.metadata.get("run_id") == run_id
            and a.tenant_id == tenant_id
        ]


def handle_get_artifact_request(
    store: GatewayArtifactStore,
    auth_ctx: AuthContext,
    artifact_id: str,
) -> JsonObject:
    """Gateway endpoint handler for ``GET /v1/artifacts/{artifact_id}``.

    Calls ``store.get_artifact(artifact_id, tenant_id=auth_ctx.tenant_id)``.
    Returns the artifact metadata as a JSON dict. Returns 404 if the
    artifact is not found (or cross-tenant denied — both return 404 to
    avoid leaking existence).

    The response does NOT include raw artifact content — only the
    ``uri_ref`` pointing to the storage location.
    """
    artifact = store.get_artifact(artifact_id, tenant_id=auth_ctx.tenant_id)
    if artifact is None:
        # 404 for both not-found and cross-tenant denied — no existence leak
        return {
            "error": {
                "code": "not_found",
                "message": f"Artifact not found: {artifact_id}",
            },
            "status": 404,
        }

    return {
        "artifact_id": artifact.artifact_id,
        "kind": artifact.kind,
        "uri_ref": artifact.uri_ref,
        "name": artifact.name,
        "tenant_id": artifact.tenant_id,
        "reference_only": True,
        "status": 200,
    }


__all__ = [
    "ArtifactMetadata",
    "GatewayArtifactStore",
    "handle_get_artifact_request",
]
