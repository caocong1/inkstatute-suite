#!/usr/bin/env python3
"""InkStatute QQBot one-click smoke test (stdlib orchestrator).

Default ``--dry-run`` exercises leaf helpers (signature, egress, callback) plus
the host Protocol path (verify_and_ack → ingress/session → deliver) via the same
Phase 70 webhook helpers, using Fake transports and public DEMO / fixture
credentials. ``--live`` is a human gate (Phase 72).

QQ-only path (no WeCom channel imports). Never commits or prints secrets.
Dry-run never claims live acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]

for _rel in (
    "packages/channels/qqbot/src",
    "packages/channel-core/src",
    "packages/platform-contract/src",
    "packages/platform-runtime/src",
    "services/qqbot-service/src",
):
    _p = REPO_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from inkstatute_channels_qqbot._ed25519 import sign  # noqa: E402
from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback  # noqa: E402
from inkstatute_channels_qqbot.sender import (  # noqa: E402
    FEEDBACK_ACTIONS,
    FakeMessageTransport,
    SendError,
    UrllibMessageTransport,
    ack_interaction,
    build_feedback_keyboard_envelope,
    build_text_envelope,
    send_message,
)
from inkstatute_channels_qqbot.signature import (  # noqa: E402
    derive_keypair,
    handle_validation_challenge,
    verify_callback_signature,
)
from inkstatute_channels_qqbot.token_manager import (  # noqa: E402
    FakeTokenTransport,
    TokenManager,
    UrllibTokenTransport,
)
from platform_runtime.fakes import FakeBackendAdapter  # noqa: E402
from platform_runtime.feature_flags import RuntimeFeatureFlags  # noqa: E402
from qqbot_service.config import QQBotHostConfig  # noqa: E402
from qqbot_service.webhook import handle_qqbot_webhook_request  # noqa: E402
from qqbot_service.wiring import build_qqbot_wired_runtime  # noqa: E402

# Official QQ demo vectors (public documentation — NOT production secrets).
DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SIG_BODY = b'{\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}'
DEMO_SIG_TIMESTAMP = "1725442341"

FIXTURE_USER_OPENID = "FIXTURE_USER_OPENID_C2C_001"
FIXTURE_MSG_ID = "ROBOT1.0_fixture_c2c_msg_001"
DEFAULT_CALLBACK_FIXTURE = (
    REPO_ROOT
    / "packages"
    / "channels"
    / "qqbot"
    / "fixtures"
    / "qqbot_interaction_create.json"
)
C2C_MESSAGE_FIXTURE = (
    REPO_ROOT
    / "packages"
    / "channels"
    / "qqbot"
    / "fixtures"
    / "qqbot_c2c_message.json"
)
CALLBACK_PATH = "/qqbot/callback"
# Keep inside C2C/group passive-reply windows (mirror Phase 70 composition harness).
PROTOCOL_FIXED_NOW = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)
PROTOCOL_FIXTURE_REPLY = (
    "根据相关裁判观点，合同解除需审查约定解除与法定解除要件。"
)
PROTOCOL_SECRET_ENV = {
    "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
    "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
    "INKSTATUTE_QQBOT_BOT_SECRET": DEMO_BOT_SECRET,
}

LIVE_ENV_KEYS = (
    "INKSTATUTE_QQBOT_APP_ID",
    "INKSTATUTE_QQBOT_CLIENT_SECRET",
    "INKSTATUTE_QQBOT_BOT_SECRET",
    "INKSTATUTE_QQBOT_USER_OPENID",
    "INKSTATUTE_QQBOT_REPLY_MSG_ID",
)

EVIDENCE_SCHEMA = "inkstatute.qqbot.smoke_evidence.v1"

# Keys dropped case-insensitively (tokens, bodies, attachment URLs).
_FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {
        "authorization",
        "access_token",
        "bot_secret",
        "client_secret",
        "content",
        "url",
        "file_url",
        "attachment_url",
        "file_data",
        "token",
        "raw_payload",
        "payload",
        "body",
        "calls",  # never dump FakeMessageTransport.calls
        "envelope",
        "headers",
    }
)

_STEP_KEY_ALLOW: dict[str, frozenset[str]] = {
    "signature": frozenset({"ok", "vector", "challenge_ok"}),
    "send_text": frozenset(
        {"ok", "msg_type", "openid_hash", "status_code", "qq_code", "send_status_code"}
    ),
    "send_keyboard": frozenset(
        {
            "ok",
            "msg_type",
            "actions",
            "openid_hash",
            "status_code",
            "qq_code",
            "send_status_code",
        }
    ),
    "callback": frozenset(
        {
            "ok",
            "status",
            "category",
            "idempotency_key_present",
            "idempotency_key_hash",
            "ack_skipped",
            "ack_status",
        }
    ),
    # Plan 01: minimal Protocol keys (ok only). Plan 02 expands allowlist (SMOKE-02).
    "adapter_ack": frozenset({"ok"}),
    "session_ingress": frozenset({"ok"}),
    "adapter_deliver": frozenset({"ok"}),
}

# Substrings that must never appear in serialized evidence (SMOKE-04).
_BANNED_SUBSTRINGS = (
    "Authorization",
    "access_token",
    DEMO_BOT_SECRET,
    "fixture-token",
    "fixture-secret",
    "http://",
    "https://",
)


def _hash16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _contains_banned(text: str) -> bool:
    lower = text.lower()
    for banned in _BANNED_SUBSTRINGS:
        if banned.lower() in lower:
            return True
    return False


def _redact_string(value: str) -> str:
    if _contains_banned(value):
        return "[redacted]"
    return value


def _strip_forbidden(node: Any) -> Any:
    """Recursively drop forbidden keys and redact banned substrings."""
    if isinstance(node, Mapping):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if str(key).lower() in _FORBIDDEN_EVIDENCE_KEYS:
                continue
            if _contains_banned(str(key)):
                continue
            out[str(key)] = _strip_forbidden(value)
        return out
    if isinstance(node, list):
        return [_strip_forbidden(item) for item in node]
    if isinstance(node, str):
        return _redact_string(node)
    if isinstance(node, (bool, int, float)) or node is None:
        return node
    # Unknown types → string then redact (never leak repr of secrets).
    return _redact_string(str(node))


def _allowlist_steps(steps: Any) -> dict[str, Any]:
    if not isinstance(steps, Mapping):
        return {}
    cleaned: dict[str, Any] = {}
    for step_name, allowed in _STEP_KEY_ALLOW.items():
        raw = steps.get(step_name)
        if not isinstance(raw, Mapping):
            continue
        step_out: dict[str, Any] = {}
        for key, value in raw.items():
            if key not in allowed:
                continue
            step_out[key] = _strip_forbidden(value)
        cleaned[step_name] = step_out
    return cleaned


def sanitize_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return allowlisted, ban-list-clean evidence for stdout/file (SMOKE-04).

    Drops tokens, Authorization, BotSecret values, raw content bodies, and
    attachment/URL keys. Dry-run always stamps ``not_live_acceptance=true``.
    """
    stripped = _strip_forbidden(evidence)
    if not isinstance(stripped, dict):
        stripped = {}

    # Prefer structured rebuild when this looks like a smoke evidence record.
    has_structure = any(k in stripped for k in ("schema", "mode", "steps", "not_live_acceptance"))
    if has_structure:
        mode = stripped.get("mode", "dry-run")
        if mode not in ("dry-run", "live"):
            mode = "dry-run"
        out: dict[str, Any] = {
            "schema": EVIDENCE_SCHEMA,
            "mode": mode,
            "not_live_acceptance": True if mode == "dry-run" else bool(
                stripped.get("not_live_acceptance", True)
            ),
            "steps": _allowlist_steps(stripped.get("steps")),
        }
        # Pitfall 5: dry-run must never claim live acceptance.
        if out["mode"] == "dry-run":
            out["not_live_acceptance"] = True
        return json.loads(json.dumps(out, default=str))

    # Arbitrary dirty payloads: return stripped remnant only (no secret keys).
    # Keep only non-forbidden top-level keys that survived stripping.
    remnant = {
        k: v
        for k, v in stripped.items()
        if k.lower() not in _FORBIDDEN_EVIDENCE_KEYS and not _contains_banned(k)
    }
    return json.loads(json.dumps(remnant, default=str))


