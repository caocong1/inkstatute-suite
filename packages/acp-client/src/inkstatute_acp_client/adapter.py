"""ACPBackendAdapter — BackendAdapter 9-method Protocol implementation over ACP.

Implements the :class:`BackendAdapter` Protocol from
``platform_runtime.protocols`` using the ACP client core from Plan 89-01.
Each ``submit_run`` spawns a new ACP subprocess (per_session mode), initializes
the protocol, creates a session, sends the prompt, and streams events.

The adapter is the production entry point for driving any ACP-speaking agent
(including ``hermes acp``) as a platform backend.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable

from platform_contract.agent_adapter import AdapterCapabilitySet, BackendProcessMode
from platform_contract.enums import AsyncTaskState
from platform_runtime.protocols import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)

from .capability_negotiation import (
    CapabilityMismatchError,
    CapabilityNegotiationResult,
    RequiredCapabilities,
)
from .client import ACPClient, ACPTransport, StdioACPTransport
from .process_mode import validate_process_mode

logger = logging.getLogger(__name__)

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# Hermes compatibility matrix — maps Hermes version to supported ACP capabilities
# ---------------------------------------------------------------------------

HERMES_COMPATIBILITY_MATRIX: dict[str, list[str]] = {
    "0.19.0": ["streaming", "session_update", "session_cancel", "session_close"],
    "0.18.0": ["streaming", "session_update", "session_cancel"],
    "0.17.0": ["streaming", "session_update"],
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ACPBackendConfig:
    """Configuration for :class:`ACPBackendAdapter`.

    Attributes
    ----------
    backend_id
        Unique identifier for this backend (e.g. ``"hermes"``, ``"echo"``).
    command
        The command tuple to spawn the ACP agent subprocess.
    env
        Additional environment variables for the subprocess.
    process_mode
        The subprocess process mode. Only ``PER_SESSION`` is implemented.
    timeout_seconds
        Subprocess/streaming timeout in seconds.
    required_capabilities
        Capabilities the caller requires from the ACP agent.
    hermes_home
        Path to set as ``HERMES_HOME`` env var (for Hermes backend).
    compatibility_matrix
        Version → features mapping for compatibility checking.
    """

    backend_id: str
    command: tuple[str, ...]
    env: dict[str, str] | None = None
    process_mode: BackendProcessMode = BackendProcessMode.PER_SESSION
    timeout_seconds: float = 300.0
    required_capabilities: RequiredCapabilities = field(
        default_factory=lambda: RequiredCapabilities(streaming=True)
    )
    hermes_home: str | None = None
    compatibility_matrix: dict[str, Any] = field(default_factory=dict)
    client_capabilities: dict | None = None


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


class _SystemClock:
    """Default clock — returns current UTC time as ISO-8601 string."""

    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Permission safety — kinds that must NEVER be auto-approved
# ---------------------------------------------------------------------------

_DANGEROUS_PERMISSION_KINDS: frozenset[str] = frozenset({"terminal", "execute_code"})


# ---------------------------------------------------------------------------
# ACPBackendAdapter
# ---------------------------------------------------------------------------


class ACPBackendAdapter:
    """ACP-based BackendAdapter implementing all 9 Protocol methods.

    Uses the ACP client core to drive any ACP-speaking agent over stdio.
    In ``per_session`` mode (the only implemented mode), each ``submit_run``
    spawns a new subprocess, initializes the protocol, creates a session,
    and streams events via a background asyncio task.
    """

    def __init__(
        self,
        config: ACPBackendConfig,
        transport_factory: Callable[[ACPBackendConfig], ACPTransport] | None = None,
    ) -> None:
        # Reject unimplemented process modes early
        validate_process_mode(config.process_mode)

        self.config = config
        self._transport_factory = transport_factory or _default_transport_factory
        self._clock = _SystemClock()

        # Run state
        self._runs: dict[str, Run] = {}
        self._events: dict[str, list[RunEvent]] = {}
        self._artifacts: dict[str, list[ArtifactRecord]] = {}

        # Session tracking: run_id → (client, session_id)
        self._sessions: dict[str, ACPClient] = {}
        self._session_ids: dict[str, str] = {}
        self._bg_tasks: dict[str, asyncio.Task] = {}

        # Negotiation result from last successful initialize
        self._negotiation_result: CapabilityNegotiationResult | None = None

        # Counters
        self._next_run = 1
        self._next_event = 1

    # ------------------------------------------------------------------
    # Protocol method 1: backend_id
    # ------------------------------------------------------------------

    def backend_id(self) -> str:
        """Return the unique backend identifier."""
        return self.config.backend_id

    # ------------------------------------------------------------------
    # Protocol method 2: capabilities
    # ------------------------------------------------------------------

    def capabilities(self) -> AdapterCapabilitySet:
        """Return the capability set from the last successful negotiation.

        If no negotiation has occurred yet, returns a default set with
        ``stream_event_support=True``.
        """
        if self._negotiation_result is not None:
            return self._negotiation_result.capabilities
        return AdapterCapabilitySet(stream_event_support=True)

    # ------------------------------------------------------------------
    # Protocol method 3: bootstrap_check
    # ------------------------------------------------------------------

    async def bootstrap_check(self) -> BootstrapStatus:
        """Spawn a transport, call initialize, check compatibility.

        Checks:
        1. Protocol version is 1 (enforced by negotiate()).
        2. Agent version against the compatibility matrix.
        3. Required capabilities are met.

        Closes the transport after the check.
        """
        transport = self._transport_factory(self.config)
        client = ACPClient(
            transport,
            self.config.required_capabilities,
            client_capabilities=self.config.client_capabilities,
        )

        try:
            await transport.start(self.config.command, self._build_env())
        except Exception as exc:
            await transport.close()
            return BootstrapStatus(
                ok=False,
                backend_id=self.config.backend_id,
                checked_at=self._clock.now(),
                issues=[f"transport_start_failed: {exc}"],
            )

        try:
            result = await client.initialize()
            self._negotiation_result = result

            issues: list[str] = []

            # Check agent version against compatibility matrix
            if self.config.compatibility_matrix:
                version_ok, version_issues = _check_version_compatibility(
                    result.agent_version, self.config.compatibility_matrix
                )
                if not version_ok:
                    issues.extend(version_issues)
                else:
                    issues.extend(version_issues)  # untested warnings

            return BootstrapStatus(
                ok=len(issues) == 0 or all("untested" in i for i in issues),
                backend_id=self.config.backend_id,
                checked_at=self._clock.now(),
                issues=issues,
                metadata={
                    "agent_name": result.agent_name,
                    "agent_version": result.agent_version,
                    "protocol_version": result.protocol_version,
                    "process_mode": self.config.process_mode.value,
                },
            )
        except CapabilityMismatchError as exc:
            return BootstrapStatus(
                ok=False,
                backend_id=self.config.backend_id,
                checked_at=self._clock.now(),
                issues=[str(exc)],
                metadata={
                    "process_mode": self.config.process_mode.value,
                },
            )
        finally:
            await transport.close()

    # ------------------------------------------------------------------
    # Protocol method 4: submit_run
    # ------------------------------------------------------------------

    async def submit_run(self, req: RunRequest) -> RunHandle:
        """Spawn a per-session ACP subprocess, initialize, create session, prompt.

        Starts a background task to collect streaming events.
        """
        run_id = self._new_run_id()

        # 1. Create transport and client
        transport = self._transport_factory(self.config)
        client = ACPClient(
            transport,
            self.config.required_capabilities,
            client_capabilities=self.config.client_capabilities,
        )

        # 2. Start transport
        await transport.start(self.config.command, self._build_env())

        # 3. Initialize
        result = await client.initialize()
        self._negotiation_result = result

        # 4. Create session
        session_id = await client.new_session()

        # 5. Send prompt
        content = req.turn.content or ""
        await client.prompt(session_id, content)

        # 6. Store session and client
        self._sessions[run_id] = client
        self._session_ids[run_id] = session_id

        # 7. Create Run
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={
                "backend_id": self.config.backend_id,
                "backend_run_id": session_id,
                "session_id": session_id,
                "process_mode": self.config.process_mode.value,
                "agent_name": result.agent_name,
                "agent_version": result.agent_version,
            },
        )
        self._runs[run_id] = run
        self._events[run_id] = []

        # 8. Start background event collection
        task = asyncio.create_task(self._collect_events(run_id, client, session_id))
        self._bg_tasks[run_id] = task

        # 9. Return handle
        return RunHandle(
            run_id=run_id,
            backend_run_id=session_id,
            status=AsyncTaskState.RUNNING,
            metadata={
                "backend_id": self.config.backend_id,
                "session_id": session_id,
            },
        )

    # ------------------------------------------------------------------
    # Protocol method 5: get_run
    # ------------------------------------------------------------------

    async def get_run(self, run_id: str) -> Run:
        """Return the current Run state, or raise KeyError."""
        if run_id not in self._runs:
            raise KeyError(f"unknown ACP run: {run_id}")
        return self._runs[run_id]

    # ------------------------------------------------------------------
    # Protocol method 6: stream_events
    # ------------------------------------------------------------------

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        """Yield events for a run in seq order.

        Polls the event buffer until the run reaches a terminal state.
        Raises KeyError for unknown run_id.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown ACP run: {run_id}")

        index = 0
        terminal_states = {
            AsyncTaskState.SUCCEEDED,
            AsyncTaskState.FAILED,
            AsyncTaskState.CANCELLED,
        }

        while True:
            events = self._events.get(run_id, [])
            while index < len(events):
                yield events[index]
                index += 1

            run = self._runs[run_id]
            if run.status in terminal_states:
                break

            await asyncio.sleep(0.01)

    # ------------------------------------------------------------------
    # Protocol method 7: cancel_run
    # ------------------------------------------------------------------

    async def cancel_run(self, run_id: str) -> Run:
        """Cancel a run by calling session/cancel on the ACP agent."""
        if run_id not in self._runs:
            raise KeyError(f"unknown ACP run: {run_id}")

        run = self._runs[run_id]
        client = self._sessions.get(run_id)
        session_id = self._session_ids.get(run_id)

        if client is not None and session_id is not None:
            try:
                await client.cancel(session_id)
            except Exception as exc:
                logger.warning("cancel failed for run %s: %s", run_id, exc)

        updated = replace(run, status=AsyncTaskState.CANCELLED)
        self._runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 8: submit_approval
    # ------------------------------------------------------------------

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        """Submit an approval response.

        CRITICAL: ``terminal`` and ``execute_code`` permissions must NEVER
        be auto-approved. If the approval metadata indicates a dangerous
        permission kind and the decision is ``"approved"``, the run is
        set to ``WAITING_FOR_USER`` with an issue — the approval is rejected.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown ACP run: {run_id}")

        run = self._runs[run_id]

        # Permission safety: reject auto-approval of dangerous permissions
        kind = str(approval.metadata.get("kind", "")).lower()
        if approval.decision == "approved" and kind in _DANGEROUS_PERMISSION_KINDS:
            updated = replace(
                run,
                status=AsyncTaskState.WAITING_FOR_USER,
                metadata={
                    **run.metadata,
                    "approval_rejected": f"dangerous_permission_{kind}",
                    "approval_id": approval.approval_id,
                    "approval_decision_recorded": False,
                    "issue": f"permission kind '{kind}' must not be auto-approved",
                },
            )
            self._runs[run_id] = updated
            return updated

        # Normal approval — record in metadata
        updated = replace(
            run,
            metadata={
                **run.metadata,
                "approval_id": approval.approval_id,
                "approval_decision": approval.decision,
                "approval_decision_recorded": True,
            },
        )
        self._runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 9: collect_artifacts
    # ------------------------------------------------------------------

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        """Return artifacts for a run (possibly empty)."""
        if run_id not in self._runs:
            raise KeyError(f"unknown ACP run: {run_id}")
        return list(self._artifacts.get(run_id, []))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Close all active sessions and transports."""
        # Cancel background tasks
        for task in self._bg_tasks.values():
            task.cancel()
        self._bg_tasks.clear()

        # Shutdown all clients (closes transports)
        for client in self._sessions.values():
            try:
                await client.shutdown()
            except Exception:
                pass
        self._sessions.clear()
        self._session_ids.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_run_id(self) -> str:
        value = self._next_run
        self._next_run += 1
        return f"acp-run-{value:03d}"

    def _make_run_event(
        self, run_id: str, event_type: str, payload: dict
    ) -> RunEvent:
        seq = self._next_event
        self._next_event += 1
        return RunEvent(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            event_type=event_type,
            occurred_at=self._clock.now(),
            seq=seq,
            payload=payload,
        )

    def _build_env(self) -> dict[str, str] | None:
        """Build env dict for subprocess, including HERMES_HOME if set."""
        env: dict[str, str] = {}
        if self.config.env:
            env.update(self.config.env)
        if self.config.hermes_home:
            env["HERMES_HOME"] = self.config.hermes_home
        return env if env else None

    async def _collect_events(
        self, run_id: str, client: ACPClient, session_id: str
    ) -> None:
        """Background task: consume stream_updates and store events."""
        try:
            async for event in client.stream_updates(
                session_id, run_id=run_id, timeout=self.config.timeout_seconds
            ):
                self._events[run_id].append(event)
                if event.event_type == "message.completed":
                    run = self._runs.get(run_id)
                    if run is not None:
                        self._runs[run_id] = replace(
                            run, status=AsyncTaskState.SUCCEEDED
                        )
                    break
        except asyncio.CancelledError:
            logger.debug("event collection cancelled for run %s", run_id)
        except Exception as exc:
            logger.warning("event collection error for run %s: %s", run_id, exc)
            run = self._runs.get(run_id)
            if run is not None:
                self._runs[run_id] = replace(
                    run,
                    status=AsyncTaskState.FAILED,
                    metadata={**run.metadata, "error": str(exc)},
                )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _default_transport_factory(config: ACPBackendConfig) -> ACPTransport:
    """Default transport factory — returns a new StdioACPTransport."""
    return StdioACPTransport()


