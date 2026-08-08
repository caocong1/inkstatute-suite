"""Prompt assembler — Chinese legal system prompt builder (pure functions).

Ports the prompt assembly logic from ``lawyer-desktop/src-tauri/src/skills/router.rs``
(627 lines) into a pure-function Python module.  The system prompt is the
primary legal guardrail delivery mechanism: the research-gate, citation spec,
and ask-user mandate are all injected via the prompt.

Three modes (Chat / Draft / Evidence) each get a different base prompt.
The research-gate, retrieval tool mapping, citation writing spec, skill
descriptions, and active skill body are injected in **every** mode.

This module has no state and no side effects.  It depends only on the
Python standard library.

Golden fixture set: the 10 Rust test cases in ``router.rs:507-627`` are
replicated as Python tests in ``tests/test_prompt_assembler.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# AgentMode — matches Rust AgentMode (agent_classifier.rs:8-12)
# ---------------------------------------------------------------------------


class AgentMode(str, Enum):
    """Three legal assistant modes, serialized as lowercase strings."""

    CHAT = "chat"
    DRAFT = "draft"
    EVIDENCE = "evidence"


# ---------------------------------------------------------------------------
# SkillMetadata — lightweight dataclass matching Rust SkillMetadata fields
# used by router.rs (name, plugin_name, description, full_content)
# ---------------------------------------------------------------------------


@dataclass
class SkillMetadata:
    """Minimal skill metadata used by the prompt assembler.

    Mirrors the fields of ``loader::SkillMetadata`` that ``router.rs``
    actually reads: ``name``, ``plugin_name``, ``description``,
    ``full_content``.
    """

    name: str
    plugin_name: str
    description: str
    full_content: str


# ---------------------------------------------------------------------------
# RESEARCH_GATE_FALLBACK — verbatim from router.rs:5-14
# ---------------------------------------------------------------------------

RESEARCH_GATE_FALLBACK = """## research-gate（强制前置）

在生成任何法律文书、出具法律意见或引用具体法条之前，你必须：