def load_live_credentials() -> dict[str, str]:
    """Load live value env vars. Fail closed on missing keys; never log values."""
    missing = [k for k in LIVE_ENV_KEYS if not os.environ.get(k)]
    if missing:
        # Fail closed — list key *names* only, never values.
        raise SystemExit(
            "live mode requires env vars (values not shown): " + ", ".join(missing)
        )
    return {
        "bot_secret": os.environ["INKSTATUTE_QQBOT_BOT_SECRET"],
        "user_openid": os.environ["INKSTATUTE_QQBOT_USER_OPENID"],
        "msg_id": os.environ["INKSTATUTE_QQBOT_REPLY_MSG_ID"],
        "app_id": os.environ["INKSTATUTE_QQBOT_APP_ID"],
        "client_secret": os.environ["INKSTATUTE_QQBOT_CLIENT_SECRET"],
    }


def load_credentials(mode: str) -> dict[str, str]:
    """Load credentials for the selected mode. Never log secret values."""
    if mode == "dry-run":
        return {
            "bot_secret": DEMO_BOT_SECRET,
            "user_openid": FIXTURE_USER_OPENID,
            "msg_id": FIXTURE_MSG_ID,
            "app_id": "fixture-app-id",
            "client_secret": "fixture-secret",
        }
    return load_live_credentials()


