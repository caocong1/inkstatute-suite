"""Practice profile handler for the InkStatute Gateway.

Implements three endpoints:

- ``GET /v1/practice-profile`` — returns the tenant's profile (all
  plugins or filtered by ``?plugin=X``).
- ``PUT /v1/practice-profile`` — updates the tenant's profile
  (ADMIN/OPERATOR only, validates no secrets).
- ``POST /v1/practice-profile/interview`` — starts a cold-start
  interview (ADMIN/OPERATOR only, returns the initial
  ``ElicitationRequestedPayload`` as JSON).

All handler methods use ``ctx.tenant_id`` from the auth context —
cross-tenant access is structurally impossible because the tenant_id
comes from the auth context, not the request body.

The handler does **not** log profile content to the contract event
log — profile data is runtime-only (binding constraint #6).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping

from platform_contract.events import JsonObject

from .auth import AuthContext, GatewayAuthError

from inkstatute_practice_profile import (
    ColdStartInterviewOrchestrator,
    InterviewState,
    PracticeProfile,
    PracticeProfileStore,
    SecretDetectedError,
    check_read_access,
    check_write_access,
    validate_no_secrets,
)


class GatewayPracticeProfileHandler:
    """Handle the 3 practice-profile Gateway endpoints.

    Parameters
    ----------
    store
        The :class:`PracticeProfileStore` used to read/write profiles.
    orchestrator
        The :class:`ColdStartInterviewOrchestrator` used to start
        cold-start interviews.

    The handler stores in-progress interview states in-memory keyed by
    ``(tenant_id, plugin)`` so the client can submit answers across
    multiple requests.
    """

    def __init__(
        self,
        store: PracticeProfileStore,
        orchestrator: ColdStartInterviewOrchestrator,
    ) -> None:
        self._store = store
        self._orchestrator = orchestrator
        self._interview_states: dict[tuple[str, str], InterviewState] = {}

    # ------------------------------------------------------------------
    # GET /v1/practice-profile
    # ------------------------------------------------------------------

    def handle_get_profile(
        self,
        ctx: AuthContext,
        plugin: str | None = None,
    ) -> JsonObject:
        """Return the tenant's profile(s) as JSON.

        When *plugin* is ``None``, returns all profiles for the tenant
        (a dict of plugin -> profile JSON).  When *plugin* is specified,
        returns that plugin's profile or raises 404.
        """
        # All authenticated roles can read — check_read_access is
        # implicitly satisfied for all roles in PROFILE_READ_ROLES.
        # The require_auth call in the dispatch layer already ensures
        # the user is authenticated.  We still call check_read_access
        # for completeness and future-proofing.
        if ctx.identity is not None:
            if not check_read_access(ctx.identity.role):
                raise GatewayAuthError(
                    status=403,
                    code="forbidden",
                    message=(
                        f"Role '{ctx.identity.role.value}' is not permitted "
                        "to read practice profiles"
                    ),
                )

        if plugin is not None:
            profile = self._store.get(ctx.tenant_id, plugin)
            if profile is None:
                from .app import GatewayError
                raise GatewayError(
                    f"No practice profile found for plugin '{plugin}'",
                    code="not_found",
                    status=404,
                    details={"plugin": plugin},
                )
            return profile.to_json()

        # Return all profiles for the tenant
        plugins = self._store.list_plugins(ctx.tenant_id)
        profiles: dict[str, JsonObject] = {}
        for p in plugins:
            prof = self._store.get(ctx.tenant_id, p)
            if prof is not None:
                profiles[p] = prof.to_json()
        return {
            "tenant_id": ctx.tenant_id,
            "profiles": profiles,
            "count": len(profiles),
        }

    # ------------------------------------------------------------------
    # PUT /v1/practice-profile
    # ------------------------------------------------------------------

    def handle_put_profile(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Update the tenant's practice profile.

        Enforces ADMIN/OPERATOR role, validates no secrets, constructs
        a :class:`PracticeProfile` from the body, and calls
        ``store.upsert``.

        Returns ``{"status": "updated", "tenant_id": ..., "plugin": ...}``.
        Raises ``GatewayAuthError`` (403) for unauthorized roles.
        Raises ``GatewayError`` (400) for secret detection.
        """
        from .app import GatewayError

        # Enforce write access — ADMIN/OPERATOR only
        if ctx.identity is not None:
            if not check_write_access(ctx.identity.role):
                raise GatewayAuthError(
                    status=403,
                    code="forbidden",
                    message=(
                        f"Role '{ctx.identity.role.value}' is not permitted "
                        "to write practice profiles"
                    ),
                )

        # Validate no secrets in the body
        body_dict = dict(body)
        try:
            validate_no_secrets(body_dict)
        except SecretDetectedError as exc:
            raise GatewayError(
                f"Secret pattern detected: {exc.pattern_name} at field "
                f"path '{exc.field_path}' — secret value redacted",
                code="secret_detected",
                status=400,
                details={
                    "field_path": exc.field_path,
                    "pattern_name": exc.pattern_name,
                },
            )

        # Construct the profile with tenant_id from the auth context
        # (never from the request body — cross-tenant prevention)
        body_dict["tenant_id"] = ctx.tenant_id
        profile = PracticeProfile.from_json(body_dict)

        # Store the profile
        self._store.upsert(ctx.tenant_id, profile)

        return {
            "status": "updated",
            "tenant_id": ctx.tenant_id,
            "plugin": profile.plugin,
        }

    # ------------------------------------------------------------------
    # POST /v1/practice-profile/interview
    # ------------------------------------------------------------------

    def handle_start_interview(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Start a cold-start interview for the tenant.

        Enforces ADMIN/OPERATOR role, calls
        ``orchestrator.start(tenant_id, plugin)``, and returns the
        initial elicitation payload as JSON.

        Returns ``{"interrupt_id": ..., "intro": ..., "questions": [...]}``.
        Raises ``GatewayAuthError`` (403) for unauthorized roles.
        """
        # Enforce write access — ADMIN/OPERATOR only
        if ctx.identity is not None:
            if not check_write_access(ctx.identity.role):
                raise GatewayAuthError(
                    status=403,
                    code="forbidden",
                    message=(
                        f"Role '{ctx.identity.role.value}' is not permitted "
                        "to start a cold-start interview"
                    ),
                )

        plugin = str(body.get("plugin", "commercial-legal"))

        # Start the interview
        state = self._orchestrator.start(ctx.tenant_id, plugin)
        elicitation = self._orchestrator.get_current_elicitation(state)

        # Store the interview state for subsequent answer submissions
        self._interview_states[(ctx.tenant_id, plugin)] = state

        # Serialize the elicitation payload as JSON
        return _serialize_elicitation(elicitation)

    # ------------------------------------------------------------------
    # Interview state management (for multi-round interviews)
    # ------------------------------------------------------------------

    def get_interview_state(
        self,
        tenant_id: str,
        plugin: str,
    ) -> InterviewState | None:
        """Retrieve an in-progress interview state (for testing/inspection)."""
        return self._interview_states.get((tenant_id, plugin))

    def submit_interview_answers(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Submit answers for the current interview step and advance.

        This is a helper for multi-round interview flow.  The client
        calls this after receiving an elicitation payload and collecting
        answers from the user.

        Returns the next elicitation payload, or a finalized profile
        when the interview is complete.
        """
        from .app import GatewayError

        # Enforce write access — ADMIN/OPERATOR only
        if ctx.identity is not None:
            if not check_write_access(ctx.identity.role):
                raise GatewayAuthError(
                    status=403,
                    code="forbidden",
                    message=(
                        f"Role '{ctx.identity.role.value}' is not permitted "
                        "to submit interview answers"
                    ),
                )

        plugin = str(body.get("plugin", "commercial-legal"))
        answers_raw = body.get("answers")
        if not isinstance(answers_raw, dict):
            raise GatewayError(
                "answers must be an object mapping question_id -> answer",
                code="invalid_request",
                details={"field": "answers"},
            )
        answers: dict[str, str] = {
            str(k): str(v) for k, v in answers_raw.items()
        }

        state = self._interview_states.get((ctx.tenant_id, plugin))
        if state is None:
            raise GatewayError(
                f"No in-progress interview for tenant '{ctx.tenant_id}' "
                f"and plugin '{plugin}'",
                code="not_found",
                status=404,
            )

        # Submit answers and advance
        new_state = self._orchestrator.submit_answers(state, answers)
        self._interview_states[(ctx.tenant_id, plugin)] = new_state

        # If the interview is complete, finalize and return the profile
        if self._orchestrator.is_complete(new_state):
            profile = self._orchestrator.finalize(new_state)
            # Clean up the interview state
            self._interview_states.pop((ctx.tenant_id, plugin), None)
            return {
                "status": "finalized",
                "tenant_id": ctx.tenant_id,
                "plugin": profile.plugin,
                "profile": profile.to_json(),
            }

        # Return the next elicitation payload
        elicitation = self._orchestrator.get_current_elicitation(new_state)
        return _serialize_elicitation(elicitation)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_elicitation(payload: Any) -> JsonObject:
    """Serialize an :class:`ElicitationRequestedPayload` to a JSON dict."""
    questions = []
    for q in payload.questions:
        question_dict: JsonObject = {
            "id": q.id,
            "question": q.question,
            "allow_multiple": q.allow_multiple,
        }
        if q.options:
            question_dict["options"] = [
                {"label": opt.label, "value": opt.value} for opt in q.options
            ]
        questions.append(question_dict)

    return {
        "interrupt_id": payload.interrupt_id,
        "intro": payload.intro,
        "questions": questions,
        "resume_state_ref": payload.resume_state_ref,
        "metadata": dict(payload.metadata) if payload.metadata else {},
    }


__all__ = [
    "GatewayPracticeProfileHandler",
]
