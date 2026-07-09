#!/usr/bin/env python3
"""InkStatute QQBot one-click smoke test (stdlib orchestrator).

Default ``--dry-run`` exercises signature verification, text + markdown+keyboard
egress, and INTERACTION callback simulation with Fake transports and public
DEMO / fixture credentials. ``--live`` is a human gate (Plan 03).

QQ-only path (no WeCom channel imports). Never commits or prints secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]

for _rel in (
    "packages/channels/qqbot/src",
    "packages/channel-core/src",
    "packages/platform-contract/src",
    "packages/platform-runtime/src",
):
    _p = REPO_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from inkstatute_channels_qqbot._ed25519 import sign  # noqa: E402
from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback  # noqa: E402
from inkstatute_channels_qqbot.sender import (  # noqa: E402
    FEEDBACK_ACTIONS,
    FakeMessageTransport,
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
)

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

LIVE_ENV_KEYS = (
    "INKSTATUTE_QQBOT_APP_ID",
    "INKSTATUTE_QQBOT_CLIENT_SECRET",
    "INKSTATUTE_QQBOT_BOT_SECRET",
    "INKSTATUTE_QQBOT_USER_OPENID",
    "INKSTATUTE_QQBOT_REPLY_MSG_ID",
)

EVIDENCE_SCHEMA = "inkstatute.qqbot.smoke_evidence.v1"


def _hash16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def sanitize_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return evidence for stdout/file.

    Plan 01 emits already-clean step evidence. Plan 02 hardens recursive
    ban-list redaction for arbitrary dirty payloads.
    """
    return json.loads(json.dumps(evidence, default=str))


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
    transport: FakeMessageTransport,
    user_openid: str,
    msg_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    text_env = build_text_envelope(
        content="墨律冒烟：文本通道",
        msg_id=msg_id,
        msg_seq=1,
    )
    await send_message(
        envelope=text_env,
        scene="c2c",
        token_manager=token_manager,
        transport=transport,
        user_openid=user_openid,
    )
    text_step = {
        "ok": True,
        "msg_type": int(text_env.get("msg_type", -1)),
        "openid_hash": _hash16(user_openid),
    }

    kb_env = build_feedback_keyboard_envelope(
        title="墨律冒烟：请评价",
        feedback_target="smoke-target-001",
        msg_id=msg_id,
        msg_seq=2,
    )
    await send_message(
        envelope=kb_env,
        scene="c2c",
        token_manager=token_manager,
        transport=transport,
        user_openid=user_openid,
    )
    keyboard_step = {
        "ok": True,
        "msg_type": int(kb_env.get("msg_type", -1)),
        "actions": list(FEEDBACK_ACTIONS),
        "openid_hash": _hash16(user_openid),
    }
    return text_step, keyboard_step


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


def _step_callback(
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
        # Never embed the raw key value if it looks like a secret; fixture keys are ok to omit.
        "idempotency_key_hash": _hash16(str(idem)) if idem else None,
    }
    return step, put_delta


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
        # Plan 03 owns full live path; fail closed if credentials incomplete.
        creds = load_credentials("live")
        raise SystemExit(
            "live mode is a HUMAN GATE — full OpenAPI path lands in Plan 03 "
            f"(credentials present for app_id={_hash16(creds['app_id'])})"
        )

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

    callback_step, put_delta = _step_callback(
        callback_json=callback_json,
        transport=message_transport,
    )
    if not callback_step["ok"]:
        raise SystemExit("callback step failed")
    if put_delta != 0:
        raise SystemExit("dry-run must not PUT interaction ACK")

    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "mode": "dry-run",
        "not_live_acceptance": True,
        "steps": {
            "signature": sig_step,
            "send_text": text_step,
            "send_keyboard": keyboard_step,
            "callback": callback_step,
        },
    }
    evidence = sanitize_evidence(evidence)

    if evidence_out is not None:
        evidence_out.parent.mkdir(parents=True, exist_ok=True)
        evidence_out.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