def _step_signature(*, bot_secret: str) -> dict[str, Any]:
    public_key, seed = derive_keypair(bot_secret)
    sig_hex = sign(seed, DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY).hex()
    ok = verify_callback_signature(
        public_key, sig_hex, DEMO_SIG_TIMESTAMP, DEMO_SIG_BODY
    )
    challenge = handle_validation_challenge(
        bot_secret, "smoke-plain-token", DEMO_SIG_TIMESTAMP
    )
    challenge_ok = bool(challenge.get("signature")) and challenge.get("plain_token") == (
        "smoke-plain-token"
    )
    return {
        "ok": bool(ok and challenge_ok),
        "vector": "qq_official_demo",
        "challenge_ok": challenge_ok,
    }


async def _step_egress(
    *,
    token_manager: TokenManager,
    transport: Any,
    user_openid: str,
    msg_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    text_env = build_text_envelope(
        content="墨律冒烟：文本通道",
        msg_id=msg_id,
        msg_seq=1,
    )
    try:
        text_result = await send_message(
            envelope=text_env,
            scene="c2c",
            token_manager=token_manager,
            transport=transport,
            user_openid=user_openid,
        )
    except SendError as exc:
        raise SystemExit(
            f"send_text step failed (status_code={exc.status_code}, qq_code={exc.qq_code})"
        ) from None
    text_step: dict[str, Any] = {
        "ok": True,
        "msg_type": int(text_env.get("msg_type", -1)),
        "openid_hash": _hash16(user_openid),
    }
    _stamp_send_status(text_step, text_result)

    kb_env = build_feedback_keyboard_envelope(
        title="墨律冒烟：请评价",
        feedback_target="smoke-target-001",
        msg_id=msg_id,
        msg_seq=2,
    )
    try:
        kb_result = await send_message(
            envelope=kb_env,
            scene="c2c",
            token_manager=token_manager,
            transport=transport,
            user_openid=user_openid,
        )
    except SendError as exc:
        raise SystemExit(
            f"send_keyboard step failed (status_code={exc.status_code}, qq_code={exc.qq_code})"
        ) from None
    keyboard_step: dict[str, Any] = {
        "ok": True,
        "msg_type": int(kb_env.get("msg_type", -1)),
        "actions": list(FEEDBACK_ACTIONS),
        "openid_hash": _hash16(user_openid),
    }
    _stamp_send_status(keyboard_step, kb_result)
    return text_step, keyboard_step


def _stamp_send_status(step: dict[str, Any], result: Any) -> None:
    """Attach sanitized status/qq_code from send result (never tokens/URLs)."""
    if not isinstance(result, Mapping):
        return
    qq_code = result.get("code", result.get("err_code"))
    if isinstance(qq_code, (int, float)) and not isinstance(qq_code, bool):
        step["qq_code"] = int(qq_code)
    status = result.get("status")
    if isinstance(status, int):
        step["status_code"] = status
        step["send_status_code"] = status


def _load_callback_envelope(callback_json: Path | None) -> Mapping[str, Any]:
    path = callback_json or DEFAULT_CALLBACK_FIXTURE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "envelope" in payload:
        envelope = payload["envelope"]
    else:
        envelope = payload
    if not isinstance(envelope, Mapping):
        raise SystemExit("callback JSON must be an object or fixture with envelope")
    return envelope


def _extract_interaction_id(envelope: Mapping[str, Any]) -> str | None:
    """Return interaction id from INTERACTION_CREATE envelope, else None."""
    data = envelope.get("d")
    if isinstance(data, Mapping):
        raw = data.get("id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    top = envelope.get("id")
    if isinstance(top, str) and top.strip() and envelope.get("t") == "INTERACTION_CREATE":
        return top.strip()
    return None


def _is_fixture_interaction_id(interaction_id: str) -> bool:
    """Fixture / demo ids must never trigger live ACK PUT."""
    upper = interaction_id.upper()
    return (
        upper.startswith("FIXTURE_")
        or "FIXTURE" in upper
        or interaction_id.startswith("evt-interaction-")
    )


def _step_callback_dry_run(
    *,
    callback_json: Path | None,
    transport: FakeMessageTransport,
) -> tuple[dict[str, Any], int]:
    puts_before = sum(1 for c in transport.calls if c.get("method") == "PUT")
    envelope = _load_callback_envelope(callback_json)
    outcome = handle_feedback_callback(
        envelope,
        received_at="2026-07-09T12:00:00+00:00",
        payload_ref="fixture://qqbot/smoke/interaction",
    )
    puts_after = sum(1 for c in transport.calls if c.get("method") == "PUT")
    put_delta = puts_after - puts_before
    idem = outcome.get("idempotency_key")
    status = outcome.get("status")
    step = {
        "ok": status == "normalized" and bool(idem),
        "status": status,
        "category": "interaction",
        "idempotency_key_present": bool(idem),
        "idempotency_key_hash": _hash16(str(idem)) if idem else None,
        "ack_skipped": True,
    }
    return step, put_delta


class _RecordingScheduler:
    """Collect post-ACK thunks and run them synchronously (avoid nested asyncio.run)."""

    def __init__(self) -> None:
        self.thunks: list[Callable[[], Any]] = []

    def __call__(self, thunk: Callable[[], Any]) -> None:
        self.thunks.append(thunk)

    def run_all(self) -> None:
        for thunk in list(self.thunks):
            result = thunk()
            if asyncio.iscoroutine(result):
                asyncio.run(result)


def _load_c2c_envelope() -> dict[str, Any]:
    payload = json.loads(C2C_MESSAGE_FIXTURE.read_text(encoding="utf-8"))
    envelope = payload.get("envelope", payload)
    if not isinstance(envelope, dict):
        raise SystemExit("C2C fixture must contain an envelope object")
    return envelope


def _sign_protocol_body(body: bytes, *, bot_secret: str = DEMO_BOT_SECRET) -> str:
    _public_key, seed = derive_keypair(bot_secret)
    return sign(seed, DEMO_SIG_TIMESTAMP.encode("utf-8") + body).hex()


def _step_protocol_path_dry_run() -> dict[str, dict[str, Any]]:
    """Mandatory host Protocol path: verify_and_ack → ingress/session → deliver.

    Uses Phase 70 ``handle_qqbot_webhook_request`` + ``build_qqbot_wired_runtime``
    with Fake transports only. Returns allowlist-safe step dicts.
    """
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    message_transport = FakeMessageTransport(
        response={"id": "fixture-protocol-msg", "status": 200}
    )
    backend = FakeBackendAdapter()
    wired = build_qqbot_wired_runtime(
        backend=backend,
        flags=RuntimeFeatureFlags(
            qqbot_channel_enabled=True,
            run_runtime_enabled=True,
        ),
        host_config=QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            bot_secret_ref="secret://qqbot/bot-secret",
        ),
        env=PROTOCOL_SECRET_ENV,
        token_manager=token_manager,
        transport=message_transport,
        token_transport=token_transport,
    )

    envelope = _load_c2c_envelope()
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Signature-Ed25519": _sign_protocol_body(body),
        "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
    }
    scheduler = _RecordingScheduler()

    status, resp_body, _ = asyncio.run(
        handle_qqbot_webhook_request(
            "POST",
            CALLBACK_PATH,
            headers,
            body,
            wired=wired,
            env=PROTOCOL_SECRET_ENV,
            post_ack_scheduler=scheduler,
            received_at=PROTOCOL_FIXED_NOW,
            reply_text=PROTOCOL_FIXTURE_REPLY,
            tenant_id="tenant-smoke",
            workspace_id="ws-smoke",
            bot_instance_id="bot-smoke",
        )
    )

    op: int | None = None
    try:
        parsed = json.loads(resp_body.decode("utf-8") if isinstance(resp_body, bytes) else resp_body)
        if isinstance(parsed, Mapping) and "op" in parsed:
            op = int(parsed["op"])
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        op = None

    ack_ok = status == 200 and op == 12 and len(scheduler.thunks) >= 1
    adapter_ack = {
        "ok": ack_ok,
        "http_status": status,
        "op": op,
        "accepted": ack_ok,
    }

    if not ack_ok:
        return {
            "adapter_ack": adapter_ack,
            "session_ingress": {
                "ok": False,
                "ingress_action": None,
                "run_id_present": False,
                "branch": "message",
            },
            "adapter_deliver": {
                "ok": False,
                "deliver_accepted": False,
                "boundary_action": None,
            },
        }

    # Post-ACK composition runs on the sync side (thunk owns its asyncio.run).
    scheduler.run_all()

    submitted = getattr(backend, "submitted_requests", None) or []
    deliveries = getattr(wired.adapter, "deliveries", None) or []
    deliver_count = getattr(message_transport, "call_count", 0) or 0
    ingress_ok = len(submitted) >= 1
    deliver_ok = deliver_count >= 1 and len(deliveries) >= 1

    session_ingress = {
        "ok": ingress_ok,
        "ingress_action": "accepted" if ingress_ok else None,
        "run_id_present": ingress_ok,
        "branch": "message",
    }
    adapter_deliver = {
        "ok": deliver_ok,
        "deliver_accepted": deliver_ok,
        "boundary_action": "allow" if deliver_ok else None,
    }
    return {
        "adapter_ack": adapter_ack,
        "session_ingress": session_ingress,
        "adapter_deliver": adapter_deliver,
    }


