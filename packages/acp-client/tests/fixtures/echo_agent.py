#!/usr/bin/env python3
"""Standalone ACP echo agent fixture for CI testing.

Reads JSON-RPC 2.0 messages from stdin line-by-line and responds over stdout.
No external imports beyond stdlib (``sys``, ``json``, ``uuid``).

Supported methods:
  - ``initialize`` — responds with protocolVersion 1 and capabilities
  - ``session/new`` — responds with a session_id
  - ``session/prompt`` — emits ``session/update`` notifications echoing the
    prompt as ``agent_message_chunk`` then a final ``agent_message``
  - ``session/cancel`` — responds with empty result
  - ``session/close`` — responds with empty result

Capabilities can be overridden via the ``ECHO_AGENT_CAPABILITIES`` environment
variable (JSON dict).  Default: ``{"streaming": true, "elicitation": false,
"permissions": false}``.
"""

from __future__ import annotations

import json
import os
import sys
import uuid


def _default_capabilities() -> dict:
    """Return capabilities, optionally overridden by env var."""
    env_caps = os.environ.get("ECHO_AGENT_CAPABILITIES")
    if env_caps:
        try:
            return json.loads(env_caps)
        except (json.JSONDecodeError, TypeError):
            pass
    return {"streaming": True, "elicitation": False, "permissions": False}


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


def handle_initialize(req: dict) -> None:
    caps = _default_capabilities()
    result = {
        "protocolVersion": 1,
        "agentInfo": {"name": "echo", "version": "0.1.0"},
        "capabilities": caps,
    }
    _send(_response(req.get("id"), result))


def handle_session_new(req: dict) -> None:
    session_id = str(uuid.uuid4())
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

    # Emit agent_message_chunk notifications (streaming)
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

    # Emit final agent_message
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

    # Respond to the prompt request with empty result
    _send(_response(req.get("id"), {}))


def handle_session_cancel(req: dict) -> None:
    _send(_response(req.get("id"), {}))


def handle_session_close(req: dict) -> None:
    _send(_response(req.get("id"), {}))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_METHOD_HANDLERS = {
    "initialize": handle_initialize,
    "session/new": handle_session_new,
    "session/prompt": handle_session_prompt,
    "session/cancel": handle_session_cancel,
    "session/close": handle_session_close,
}


def main() -> None:
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
            # Unknown method — return method-not-found error
            _send(
                _error_response(
                    req.get("id"),
                    -32601,
                    f"Method not found: {method}",
                )
            )


if __name__ == "__main__":
    main()
