"""ModeClassifierPort — Chat / Draft / Evidence three-mode detection.

Ported 1:1 from ``lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`` (691 lines).

Defines the core data structures for three-mode detection:

- ``AgentMode`` — StrEnum with values ``chat``, ``draft``, ``evidence``
  (lowercase, matching Rust ``#[serde(rename_all = "lowercase")]``).
- ``ClassifyContext`` — 7-field dataclass mirroring the Rust struct.
- ``ClassifyResult`` — 7-field dataclass mirroring the Rust struct.
- ``ModeClassifierPort`` — Protocol with ``classify(context) -> ClassifyResult``.

The ``AgentMode`` enum provides ``ui_label()`` returning the Chinese labels
("法律问答", "文书起草", "案情分析").

This module defines only the Protocol and data shapes — the actual LLM
call is host-injected, preserving the ``dependencies = []`` invariant.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol


class AgentMode(StrEnum):
    """Three interaction modes for the agent.

    Values are lowercase to match the Rust ``#[serde(rename_all = "lowercase")]``.
    """

    CHAT = "chat"       # 法律问答
    DRAFT = "draft"      # 文书起草
    EVIDENCE = "evidence"  # 案情分析

    def ui_label(self) -> str:
        """Return the Chinese UI label for this mode."""
        if self is AgentMode.CHAT:
            return "法律问答"
        if self is AgentMode.DRAFT:
            return "文书起草"
        return "案情分析"

    def is_evidence(self) -> bool:
        """Return True if this mode is Evidence."""
        return self is AgentMode.EVIDENCE


@dataclass
class ClassifyContext:
    """Context for mode classification — mirrors Rust ``ClassifyContext``.

    Fields (same 7 as Rust struct):
    - ``user_message`` — the user's message text
    - ``has_directory_ref`` — whether user attached a case directory
    - ``has_file_ref`` — whether user attached a file
    - ``directory_aliases`` — alias names for attached directories
    - ``current_mode`` — mode of the committed task ("draft"/"evidence") or None
    - ``current_task_label`` — human label of committed task
    - ``has_active_document`` — whether a document/report already exists
    """

    user_message: str
    has_directory_ref: bool = False
    has_file_ref: bool = False
    directory_aliases: list[str] = field(default_factory=list)
    current_mode: str | None = None
    current_task_label: str | None = None
    has_active_document: bool = False


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    """Result of mode classification — mirrors Rust ``ClassifyResult``.

    Fields (same 7 as Rust struct):
    - ``mode`` — AgentMode (Chat / Draft / Evidence)
    - ``label`` — short Chinese task label
    - ``reason`` — one-sentence reason
    - ``action`` — "continue" | "switch" | "aside"
    - ``source`` — "llm" | "fallback"
    - ``fallback_reason`` — error category when fallback used (or None)
    - ``diagnostic`` — error detail (or None)
    """

    mode: AgentMode
    label: str
    reason: str
    action: str
    source: str
    fallback_reason: str | None = None
    diagnostic: str | None = None


class ModeClassifierPort(Protocol):
    """Protocol for injectable mode classifiers.

    Implementations must be stateless and side-effect free.  When no
    classifier is injected (``None``), mode detection is skipped and
    no mode-related metadata is added to ``RouteDecision``.
    """

    def classify(self, context: ClassifyContext) -> ClassifyResult:
        """Classify *context* and return mode + action + label + reason."""
        ...


# ---------------------------------------------------------------------------
# System prompt + policy supplement — ported verbatim from agent_classifier.rs
# lines 92-123.
# ---------------------------------------------------------------------------

CLASSIFIER_SYSTEM = (
    '你是墨律 Inkstatute 的任务路由器。根据用户消息、附加资料与「当前任务」上下文，判断本条消息应使用的 Agent 模式 mode 与意图动作 action。\n'
    '\n'
    '模式 mode（只能选一个）：\n'
    '- draft：用户要生成正式法律文书（合同、起诉状、答辩状、法律意见书等），输出进入右侧结构化文书预览。\n'
    '- evidence：用户要基于本地案卷/案件资料做案情分析、诉讼方案、证据梳理、尽调报告等；通过索引检索工具取证，输出 Markdown 分析报告（非 JSON 文书）。\n'
    '- chat：法律问答 / 咨询解惑——就具体法律问题、法条含义、可行性、风险、流程等寻求解答，不产出成稿文书、也不基于本地案卷写诉讼方案。\n'
    '\n'
    '意图动作 action（只能选一个，结合「当前任务」判断）：\n'
    '- continue：延续或细化当前任务（例如对当前正在起草的文书提出修改、补充要求）。\n'
    '- switch：改做另一件产出型任务（换一种文书；从问答转为起草；从起草转为案情分析；起草 A 改为起草明显不同的 B）。\n'
    '- aside：在当前产出型任务进行中插入一个法律问题/咨询，并不打算放弃当前产出物（此时 mode 通常为 chat）。\n'
    '\n'
    '规则：\n'
    '1. 仅输出一行 JSON，无 markdown 代码块，无其它文字。\n'
    '2. 格式：{"mode":"draft|evidence|chat","action":"continue|switch|aside","label":"简短中文任务标签","reason":"一句话理由"}\n'
    '3. 没有「当前任务」（首次消息，或此前只做问答、无产出文书）时，action 一律填 continue。\n'
    '4. 「当前任务」是某类文书起草，且本条只是顺带问个法律问题、并未要求改文书 → mode=chat、action=aside。\n'
    '5. 「当前任务」是某类文书，且本条要求改做另一类文书或另一种产出 → action=switch，mode 取新任务的模式。\n'
    '6. 「当前任务」是某类文书，且本条是对它的修改/补充 → action=continue，mode 保持该产出型模式。\n'
    '7. 读取目录/案件资料 + 诉讼方案/案情分析 → evidence，不是 draft。附了案卷目录时：分析材料或写诉讼方案→evidence；明确要起草某类格式文书→draft。\n'
    '8. label 用最能描述「本条所指任务」的简短中文（如「房屋租赁合同起草」「股东知情权咨询」）。\n'
    '9. 不确定 mode 时选 chat；不确定 action 时选 continue，不要轻易 switch。\n'
    '10. 消息以「以下是补充信息」开头说明用户在回答此前任务的澄清问题：action=continue；附加目录为「是」时 evidence；提到起草/文书时 draft；不要选 chat。'
)

CLASSIFIER_POLICY_SUPPLEMENT = (
    '## 墨律当前路由边界（优先遵守）\n'
    '1. chat 是默认底座：法律咨询、法规适用分析、法律研究、风险评估、流程说明、谈判建议、书面分析性答复，默认都走 chat。\n'
    '2. 只有用户明确要求生成具体正式文书/文档产物（例如合同、起诉状、答辩状、正式法律意见书、正式报告并要求作为交付物）时才选 draft。\n'
    '3. 只有用户要求基于本地案卷/目录资料生成独立诉讼方案、案情分析报告、证据梳理报告时才选 evidence。\n'
    '4. 不要用单个词触发模式切换；必须结合整条消息、附件/目录、本轮上下文和当前任务判断。\n'
    '5. 不确定时选 chat；分类失败时系统会结构性降级，模型不要为了"稳妥"把问答误判为 draft。'
)


# ---------------------------------------------------------------------------
# normalize_action — ported from agent_classifier.rs lines 73-79.
# ---------------------------------------------------------------------------

def normalize_action(raw: str | None) -> str:
    """Normalize the model's action token to one of three known values.

    Anything unrecognized degrades to the safe ``"continue"``.
    """
    if raw is None:
        return "continue"
    match raw.strip().lower():
        case "switch" | "切换":
            return "switch"
        case "aside" | "插问" | "提问":
            return "aside"
        case _:
            return "continue"


# ---------------------------------------------------------------------------
# parse_mode_str — ported from agent_classifier.rs lines 328-345.
# ---------------------------------------------------------------------------

def parse_mode_str(s: str) -> AgentMode | None:
    """Parse a mode string (Chinese or English) into an ``AgentMode``.

    Handles Chinese aliases: "文书"/"起草"/"文书起草"/"法律文书"/"法律文书起草"
    → Draft; "案情"/"案情分析"/"诉讼"/"诉讼方案"/"分析"/"证据"/"证据分析"
    → Evidence; "咨询"/"问答"/"法律问答"/"法律咨询" → Chat.

    Also handles English: "draft"/"document"/"doc",
    "evidence"/"caseanalysis"/"case", "chat"/"qa"/"q&a".
    """
    compact = "".join(
        c for c in s.strip().lower() if c not in (" ", "_", "-", "\u3000")
    )
    if compact in (
        "draft", "document", "doc", "文书", "起草", "文书起草",
        "法律文书", "法律文书起草",
    ):
        return AgentMode.DRAFT
    if compact in (
        "evidence", "caseanalysis", "case", "案情", "案情分析",
        "诉讼", "诉讼方案", "分析", "证据", "证据分析",
    ):
        return AgentMode.EVIDENCE
    if compact in ("chat", "qa", "q&a", "咨询", "问答", "法律问答", "法律咨询"):
        return AgentMode.CHAT
    return None


# ---------------------------------------------------------------------------
# fallback_classify — ported from agent_classifier.rs lines 349-376.
# Deliberately structural-only: NO keyword matching on user text.
# ---------------------------------------------------------------------------

def fallback_classify(
    ctx: ClassifyContext,
    fallback_reason: str,
    diagnostic: str | None,
) -> ClassifyResult:
    """Structural-only fallback — never reads ``ctx.user_message``.

    - If ``has_active_document`` is True: use ``current_mode`` (parse via
      ``parse_mode_str``, default Chat if unparseable).
    - If ``has_active_document`` is False: always Chat.
    - Action is always ``"continue"`` — fallback must never surprise-switch.
    - Source is ``"fallback"`` with error reason.
    """
    if ctx.has_active_document:
        mode = parse_mode_str(ctx.current_mode) if ctx.current_mode else None
        if mode is None:
            mode = AgentMode.CHAT
    else:
        mode = AgentMode.CHAT

    label = (
        ctx.current_task_label
        if ctx.current_task_label and ctx.current_task_label.strip()
        else mode.ui_label()
    )

    return ClassifyResult(
        mode=mode,
        label=label,
        reason="AI 分类失败，已使用结构性安全默认模式",
        action="continue",  # fallback must never surprise-switch
        source="fallback",
        fallback_reason=fallback_reason,
        diagnostic=diagnostic,
    )


# ---------------------------------------------------------------------------
# extract_json_object — ported from agent_classifier.rs lines 310-326.
# ---------------------------------------------------------------------------

def extract_json_object(text: str) -> str | None:
    """Extract the first balanced ``{...}`` substring from *text*."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : start + i + 1]
    return None