async def _step_callback_live(
    *,
    callback_json: Path | None,
    token_manager: TokenManager,
    transport: UrllibMessageTransport,
) -> tuple[dict[str, Any], int]:
    """Normalize always; PUT ACK only when a real (non-fixture) interaction_id is present."""
    envelope = _load_callback_envelope(callback_json)
    outcome = handle_feedback_callback(
        envelope,
        received_at="2026-07-09T12:00:00+00:00",
        payload_ref="operator://qqbot/smoke/interaction",
    )
    idem = outcome.get("idempotency_key")
    status = outcome.get("status")
    interaction_id = _extract_interaction_id(envelope)
    put_delta = 0
    ack_skipped = True
    ack_status = "skipped"

    # OQ-1: live PUT only when --callback-json yields a real interaction_id.
    if (
        callback_json is not None
        and interaction_id
        and not _is_fixture_interaction_id(interaction_id)
    ):
        try:
            await ack_interaction(
                interaction_id=interaction_id,
                token_manager=token_manager,
                transport=transport,
                code=0,
            )
            put_delta = 1
            ack_skipped = False
            ack_status = "sent"
        except SendError as exc:
            # Record sanitized failure; do not leak Authorization / tokens.
            raise SystemExit(
                f"live interaction ACK failed (status_code={exc.status_code}, "
                f"qq_code={exc.qq_code})"
            ) from None
    else:
        # OQ-1: normalize-only when no real interaction_id (ACK optional follow-up).
        ack_skipped = True
        ack_status = "skipped"

    step = {
        "ok": status == "normalized" and bool(idem),
        "status": status,
        "category": "interaction",
        "idempotency_key_present": bool(idem),
        "idempotency_key_hash": _hash16(str(idem)) if idem else None,
        "ack_skipped": ack_skipped,
        "ack_status": ack_status,
    }
    return step, put_delta


