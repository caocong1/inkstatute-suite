#!/usr/bin/env python3
"""Run an InkStatute-owned live WeCom bridge for the 155 AI Bot.

This is an operator-run bridge for Phase 8 live validation. It connects to the
WeCom AI Bot WebSocket directly, calls Hermes lawfirm only through one-shot
agent invocation, applies the InkStatute output boundary, and sends ordinary
user replies from this process rather than from Hermes gateway.

Runtime secrets are read from the external lawfirm profile .env file and are
never written to this repository.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = Path(os.environ.get("INKSTATUTE_HERMES_AGENT_ROOT", "/home/sorawatcher/.hermes/hermes-agent"))
LAWFIRM_HOME = Path(os.environ.get("INKSTATUTE_LAWFIRM_HOME", "/home/sorawatcher/.hermes/profiles/lawfirm"))
HERMES_PYTHON = Path(
    os.environ.get(
        "INKSTATUTE_HERMES_PYTHON",
        "/home/sorawatcher/.hermes/hermes-agent/venv/bin/python",
    )
)
RUNTIME_DIR = Path(os.environ.get("INKSTATUTE_WECOM_RUNTIME_DIR", "/tmp/inkstatute-wecom-live"))

sys.path.insert(0, str(HERMES_ROOT))
sys.path.insert(0, str(REPO_ROOT / "services/wecom-service/src"))
sys.path.insert(0, str(REPO_ROOT / "packages/platform-contract/src"))

from gateway.config import PlatformConfig  # noqa: E402
from gateway.platforms.base import BasePlatformAdapter  # noqa: E402
from plugins.platforms.wecom.adapter import WeComAdapter  # noqa: E402
from tools.credential_files import to_agent_visible_cache_path  # noqa: E402
from wecom_service.active_task_router import AdapterTaskCapabilities, route_active_task_turn  # noqa: E402
from wecom_service.output_policy import apply_output_policy  # noqa: E402
from wecom_service.owned_notices import build_owned_notice  # noqa: E402
from wecom_service.task_flow import (  # noqa: E402
    TaskFlow,
    TaskFlowConfig,
    WeComTaskStage,
    create_task_flow,
    progress_notice_due,
    record_stage,
    task_snapshot,
)


LOGGER = logging.getLogger("inkstatute.wecom.live_bridge")

HERMES_ONE_SHOT_CAPABILITIES = AdapterTaskCapabilities(
    supports_live_task_update=False,
    supports_cancel=False,
    supports_streaming_progress=False,
    supports_parallel_tasks=False,
)


@dataclass(frozen=True)
class BridgeConfig:
    chat_id: str
    bot_id: str
    secret: str
    websocket_url: str
    hermes_timeout_seconds: int
    send_ack: bool
    turn_buffer_seconds: float
    long_task_notice_interval_seconds: float
    runtime_dir: Path


@dataclass
class PendingTurn:
    event: Any
    task: asyncio.Task[None]


class InkStatuteWeComBridge(WeComAdapter):
    """WeCom adapter with an InkStatute-owned message handler."""

    def __init__(self, config: PlatformConfig, bridge_config: BridgeConfig) -> None:
        super().__init__(config)
        self.bridge_config = bridge_config
        self.events_path = bridge_config.runtime_dir / "contract-events.jsonl"
        self._tasks: set[asyncio.Task[None]] = set()
        self._pending_turns: dict[str, PendingTurn] = {}
        self._active_task_flows: dict[str, TaskFlow] = {}
        self._send_idempotency_keys: set[str] = set()

    async def handle_message(self, event: Any) -> None:
        """Accept an inbound WeCom event and process it in the background."""

        turn = _turn_record(event, stage="received")
        _append_jsonl(self.events_path, turn)
        LOGGER.info(
            "received message_id=%s chat_id=%s text_sha=%s text_len=%s",
            turn.get("message_id"),
            turn.get("chat_id"),
            turn.get("text_sha256_16"),
            turn.get("text_length"),
        )

        self._enqueue_turn(event)

    def _enqueue_turn(self, event: Any) -> None:
        key = _turn_key(event)
        pending = self._pending_turns.get(key)
        if pending is None:
            task = asyncio.create_task(self._flush_turn(key))
            self._pending_turns[key] = PendingTurn(event=event, task=task)
            return

        _merge_event(pending.event, event)
        if not pending.task.done():
            pending.task.cancel()
        pending.task = asyncio.create_task(self._flush_turn(key))

    async def _flush_turn(self, key: str) -> None:
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(self.bridge_config.turn_buffer_seconds)
        except asyncio.CancelledError:
            return

        pending = self._pending_turns.get(key)
        if pending is None or pending.task is not current_task:
            return
        self._pending_turns.pop(key, None)

        event = pending.event
        _append_jsonl(self.events_path, _turn_record(event, stage="turn_ready"))

        active_task = self._active_task_flows.get(key)
        if active_task and active_task.active:
            await self._handle_active_task_followup(event, active_task)
            return
        if active_task and not active_task.active:
            self._active_task_flows.pop(key, None)

        flow = create_task_flow(
            conversation_id=str(getattr(getattr(event, "source", None), "chat_id", "") or ""),
            user_id=str(getattr(getattr(event, "source", None), "user_id", "") or ""),
            message_id=str(getattr(event, "message_id", "") or ""),
            text=str(getattr(event, "text", "") or ""),
            media_types=list(getattr(event, "media_types", []) or []),
            raw_payload_ref=_raw_payload_ref(event),
            config=TaskFlowConfig(
                progress_interval_seconds=self.bridge_config.long_task_notice_interval_seconds,
                timeout_seconds=self.bridge_config.hermes_timeout_seconds,
            ),
        )
        _append_jsonl(self.events_path, flow.stage_records[-1].as_event())
        queued = record_stage(
            flow,
            WeComTaskStage.QUEUED,
            metadata={
                "adapter_mode": "hermes",
                "adapter_invocation": "one_shot_background",
                "adapter_capabilities": HERMES_ONE_SHOT_CAPABILITIES.as_metadata(),
            },
        )
        _append_jsonl(self.events_path, queued.as_event())

        if self.bridge_config.send_ack:
            await self._send_owned_notice(
                event,
                build_owned_notice("processing", seed=flow.task_id),
                stage="ack_sent",
                task_id=flow.task_id,
                idempotency_key=queued.idempotency_key,
            )

        self._active_task_flows[key] = flow
        task = asyncio.create_task(self._process_event(key, event, flow))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle_active_task_followup(self, event: Any, active_task: TaskFlow) -> None:
        decision = route_active_task_turn(
            text=str(getattr(event, "text", "") or ""),
            active_task=task_snapshot(active_task),
            capabilities=HERMES_ONE_SHOT_CAPABILITIES,
            raw_payload_ref=_raw_payload_ref(event),
        )
        _append_jsonl(
            self.events_path,
            {
                **_turn_record(event, stage="active_task_followup"),
                **decision.as_event(),
                "task_snapshot": task_snapshot(active_task),
            },
        )
        await self._send_owned_notice(
            event,
            build_owned_notice(decision.notice_kind, seed=f"{decision.task_id}:{decision.route.value}"),
            stage=f"active_task_{decision.route.value}",
            task_id=decision.task_id,
            idempotency_key=(
                f"wecom-active:{decision.task_id}:{getattr(event, 'message_id', '')}:{decision.route.value}"
            ),
        )

    async def _process_event(self, key: str, event: Any, flow: TaskFlow) -> None:
        running = record_stage(
            flow,
            WeComTaskStage.RUNNING,
            metadata={
                "execution_lane": "background_task",
                "control_plane": "active_task_router",
                "service_owned_progress": True,
                "model_reasoning_forwarded": False,
            },
        )
        _append_jsonl(self.events_path, running.as_event())
        progress_task: asyncio.Task[None] | None = None
        if self.bridge_config.long_task_notice_interval_seconds > 0:
            progress_task = asyncio.create_task(
                self._send_long_task_notices(event, flow, self.bridge_config.long_task_notice_interval_seconds)
            )
        try:
            answer = await asyncio.to_thread(
                _call_hermes_lawfirm,
                str(getattr(event, "text", "") or ""),
                list(getattr(event, "media_urls", []) or []),
                list(getattr(event, "media_types", []) or []),
                timeout_seconds=self.bridge_config.hermes_timeout_seconds,
            )
            delivery = await self._deliver_answer(event, answer)
            if delivery.get("file_count"):
                artifact_ready = record_stage(
                    flow,
                    WeComTaskStage.ARTIFACT_READY,
                    metadata={
                        "file_count": delivery.get("file_count", 0),
                        "artifact_refs_only": True,
                    },
                )
                _append_jsonl(self.events_path, artifact_ready.as_event())
            completed = record_stage(
                flow,
                WeComTaskStage.COMPLETED,
                metadata={
                    "policy_action": delivery.get("policy_action"),
                    "policy_reason": delivery.get("policy_reason"),
                    "send_success": delivery.get("send_success"),
                    "file_count": delivery.get("file_count", 0),
                },
            )
            _append_jsonl(self.events_path, completed.as_event())
            _append_jsonl(
                self.events_path,
                {
                    **_turn_record(event, stage="result_sent"),
                    **delivery,
                    "task_id": flow.task_id,
                    "trace_id": flow.trace_id,
                },
            )
            if delivery["send_success"]:
                LOGGER.info(
                    "sent result text_message_id=%s file_count=%s",
                    delivery.get("wecom_message_id"),
                    delivery.get("file_count"),
                )
            else:
                LOGGER.error("failed to send result: %s", delivery.get("send_error"))
        except TimeoutError as exc:
            LOGGER.exception("event processing timed out")
            timeout = record_stage(
                flow,
                WeComTaskStage.TIMEOUT,
                metadata={
                    "error_category": "runtime_error",
                    "error_code": "agent_backend_timeout",
                    "retryable": True,
                    "timeout_seconds": self.bridge_config.hermes_timeout_seconds,
                },
            )
            _append_jsonl(self.events_path, timeout.as_event())
            await self._send_owned_notice(
                event,
                build_owned_notice("timeout", seed=flow.task_id),
                stage="processing_timeout",
                error=str(exc),
                task_id=flow.task_id,
                idempotency_key=timeout.idempotency_key,
            )
        except Exception as exc:
            LOGGER.exception("event processing failed")
            failed = record_stage(
                flow,
                WeComTaskStage.FAILED,
                metadata={
                    "error_category": "runtime_error",
                    "error_code": "agent_backend_failed",
                    "retryable": True,
                },
            )
            _append_jsonl(self.events_path, failed.as_event())
            await self._send_owned_notice(
                event,
                build_owned_notice("failed", seed=flow.task_id),
                stage="processing_failed",
                error=str(exc),
                task_id=flow.task_id,
                idempotency_key=failed.idempotency_key,
            )
        finally:
            if progress_task and not progress_task.done():
                progress_task.cancel()
            if self._active_task_flows.get(key) is flow:
                self._active_task_flows.pop(key, None)

    async def _send_long_task_notices(self, event: Any, flow: TaskFlow, interval_seconds: float) -> None:
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                if not progress_notice_due(flow):
                    continue
                progress = record_stage(
                    flow,
                    WeComTaskStage.PROGRESS_NOTICE_DUE,
                    metadata={
                        "progress_notice_owner": "inkstatute_wecom_service",
                        "model_reasoning_forwarded": False,
                    },
                )
                _append_jsonl(self.events_path, progress.as_event())
                await self._send_owned_notice(
                    event,
                    build_owned_notice("long_processing", seed=progress.idempotency_key),
                    stage="long_task_notice_sent",
                    task_id=flow.task_id,
                    idempotency_key=progress.idempotency_key,
                )
        except asyncio.CancelledError:
            return
        except Exception:
            LOGGER.exception("long task notice failed")

    async def _deliver_answer(self, event: Any, answer: str) -> dict[str, Any]:
        media_files, cleaned = self.extract_media(answer)
        media_files = BasePlatformAdapter.filter_media_delivery_paths(media_files)
        local_files, cleaned = self.extract_local_files(cleaned)
        local_files = BasePlatformAdapter.filter_local_delivery_paths(local_files)
        file_paths = _dedupe([media_path for media_path, _is_voice in media_files] + local_files)

        decision = apply_output_policy(cleaned)
        visible_text = str(decision.visible_text or "").strip()
        if decision.action == "block":
            visible_text = "" if file_paths else build_owned_notice("blocked")

        text_result = None
        if visible_text:
            text_result = await self.send(
                chat_id=event.source.chat_id,
                content=visible_text,
                reply_to=getattr(event, "message_id", None),
            )

        file_results = []
        for file_path in file_paths:
            result = await self.send_document(
                chat_id=event.source.chat_id,
                file_path=file_path,
                reply_to=getattr(event, "message_id", None),
            )
            file_results.append(result)

        if not visible_text and not file_paths:
            visible_text = build_owned_notice("blocked")
            text_result = await self.send(
                chat_id=event.source.chat_id,
                content=visible_text,
                reply_to=getattr(event, "message_id", None),
            )

        send_results = [result for result in [text_result, *file_results] if result is not None]
        errors = [str(result.error) for result in send_results if not result.success and result.error]
        return {
            "policy_action": decision.action,
            "policy_reason": decision.reason,
            "output_sha256_16": _sha16(visible_text),
            "output_length": len(visible_text),
            "file_count": len(file_paths),
            "file_send_success_count": sum(1 for result in file_results if result.success),
            "send_success": bool(send_results) and all(result.success for result in send_results),
            "send_error": "; ".join(errors) or None,
            "wecom_message_id": getattr(text_result, "message_id", None),
        }

    async def _send_owned_notice(
        self,
        event: Any,
        text: str,
        *,
        stage: str,
        error: str | None = None,
        task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        send_key = idempotency_key or f"wecom-notice:{getattr(event, 'message_id', '')}:{stage}:{_sha16(text)}"
        if send_key in self._send_idempotency_keys:
            return
        self._send_idempotency_keys.add(send_key)
        decision = apply_output_policy(text)
        if decision.action == "block" or not decision.visible_text:
            return
        result = await self.send(
            chat_id=event.source.chat_id,
            content=decision.visible_text,
            reply_to=getattr(event, "message_id", None),
        )
        _append_jsonl(
            self.events_path,
            {
                **_turn_record(event, stage=stage),
                "task_id": task_id,
                "send_idempotency_key": send_key,
                "policy_action": decision.action,
                "policy_reason": decision.reason,
                "notice_sha256_16": _sha16(decision.visible_text),
                "notice_length": len(decision.visible_text),
                "send_success": result.success,
                "send_error": result.error,
                "error": error,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run InkStatute live WeCom bridge")
    parser.add_argument("--chat-id", default=os.environ.get("WECOM_HOME_CHANNEL", "155"))
    parser.add_argument("--no-ack", action="store_true", help="Do not send visible processing ACK messages")
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("INKSTATUTE_HERMES_TIMEOUT", "7200")))
    parser.add_argument(
        "--turn-buffer",
        type=float,
        default=float(os.environ.get("INKSTATUTE_WECOM_TURN_BUFFER_SECONDS", "0.9")),
        help="Seconds to wait for adjacent file/text events before invoking the agent",
    )
    long_task_notice_default = os.environ.get(
        "INKSTATUTE_WECOM_LONG_TASK_NOTICE_INTERVAL_SECONDS",
        os.environ.get("INKSTATUTE_WECOM_LONG_TASK_NOTICE_SECONDS", "180"),
    )
    parser.add_argument(
        "--long-task-notice",
        "--long-task-notice-interval",
        dest="long_task_notice_interval",
        type=float,
        default=float(long_task_notice_default),
        help="Seconds between long-task progress notices; 0 disables them",
    )
    args = parser.parse_args()

    _load_env_file(LAWFIRM_HOME / ".env")
    _load_env_file(Path("/home/sorawatcher/.hermes/.env"))

    runtime_dir = RUNTIME_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(runtime_dir / "bridge.log")

    bridge_config = BridgeConfig(
        chat_id=str(args.chat_id),
        bot_id=_required_env("WECOM_BOT_ID"),
        secret=_required_env("WECOM_SECRET"),
        websocket_url=os.environ.get("WECOM_WEBSOCKET_URL", "wss://openws.work.weixin.qq.com"),
        hermes_timeout_seconds=args.timeout,
        send_ack=not args.no_ack,
        turn_buffer_seconds=max(0.0, args.turn_buffer),
        long_task_notice_interval_seconds=max(0.0, args.long_task_notice_interval),
        runtime_dir=runtime_dir,
    )

    adapter_config = PlatformConfig(
        enabled=True,
        home_channel={
            "platform": "wecom",
            "chat_id": bridge_config.chat_id,
        },
        extra={
            "bot_id": bridge_config.bot_id,
            "secret": bridge_config.secret,
            "websocket_url": bridge_config.websocket_url,
            "dm_policy": os.environ.get("WECOM_DM_POLICY", "open"),
            "allow_from": os.environ.get("WECOM_ALLOWED_USERS", ""),
            "group_policy": os.environ.get("WECOM_GROUP_POLICY", "open"),
        },
    )

    return asyncio.run(_run(adapter_config, bridge_config))


async def _run(adapter_config: PlatformConfig, bridge_config: BridgeConfig) -> int:
    adapter = InkStatuteWeComBridge(adapter_config, bridge_config)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    connected = await adapter.connect()
    if not connected:
        LOGGER.error("WeCom bridge failed to connect")
        return 2

    _append_jsonl(
        adapter.events_path,
        {
            "event": "bridge_started",
            "occurred_at": _now(),
            "channel": "wecom",
            "chat_id": bridge_config.chat_id,
            "no_channel_io_from_hermes": True,
            "runtime_dir": str(bridge_config.runtime_dir),
            "hermes_timeout_seconds": bridge_config.hermes_timeout_seconds,
            "long_task_notice_interval_seconds": bridge_config.long_task_notice_interval_seconds,
            "turn_buffer_seconds": bridge_config.turn_buffer_seconds,
        },
    )
    LOGGER.info(
        "InkStatute WeCom bridge connected for chat_id=%s timeout=%ss long_notice_interval=%ss",
        bridge_config.chat_id,
        bridge_config.hermes_timeout_seconds,
        bridge_config.long_task_notice_interval_seconds,
    )
    print(f"READY InkStatute WeCom bridge connected for chat_id={bridge_config.chat_id}", flush=True)

    await stop_event.wait()
    LOGGER.info("stopping bridge")
    await adapter.disconnect()
    return 0


def _call_hermes_lawfirm(
    message: str,
    media_urls: list[str] | None = None,
    media_types: list[str] | None = None,
    *,
    timeout_seconds: int,
) -> str:
    prompt = _build_lawfirm_prompt(message, media_urls or [], media_types or [])
    prompt_path = _write_prompt_file(prompt)
    runner = (
        "import pathlib, sys; "
        "from hermes_cli.oneshot import run_oneshot; "
        "prompt = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); "
        "raise SystemExit(run_oneshot(prompt))"
    )
    try:
        env = os.environ.copy()
        env["HERMES_HOME"] = str(LAWFIRM_HOME)
        env["HERMES_ACCEPT_HOOKS"] = "1"
        try:
            proc = subprocess.run(
                [str(HERMES_PYTHON), "-c", runner, str(prompt_path)],
                cwd=str(LAWFIRM_HOME),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Hermes one-shot timed out after {timeout_seconds} seconds") from exc
    finally:
        _unlink_quietly(prompt_path)

    if proc.returncode != 0:
        raise RuntimeError(f"Hermes one-shot failed with exit {proc.returncode}: {_redact(proc.stderr)[-500:]}")
    output = proc.stdout.strip()
    if not output:
        raise RuntimeError("Hermes one-shot returned empty output")
    return output


def _build_lawfirm_prompt(message: str, media_urls: list[str], media_types: list[str]) -> str:
    attachment_context = _build_attachment_context(media_urls, media_types)
    return (
        "你是墨律 InkStatute 企业微信律师助手后端。"
        "请只输出普通律师用户可见的法律业务回复，不要输出 Hermes 网关、系统、更新、命令、"
        "调试、路径、token、运行时细节。不要声称已经完成无法确认的外部操作。\n\n"
        "如果你生成了需要交付给用户的文件，请在最终回复中单独写一行 MEDIA:<文件绝对路径>；"
        "企业微信入口会把该文件作为附件发送，并移除这行路径。\n\n"
        f"{attachment_context}"
        f"用户消息：\n{message.strip() or '（用户这次没有输入文字正文，请结合附件处理。）'}"
    )


def _build_attachment_context(media_urls: list[str], media_types: list[str]) -> str:
    if not media_urls:
        return ""

    notes = ["用户本次上传了附件，已由 InkStatute 企业微信入口缓存到本机："]
    for index, path in enumerate(media_urls, start=1):
        media_type = media_types[index - 1] if index - 1 < len(media_types) else ""
        if not media_type or media_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(path)
            media_type = guessed or media_type or "unknown"
        agent_path = to_agent_visible_cache_path(path)
        display_name = _display_filename(path)
        notes.append(
            f"{index}. 文件名：{display_name}；MIME：{media_type}；本地路径：{agent_path}"
        )
    notes.append(
        "如果用户要求审查、修改、转换或起草，请先读取/解析附件内容；"
        "不要因为文字正文为空就要求用户重发。不要在回复中暴露本地路径。"
    )
    return "\n".join(notes) + "\n\n"


def _write_prompt_file(prompt: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=RUNTIME_DIR,
        prefix="hermes-prompt-",
        suffix=".txt",
        delete=False,
    ) as handle:
        os.chmod(handle.name, 0o600)
        handle.write(prompt)
        return Path(handle.name)


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _turn_record(event: Any, *, stage: str) -> dict[str, Any]:
    text = str(getattr(event, "text", "") or "")
    source = getattr(event, "source", None)
    media_urls = list(getattr(event, "media_urls", []) or [])
    media_types = list(getattr(event, "media_types", []) or [])
    return {
        "event": "wecom_live_turn",
        "stage": stage,
        "occurred_at": _now(),
        "channel": "wecom",
        "chat_id": str(getattr(source, "chat_id", "") or ""),
        "user_id_hash": _sha16(str(getattr(source, "user_id", "") or "")),
        "message_id": str(getattr(event, "message_id", "") or ""),
        "message_type": str(getattr(getattr(event, "message_type", None), "value", getattr(event, "message_type", ""))),
        "text_sha256_16": _sha16(text),
        "text_length": len(text),
        "media_count": len(media_urls),
        "media_types": media_types,
        "raw_payload_ref": _raw_payload_ref(event),
        "privacy": "no_raw_payload_or_legal_text_stored",
    }


def _raw_payload_ref(event: Any) -> str:
    return f"runtime://wecom-live/{getattr(event, 'message_id', 'unknown')}"


def _turn_key(event: Any) -> str:
    source = getattr(event, "source", None)
    parts = (
        str(getattr(source, "platform", "") or "wecom"),
        str(getattr(source, "chat_id", "") or ""),
        str(getattr(source, "user_id", "") or ""),
    )
    return ":".join(parts)


def _merge_event(existing: Any, incoming: Any) -> None:
    incoming_text = str(getattr(incoming, "text", "") or "").strip()
    existing_text = str(getattr(existing, "text", "") or "").strip()
    if incoming_text:
        existing.text = f"{existing_text}\n{incoming_text}" if existing_text else incoming_text
        existing.message_id = getattr(incoming, "message_id", getattr(existing, "message_id", None))

    incoming_media_urls = list(getattr(incoming, "media_urls", []) or [])
    incoming_media_types = list(getattr(incoming, "media_types", []) or [])
    if incoming_media_urls:
        existing.media_urls.extend(incoming_media_urls)
        existing.media_types.extend(incoming_media_types)
        existing.message_type = getattr(incoming, "message_type", getattr(existing, "message_type", None))
        if not getattr(existing, "message_id", None):
            existing.message_id = getattr(incoming, "message_id", None)

    if getattr(incoming, "reply_to_text", None) and not getattr(existing, "reply_to_text", None):
        existing.reply_to_text = incoming.reply_to_text
        existing.reply_to_message_id = getattr(incoming, "reply_to_message_id", None)
    if getattr(incoming, "timestamp", None):
        existing.timestamp = incoming.timestamp


def _display_filename(path: str) -> str:
    name = Path(path).name
    match = re.match(r"^(?:doc|img|media)_([0-9a-fA-F-]{8,})_(.+)$", name)
    if match:
        name = match.group(2)
    return re.sub(r"[^\w.\- \u4e00-\u9fff（）()【】\\[\\]]", "_", name)[:180] or "attachment"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


def _setup_logging(path: Path) -> None:
    logging.basicConfig(
        level=os.environ.get("INKSTATUTE_WECOM_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(path, encoding="utf-8"),
        ],
    )


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: str) -> str:
    text = value or ""
    for secret_name in ("WECOM_SECRET", "WECOM_BOT_ID", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        secret = os.environ.get(secret_name, "")
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


if __name__ == "__main__":
    raise SystemExit(main())