# ---------------------------------------------------------------------------
# parse_classifier_response — ported from agent_classifier.rs lines 220-275.
# ---------------------------------------------------------------------------

def parse_classifier_response(raw: str, ctx: ClassifyContext) -> ClassifyResult:
    """Parse the LLM's raw response text into a ``ClassifyResult``.

    - Empty content → fallback with ``"empty_response"``.
    - No JSON object found → fallback with ``"invalid_json"``.
    - JSON parse failure → fallback with ``"invalid_json"``.
    - Unrecognized mode → fallback with ``"invalid_mode"``.
    - Valid mode + action: action is normalized; when ``current_mode`` is
      None, action is pinned to ``"continue"`` (action pinning rule).
    """
    trimmed = raw.strip()
    if not trimmed:
        return fallback_classify(ctx, "empty_response", "分类模型返回空内容")

    json_str = extract_json_object(trimmed)
    if json_str is None:
        return fallback_classify(
            ctx, "invalid_json", "分类返回格式异常：未找到 JSON 对象",
        )

    try:
        parsed: dict[str, Any] = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return fallback_classify(
            ctx, "invalid_json", f"分类返回格式异常：{e}",
        )

    mode_str = parsed.get("mode", "")
    mode = parse_mode_str(mode_str) if isinstance(mode_str, str) else None
    if mode is None:
        return fallback_classify(
            ctx, "invalid_mode", f"分类返回了无法识别的模式：{mode_str}",
        )

    # Action pinning: without a committed task there is nothing to switch
    # away from, so a switch/aside verdict is meaningless — pin to continue.
    if ctx.current_mode is None:
        action = "continue"
    else:
        action = normalize_action(parsed.get("action"))

    label = parsed.get("label")
    if not label or not isinstance(label, str) or not label.strip():
        label = mode.ui_label()

    reason = parsed.get("reason", "")
    if not isinstance(reason, str):
        reason = ""

    return ClassifyResult(
        mode=mode,
        label=label,
        reason=reason,
        action=action,
        source="llm",
        fallback_reason=None,
        diagnostic=None,
    )