def _write_evidence(evidence: dict[str, Any], evidence_out: Path | None) -> dict[str, Any]:
    evidence = sanitize_evidence(evidence)
    if evidence_out is not None:
        evidence_out.parent.mkdir(parents=True, exist_ok=True)
        evidence_out.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return evidence


def run_smoke(
    *,
    mode: str = "dry-run",
    callback_json: Path | None = None,
    evidence_out: Path | None = None,
) -> dict[str, Any]:
    """Run smoke steps and return outcome + evidence (importable for tests)."""
    if mode not in ("dry-run", "live"):
        raise ValueError(f"unsupported mode: {mode}")

    if mode == "live":
        return _run_smoke_live(callback_json=callback_json, evidence_out=evidence_out)

    creds = load_credentials("dry-run")
    # Dry-run: Fake transports only — never construct Urllib* transports.
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id=creds["app_id"],
        client_secret=creds["client_secret"],
        transport=token_transport,
    )
    message_transport = FakeMessageTransport(response={"id": "fixture-smoke-msg", "status": 200})

    sig_step = _step_signature(bot_secret=creds["bot_secret"])
    if not sig_step["ok"]:
        raise SystemExit("signature step failed")

    text_step, keyboard_step = asyncio.run(
        _step_egress(
            token_manager=token_manager,
            transport=message_transport,
            user_openid=creds["user_openid"],
            msg_id=creds["msg_id"],
        )
    )
    if not text_step["ok"] or text_step["msg_type"] != 0:
        raise SystemExit("send_text step failed")
    if not keyboard_step["ok"] or keyboard_step["msg_type"] != 2:
        raise SystemExit("send_keyboard step failed")

    callback_step, put_delta = _step_callback_dry_run(
        callback_json=callback_json,
        transport=message_transport,
    )
    if not callback_step["ok"]:
        raise SystemExit("callback step failed")
    if put_delta != 0:
        raise SystemExit("dry-run must not PUT interaction ACK")

    # Mandatory host Protocol path (SMOKE-01) — leaf steps alone are insufficient.
    protocol_steps = _step_protocol_path_dry_run()
    for name in ("adapter_ack", "session_ingress", "adapter_deliver"):
        step = protocol_steps.get(name) or {}
        if not step.get("ok"):
            raise SystemExit(f"protocol path step failed: {name}")

    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "mode": "dry-run",
        "not_live_acceptance": True,
        "steps": {
            "signature": sig_step,
            "send_text": text_step,
            "send_keyboard": keyboard_step,
            "callback": callback_step,
            "adapter_ack": protocol_steps["adapter_ack"],
            "session_ingress": protocol_steps["session_ingress"],
            "adapter_deliver": protocol_steps["adapter_deliver"],
        },
    }
    evidence = _write_evidence(evidence, evidence_out)

    return {
        "evidence": evidence,
        "transport": "fake",
        "transport_class": type(message_transport).__name__,
        "token_transport_class": type(token_transport).__name__,
        "fake_send_count": sum(
            1 for c in message_transport.calls if c.get("method") == "POST"
        ),
        "callback_put_count": put_delta,
    }


