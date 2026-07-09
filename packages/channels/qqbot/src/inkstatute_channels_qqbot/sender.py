"""QQ Bot egress sender — text/markdown/keyboard/media envelopes + send path.

Pure envelope builders with output-boundary enforcement, passive-reply
window gate (EGRESS-04), injectable MessageTransport with retry/auth
(EGRESS-02), and two-step rich-media upload → msg_type=7 (EGRESS-06).
Stdlib + channel_core only; dependencies = [] invariant preserved.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

from channel_core.owned_notices import build_owned_notice
from channel_core.output_policy import OutputPolicyDecision, apply_output_policy

from .token_manager import TokenError, TokenManager

FEEDBACK_ACTIONS = ("up", "down", "needs_fix", "route_wrong")

_FEEDBACK_LABELS = {
    "up": "有帮助",
    "down": "需改进",
    "needs_fix": "需要修正",
    "route_wrong": "路由错误",
}

_WIRE_AUDIT_KEYS = frozenset({"policy", "inkstatute"})

# Passive-reply limits (CONTEXT/REQUIREMENTS — C2C max replies is 4, not stale doc 5).
_C2C_MAX_AGE_SECONDS = 3600
_C2C_MAX_REPLIES = 4
_GROUP_MAX_AGE_SECONDS = 300
_GROUP_MAX_REPLIES = 5

_ISSUE_WINDOW_EXPIRED = "qqbot_passive_reply_window_expired"

_API_BASE = "https://api.sgroup.qq.com"

# Openids are path-interpolated into wire URLs — reject injection characters.
_OPENID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Bounded backoff for transient OpenAPI failures (injectable sleep; no wall-clock in tests).
_BACKOFF_SECONDS = (0.05, 0.1, 0.2)

_TERMINAL_QQ_CODES = frozenset({304027, 304026, 22009, 50006, 304003})
# 304082/304083: official rich-media upload/convert transient failures.
_TRANSIENT_QQ_CODES = frozenset({11242, 11252, 11263, 304082, 304083})
_TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 504})

_ISSUE_RICH_MEDIA_UPLOAD_FAILED = "qqbot_rich_media_upload_failed"
_ISSUE_RICH_MEDIA_SEND_FAILED = "qqbot_send_failed"


def _base_envelope(
    decision: OutputPolicyDecision,
    *,
    msg_id: str,
    msg_seq: int,
) -> dict[str, Any]:
    return {
        "msg_id": msg_id,
        "msg_seq": msg_seq,
        "policy": {
            "action": decision.action,
            "reason": decision.reason,
            "audit_metadata": decision.audit_metadata,
        },
    }


def build_text_envelope(
    *,
    content: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build a QQ text send envelope (msg_type=0) after output policy."""

    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        envelope.update({"msg_type": 0, "content": decision.visible_text})
    return envelope