# ---------------------------------------------------------------------------
# validate_classifier_response — ported from agent_classifier.rs lines 277-279.
# ---------------------------------------------------------------------------

def validate_classifier_response(raw: str, ctx: ClassifyContext) -> ClassifyResult:
    """Public alias for ``parse_classifier_response`` (matches Rust API)."""
    return parse_classifier_response(raw, ctx)


# ---------------------------------------------------------------------------
# classify_error_diagnostic — ported from agent_classifier.rs lines 281-298.
# ---------------------------------------------------------------------------

def classify_error_diagnostic(error_msg: str) -> tuple[str, str]:
    """Categorize an error message into a reason + compact diagnostic.

    Returns ``(reason, diagnostic)`` where reason is one of:
    ``auth_failed``, ``model_not_found``, ``timeout``,
    ``response_parse_failed``, ``network_error``, ``request_failed``.
    """
    lower = error_msg.lower()
    if "401" in lower or "403" in lower:
        reason = "auth_failed"
    elif "404" in lower:
        reason = "model_not_found"
    elif "timeout" in lower or "timed out" in lower:
        reason = "timeout"
    elif "failed to parse llm response" in lower:
        reason = "response_parse_failed"
    elif "failed to send" in lower or "dns" in lower or "connect" in lower:
        reason = "network_error"
    else:
        reason = "request_failed"
    return (reason, compact_diagnostic(error_msg, 180))