def _run_smoke_live(
    *,
    callback_json: Path | None,
    evidence_out: Path | None,
) -> dict[str, Any]:
    """HUMAN GATE live path: fail-closed env, then Urllib OpenAPI Steps A–C.

    Never call this from CI. Credentials come from value env vars only.
    """
    # Validate env BEFORE constructing any Urllib transport (T-67-01 / Pattern 2).
    creds = load_live_credentials()

    token_transport = UrllibTokenTransport()
    token_manager = TokenManager(
        app_id=creds["app_id"],
        client_secret=creds["client_secret"],
        transport=token_transport,
    )
    message_transport = UrllibMessageTransport()

    sig_step = _step_signature(bot_secret=creds["bot_secret"])
    if not sig_step["ok"]:
        raise SystemExit("signature step failed")
    # Live signature uses operator BotSecret (not DEMO vector label).
    sig_step = {
        "ok": True,
        "vector": "live_bot_secret",
        "challenge_ok": sig_step["challenge_ok"],
    }

    text_step, keyboard_step = asyncio.run(
        _step_egress(
            token_manager=token_manager,
            transport=message_transport,
            user_openid=creds["user_openid"],
            msg_id=creds["msg_id"],
        )
    )
    if not text_step["ok"] or text_step["msg_type"] != 0:
        raise SystemExit("send_text step failed")
    if not keyboard_step["ok"] or keyboard_step["msg_type"] != 2:
        raise SystemExit("send_keyboard step failed")

    callback_step, put_delta = asyncio.run(
        _step_callback_live(
            callback_json=callback_json,
            token_manager=token_manager,
            transport=message_transport,
        )
    )
    if not callback_step["ok"]:
        raise SystemExit("callback step failed")

    # Prefer keep not_live_acceptance=true from script; human may relabel archive.
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "mode": "live",
        "not_live_acceptance": True,
        "steps": {
            "signature": sig_step,
            "send_text": text_step,
            "send_keyboard": keyboard_step,
            "callback": callback_step,
        },
    }
    evidence = _write_evidence(evidence, evidence_out)

    return {
        "evidence": evidence,
        "transport": "urllib",
        "transport_class": type(message_transport).__name__,
        "token_transport_class": type(token_transport).__name__,
        "fake_send_count": 0,
        "callback_put_count": put_delta,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="InkStatute QQBot one-click smoke test",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_const",
        const="dry-run",
        dest="mode",
        help="CI mode: fixtures + Fake transports (default)",
    )
    mode.add_argument(
        "--live",
        action="store_const",
        const="live",
        dest="mode",
        help="HUMAN GATE: real OpenAPI; requires env credentials",
    )
    parser.set_defaults(mode="dry-run")
    parser.add_argument(
        "--evidence-out",
        type=Path,
        default=None,
        help="Optional path to write sanitized evidence JSON",
    )
    parser.add_argument(
        "--callback-json",
        type=Path,
        default=None,
        help="Optional INTERACTION envelope / fixture for callback step",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        outcome = run_smoke(
            mode=args.mode,
            callback_json=args.callback_json,
            evidence_out=args.evidence_out,
        )
    except SystemExit as exc:
        # Preserve exit semantics; print message without secret values.
        msg = str(exc)
        if msg and msg != "0":
            print(msg, file=sys.stderr)
        code = exc.code if isinstance(exc.code, int) else 1
        return code if code else 1

    print(json.dumps(outcome["evidence"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