def _parse_semver(version: str) -> tuple[int, ...]:
    """Parse a semver string like '0.19.0' into a tuple (0, 19, 0)."""
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _check_version_compatibility(
    agent_version: str, matrix: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Check agent version against a compatibility matrix.

    Returns ``(is_compatible, issues)``. If the agent version is below
    the minimum key in the matrix, it is incompatible. If the version
    is not in the matrix but is above the minimum, it is "untested" but
    still compatible.
    """
    if not matrix:
        return True, []

    min_version = min(matrix.keys(), key=_parse_semver)
    agent_tuple = _parse_semver(agent_version)
    min_tuple = _parse_semver(min_version)

    if agent_tuple < min_tuple:
        return False, [f"version_below_minimum: {agent_version} < {min_version}"]

    if agent_version not in matrix:
        return True, [f"version_untested: {agent_version}"]

    return True, []


def check_hermes_compatibility(
    agent_version: str,
    matrix: dict[str, list[str]] | None = None,
) -> tuple[bool, list[str]]:
    """Check Hermes agent version against the compatibility matrix.

    Parameters
    ----------
    agent_version
        The Hermes agent version string (e.g. ``"0.19.0"``).
    matrix
        The compatibility matrix to check against. Defaults to
        :data:`HERMES_COMPATIBILITY_MATRIX`.

    Returns
    -------
    tuple[bool, list[str]]
        ``(is_compatible, issues)``. The agent version must be >= the
        minimum key in the matrix. If below minimum, an issue with
        ``"below_minimum"`` is added and ``is_compatible`` is ``False``.
        If the version is not in the matrix, an issue with
        ``"untested"`` is added but ``is_compatible`` remains ``True``
        (untested != incompatible).
    """
    if matrix is None:
        matrix = HERMES_COMPATIBILITY_MATRIX

    if not matrix:
        return True, []

    min_version = min(matrix.keys(), key=_parse_semver)
    agent_tuple = _parse_semver(agent_version)
    min_tuple = _parse_semver(min_version)

    issues: list[str] = []

    if agent_tuple < min_tuple:
        issues.append(f"hermes_version_below_minimum: {agent_version} < {min_version}")
        return False, issues

    if agent_version not in matrix:
        issues.append(f"hermes_version_untested: {agent_version}")

    return True, issues


def create_hermes_adapter(
    hermes_home: str,
    hermes_command: tuple[str, ...] = ("hermes", "acp"),
    timeout_seconds: float = 300.0,
) -> ACPBackendAdapter:
    """Create an :class:`ACPBackendAdapter` configured for ``hermes acp``.

    This is the production entry point for driving ``hermes acp`` as a
    platform backend. Sets ``HERMES_HOME`` env var for profile loading.

    Parameters
    ----------
    hermes_home
        Path to the Hermes home directory (for profile loading).
    hermes_command
        The command to spawn the Hermes ACP agent. Defaults to
        ``("hermes", "acp")``.
    timeout_seconds
        Subprocess/streaming timeout in seconds.

    Returns
    -------
    ACPBackendAdapter
        A configured adapter ready for ``bootstrap_check`` and ``submit_run``.
    """
    config = ACPBackendConfig(
        backend_id="hermes",
        command=hermes_command,
        env={"HERMES_HOME": hermes_home},
        process_mode=BackendProcessMode.PER_SESSION,
        timeout_seconds=timeout_seconds,
        compatibility_matrix=dict(HERMES_COMPATIBILITY_MATRIX),
    )
    return ACPBackendAdapter(config)


__all__ = [
    "ACPBackendAdapter",
    "ACPBackendConfig",
    "HERMES_COMPATIBILITY_MATRIX",
    "check_hermes_compatibility",
    "create_hermes_adapter",
]
