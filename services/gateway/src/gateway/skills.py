"""Skills endpoint handler for the InkStatute Gateway.

Proxies ``GET /v1/skills`` requests to the existing ``skill-registry``
read API (``handle_get``), adding auth and tenant checks. The Gateway
translates its ``/v1/skills`` path prefix to the skill-registry's
``/skills`` path by stripping the ``/v1`` prefix.

CRITICAL: The skills endpoint is read-only. No write API is exposed
through the Gateway (write API stays in admin-console). The
``skill_registry_enabled`` feature flag is preserved (default-off).

This satisfies GW-05: 取代 apps/platform_api 与 services/lawyer-web-chat
的职责重叠，全项目单一网关 — the skills read API is now accessible
through the unified Gateway.
"""

from __future__ import annotations

from typing import Any

from inkstatute_skill_registry.api import handle_get
from inkstatute_skill_registry.registry import SkillRegistry
from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)

from .auth import AuthContext

JsonObject = dict[str, Any]


class GatewaySkillsHandler:
    """Handle skill catalog requests by proxying to skill-registry's ``handle_get``.

    The handler stores a :class:`SkillRegistry` and optional
    :class:`RuntimeFeatureFlags`. When feature flags are provided,
    ``skill_registry_enabled`` is checked before processing (default-off,
    same as skill-registry).
    """

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        feature_flags: RuntimeFeatureFlags | None = None,
    ) -> None:
        self._registry = registry
        self._feature_flags = feature_flags

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    @property
    def feature_flags(self) -> RuntimeFeatureFlags | None:
        return self._feature_flags

    def handle_list_skills(
        self,
        auth_ctx: AuthContext,
        path: str,
        query: str | None,
    ) -> JsonObject:
        """Proxy to ``handle_get`` for ``GET /v1/skills``.

        Translates the Gateway path to the skill-registry path by
        stripping the ``/v1`` prefix, calls ``handle_get``, and adds
        ``tenant_id`` from the auth context to the response metadata.
        """
        return self._proxy(auth_ctx, path, query)

    def handle_skill_search(
        self,
        auth_ctx: AuthContext,
        query: str,
    ) -> JsonObject:
        """Proxy to ``handle_get`` for ``GET /v1/skills/search``."""
        return self._proxy(auth_ctx, "/v1/skills/search", query)

    def handle_get_skill(
        self,
        auth_ctx: AuthContext,
        skill_id: str,
    ) -> JsonObject:
        """Proxy to ``handle_get`` for ``GET /v1/skills/{skill_id}``."""
        return self._proxy(auth_ctx, f"/v1/skills/{skill_id}", None)

    def _proxy(
        self,
        auth_ctx: AuthContext,
        path: str,
        query: str | None,
    ) -> JsonObject:
        """Internal proxy: translate path, call handle_get, add tenant_id."""
        # Translate /v1/skills... → /skills...
        translated_path = path
        if translated_path.startswith("/v1/skills"):
            translated_path = translated_path[len("/v1"):]

        try:
            status_code, body = handle_get(
                translated_path,
                query,
                self._registry,
                self._feature_flags,
            )
        except RuntimeFeatureDisabledError:
            return _feature_disabled_response()

        # Add tenant_id from auth context to response metadata.
        if isinstance(body, dict):
            metadata = body.get("metadata")
            if isinstance(metadata, dict):
                metadata["tenant_id"] = auth_ctx.tenant_id
            else:
                body["metadata"] = {"tenant_id": auth_ctx.tenant_id}

        body["status"] = status_code
        return body


def handle_skills_request(
    handler: GatewaySkillsHandler,
    auth_ctx: AuthContext,
    path: str,
    query: str | None,
) -> JsonObject:
    """Gateway endpoint handler for ``GET /v1/skills*``.

    Determines whether the request is for list, search, or get-single
    based on the path, delegates to the appropriate handler method, and
    returns the response. Returns 404 for unknown skill paths.
    """
    # Strip query string from path for routing.
    clean_path = path.split("?")[0]

    # GET /v1/skills — list all skills
    if clean_path == "/v1/skills":
        return handler.handle_list_skills(auth_ctx, path, query)

    # GET /v1/skills/search — search skills (must be checked before /v1/skills/{id})
    if clean_path == "/v1/skills/search":
        return handler.handle_skill_search(auth_ctx, query)

    # GET /v1/skills/{skill_id} — get single skill
    if clean_path.startswith("/v1/skills/"):
        skill_id = clean_path.removeprefix("/v1/skills/")
        return handler.handle_get_skill(auth_ctx, skill_id)

    # Unknown skill path
    return _not_found_response(path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _feature_disabled_response() -> JsonObject:
    """Response when skill_registry_enabled flag is False."""
    return {
        "error": {
            "code": "feature_disabled",
            "message": "skill_registry_enabled feature flag is False",
        },
        "status": 503,
    }


def _not_found_response(path: str) -> JsonObject:
    """404 response for unknown skill paths."""
    return {
        "error": {
            "code": "not_found",
            "resource": "skill_route",
            "identifier": path,
        },
        "status": 404,
    }


__all__ = [
    "GatewaySkillsHandler",
    "handle_skills_request",
]
