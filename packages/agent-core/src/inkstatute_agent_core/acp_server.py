"""ACP server protocol handler — ``inkstatute-agent acp``.

Speaks ACP v1 (Zed Agent Client Protocol) over stdio.  Reads JSON-RPC 2.0
messages from stdin line-by-line and responds over stdout.  This is the
*second* entry point for the self-built agent core — the same
``run_turn()`` implementation that powers the in-process
``InProcessAgentCoreAdapter`` (Plan 103-01) is reused here, proving the
core has no architectural privilege: it can be driven in-process OR as
an ACP subprocess, just like Hermes.

Protocol methods:
  - ``initialize`` → protocolVersion 1, agentInfo, capabilities
  - ``session/new`` → create session, return sessionId
  - ``session/prompt`` → run ``run_turn()``, map RunEvents → ACP
    ``session/update`` notifications, respond with empty result
  - ``session/cancel`` → cancel the running turn
  - ``session/close`` → clean up session

Capabilities declared: ``streaming``, ``elicitation``, ``permissions``.
Does NOT declare ``fs/*`` or ``terminal/*`` (AGENTS.md safety rule).

Reverse event mapping (RunEvent → ACP session/update):
  - ``message.delta`` → ``agent_message_chunk``
  - ``message.completed`` → ``agent_message``
  - ``thought.delta`` → ``agent_thought_chunk``
  - ``tool_call.started`` → ``tool_call_update`` (status=started)
  - ``tool_call.delta`` → ``tool_call_update`` (content)
  - ``tool_call.completed`` → ``tool_call_update`` (status=completed)
  - ``plan.updated`` → ``plan``
  - ``phase.changed`` → ``plan`` (folded)
  - ``error`` → ``error``
  - ``elicitation.requested`` → ``elicitation/create`` request
  - ``permission.requested`` → ``session/request_permission`` request
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, TextIO

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from .config import AgentCoreConfig
from .event_emitter import EventEmitter
from .model.provider import LlmProvider
from .prompt_assembler import AgentMode, SkillMetadata, build_system_prompt
from .turn_loop import run_turn

JsonObject = dict[str, Any]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 1
AGENT_NAME = "inkstatute-agent"
AGENT_VERSION = "0.1.0"

#: Capabilities declared at ``initialize``.  Does NOT include ``fs/*`` or
#: ``terminal/*`` — AGENTS.md safety rule.
AGENT_CAPABILITIES: JsonObject = {
    "streaming": True,
    "elicitation": True,
    "permissions": True,
}

#: Permission kinds that must NEVER be auto-approved (AGENTS.md).
_DANGEROUS_PERMISSION_KINDS: frozenset[str] = frozenset({
    "terminal", "execute_code",
})


# ---------------------------------------------------------------------------
# Reverse event mapping — RunEvent → ACP session/update
# ---------------------------------------------------------------------------


def map_run_event_to_acp_update(event: RunEvent) -> JsonObject | None:
    """Map a unified :class:`RunEvent` to an ACP ``session/update`` dict.

    Returns the ``update`` dict (the inner payload of a
    ``session/update`` notification), or ``None`` if the event type
    should not be forwarded to the ACP client (e.g. ``run.state_changed``
    and ``session.started`` are internal bookkeeping).

    Reverse of :func:`inkstatute_acp_client.event_mapping.map_acp_update_to_run_event`.
    """
    et = event.event_type
    payload = event.payload or {}

    if et == RunEventType.MESSAGE_DELTA_V3.value:
        return {
            "type": "agent_message_chunk",
            "content": payload.get("delta", ""),
            "messageId": payload.get("message_id") or "msg-1",
        }

    if et == RunEventType.MESSAGE_COMPLETED.value:
        return {
            "type": "agent_message",
            "content": payload.get("content", ""),
            "messageId": payload.get("message_id") or "msg-1",
        }

    if et == RunEventType.THOUGHT_DELTA.value:
        return {
            "type": "agent_thought_chunk",
            "content": payload.get("delta", ""),
        }

    if et == RunEventType.TOOL_CALL_STARTED_V3.value:
        return {
            "type": "tool_call_update",
            "toolCallId": payload.get("tool_call_id", ""),
            "toolName": payload.get("tool_name", ""),
            "status": "started",
        }

    if et == RunEventType.TOOL_CALL_DELTA.value:
        update: JsonObject = {
            "type": "tool_call_update",
            "toolCallId": payload.get("tool_call_id", ""),
        }
        content = payload.get("content")
        if content is not None:
            update["content"] = content
        status = payload.get("status")
        if status is not None:
            update["status"] = status
        return update

    if et == RunEventType.TOOL_CALL_COMPLETED_V3.value:
        update = {
            "type": "tool_call_update",
            "toolCallId": payload.get("tool_call_id", ""),
            "status": "completed",
        }
        content = payload.get("content")
        if content is not None:
            update["content"] = content
        return update

    if et == RunEventType.PLAN_UPDATED.value:
        return {
            "type": "plan",
            "plan": payload.get("plan", []),
        }

    if et == RunEventType.PHASE_CHANGED.value:
        # Fold phase.changed into a plan update — ACP has no separate
        # phase event.  Emit a minimal plan dict so the client can track
        # phase transitions.
        return {
            "type": "plan",
            "plan": [{"phase": payload.get("phase", "")}],
        }

    if et == RunEventType.ERROR.value:
        error = payload.get("error", {})
        return {
            "type": "error",
            "message": error.get("message", "Unknown error") if isinstance(error, dict) else str(error),
        }

    # Events that are internal bookkeeping — not forwarded as session/update.
    # run.state_changed, session.started, citation.recorded, artifact.created
    # are handled separately or are internal-only.
    return None


def map_run_event_to_acp_request(
    event: RunEvent,
    req_id: int,
) -> JsonObject | None:
    """Map an elicitation/permission RunEvent to an ACP *request* (not update).

    When the turn loop emits ``elicitation.requested`` or
    ``permission.requested``, the ACP server must send a JSON-RPC
    *request* (with an ``id``) to the client and wait for the response.

    Returns the full JSON-RPC request dict, or ``None`` if the event
    is not an elicitation/permission request.
    """
    et = event.event_type
    payload = event.payload or {}

    if et == RunEventType.ELICITATION_REQUESTED.value:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "elicitation/create",
            "params": {
                "id": payload.get("interrupt_id", str(uuid.uuid4())),
                "intro": payload.get("intro", ""),
                "questions": payload.get("questions", []),
            },
        }

    if et == RunEventType.PERMISSION_REQUESTED.value:
        kind = payload.get("kind")
        # CRITICAL: dangerous permissions must never be auto-approved.
        # The server sends the request to the client; the client (host)
        # is responsible for showing an approval card.  We do NOT set
        # ``auto_approve`` or ``default_decision``.
        params: JsonObject = {
            "id": payload.get("permission_id", str(uuid.uuid4())),
            "tool_call_id": payload.get("tool_call_id", ""),
            "description": payload.get("description", ""),
        }
        if kind is not None:
            params["kind"] = kind
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "session/request_permission",
            "params": params,
        }

    return None


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


@dataclass
class SessionState:
    """In-memory state for a single ACP session."""

    session_id: str
    messages: list[dict] = field(default_factory=list)
    active_turn: asyncio.Task | None = None
    cancelled: bool = False


# ---------------------------------------------------------------------------
# ACPServer
# ---------------------------------------------------------------------------


class ACPServer:
    """ACP v1 server that drives the agent-core ``run_turn()`` over stdio.

    The server is constructed with a ``provider_factory`` callable (so
    tests can inject a :class:`FixtureProvider`) and an optional
    ``config``.  In production, ``provider_factory`` reads env/config
    to create an OpenAI / Anthropic / Ollama provider.

    Args:
        provider_factory: Callable that returns a fresh
            :class:`LlmProvider` for each ``session/prompt``.
        config: :class:`AgentCoreConfig` for the turn loop.
        stdin: Injectable stdin stream (default ``sys.stdin``).
        stdout: Injectable stdout stream (default ``sys.stdout``).
    """

    def __init__(
        self,
        provider_factory: Callable[[], LlmProvider],
        config: AgentCoreConfig | None = None,
        *,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._config = config or AgentCoreConfig()
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._sessions: dict[str, SessionState] = {}
        self._next_request_id = 1

    # ------------------------------------------------------------------
    # JSON-RPC helpers
    # ------------------------------------------------------------------

    def _send(self, message: JsonObject) -> None:
        """Write a JSON-RPC message as a single line to stdout."""
        self._stdout.write(json.dumps(message) + "\n")
        self._stdout.flush()

    def _response(self, req_id: int | str | None, result: Any) -> JsonObject:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error_response(
        self, req_id: int | str | None, code: int, message: str
    ) -> JsonObject:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def _notification(self, method: str, params: JsonObject) -> JsonObject:
        return {"jsonrpc": "2.0", "method": method, "params": params}

    def _next_id(self) -> int:
        rid = self._next_request_id
        self._next_request_id += 1
        return rid

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    def handle_initialize(self, req: JsonObject) -> None:
        """Respond to ``initialize`` with protocolVersion 1 and capabilities."""
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "agentInfo": {"name": AGENT_NAME, "version": AGENT_VERSION},
            "capabilities": dict(AGENT_CAPABILITIES),
        }
        self._send(self._response(req.get("id"), result))

    def handle_session_new(self, req: JsonObject) -> None:
        """Create a new session and return the sessionId."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = SessionState(session_id=session_id)
        self._send(self._response(req.get("id"), {"sessionId": session_id}))

    async def handle_session_prompt(self, req: JsonObject) -> None:
        """Run ``run_turn()`` and stream ``session/update`` notifications.

        Extracts text from the prompt content blocks, builds messages,
        creates an EventEmitter + provider, starts ``run_turn()``, and
        maps each RunEvent to an ACP notification.  When the turn
        completes, responds with an empty result.
        """
        params = req.get("params", {})
        session_id = params.get("sessionId", "")
        prompt_list = params.get("prompt", [])

        session = self._sessions.get(session_id)
        if session is None:
            self._send(
                self._error_response(req.get("id"), -32602, f"Invalid session: {session_id}")
            )
            return

        # Extract text from prompt content blocks
        text_parts: list[str] = []
        for block in prompt_list:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        prompt_text = " ".join(text_parts)

        # Build messages: system prompt + user message
        system_prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.CHAT,
            retrieval_tools=[],
        )
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
        ]
        # Carry over any prior messages from the session
        messages = session.messages + messages

        # Create provider and emitter
        provider = self._provider_factory()
        run_id = str(uuid.uuid4())
        emitter = EventEmitter(run_id, self._config)

        # Run the turn loop and stream notifications
        try:
            async for event in run_turn(
                messages=messages,
                tools=None,
                provider=provider,
                emitter=emitter,
                config=self._config,
                run_id=run_id,
                phase="research",
            ):
                if session.cancelled:
                    break

                # Check for elicitation/permission requests (agent-side)
                acp_request = map_run_event_to_acp_request(
                    event, self._next_id()
                )
                if acp_request is not None:
                    self._send(acp_request)
                    # In a full implementation, we would wait for the
                    # client's response here and feed it back into the
                    # turn loop.  For now, the request is sent and the
                    # turn continues (the turn loop handles the
                    # side-channel event).
                    continue

                # Map to session/update notification
                update = map_run_event_to_acp_update(event)
                if update is not None:
                    self._send(
                        self._notification(
                            "session/update",
                            {"sessionId": session_id, "update": update},
                        )
                    )
        except Exception as exc:
            # Emit an error notification
            self._send(
                self._notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {"type": "error", "message": str(exc)},
                    },
                )
            )

        # Respond with empty result
        self._send(self._response(req.get("id"), {}))

    def handle_session_cancel(self, req: JsonObject) -> None:
        """Cancel the running turn for the session."""
        params = req.get("params", {})
        session_id = params.get("sessionId", "")
        session = self._sessions.get(session_id)
        if session is not None:
            session.cancelled = True
            if session.active_turn is not None:
                session.active_turn.cancel()
        self._send(self._response(req.get("id"), {}))

    def handle_session_close(self, req: JsonObject) -> None:
        """Clean up and remove the session."""
        params = req.get("params", {})
        session_id = params.get("sessionId", "")
        session = self._sessions.pop(session_id, None)
        if session is not None and session.active_turn is not None:
            session.active_turn.cancel()
        self._send(self._response(req.get("id"), {}))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main async loop — read lines from stdin and dispatch.

        Uses ``asyncio.to_thread`` for blocking stdin reads so the
        async event loop remains responsive.
        """
        while True:
            line = await asyncio.to_thread(self._stdin.readline)
            if not line:
                break  # EOF
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            method = req.get("method", "")
            if method == "initialize":
                self.handle_initialize(req)
            elif method == "session/new":
                self.handle_session_new(req)
            elif method == "session/prompt":
                await self.handle_session_prompt(req)
            elif method == "session/cancel":
                self.handle_session_cancel(req)
            elif method == "session/close":
                self.handle_session_close(req)
            else:
                self._send(
                    self._error_response(
                        req.get("id"), -32601, f"Method not found: {method}"
                    )
                )

    def run_sync(self) -> None:
        """Synchronous entry point — runs the async loop via ``asyncio.run``."""
        asyncio.run(self.run())


# ---------------------------------------------------------------------------
# --check flag
# ---------------------------------------------------------------------------


def run_check(provider_factory: Callable[[], LlmProvider]) -> int:
    """Run the bootstrap check for ``inkstatute-agent acp --check``.

    Tries to create a model provider from the factory.  If successful,
    prints ``"InkStatute ACP check OK"`` and returns 0.  If failed,
    prints the error and returns 1.

    Matches the ``hermes acp --check`` pattern.
    """
    try:
        provider = provider_factory()
        # Basic sanity — verify the provider has the required methods
        _ = provider.model_name()
        _ = provider.supports_tools()
    except Exception as exc:
        print(f"InkStatute ACP check FAILED: {exc}", file=sys.stderr)
        return 1
    print("InkStatute ACP check OK")
    return 0


# ---------------------------------------------------------------------------
# Default provider factory — reads env vars
# ---------------------------------------------------------------------------


def default_provider_factory() -> LlmProvider:
    """Create a model provider from environment variables.

    Reads ``INKSTATUTE_MODEL_PROVIDER`` (``openai`` / ``anthropic`` /
    ``ollama``) and the corresponding API key / base URL env vars.

    Raises ``RuntimeError`` if no provider is configured.
    """
    from .model.config import ProviderModelConfig

    provider_type = os.environ.get("INKSTATUTE_MODEL_PROVIDER", "").lower()

    if provider_type == "openai":
        from .model.openai_runner import OpenAIStreamProvider

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        model = os.environ.get("INKSTATUTE_MODEL_NAME", "gpt-4o")
        return OpenAIStreamProvider(
            config=ProviderModelConfig(
                model_name=model,
                api_key_ref="OPENAI_API_KEY",
            )
        )

    if provider_type == "anthropic":
        from .model.anthropic_runner import AnthropicStreamProvider

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        model = os.environ.get("INKSTATUTE_MODEL_NAME", "claude-sonnet-4-20250514")
        return AnthropicStreamProvider(
            config=ProviderModelConfig(
                model_name=model,
                api_key_ref="ANTHROPIC_API_KEY",
            )
        )

    if provider_type == "ollama":
        from .model.ollama_runner import OllamaStreamProvider

        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("INKSTATUTE_MODEL_NAME", "qwen2.5")
        return OllamaStreamProvider(
            config=ProviderModelConfig(
                model_name=model,
                api_base_url=base_url,
            )
        )

    raise RuntimeError(
        "No model provider configured. Set INKSTATUTE_MODEL_PROVIDER "
        "to 'openai', 'anthropic', or 'ollama' with the corresponding "
        "API key environment variable."
    )


__all__ = [
    "AGENT_CAPABILITIES",
    "AGENT_NAME",
    "AGENT_VERSION",
    "ACPServer",
    "PROTOCOL_VERSION",
    "SessionState",
    "default_provider_factory",
    "map_run_event_to_acp_request",
    "map_run_event_to_acp_update",
    "run_check",
]