def compact_diagnostic(text: str, max_chars: int) -> str:
    """Collapse whitespace and truncate to *max_chars* characters."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "…"


# ---------------------------------------------------------------------------
# LLM callable Protocol — host-injected LLM interface.
# ---------------------------------------------------------------------------

class LlmCallable(Protocol):
    """Protocol for a host-injected LLM callable.

    Implementations receive a system prompt and user prompt, and return
    the raw response text (or raise an exception on failure).
    """

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat request and return the response text."""
        ...


# ---------------------------------------------------------------------------
# LLMModeClassifier — concrete ModeClassifierPort using a host-injected LLM.
# ---------------------------------------------------------------------------

def _build_user_prompt(ctx: ClassifyContext) -> str:
    """Build the user prompt from the classify context.

    Ported from agent_classifier.rs lines 129-152.
    """
    return (
        f"用户消息：{ctx.user_message}\n"
        f"附加目录：{'是' if ctx.has_directory_ref else '否'}\n"
        f"附加文件：{'是' if ctx.has_file_ref else '否'}\n"
        f"目录别名：{'无' if not ctx.directory_aliases else '、'.join(ctx.directory_aliases)}\n"
        f"当前任务模式：{ctx.current_mode if ctx.current_mode is not None else '无'}\n"
        f"当前任务标签：{ctx.current_task_label if ctx.current_task_label is not None else '无'}\n"
        f"当前是否已有产出文书：{'是' if ctx.has_active_document else '否'}"
    )


class LLMModeClassifier:
    """Concrete ``ModeClassifierPort`` that calls an LLM.

    The LLM callable is host-injected (same pattern as
    ``ModelClassifierPort``).  The system prompt and policy supplement
    are ported verbatim from ``agent_classifier.rs`` lines 92-123.

    Temperature 0.0, max_tokens 160, non-streaming (metadata only —
    the actual request parameters are the host's responsibility).
    """

    def __init__(self, llm: LlmCallable) -> None:
        self._llm = llm

    def classify(self, context: ClassifyContext) -> ClassifyResult:
        """Call the LLM and parse the response into a ``ClassifyResult``."""
        system_prompt = f"{CLASSIFIER_SYSTEM}\n\n{CLASSIFIER_POLICY_SUPPLEMENT}"
        user_prompt = _build_user_prompt(context)
        try:
            raw = self._llm.chat(system_prompt, user_prompt)
        except Exception as e:
            reason, diagnostic = classify_error_diagnostic(str(e))
            return fallback_classify(context, reason, diagnostic)
        return parse_classifier_response(raw, context)


# ---------------------------------------------------------------------------
# classify_with_retry — ported from agent_classifier.rs lines 198-218.
# ---------------------------------------------------------------------------

def classify_with_retry(
    fast_classifier: ModeClassifierPort,
    primary_classifier: ModeClassifierPort,
    ctx: ClassifyContext,
) -> ClassifyResult:
    """Try fast provider first; if fallback, retry with primary.

    If both fail (both return ``source="fallback"``), returns the
    second (primary) fallback result.
    """
    fast = fast_classifier.classify(ctx)
    if fast.source != "fallback":
        return fast

    primary = primary_classifier.classify(ctx)
    if primary.source != "fallback":
        return primary

    return primary


__all__ = [
    "AgentMode",
    "CLASSIFIER_POLICY_SUPPLEMENT",
    "CLASSIFIER_SYSTEM",
    "ClassifyContext",
    "ClassifyResult",
    "LlmCallable",
    "LLMModeClassifier",
    "ModeClassifierPort",
    "classify_error_diagnostic",
    "classify_with_retry",
    "compact_diagnostic",
    "extract_json_object",
    "fallback_classify",
    "normalize_action",
    "parse_classifier_response",
    "parse_mode_str",
    "validate_classifier_response",
]
