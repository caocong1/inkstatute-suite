#!/usr/bin/env python3
"""Configurable ACP echo agent fixture — simulates a second ACP backend.

This agent simulates a different ACP backend (e.g. ``codex-acp`` or
``claude-agent-acp``) with configurable capabilities, thought chunks,
elicitation, and permission requests.  It proves that a different ACP
backend with different capabilities and event patterns works through the
same :class:`ACPBackendAdapter`.

Reads JSON-RPC 2.0 messages from stdin line-by-line and responds over
stdout.  No external imports beyond stdlib (``sys``, ``json``, ``uuid``,
``argparse``).

CLI arguments:
  --backend-name   Name reported in ``initialize`` agentInfo (default ``codex-acp``)
  --capabilities   JSON string of capabilities (default streaming+elicitation+permissions)

Supported methods:
  - ``initialize`` — responds with protocolVersion 1, agentInfo, and configured capabilities
  - ``session/new`` — responds with a session_id prefixed by the backend name
  - ``session/prompt`` — emits thought chunks, chunked message chunks, and a final
    agent_message.  When the prompt contains ``"ask:"``, emits an
    ``elicitation/create`` request.  When the prompt contains
    ``"permission:"``, emits a ``session/request_permission`` request.
  - ``session/cancel`` — responds with empty result
  - ``session/close`` — responds with empty result
  - ``elicitation/create`` — responds to elicitation answers
  - ``session/request_permission`` — responds to permission decisions
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> tuple[str, dict]:
    """Parse --backend-name and --capabilities from argv."""
    parser = argparse.ArgumentParser(description="Configurable ACP echo agent")
    parser.add_argument(
        "--backend-name",
        default="codex-acp",
        help="Backend name reported in initialize agentInfo (default: codex-acp)",
    )
    parser.add_argument(
        "--capabilities",
        default='{"streaming": true, "elicitation": true, "permissions": true}',
        help="JSON string of capabilities",
    )
    args, _ = parser.parse_known_args()
    try:
        caps = json.loads(args.capabilities)
    except (json.JSONDecodeError, TypeError):
        caps = {"streaming": True, "elicitation": True, "permissions": True}
    return args.backend_name, caps


# ---------------------------------------------------------------------------
# Global state (set in main)
# ---------------------------------------------------------------------------

_BACKEND_NAME = "codex-acp"
_CAPABILITIES: dict = {"streaming": True, "elicitation": True, "permissions": True}


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _send(message: dict) -> None:
    """Write a JSON-RPC message as a single line to stdout."""
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _notification(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _response(req_id: int | str, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error_response(req_id: int | str, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------

def handle_initialize(req: dict) -> None:
    result = {
        "protocolVersion": 1,
        "agentInfo": {"name": _BACKEND_NAME, "version": "0.1.0"},
        "capabilities": _CAPABILITIES,
    }
    _send(_response(req.get("id"), result))


def handle_session_new(req: dict) -> None:
    session_id = f"{_BACKEND_NAME}-session-{uuid.uuid4()}"
    result = {"sessionId": session_id}
    _send(_response(req.get("id"), result))


def handle_session_prompt(req: dict) -> None:
    params = req.get("params", {})
    session_id = params.get("sessionId", "")
    prompt_list = params.get("prompt", [])
    # Extract text from the prompt content blocks
    text_parts: list[str] = []
    for block in prompt_list:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    prompt_text = " ".join(text_parts)

    # 1. Emit agent_thought_chunk (this differs from the base echo agent)
    _send(
        _notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "type": "agent_thought_chunk",
                    "content": f"Thinking about: {prompt_text}",
                    "messageId": "thought-1",
                },
            },
        )
    )

    # 2. Check for elicitation request (prompt contains "ask:")
    if "ask:" in prompt_text:
        _send(
            _notification(
                "elicitation/create",
                {
                    "sessionId": session_id,
                    "id": f"elicitation-{uuid.uuid4()}",
                    "intro": "I need some clarification before proceeding.",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "What is the case number?",
                            "type": "free_text",
                        },
                        {
                            "id": "q2",
                            "text": "Which party are you representing?",
                            "type": "single_choice",
                            "options": ["plaintiff", "defendant"],
                        },
                    ],
                },
            )
        )

    # 3. Check for permission request (prompt contains "permission:")
    if "permission:" in prompt_text:
        _send(
            _notification(
                "session/request_permission",
                {
                    "sessionId": session_id,
                    "id": f"permission-{uuid.uuid4()}",
                    "tool_call_id": f"tool-{uuid.uuid4()}",
                    "description": "Run a shell command",
                    "kind": "terminal",
                },
            )
        )

    # 4. Emit agent_message_chunk notifications (split into 3 chunks)
    chunk_size = max(1, len(prompt_text) // 3) if prompt_text else 1
    for i in range(0, len(prompt_text), chunk_size):
        chunk = prompt_text[i : i + chunk_size]
        _send(
            _notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "type": "agent_message_chunk",
                        "content": chunk,
                        "messageId": "msg-1",
                    },
                },
            )
        )

    # 5. Emit final agent_message
    _send(
        _notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "type": "agent_message",
                    "content": prompt_text,
                    "messageId": "msg-1",
                },
            },
        )
    )

    # 6. Respond to the prompt request with empty result
    _send(_response(req.get("id"), {}))


def handle_session_cancel(req: dict) -> None:
    _send(_response(req.get("id"), {}))


def handle_session_close(req: dict) -> None:
    _send(_response(req.get("id"), {}))


def handle_elicitation_create(req: dict) -> None:
    """Respond to elicitation answers (client → agent)."""
    _send(_response(req.get("id"), {"status": "answered"}))


def handle_session_request_permission(req: dict) -> None:
    """Respond to permission decisions (client → agent)."""
    _send(_response(req.get("id"), {"status": "processed"}))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_METHOD_HANDLERS = {
    "initialize": handle_initialize,
    "session/new": handle_session_new,
    "session/prompt": handle_session_prompt,
    "session/cancel": handle_session_cancel,
    "session/close": handle_session_close,
    "elicitation/create": handle_elicitation_create,
    "session/request_permission": handle_session_request_permission,
}


def main() -> None:
    global _BACKEND_NAME, _CAPABILITIES
    _BACKEND_NAME, _CAPABILITIES = _parse_args()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        handler = _METHOD_HANDLERS.get(method)
        if handler is not None:
            handler(req)
        else:
            _send(
                _error_response(
                    req.get("id"),
                    -32601,
                    f"Method not found: {method}",
                )
            )


if __name__ == "__main__":
    main()
