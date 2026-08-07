"""Approval submission handler for the InkStatute Gateway.

Implements ``POST /v1/runs/{run_id}/approvals`` — accepts permission
approval decisions from the web client and stores them for the agent
core to resume the interrupted run.

CRITICAL SECURITY CONSTRAINT (AGENTS.md): The server MUST NOT auto-approve.
The decision comes from the user. The handler simply records the user's
decision and passes it to the runtime. There is no server-side auto-allow
path.

MVP (pre-Phase 100): The handler accepts the submission, stores it in an
in-memory dict keyed by ``(run_id, permission_id)``, and returns success.
The agent core (when implemented in Phase 100) will poll or be notified
of the submission.
"""

from __future__ import annotations

from typing import Any, Mapping

from .auth import AuthContext

JsonObject = dict[str, Any]

_VALID_DECISIONS = frozenset({"allow", "deny"})


class GatewayApprovalHandler:
    """Handle approval (permission request) submissions.

    Stores submitted decisions in-memory keyed by ``(run_id, permission_id)``.
    The agent core (Phase 100+) will consume these to resume interrupted runs.

    CRITICAL: This handler NEVER auto-approves. The decision always comes
    from the user. There is no code path that produces an automatic "allow".
    """

    def __init__(self, runtime: object | None = None) -> None:
        self._runtime = runtime
        self._submissions: dict[tuple[str, str], dict[str, Any]] = {}

    def handle_submit_approval(
        self,
        ctx: AuthContext,
        run_id: str,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Process an approval submission.

        Extracts ``permission_id`` and ``decision`` from the body, validates
        them, stores the submission, and returns a success response.

        Returns ``{ status: "submitted", run_id, permission_id, decision }``.
        Raises ``GatewayError`` (400) for missing/invalid fields.
        """
        from .app import GatewayError

        permission_id = body.get("permission_id")
        if not permission_id or not isinstance(permission_id, str):
            raise GatewayError(
                "permission_id is required",
                code="invalid_request",
                details={"field": "permission_id"},
            )

        decision = body.get("decision")
        if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
            raise GatewayError(
                f"decision must be one of {sorted(_VALID_DECISIONS)}, got: {decision!r}",
                code="invalid_request",
                details={"field": "decision"},
            )

        # Store the user's decision exactly — no auto-approve path
        key = (run_id, permission_id)
        self._submissions[key] = {
            "permission_id": permission_id,
            "decision": decision,
            "tenant_id": ctx.tenant_id,
        }

        # If the runtime supports resume_approval, delegate to it
        resume = getattr(self._runtime, "resume_approval", None) if self._runtime else None
        if callable(resume):
            resume(run_id, permission_id, decision)

        return {
            "status": "submitted",
            "run_id": run_id,
            "permission_id": permission_id,
            "decision": decision,
        }

    def get_submission(self, run_id: str, permission_id: str) -> dict[str, Any] | None:
        """Retrieve a stored approval submission (for testing/inspection)."""
        return self._submissions.get((run_id, permission_id))


__all__ = [
    "GatewayApprovalHandler",
]
