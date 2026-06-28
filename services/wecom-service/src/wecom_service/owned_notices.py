"""InkStatute-owned short notices for ordinary WeCom users."""

from __future__ import annotations

import hashlib
import secrets
from typing import Literal


NoticeKind = Literal[
    "processing",
    "long_processing",
    "blocked",
    "failed",
    "timeout",
    "backend_lifecycle",
    "status_running",
    "cancel_accepted",
    "cancel_unsupported",
    "update_accepted",
    "update_received_not_applied",
    "parallel_task_accepted",
    "parallel_task_unsupported",
]

OWNED_NOTICE_TEMPLATES: dict[NoticeKind, tuple[str, ...]] = {
    "processing": (
        "小律正在处理中，请耐心等待。",
        "小律收到，正在整理。",
        "小律在看了，稍等一下。",
        "小律正在为你处理，马上回来。",
        "小律已收到，请稍等片刻。",
    ),
    "long_processing": (
        "小律还在处理文件，请再等一下。",
        "小律还在整理文档，请稍候。",
        "小律正在处理这份文件，需要再等一下。",
        "小律还没处理完，请再稍等片刻。",
        "小律正在生成结果，请再等一下。",
        "小律还在读文件，处理完就发你。",
        "小律还在核对文档内容，请稍候。",
        "小律还在生成修订稿，请再等一下。",
    ),
    "blocked": (
        "小律这次没整理好，请你再发一次。",
        "小律刚才的回复不够稳妥，请换个问法再试。",
        "小律先不发这版，请你补充一下需求再试。",
        "小律需要重新整理，请你再发一遍。",
        "这版小律先收住了，请换个说法再试。",
    ),
    "failed": (
        "小律这次没处理成功，请稍后再试。",
        "小律刚才卡住了，请你再发一次。",
        "小律暂时没跑完，请稍后再试。",
        "小律这边出了点问题，请再试一次。",
        "小律没能完成这次处理，请稍后重发。",
    ),
    "timeout": (
        "小律这次处理时间太长，已经先停在超时状态。请稍后重发或拆成更小的任务。",
        "小律还没在限定时间内处理完，本次先记为超时。请稍后再试。",
        "小律这次处理超时了，请稍后重发，或把文件和要求拆小一点。",
    ),
    "backend_lifecycle": (
        "小律正在调整中，请稍后再试。",
        "小律这边暂时不稳定，请稍后再试。",
        "小律正在恢复，请等一下再试。",
        "小律稍微卡了一下，请稍后再试。",
        "小律这边还没准备好，请稍后再试。",
    ),
    "status_running": (
        "小律还在处理上一个任务，处理完会马上发你。",
        "小律还在跑刚才的任务，当前没有结束。",
        "小律正在继续处理上一条任务，请稍等。",
    ),
    "cancel_accepted": (
        "小律收到取消请求，正在停止当前任务。",
        "小律会尝试取消刚才的任务。",
        "小律已收到停止当前任务的请求。",
    ),
    "cancel_unsupported": (
        "小律收到取消请求，但当前后端暂时不能中途取消；处理完或超时后会给你结果。",
        "小律知道你想取消，但这类任务暂时不能可靠中途停止；我会继续跟进最终状态。",
        "小律收到你的停止意图了，不过当前任务不能中途确认取消。",
    ),
    "update_accepted": (
        "小律收到补充要求，并已提交给当前任务继续处理。",
        "小律已把你的补充要求加入当前任务。",
        "小律收到，这条补充已经进入当前处理流程。",
    ),
    "update_received_not_applied": (
        "小律收到你的补充说明；当前后端暂时不能中途应用，我会在本次结果后提醒你是否需要继续处理。",
        "小律看到了补充要求，但当前任务不能确认中途更新；这次不会把它说成已经应用。",
        "小律收到补充内容，不过当前任务暂时不能实时改写执行。",
    ),
    "parallel_task_accepted": (
        "小律收到新的独立任务，会和当前任务分开处理。",
        "小律已把这条作为新的任务处理。",
        "小律收到，这条会作为独立任务进入队列。",
    ),
    "parallel_task_unsupported": (
        "小律还在处理上一个任务，当前不能并行开启新的独立任务。",
        "小律收到新的需求，但当前后端暂时不能并行处理；请等上一个任务结束后再发。",
        "小律还没处理完上一条，暂时不能同时开新任务。",
    ),
}


def build_owned_notice(kind: NoticeKind, *, seed: str | None = None) -> str:
    """Return a short InkStatute-owned user notice.

    A seed makes the choice reproducible for tests and persisted event replay.
    Live delivery omits the seed so repeated turns avoid sounding mechanical.
    """

    candidates = OWNED_NOTICE_TEMPLATES[kind]
    if seed is None:
        return secrets.choice(candidates)
    digest = hashlib.sha256(f"{kind}:{seed}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(candidates)
    return candidates[index]


__all__ = ["NoticeKind", "OWNED_NOTICE_TEMPLATES", "build_owned_notice"]
