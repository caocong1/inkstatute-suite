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
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol
from zoneinfo import ZoneInfo

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
_ISSUE_WAKEUP_QUOTA_EXHAUSTED = "qqbot_wakeup_quota_exhausted"
_ISSUE_WAKEUP_OUTSIDE_WINDOW = "qqbot_wakeup_outside_window"
_ISSUE_WAKEUP_UNSUPPORTED_SCENE = "qqbot_wakeup_unsupported_scene"

# RECALL-01: default calendar TZ for period day labels (injectable).
_DEFAULT_WAKEUP_TZ = ZoneInfo("Asia/Shanghai")

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


def build_wakeup_text_envelope(*, content: str) -> dict[str, Any]:
    """Build a C2C wakeup text envelope (msg_type=0) after output policy.

    Mutual exclusion: sets ``is_wakeup=True`` and intentionally omits
    ``msg_id`` / ``event_id`` / ``msg_seq`` (never calls ``_base_envelope``).
    """

    decision = apply_output_policy(content)
    envelope: dict[str, Any] = {
        "is_wakeup": True,
        "policy": {
            "action": decision.action,
            "reason": decision.reason,
            "audit_metadata": decision.audit_metadata,
        },
    }
    if decision.action != "block" and decision.visible_text:
        envelope.update({"msg_type": 0, "content": decision.visible_text})
    return envelope


def build_wakeup_markdown_envelope(*, content: str) -> dict[str, Any]:
    """Build a C2C wakeup markdown envelope (msg_type=2) after output policy.

    Same mutual-exclusion rules as :func:`build_wakeup_text_envelope`.
    """

    decision = apply_output_policy(content)
    envelope: dict[str, Any] = {
        "is_wakeup": True,
        "policy": {
            "action": decision.action,
            "reason": decision.reason,
            "audit_metadata": decision.audit_metadata,
        },
    }
    if decision.action != "block" and decision.visible_text:
        envelope.update(
            {
                "msg_type": 2,
                "markdown": {"content": decision.visible_text},
                "content": "",
            }
        )
    return envelope