1. 先通过可用工具检索相关法律法规、司法解释或权威案例
2. 确认检索结果与用户需求匹配后，再起草文书内容
3. 每条法条引用必须标注精确条文号与来源层级
4. 无法检索到权威来源时，标注 [待律师复核] 并说明检索局限
5. 禁止仅依据训练数据中的法条记忆直接作答
"""


# ---------------------------------------------------------------------------
# Retrieval tool detection — router.rs:36-63
# ---------------------------------------------------------------------------

_RETRIEVAL_TOOL_NAME_FRAGMENTS = [
    "law", "legal", "fagui", "statute", "wenshu", "case", "judgment",
]

_PUBLIC_WEB_TOOL_TEXT_FRAGMENTS = [
    "web", "search", "fetch", "url", "browser", "crawl",
    "网页", "搜索", "抓取", "链接",
]

_DIRECT_RETRIEVAL_TOOL_NAMES = {
    "legal_search", "search_law", "get_law_article", "fetch_url",
    "search_workspace",
}


def is_retrieval_tool_name(name: str) -> bool:
    """Return True if *name* is a known retrieval-capable tool name.

    Direct matches: ``legal_search``, ``search_law``, ``get_law_article``,
    ``fetch_url``, ``search_workspace``.

    For ``mcp__`` prefixed names, checks if the lowercased name contains
    any law/legal fragment OR matches public web tool text.
    """
    if name in _DIRECT_RETRIEVAL_TOOL_NAMES:
        return True
    if name.startswith("mcp__"):
        lower = name.lower()
        if any(frag in lower for frag in _RETRIEVAL_TOOL_NAME_FRAGMENTS):
            return True
        return is_public_web_tool_text(lower)
    return False


def is_public_web_tool_text(text: str) -> bool:
    """Return True if *text* contains any public-web/search/fetch fragment."""
    lower = text.lower()
    return any(frag in lower for frag in _PUBLIC_WEB_TOOL_TEXT_FRAGMENTS)


def is_retrieval_tool(name: str, description: str) -> bool:
    """Return True if *name* is a retrieval tool name OR if *name* is an
    MCP tool whose *description* matches public web tool text.
    """
    if is_retrieval_tool_name(name):
        return True
    return name.startswith("mcp__") and is_public_web_tool_text(description)


# ---------------------------------------------------------------------------
# RETRIEVAL_TOOL_MAP — 10 (tool_name, mapped_step) pairs (router.rs:67-99)
# ---------------------------------------------------------------------------

RETRIEVAL_TOOL_MAP: list[tuple[str, str]] = [
    (
        "legal_search",
        "聚合检索法律依据（一次并发查本地法规库与在线官方源，检索首选）",
    ),
    (
        "fetch_url",
        "读取用户本轮明确提供的网页链接（公众号、公告、公开资料等）",
    ),
    ("search_law", "本地法规库全文检索（定位法条，离线可用）"),
    (
        "get_law_article",
        "本地法规库精确取条文原文（《法名》+ 条号，引用核验基准）",
    ),
    (
        "mcp__law-database__search_laws",
        "在线检索法律法规（国家法律法规数据库等官方源）",
    ),
    (
        "mcp__law-database__get_law_detail",
        "在线获取法规全文（flk → court.gov.cn → gov.cn 回退链）",
    ),
    (
        "mcp__law-database__search_cases_by_law",
        "按法条检索关联指导/公报案例",
    ),
    (
        "mcp__wenshu__search_cases",
        "检索裁判案例（人民法院案例库为主源，裁判文书网为补充）",
    ),
    ("mcp__wenshu__get_case_detail", "按案号获取案例详情"),
    ("search_workspace", "检索本地案卷材料（案件事实唯一来源）"),
]


# ---------------------------------------------------------------------------
# build_retrieval_tool_mapping — router.rs:103-137
# ---------------------------------------------------------------------------


def build_retrieval_tool_mapping(retrieval_tools: list[str]) -> str:
    """Build the ``## 检索工具映射`` prompt section.

    If *retrieval_tools* is empty, emit honest degradation text.
    Otherwise, emit the mapping header, lines from ``RETRIEVAL_TOOL_MAP``
    for tools that are actually available, generic descriptions for unknown
    retrieval tools, and a closing warning.
    """
    if not retrieval_tools:
        return (
            "## 检索工具映射\n\n"
            "当前未接入任何法律检索工具（research-gate 中的 WebSearch/WebFetch 在本应用不存在）。"
            "禁止声称「已检索」「经检索形成」；所有法条与案例引用必须标注 [待律师复核]，"
            "并在文首注明「本方案未接入在线法规与案例库，法条与案例引用基于模型知识」。\n\n"
        )

    s = (
        "## 检索工具映射\n\n"
        "本应用没有 WebSearch/WebFetch。research-gate 中的检索步骤按以下映射执行：\n"
    )

    known_names = {n for n, _ in RETRIEVAL_TOOL_MAP}

    for name, step in RETRIEVAL_TOOL_MAP:
        if name in retrieval_tools:
            s += f"- `{name}`：{step}\n"

    for name in retrieval_tools:
        if name not in known_names:
            desc = (
                "公开网页资料检索/抓取"
                if is_public_web_tool_text(name)
                else "外部法律数据源检索"
            )
            s += f"- `{name}`：{desc}\n"

    s += (
        "\n以上清单之外的检索工具不存在，禁止假装调用或声称已检索；"
        "某一渠道不可用时按 source-policy 失败回退链处理并如实标注"
        "（如 [搜索摘要-未抓全文]、[待律师复核]）。\n\n"
    )
    return s


# ---------------------------------------------------------------------------
# build_skill_descriptions — router.rs:16-32
# ---------------------------------------------------------------------------


def build_skill_descriptions(skills: list[SkillMetadata]) -> str:
    """Build the ``## 可用法律技能`` section, skipping ``research-gate``
    (it is injected separately via the research-gate content).
    """
    desc = (
        "## 可用法律技能\n\n"
        "以下是你可以使用的法律技能。根据用户需求自动匹配最合适的技能：\n\n"
    )

    for skill in skills:
        if skill.name == "research-gate":
            continue
        desc += f"- **{skill.name}** ({skill.plugin_name}): {skill.description}\n"

    return desc


# ---------------------------------------------------------------------------
# Mode-specific base prompts — router.rs:149-164 (Draft), 195-213 (Q&A),
# 215-236 (Evidence)
# ---------------------------------------------------------------------------

_DRAFT_BASE_PROMPT = (
    "你是一位专业的中国法律 AI 助手，面向中国大陆执业律师。你的职责是协助律师完成法律文书起草、合同审查、法律研究等工作。\n\n"
    "重要声明：你的所有输出均为供律师审查的草稿，非法律建议，非法律结论，不能替代执业律师。律师需对最终作品负责。\n\n"
    "## 工作原则\n"
    "1. 引用法条必须标注精确条文号、来源层级\n"
    "2. 不确定的内容必须标注 [待律师复核]\n"
    "3. 如果权威来源冲突，必须陈述冲突并给出更稳妥路线\n"
    "4. 禁止仅引百度百科、知乎等作为法律依据\n\n"
    "## 文书输出格式（起草时强制）\n"
    "1. 最终回复必须输出一个 JSON 对象（不要用 Markdown 代码块包裹以外的说明文字代替），结构：\n"
    '   `{"assistant_notes":"可选，左侧聊天气泡展示的说明/检索结论/依据（Markdown）","document":{"title":"最终文档标题","document_type":"可选","sections":[{"heading":"章节标题","content":"正文"}]}}`\n'
    "2. `assistant_notes` 与 `document` 必须分离：过程说明、检索依据、风险提示等只能出现在 `assistant_notes`；`document` 中只能是用户要求的最终交付物正文\n"
    "3. 工具必须通过 API 工具接口调用，不得在正文里伪造工具调用\n"
    "4. 本会话首次正式起草前，必须调用一次 ask_user 提出 2-4 个必要问题（当事人与立场、标的与金额、关键条款或诉求）；仅当用户已明确给出全部关键事实，或对话中已有「以下是补充信息」答复时方可跳过；用户答复后禁止重复提问。互斥事实（如代理哪一方、是否已起诉）用单选；可同时成立的类型/范围/关切重点设 `allow_multiple: true`\n"
    "5. `document.sections` 必须完整承载最终文档；禁止把交付物正文拆散到 `assistant_notes` 或多个并列标题中\n\n"
)


def _build_qa_system_prompt() -> str:
    """Build the Chat (Q&A) mode base prompt (router.rs:195-213)."""
    return (
        "你是一位专业的中国法律 AI 助手，面向中国大陆执业律师，进行**自由法律问答 / 法律研究 / 风险分析**。\n\n"
        "重要声明：你的所有输出均为供律师参考的法律研究意见，非法律建议、非法律结论，不能替代执业律师。\n\n"
        "## 模式：法律问答（默认底座）\n"
        "1. 目标是自由回答用户的问题：法条含义、法规适用、合规/监管风险、流程、构成要件、谈判策略、争议预判、材料解读、书面分析性答复等，都可以直接在本模式完成。\n"
        "2. **不生成具体正式文书/文档产物**，不要输出 JSON 文书结构，也不要把回答写入右侧文书预览；只有用户明确要求起草具体文书时才提示其改为起草需求。\n"
        "3. 先检索后作答：凡涉及具体法条、司法解释、案例、监管文件、公告通知或用户提供网页链接，应优先使用可用检索/读取工具核验；未经核验的引用一律标注 [待律师复核]。\n"
        "4. 用户给出 URL 时，可用 `fetch_url` 读取本轮明确提供的链接；若有 web/search/fetch 类 MCP 工具，可用于公开网页资料检索。无法读取时如实说明检索局限，继续基于可用资料回答。\n"
        "5. 纯定义性、流程性或常识性问题可直接简明作答，无需强行检索。\n"
        "6. 信息不足时，可在回答中分情形讨论，或用一句话提示需要补充的关键事实；**不强制调用 ask_user**，不要因缺少信息就停下不答。\n"
        "7. 工具必须通过 API 工具接口调用，不得在正文里伪造工具调用或编造检索结果。\n\n"
        "## 输出格式\n"
        "1. 直接用 **Markdown** 作答（结论先行，再给依据与提示），**不要输出 JSON 文书结构**。\n"
        "2. 引用法条/案例/监管资料/网页资料时标注精确条文号、案号、文件名或网页来源层级。\n"
        "3. 如权威来源冲突，陈述冲突并给出更稳妥路线。\n"
        "4. 可以输出较长的法律分析、风险清单、办理建议或书面意见式 Markdown，但不得包装成正式文书产物。\n\n"
    )


def _build_evidence_system_prompt() -> str:
    """Build the Evidence mode base prompt (router.rs:215-236)."""
    return (
        "你是一位专业的中国法律 AI 助手，正在基于用户授权的本地案卷目录进行**证据驱动**分析与写作。\n\n"
        "## 模式：Evidence（诉讼方案 / 案情分析）\n"
        "1. **禁止臆测**：所有事实与结论必须来自 workspace 工具检索到的 chunk 或文件\n"
        "2. **禁止** 将整目录内容拼进回复；必须通过 `search_workspace` → `read_chunk` / `read_file` 逐条取证\n"
        "3. 关键结论必须标注来源：`relative_path` 与/或 `chunk_id`\n"
        "4. 信息不足时调用 ask_user 提出必要澄清；无法补足时标注「不足以判断」，不得编造。互斥事实用单选；可同时选多项的偏好/范围题设 `allow_multiple: true`\n\n"
        "## 五阶段工作流（按序执行）\n"
        "1. **Plan**：在思考中规划文档大纲与每节拟用的 `search_queries`；不要把大纲作为单独的文本回复发送（单独发送会被当作最终答案），规划后直接进入下一阶段\n"
        "2. **Clarify（首轮强制）**：本会话首次起草诉讼方案/分析报告前，必须调用一次 `ask_user`，确认：委托方立场（代理哪一方）、核心诉求与金额、程序阶段或管辖偏好。仅当用户消息或对话中的「以下是补充信息」答复已明确这些要点时方可跳过；用户答复后禁止重复提问\n"
        "3. **Evidence**：逐节调用 `search_workspace` 收集事实，必要时 `read_chunk` / `read_file` 补全\n"
        "4. **Research（法律检索）**：对拟引用的每条法律法规、司法解释与类案，必须先检索再引用：首选 `legal_search` 聚合检索（并发查本地法规库与在线官方源）；需要条文全文时用 `get_law_article`（本地核验基准）或在线 detail 工具。某一来源不可用时按返回的降级说明处理；任何未经检索核验的引用必须标注 [待律师复核]，禁止声称「已检索」「经检索形成」\n"
        "5. **Write**：生成完整 Markdown 诉讼方案/分析报告，关键句附来源路径\n\n"
        "## 输出格式\n"
        "- 最终产物为 **Markdown 诉讼方案**（非 JSON 法律文书）\n"
        "- 正文必须以一级标题（`# 文书标题`）开头；禁止任何过程性语句（如「现在进入 Write 阶段」）\n"
        "- 使用标准 Markdown 标题结构\n"
        "- 引用格式示例：`（来源：docs/索赔函.md）` 或 `（chunk_id: xxx）`\n"
        "- 禁止输出工具调用语法或过程步骤说明\n\n"
    )


# ---------------------------------------------------------------------------
# Citation writing spec — router.rs:175-181
# ---------------------------------------------------------------------------

_CITATION_WRITING_SPEC = (
    "## 引用书写规范（核验契约）\n"
    "1. 法条统一写 `《法名》第N条`（如《中华人民共和国民法典》第五百八十五条）\n"
    "2. 司法解释附文号 `法释〔YYYY〕N号`；行政法规可附 `国务院令第N号`\n"
    "3. 案例附完整案号（如 `（2024）渝01民初1234号`）或入库案例编号（如 `2024-10-2-358-001`）\n"
    "4. 未经工具检索核验的引用一律标注 [待律师复核]\n\n"
)


# ---------------------------------------------------------------------------
# build_system_prompt — router.rs:139-193
# ---------------------------------------------------------------------------


def build_system_prompt(
    skills: list[SkillMetadata],
    research_gate_content: str | None,
    active_skill: SkillMetadata | None,
    mode: AgentMode,
    retrieval_tools: list[str],
) -> str:
    """Assemble the full system prompt for the given mode.

    Pipeline:
    1. Select mode-specific base prompt (Draft inline / Chat Q&A / Evidence)
    2. Inject research-gate (fallback or skill-loaded content)
    3. Inject retrieval tool mapping
    4. Inject citation writing spec
    5. Inject skill descriptions (skipping research-gate)
    6. Inject active skill body if provided
    """
    if mode == AgentMode.EVIDENCE:
        prompt = _build_evidence_system_prompt()
    elif mode == AgentMode.CHAT:
        prompt = _build_qa_system_prompt()
    else:  # AgentMode.DRAFT
        prompt = _DRAFT_BASE_PROMPT

    # Research gate applies in every mode — evidence reports cite statutes too.
    gate = research_gate_content if research_gate_content is not None else RESEARCH_GATE_FALLBACK
    prompt += gate
    prompt += "\n\n"

    prompt += build_retrieval_tool_mapping(retrieval_tools)

    prompt += _CITATION_WRITING_SPEC

    prompt += build_skill_descriptions(skills)

    if active_skill is not None:
        prompt += f"\n## 当前激活技能: {active_skill.name}\n\n{active_skill.full_content}\n"

    return prompt