def build_markdown_envelope(
    *,
    content: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build a QQ markdown send envelope (msg_type=2) after output policy."""

    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        # Group markdown companion content="" (Plan 01 / A4).
        envelope.update(
            {
                "msg_type": 2,
                "markdown": {"content": decision.visible_text},
                "content": "",
            }
        )
    return envelope


def build_feedback_keyboard_envelope(
    *,
    title: str,
    feedback_target: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build markdown + keyboard feedback card (msg_type=2) after output policy."""

    decision = apply_output_policy(title)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action == "block":
        return envelope

    visible = decision.visible_text or "请评价本次回复"
    buttons: list[dict[str, Any]] = []
    for action in FEEDBACK_ACTIONS:
        label = _FEEDBACK_LABELS[action]
        buttons.append(
            {
                "id": action,
                "render_data": {
                    "label": label,
                    "visited_label": label,
                    "style": 1,
                },
                "action": {
                    "type": 1,
                    "permission": {"type": 2},
                    "data": action,
                    "unsupport_tips": "请升级 QQ 后重试",
                },
            }
        )

    envelope.update(
        {
            "msg_type": 2,
            "markdown": {"content": visible},
            "keyboard": {"content": {"rows": [{"buttons": buttons}]}},
            "inkstatute": {"feedback_target": feedback_target},
        }
    )
    return envelope


def build_media_envelope(
    *,
    file_info: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build a QQ rich-media send envelope (msg_type=7) from upload file_info.

    No user-visible text → no output_policy pass. Group companion content is "".
    """

    return {
        "msg_id": msg_id,
        "msg_seq": msg_seq,
        "msg_type": 7,
        "media": {"file_info": file_info},
        "content": "",
    }


def strip_for_wire(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without audit-only keys for QQ OpenAPI POST."""

    return {key: value for key, value in envelope.items() if key not in _WIRE_AUDIT_KEYS}


@dataclass(frozen=True)
class PassiveReplyWindowResult:
    """Outcome of EGRESS-04 passive-reply window enforcement."""

    ok: bool
    issue_code: str | None = None
    interim_notice: str | None = None


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _parse_received_at(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_passive_reply_window(
    *,
    scene: str,
    received_at: str | None,
    reply_count: int,
    clock: Callable[[], datetime] | None = None,
    msg_id: str | None = None,
) -> PassiveReplyWindowResult:
    """Fail closed when passive-reply age/count limits are exceeded or unknown.

    Interim notice kind is ``long_processing`` (owned notice templates).
    Missing/unparseable ``received_at`` never allows send.
    """

    now = (clock or _default_clock)()
    seed = str(msg_id or received_at or "missing-received-at")

    def _expired() -> PassiveReplyWindowResult:
        return PassiveReplyWindowResult(
            ok=False,
            issue_code=_ISSUE_WINDOW_EXPIRED,
            interim_notice=build_owned_notice("long_processing", seed=seed),
        )

    if scene == "c2c":
        max_age = _C2C_MAX_AGE_SECONDS
        max_replies = _C2C_MAX_REPLIES
    elif scene == "group":
        max_age = _GROUP_MAX_AGE_SECONDS
        max_replies = _GROUP_MAX_REPLIES
    else:
        return _expired()

    if received_at is None or (isinstance(received_at, str) and not received_at.strip()):
        return _expired()

    parsed = _parse_received_at(received_at)
    if parsed is None:
        return _expired()

    age_seconds = (now - parsed).total_seconds()
    if age_seconds < 0:
        age_seconds = 0.0

    if age_seconds >= max_age or reply_count >= max_replies:
        return _expired()

    return PassiveReplyWindowResult(ok=True)


class SendError(Exception):
    """QQ message send failure with a sanitized message (never includes tokens)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        qq_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.qq_code = qq_code


class MessageTransport(Protocol):
    """Transport abstraction for QQ OpenAPI message POST.

    Tests inject FakeMessageTransport so no real network I/O is required.
    """

    async def post_message(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST JSON body; return parsed JSON or raise SendError."""
        ...


class FakeMessageTransport:
    """Convenience fake transport for tests (no HTTP client required)."""

    def __init__(
        self,
        *,
        responses: list[Any] | None = None,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._queue: list[Any] = list(responses) if responses is not None else []
        if responses is None:
            if error is not None:
                self._queue.append(error)
            elif response is not None:
                self._queue.append(response)
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []
        self.last_authorization: str | None = None

    async def post_message(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.call_count += 1
        self.last_authorization = authorization
        self.calls.append(
            {"url": url, "authorization": authorization, "body": body}
        )
        if not self._queue:
            return {"id": "fixture-message", "status": 200}
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return item
        raise SendError("FakeMessageTransport queued invalid response")


class UrllibMessageTransport:
    """Production transport using lazy urllib.request + asyncio.to_thread.

    Host is constrained via wire_url_for_scene (api.sgroup.qq.com only).
    urllib is imported inside _blocking_post — never at module top level.
    """

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def post_message(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if not url.startswith(_API_BASE + "/"):
            raise SendError("QQ Bot message URL host not allowed")
        return await asyncio.to_thread(
            self._blocking_post, url, authorization, body
        )

    def _blocking_post(
        self, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": authorization,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {"status": getattr(resp, "status", 200)}
                parsed = json.loads(raw)
        except urllib.error.HTTPError as exc:
            qq_code = _qq_code_from_http_error(exc)
            raise SendError(
                "QQ Bot message request failed",
                status_code=exc.code,
                qq_code=qq_code,
            ) from None
        except urllib.error.URLError:
            raise SendError("QQ Bot message endpoint unreachable") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise SendError("QQ Bot message response invalid") from None
        if not isinstance(parsed, dict):
            raise SendError("QQ Bot message response invalid")
        return parsed


def _qq_code_from_http_error(exc: Any) -> int | None:
    try:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    code = parsed.get("code", parsed.get("err_code"))
    if isinstance(code, bool) or not isinstance(code, (int, float)):
        return None
    return int(code)


def _require_openid(value: str, *, label: str) -> str:
    if not _OPENID_RE.fullmatch(value):
        raise SendError(f"invalid {label}")
    return value


def wire_url_for_scene(
    scene: str,
    *,
    user_openid: str | None = None,
    group_openid: str | None = None,
) -> str:
    """Build hardcoded api.sgroup.qq.com message URL for C2C or group."""

    if scene == "c2c":
        if not user_openid:
            raise SendError("C2C send requires user_openid")
        safe = _require_openid(user_openid, label="user_openid")
        return f"{_API_BASE}/v2/users/{safe}/messages"
    if scene == "group":
        if not group_openid:
            raise SendError("group send requires group_openid")
        safe = _require_openid(group_openid, label="group_openid")
        return f"{_API_BASE}/v2/groups/{safe}/messages"
    raise SendError("unsupported QQ Bot scene")


def wire_files_url_for_scene(
    scene: str,
    *,
    user_openid: str | None = None,
    group_openid: str | None = None,
) -> str:
    """Build hardcoded api.sgroup.qq.com rich-media upload URL for C2C or group."""

    if scene == "c2c":
        if not user_openid:
            raise SendError("C2C upload requires user_openid")
        safe = _require_openid(user_openid, label="user_openid")
        return f"{_API_BASE}/v2/users/{safe}/files"
    if scene == "group":
        if not group_openid:
            raise SendError("group upload requires group_openid")
        safe = _require_openid(group_openid, label="group_openid")
        return f"{_API_BASE}/v2/groups/{safe}/files"
    raise SendError("unsupported QQ Bot scene")


def _extract_qq_code(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    code = payload.get("code", payload.get("err_code"))
    if isinstance(code, bool) or not isinstance(code, (int, float)):
        return None
    return int(code)


def _is_transient(
    *,
    status_code: int | None,
    qq_code: int | None,
    exc: BaseException | None,
) -> bool:
    if status_code in _TRANSIENT_HTTP_STATUSES:
        return True
    if qq_code in _TRANSIENT_QQ_CODES:
        return True
    if qq_code is not None and 504000 <= qq_code <= 504999:
        return True
    if exc is not None and not isinstance(exc, SendError):
        # URLError / timeout / unexpected transport errors are transient.
        return True
    if isinstance(exc, SendError):
        if exc.status_code in _TRANSIENT_HTTP_STATUSES:
            return True
        if exc.qq_code in _TRANSIENT_QQ_CODES:
            return True
        if exc.qq_code is not None and 504000 <= exc.qq_code <= 504999:
            return True
        if exc.status_code is None and exc.qq_code is None:
            # Unreachable / invalid response without codes → treat as transient.
            msg = str(exc).lower()
            if "unreachable" in msg or "timeout" in msg:
                return True
    return False


def _is_terminal(*, status_code: int | None, qq_code: int | None) -> bool:
    if qq_code in _TERMINAL_QQ_CODES:
        return True
    return False


def _sanitize_send_error(
    exc: BaseException,
    *,
    status_code: int | None = None,
    qq_code: int | None = None,
) -> SendError:
    if isinstance(exc, SendError):
        return SendError(
            str(exc),
            status_code=exc.status_code if status_code is None else status_code,
            qq_code=exc.qq_code if qq_code is None else qq_code,
        )
    return SendError(
        "QQ Bot message request failed",
        status_code=status_code,
        qq_code=qq_code,
    )


async def _bearer(token_manager: TokenManager) -> str:
    """Fetch a bearer token, mapping TokenError to sanitized SendError."""

    try:
        return await token_manager.get_token()
    except TokenError as exc:
        raise SendError(
            "QQ Bot token unavailable",
            status_code=getattr(exc, "status_code", None),
        ) from None


async def send_message(
    *,
    envelope: dict[str, Any],
    scene: str,
    token_manager: TokenManager,
    transport: MessageTransport,
    user_openid: str | None = None,
    group_openid: str | None = None,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """POST strip_for_wire(envelope) with TokenManager bearer; retry transients.

    Backoff schedule: 0.05 / 0.1 / 0.2s (injectable sleep). HTTP 401 invalidates
    the token and refreshes once. Terminal QQ codes do not retry.
    """

    body = strip_for_wire(envelope)
    url = wire_url_for_scene(
        scene, user_openid=user_openid, group_openid=group_openid
    )
    result, _attempts = await _post_with_retry(
        url=url,
        body=body,
        token_manager=token_manager,
        transport=transport,
        max_attempts=max_attempts,
        sleep=sleep,
    )
    return result


def _rich_media_evidence(
    *,
    stage: str,
    attempts: int,
    status_code: int | None = None,
    qq_code: int | None = None,
    file_uuid: str | None = None,
    ttl: int | None = None,
    issue_code: str | None = None,
) -> dict[str, Any]:
    """Build sanitized rich-media evidence (never tokens, URLs, or file_data)."""

    out: dict[str, Any] = {
        "rich_media_stage": stage,
        "attempts": attempts,
    }
    if status_code is not None:
        out["send_status_code"] = status_code
    if qq_code is not None:
        out["send_qq_code"] = qq_code
    if file_uuid:
        out["file_uuid_hash"] = hashlib.sha256(
            file_uuid.encode("utf-8")
        ).hexdigest()[:16]
    if ttl is not None:
        out["ttl"] = ttl
    if issue_code:
        out["issue_code"] = issue_code
    return out


def _https_file_url_or_raise(file_url: str | None) -> str | None:
    """Return validated https URL, or None when caller will use file_data only."""

    if file_url is None:
        return None
    if not isinstance(file_url, str) or not file_url.strip():
        raise SendError(
            "QQ Bot rich media file_url invalid",
            qq_code=None,
        )
    text = file_url.strip()
    if not text.lower().startswith("https://"):
        raise SendError("QQ Bot rich media file_url must be https")
    return text


async def _post_with_retry(
    *,
    url: str,
    body: dict[str, Any],
    token_manager: TokenManager,
    transport: MessageTransport,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> tuple[dict[str, Any], int]:
    """POST JSON via MessageTransport with Phase 62 retry/auth semantics.

    Returns (result, attempts_used).
    """

    sleeper = sleep or asyncio.sleep
    token = await _bearer(token_manager)
    auth_retried = False
    attempt = 0
    last_error: SendError | None = None

    while attempt < max_attempts:
        authorization = f"QQBot {token}"
        try:
            result = await transport.post_message(
                url=url, authorization=authorization, body=body
            )
        except SendError as exc:
            status_code = exc.status_code
            qq_code = exc.qq_code
            last_error = _sanitize_send_error(exc)

            if status_code == 401 and not auth_retried:
                token_manager.invalidate()
                token = await _bearer(token_manager)
                auth_retried = True
                attempt += 1
                continue

            if _is_terminal(status_code=status_code, qq_code=qq_code):
                raise last_error from None

            if status_code == 401 and auth_retried:
                raise last_error from None

            if _is_transient(status_code=status_code, qq_code=qq_code, exc=exc):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    raise last_error from None
                await sleeper(delay)
                continue

            raise last_error from None
        except Exception as exc:
            last_error = _sanitize_send_error(exc)
            if _is_transient(status_code=None, qq_code=None, exc=exc):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    raise last_error from None
                await sleeper(delay)
                continue
            raise last_error from None

        qq_code = _extract_qq_code(result)
        if qq_code is not None and qq_code != 0:
            status_code = None
            last_error = SendError(
                "QQ Bot message request failed",
                qq_code=qq_code,
            )
            if _is_terminal(status_code=status_code, qq_code=qq_code):
                raise last_error
            if _is_transient(status_code=status_code, qq_code=qq_code, exc=None):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    raise last_error
                await sleeper(delay)
                continue
            raise last_error

        return result, attempt + 1

    if last_error is not None:
        raise last_error
    raise SendError("QQ Bot message request failed after retries")


async def upload_rich_media(
    *,
    scene: str,
    token_manager: TokenManager,
    transport: MessageTransport,
    file_type: int = 4,
    file_url: str | None = None,
    file_data: str | None = None,
    user_openid: str | None = None,
    group_openid: str | None = None,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """POST scene-scoped /files upload; return file_info + sanitized evidence.

    Prefers https ``file_url``. Accepts ``file_data`` only when explicitly passed
    (fixtures/offline). Never returns tokens, URLs, or file_data in evidence.
    """

    url = wire_files_url_for_scene(
        scene, user_openid=user_openid, group_openid=group_openid
    )

    body: dict[str, Any] = {"file_type": file_type}
    try:
        validated_url = _https_file_url_or_raise(file_url)
    except SendError as exc:
        # Attach sanitized evidence for callers that inspect result metadata.
        raise SendError(str(exc)) from None

    if validated_url is not None:
        body["url"] = validated_url
    elif file_data is not None:
        body["file_data"] = file_data
    else:
        raise SendError("QQ Bot rich media requires https file_url or file_data")

    try:
        result, attempts = await _post_with_retry(
            url=url,
            body=body,
            token_manager=token_manager,
            transport=transport,
            max_attempts=max_attempts,
            sleep=sleep,
        )
    except SendError as exc:
        evidence = _rich_media_evidence(
            stage="upload",
            attempts=max_attempts,
            status_code=exc.status_code,
            qq_code=exc.qq_code,
            issue_code=_ISSUE_RICH_MEDIA_UPLOAD_FAILED,
        )
        # Preserve sanitized SendError; evidence available via attribute for adapters.
        exc.evidence = evidence  # type: ignore[attr-defined]
        raise

    file_info = result.get("file_info")
    if not isinstance(file_info, str) or not file_info:
        raise SendError("QQ Bot rich media upload missing file_info")

    file_uuid = result.get("file_uuid")
    ttl_raw = result.get("ttl")
    ttl: int | None
    if isinstance(ttl_raw, bool) or not isinstance(ttl_raw, (int, float)):
        ttl = None
    else:
        ttl = int(ttl_raw)

    uuid_str = file_uuid if isinstance(file_uuid, str) else None
    evidence = _rich_media_evidence(
        stage="upload",
        attempts=attempts,
        file_uuid=uuid_str,
        ttl=ttl,
    )
    return {
        "file_info": file_info,
        "file_uuid": uuid_str,
        "ttl": ttl,
        "evidence": evidence,
    }


async def send_rich_media(
    *,
    scene: str,
    token_manager: TokenManager,
    transport: MessageTransport,
    file_url: str | None = None,
    file_data: str | None = None,
    file_type: int = 4,
    user_openid: str | None = None,
    group_openid: str | None = None,
    msg_id: str,
    msg_seq: int = 1,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Two-step rich media: upload → msg_type=7 media envelope → send_message."""

    upload = await upload_rich_media(
        scene=scene,
        token_manager=token_manager,
        transport=transport,
        file_type=file_type,
        file_url=file_url,
        file_data=file_data,
        user_openid=user_openid,
        group_openid=group_openid,
        max_attempts=max_attempts,
        sleep=sleep,
    )
    envelope = build_media_envelope(
        file_info=upload["file_info"],
        msg_id=msg_id,
        msg_seq=msg_seq,
    )
    try:
        result = await send_message(
            envelope=envelope,
            scene=scene,
            token_manager=token_manager,
            transport=transport,
            user_openid=user_openid,
            group_openid=group_openid,
            max_attempts=max_attempts,
            sleep=sleep,
        )
    except SendError as exc:
        evidence = _rich_media_evidence(
            stage="send",
            attempts=max_attempts,
            status_code=exc.status_code,
            qq_code=exc.qq_code,
            file_uuid=upload.get("file_uuid"),
            ttl=upload.get("ttl"),
            issue_code=_ISSUE_RICH_MEDIA_SEND_FAILED,
        )
        exc.evidence = evidence  # type: ignore[attr-defined]
        raise

    send_evidence = _rich_media_evidence(
        stage="send",
        attempts=1,
        file_uuid=upload.get("file_uuid"),
        ttl=upload.get("ttl"),
    )
    # Aggregate upload+send sanitized evidence for DeliveryResult.metadata.
    result = dict(result)
    result["evidence"] = {
        **upload.get("evidence", {}),
        **send_evidence,
        "rich_media_stage": "send",
    }
    return result


__all__ = [
    "FEEDBACK_ACTIONS",
    "FakeMessageTransport",
    "MessageTransport",
    "PassiveReplyWindowResult",
    "SendError",
    "UrllibMessageTransport",
    "build_feedback_keyboard_envelope",
    "build_markdown_envelope",
    "build_media_envelope",
    "build_text_envelope",
    "check_passive_reply_window",
    "send_message",
    "send_rich_media",
    "strip_for_wire",
    "upload_rich_media",
    "wire_files_url_for_scene",
    "wire_url_for_scene",
]