def strip_for_wire(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without audit-only keys for QQ OpenAPI POST."""

    return {key: value for key, value in envelope.items() if key not in _WIRE_AUDIT_KEYS}


class WakeupPeriodId(str, Enum):
    """RECALL-01 30-day interaction-recall period identifiers."""

    P0_SAME_DAY = "p0_same_day"
    P1_1_3 = "p1_1_3"
    P2_3_7 = "p2_3_7"
    P3_7_30 = "p3_7_30"


@dataclass(frozen=True)
class WakeupQuotaResult:
    """Outcome of RECALL-01 wakeup period quota check."""

    ok: bool
    period_id: WakeupPeriodId | None = None
    issue_code: str | None = None
    interim_notice: str | None = None


class WakeupPeriodStore(Protocol):
    """Injectable store for wakeup period accounting (process-local by default)."""

    def note_user_message(self, user_openid: str, at: datetime) -> None:
        """Record a user-initiated message; reset basis on a later calendar day."""
        ...

    def last_user_message_at(self, user_openid: str) -> datetime | None:
        """Return the current period basis timestamp for ``user_openid``, if any."""
        ...

    def has_sent(self, user_openid: str, period_id: WakeupPeriodId | str) -> bool:
        """True when a wakeup was already recorded for (openid, period)."""
        ...

    def record_send(self, user_openid: str, period_id: WakeupPeriodId | str) -> None:
        """Record a successful wakeup send for (openid, period)."""
        ...


class InMemoryWakeupPeriodStore:
    """Process-local wakeup period store (host may inject a durable impl later)."""

    def __init__(self, *, tz: Any | None = None) -> None:
        self._tz = tz if tz is not None else _DEFAULT_WAKEUP_TZ
        self._basis: dict[str, datetime] = {}
        self._sent: dict[str, set[str]] = {}

    def _calendar_day(self, value: datetime) -> date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self._tz).date()

    def note_user_message(self, user_openid: str, at: datetime) -> None:
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        prior = self._basis.get(user_openid)
        if prior is None or self._calendar_day(at) > self._calendar_day(prior):
            # Later calendar day → reset period basis and send ledger.
            self._basis[user_openid] = at
            self._sent[user_openid] = set()
            return
        # Same (or earlier) day: refresh basis timestamp without clearing sends.
        self._basis[user_openid] = at

    def last_user_message_at(self, user_openid: str) -> datetime | None:
        return self._basis.get(user_openid)

    def has_sent(self, user_openid: str, period_id: WakeupPeriodId | str) -> bool:
        key = period_id.value if isinstance(period_id, WakeupPeriodId) else str(period_id)
        return key in self._sent.get(user_openid, set())

    def record_send(self, user_openid: str, period_id: WakeupPeriodId | str) -> None:
        key = period_id.value if isinstance(period_id, WakeupPeriodId) else str(period_id)
        self._sent.setdefault(user_openid, set()).add(key)


def wakeup_scene_supported(scene: str | None) -> bool:
    """RECALL-01: ``is_wakeup`` is C2C-only; group/other scenes fail closed."""

    return scene == "c2c"


def _resolve_now(
    now: datetime | Callable[[], datetime] | None,
) -> datetime:
    if now is None:
        return _default_clock()
    if callable(now):
        value = now()
    else:
        value = now
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _period_for_day_delta(day_delta: int) -> WakeupPeriodId | None:
    """Map calendar-day delta (Asia/Shanghai labels) to P0–P3.

    Half-open boundaries (documented in SUMMARY):
    - P0: day_delta == 0 (same calendar day as T0)
    - P1: 1 <= day_delta <= 3
    - P2: 3 < day_delta <= 7
    - P3: 7 < day_delta <= 30
    - else: outside 30-day window
    """

    if day_delta == 0:
        return WakeupPeriodId.P0_SAME_DAY
    if 1 <= day_delta <= 3:
        return WakeupPeriodId.P1_1_3
    if 3 < day_delta <= 7:
        return WakeupPeriodId.P2_3_7
    if 7 < day_delta <= 30:
        return WakeupPeriodId.P3_7_30
    return None


def check_wakeup_quota(
    user_openid: str,
    last_user_message_at: datetime | None = None,
    *,
    now: datetime | Callable[[], datetime] | None = None,
    store: WakeupPeriodStore | None = None,
    tz: Any | None = None,
) -> WakeupQuotaResult:
    """Enforce RECALL-01: 1 wakeup send per (openid, period) within 30 days.

    Period calendar-day labels use ``tz`` (default Asia/Shanghai). ``now`` may be
    a datetime or a zero-arg callable (injectable clock). When
    ``last_user_message_at`` is omitted, the store's recorded basis is used.
    """

    seed = user_openid or "wakeup-quota"
    tzinfo = tz if tz is not None else _DEFAULT_WAKEUP_TZ
    current = _resolve_now(now)

    basis = last_user_message_at
    if basis is None and store is not None:
        basis = store.last_user_message_at(user_openid)
    if basis is None:
        return WakeupQuotaResult(
            ok=False,
            issue_code=_ISSUE_WAKEUP_OUTSIDE_WINDOW,
            interim_notice=build_owned_notice("long_processing", seed=seed),
        )
    if basis.tzinfo is None:
        basis = basis.replace(tzinfo=timezone.utc)

    basis_day = basis.astimezone(tzinfo).date()
    now_day = current.astimezone(tzinfo).date()
    day_delta = (now_day - basis_day).days
    period_id = _period_for_day_delta(day_delta)
    if period_id is None:
        return WakeupQuotaResult(
            ok=False,
            issue_code=_ISSUE_WAKEUP_OUTSIDE_WINDOW,
            interim_notice=build_owned_notice("long_processing", seed=seed),
        )

    if store is not None and store.has_sent(user_openid, period_id):
        return WakeupQuotaResult(
            ok=False,
            period_id=period_id,
            issue_code=_ISSUE_WAKEUP_QUOTA_EXHAUSTED,
            interim_notice=build_owned_notice("long_processing", seed=seed),
        )

    return WakeupQuotaResult(ok=True, period_id=period_id)


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
        attempts: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.qq_code = qq_code
        self.attempts = attempts


class MessageTransport(Protocol):
    """Transport abstraction for QQ OpenAPI message POST.

    Tests inject FakeMessageTransport so no real network I/O is required.
    Optional ``put_json`` extension supports interaction ACK (INGRESS-06).
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
        return await self._dispatch(
            method="POST", url=url, authorization=authorization, body=body
        )

    async def put_json(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Record PUT like post_message; default empty-queue response is {"code": 0}."""
        return await self._dispatch(
            method="PUT",
            url=url,
            authorization=authorization,
            body=body,
            empty_default={"code": 0},
        )

    async def _dispatch(
        self,
        *,
        method: str,
        url: str,
        authorization: str,
        body: dict[str, Any],
        empty_default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        self.last_authorization = authorization
        self.calls.append(
            {
                "method": method,
                "url": url,
                "authorization": authorization,
                "body": body,
            }
        )
        if not self._queue:
            if empty_default is not None:
                return dict(empty_default)
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
    urllib is imported inside _blocking_request — never at module top level.
    """

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def post_message(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if not url.startswith(_API_BASE + "/"):
            raise SendError("QQ Bot message URL host not allowed")
        return await asyncio.to_thread(
            self._blocking_request, url, authorization, body, "POST"
        )

    async def put_json(
        self, *, url: str, authorization: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if not url.startswith(_API_BASE + "/"):
            raise SendError("QQ Bot message URL host not allowed")
        return await asyncio.to_thread(
            self._blocking_request, url, authorization, body, "PUT"
        )

    def _blocking_request(
        self,
        url: str,
        authorization: str,
        body: dict[str, Any],
        method: str,
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
            method=method,
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
    attempts: int | None = None,
) -> SendError:
    if isinstance(exc, SendError):
        return SendError(
            str(exc),
            status_code=exc.status_code if status_code is None else status_code,
            qq_code=exc.qq_code if qq_code is None else qq_code,
            attempts=exc.attempts if attempts is None else attempts,
        )
    return SendError(
        "QQ Bot message request failed",
        status_code=status_code,
        qq_code=qq_code,
        attempts=attempts,
    )


def _raise_with_attempts(err: SendError, attempts: int) -> None:
    """Attach attempts_used onto SendError and raise it."""

    err.attempts = attempts
    raise err


async def _bearer(token_manager: TokenManager) -> str:
    """Fetch a bearer token, mapping TokenError to sanitized SendError."""

    try:
        return await token_manager.get_token()
    except TokenError as exc:
        raise SendError(
            "QQ Bot token unavailable",
            status_code=getattr(exc, "status_code", None),
        ) from None


async def ack_interaction(
    *,
    interaction_id: str,
    token_manager: TokenManager,
    transport: Any,
    code: int = 0,
) -> dict[str, Any]:
    """PUT /interactions/{id} with {"code": code} (INGRESS-06 tier-2 ACK).

    Validates ``interaction_id`` with the same charset discipline as openids
    before path interpolation. Requires transport.put_json (duck-typed).
    """

    safe_id = _require_openid(interaction_id, label="interaction_id")
    put_json = getattr(transport, "put_json", None)
    if put_json is None or not callable(put_json):
        raise SendError("QQ Bot transport does not support put_json")
    token = await _bearer(token_manager)
    url = f"{_API_BASE}/interactions/{safe_id}"
    result = await put_json(
        url=url,
        authorization=f"QQBot {token}",
        body={"code": code},
    )
    qq_code = _extract_qq_code(result if isinstance(result, dict) else None)
    if qq_code is not None and qq_code != 0:
        raise SendError(
            "QQ Bot interaction ACK failed",
            qq_code=qq_code,
        )
    return result


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

async def _send_message_with_attempts(
    *,
    envelope: dict[str, Any],
    scene: str,
    token_manager: TokenManager,
    transport: MessageTransport,
    user_openid: str | None = None,
    group_openid: str | None = None,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> tuple[dict[str, Any], int]:
    """Like send_message, but also returns attempts_used from _post_with_retry."""

    body = strip_for_wire(envelope)
    url = wire_url_for_scene(
        scene, user_openid=user_openid, group_openid=group_openid
    )
    return await _post_with_retry(
        url=url,
        body=body,
        token_manager=token_manager,
        transport=transport,
        max_attempts=max_attempts,
        sleep=sleep,
    )


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

    Returns (result, attempts_used). Raised SendError.attempts is the count
    of transport POSTs actually consumed (not always max_attempts).
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
                _raise_with_attempts(last_error, attempt + 1)

            if status_code == 401 and auth_retried:
                _raise_with_attempts(last_error, attempt + 1)

            if _is_transient(status_code=status_code, qq_code=qq_code, exc=exc):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    _raise_with_attempts(last_error, attempt)
                await sleeper(delay)
                continue

            _raise_with_attempts(last_error, attempt + 1)
        except Exception as exc:
            last_error = _sanitize_send_error(exc)
            if _is_transient(status_code=None, qq_code=None, exc=exc):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    _raise_with_attempts(last_error, attempt)
                await sleeper(delay)
                continue
            _raise_with_attempts(last_error, attempt + 1)

        qq_code = _extract_qq_code(result)
        if qq_code is not None and qq_code != 0:
            status_code = None
            last_error = SendError(
                "QQ Bot message request failed",
                qq_code=qq_code,
            )
            if _is_terminal(status_code=status_code, qq_code=qq_code):
                _raise_with_attempts(last_error, attempt + 1)
            if _is_transient(status_code=status_code, qq_code=qq_code, exc=None):
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                if attempt >= max_attempts:
                    _raise_with_attempts(last_error, attempt)
                await sleeper(delay)
                continue
            _raise_with_attempts(last_error, attempt + 1)

        return result, attempt + 1

    if last_error is not None:
        _raise_with_attempts(last_error, max(attempt, 1))
    raise SendError(
        "QQ Bot message request failed after retries",
        attempts=max_attempts,
    )


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
        attempts_used = exc.attempts if exc.attempts is not None else max_attempts
        evidence = _rich_media_evidence(
            stage="upload",
            attempts=attempts_used,
            status_code=exc.status_code,
            qq_code=exc.qq_code,
            issue_code=_ISSUE_RICH_MEDIA_UPLOAD_FAILED,
        )
        # Preserve sanitized SendError; evidence available via attribute for adapters.
        exc.evidence = evidence  # type: ignore[attr-defined]
        raise

    file_info = result.get("file_info")
    if not isinstance(file_info, str) or not file_info:
        err = SendError(
            "QQ Bot rich media upload missing file_info",
            attempts=attempts,
        )
        err.evidence = _rich_media_evidence(  # type: ignore[attr-defined]
            stage="upload",
            attempts=attempts,
            issue_code=_ISSUE_RICH_MEDIA_UPLOAD_FAILED,
        )
        raise err

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
    upload_attempts = upload.get("evidence", {}).get("attempts")
    try:
        result, send_attempts = await _send_message_with_attempts(
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
        attempts_used = exc.attempts if exc.attempts is not None else max_attempts
        evidence = _rich_media_evidence(
            stage="send",
            attempts=attempts_used,
            status_code=exc.status_code,
            qq_code=exc.qq_code,
            file_uuid=upload.get("file_uuid"),
            ttl=upload.get("ttl"),
            issue_code=_ISSUE_RICH_MEDIA_SEND_FAILED,
        )
        if upload_attempts is not None:
            evidence["upload_attempts"] = upload_attempts
        evidence["send_attempts"] = attempts_used
        exc.evidence = evidence  # type: ignore[attr-defined]
        raise

    send_evidence = _rich_media_evidence(
        stage="send",
        attempts=send_attempts,
        file_uuid=upload.get("file_uuid"),
        ttl=upload.get("ttl"),
    )
    # Keep upload/send attempt counts distinct — do not overwrite upload attempts.
    result = dict(result)
    evidence: dict[str, Any] = {
        "rich_media_stage": "send",
        "send_attempts": send_attempts,
        "attempts": send_attempts,
    }
    if upload_attempts is not None:
        evidence["upload_attempts"] = upload_attempts
    if "file_uuid_hash" in send_evidence:
        evidence["file_uuid_hash"] = send_evidence["file_uuid_hash"]
    if "ttl" in send_evidence:
        evidence["ttl"] = send_evidence["ttl"]
    result["evidence"] = evidence
    return result


__all__ = [
    "FEEDBACK_ACTIONS",
    "FakeMessageTransport",
    "InMemoryWakeupPeriodStore",
    "MessageTransport",
    "PassiveReplyWindowResult",
    "SendError",
    "UrllibMessageTransport",
    "WakeupPeriodId",
    "WakeupPeriodStore",
    "WakeupQuotaResult",
    "ack_interaction",
    "build_feedback_keyboard_envelope",
    "build_markdown_envelope",
    "build_media_envelope",
    "build_text_envelope",
    "build_wakeup_markdown_envelope",
    "build_wakeup_text_envelope",
    "check_passive_reply_window",
    "check_wakeup_quota",
    "send_message",
    "send_rich_media",
    "strip_for_wire",
    "upload_rich_media",
    "wakeup_scene_supported",
    "wire_files_url_for_scene",
    "wire_url_for_scene",
]
