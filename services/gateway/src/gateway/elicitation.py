"""Elicitation submission handler for the InkStatute Gateway.

Implements ``POST /v1/runs/{run_id}/elicitation`` — accepts clarification
card answers from the web client and stores them for the agent core to
resume the interrupted run.

MVP (pre-Phase 100): The handler accepts the submission, stores it in an
in-memory dict keyed by ``(run_id, interrupt_id)``, and returns success.
The agent core (when implemented in Phase 100) will poll or be notified
of the submission.
"""

from __future__ import annotations

from typing import Any, Mapping

from .auth import AuthContext

JsonObject = dict[str, Any]


class GatewayElicitationHandler:
    """Handle elicitation (clarification card) submissions.

    Stores submitted answers in-memory keyed by ``(run_id, interrupt_id)``.
    The agent core (Phase 100+) will consume these to resume interrupted runs.
    """

    def __init__(self, runtime: object | None = None) -> None:
        self._runtime = runtime
        self._submissions: dict[tuple[str, str], dict[str, Any]] = {}

    def handle_submit_elicitation(
        self,
        ctx: AuthContext,
        run_id: str,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Process an elicitation submission.

        Extracts ``interrupt_id`` and ``answers`` from the body, validates
        them, stores the submission, and returns a success response.

        Returns ``{ status: "submitted", run_id, interrupt_id }``.
        Raises ``GatewayError`` (400) for missing/invalid fields.
        """
        from .app import GatewayError

        interrupt_id = body.get("interrupt_id")
        if not interrupt_id or not isinstance(interrupt_id, str):
            raise GatewayError(
                "interrupt_id is required",
                code="invalid_request",
                details={"field": "interrupt_id"},
            )

        answers = body.get("answers")
        if not isinstance(answers, list) or len(answers) == 0:
            raise GatewayError(
                "answers must be a non-empty list",
                code="invalid_request",
                details={"field": "answers"},
            )

        # Store the submission for the agent core to consume
        key = (run_id, interrupt_id)
        self._submissions[key] = {
            "interrupt_id": interrupt_id,
            "answers": list(answers),
            "tenant_id": ctx.tenant_id,
        }

        # If the runtime supports resume_elicitation, delegate to it
        resume = getattr(self._runtime, "resume_elicitation", None) if self._runtime else None
        if callable(resume):
            resume(run_id, interrupt_id, answers)

        return {
            "status": "submitted",
            "run_id": run_id,
            "interrupt_id": interrupt_id,
        }

    def get_submission(self, run_id: str, interrupt_id: str) -> dict[str, Any] | None:
        """Retrieve a stored elicitation submission (for testing/inspection)."""
        return self._submissions.get((run_id, interrupt_id))


__all__ = [
    "GatewayElicitationHandler",
]
