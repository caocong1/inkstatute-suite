"""Strong-signal deterministic routing rules.

Ports the 11 ``_Rule`` entries and the ``factual_short_circuit`` logic
verbatim from ``lawfirm-profile/scripts/router.py`` (lines 59-224).

The strong-signal rules are deterministic regex patterns that run BEFORE
the strategy cascade.  They are a separate concern from the existing
``classify_intent()`` (which has 4 generic categories).

Public API:
    StrongSignalRule — dataclass for a single rule
    build_strong_signal_rules() — returns the 11 rules (first-match-wins)
    match_strong_signal(message) — returns the first matching rule or None
    is_simple_factual(message) — ports ``_is_simple_factual()`` exactly
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StrongSignalRule:
    """Internal strong-signal rule representation.

    Ported verbatim from ``lawfirm-profile/scripts/router.py`` ``_Rule``
    (lines 59-71).  Field names match the source exactly.
    """

    name: str
    pattern: re.Pattern[str]
    primary: str | None
    supporting: list[str] = field(default_factory=list)
    gate_before: str | None = None
    gate_after: str | None = None
    skip_clarification: bool = False
    confidence: float = 0.95
    reason: str = ""


def build_strong_signal_rules() -> list[StrongSignalRule]:
    """Strong-signal patterns that unambiguously identify a target skill.

    Returns exactly 11 rules in first-match-wins order, ported verbatim
    from ``lawfirm-profile/scripts/router.py`` ``_build_strong_signal_rules()``
    (lines 74-203).
    """
    return [
        # 法院短信 — strongest signal: SMS text + 送达 + 案号
        StrongSignalRule(
            name="court_sms",
            pattern=re.compile(
                r"(法院\s*(短信|送达)|送达文书|案号\s*[\(（]?\d{4}[\)）]"
                r"|zxfw\.court\.gov\.cn|全国法院送达平台)"
            ),
            primary="legal-court-sms",
            supporting=[],
            gate_after="legal-de-ai-polish",
            reason="法院短信/送达通知 → 自动解析 + 下载 + 归档",
        ),
        # 判决书 / 庭审笔录
        StrongSignalRule(
            name="judgment_or_transcript",
            pattern=re.compile(
                r"(判决书|裁定书|庭审笔录|开庭笔录|一审判决|二审判决)"
            ),
            primary="legal-litigation-analysis",
            supporting=[],
            reason="判决书/庭审笔录 → 三层分析（内部/研究/客户版）",
        ),
        # 新案件 / 立案 / 建项目 — primary legal-new-case + supporting matter-intake
        StrongSignalRule(
            name="new_case",
            pattern=re.compile(
                r"(新\s*(接|建|立|办|收)\s*(了|一个|起)?\s*"
                r"(案子|案件|项目|业务|委托)|"
                r"立案|建项目|接收新业务|刚接了.*案子|"
                r"我.*接了.*案|接了个案|刚接了个)"
            ),
            primary="legal-new-case",
            supporting=["litigation-matter-intake"],
            gate_before="ask-user-enforcement",
            reason="新建案件 → 先建标准化目录 + 案件录入",
        ),
        # DOCX 合同审查 — strongest: file extension mentioned
        StrongSignalRule(
            name="docx_contract_review",
            pattern=re.compile(
                r"(\.docx\s*(合同|文件)?|DOCX\s*合同|合同\s*\.docx|"
                r"审\s*合同|审查\s*合同|审核\s*合同|合同\s*审查|合同\s*审核|"
                r"帮我.*合同|合同.*(帮我|需要|想))"
            ),
            primary="legal-contract-copilot",
            supporting=[],
            gate_before="ask-user-enforcement",
            gate_after="legal-de-ai-polish",
            reason="DOCX/合同审查 → 走 DOCX 批注修订 + 审查报告交付链",
        ),
        # 客户咨询 → 知识沉淀 (legal-qa-extractor)
        StrongSignalRule(
            name="qa_extraction",
            pattern=re.compile(
                r"(客户.*咨询.*(沉淀|整理|知识库)|问答对|QA\s*库|知识沉淀)"
            ),
            primary="legal-qa-extractor",
            supporting=[],
            reason="客户咨询 → 脱敏 + 结构化问答对",
        ),
        # 文书初稿完成 / 写完起诉状后 → 强制跑 AI 去化
        StrongSignalRule(
            name="polish_draft",
            pattern=re.compile(
                r"(写完(了)?.*(起诉状|答辩状|合同|意见书|律师函)|"
                r"AI\s*化表述|去\s*AI\s*腔|去除\s*AI\s*化)"
            ),
            primary="legal-de-ai-polish",
            supporting=[],
            reason="文书初稿完成 → 强制 AI 去化表述",
        ),
        # 知识产权 — 商标/专利/著作权侵权与申请
        StrongSignalRule(
            name="ip_infringement",
            pattern=re.compile(
                r"(侵犯.*(商标|专利|著作权|商业秘密|知识产权)|"
                r"(商标|专利|著作权).*(侵权|侵犯|抢注|山寨|假冒)|"
                r"被.*(抢注|仿冒|抄袭))"
            ),
            primary="ip-ip-clearance",
            supporting=[],
            reason="知识产权侵权 → IP 清查 / 不正当竞争分析",
        ),
        StrongSignalRule(
            name="ip_filing",
            pattern=re.compile(
                r"(申请.*(商标|专利|著作权|版权)|"
                r"(商标|专利|著作权|版权)\s*(登记|注册|申请)|"
                r"软件著作权\s*登记)"
            ),
            primary="ip-trademark-search",  # default; could refine
            supporting=[],
            reason="知产申请 → 商标/专利/著作权登记流程",
        ),
        # 劳动争议 — 优先于 generic 非竞业
        StrongSignalRule(
            name="labor_dispute",
            pattern=re.compile(
                r"(劳动\s*(争议|纠纷|仲裁)|劳动合同\s*(争议|纠纷)|"
                r"拖欠.*(工资|加班费|补偿金)|违法\s*解除)"
            ),
            primary="employment-labor-dispute-handling",
            supporting=[],
            reason="劳动争议 → employment-labor-dispute-handling",
        ),
        # 上市 / 合规体系建设
        StrongSignalRule(
            name="compliance_system",
            pattern=re.compile(
                r"(上市\s*(前|合规|辅导)|合规体系\s*(建设|搭建)|"
                r"合规\s*(审查|自查|检查)|合规差距)"
            ),
            primary="regulatory-compliance-system",
            supporting=[],
            reason="合规体系 / 上市前合规 → regulatory-compliance-system",
        ),
        # OPC / 一人公司 / 小微企业常年顾问
        StrongSignalRule(
            name="opc_counsel",
            pattern=re.compile(
                r"(OPC|一人公司|小微企业|常年顾问|公司设立|股权架构|公私分离)"
            ),
            primary="legal-opc-legal-counsel",
            supporting=[],
            reason="OPC 场景 → 一句话结论 + 事实缺口 + 红线",
        ),
    ]


def match_strong_signal(message: str) -> StrongSignalRule | None:
    """Return the first matching :class:`StrongSignalRule` or ``None``.

    Iterates rules in first-match-wins order, same as the source
    ``lawfirm-profile/scripts/router.py`` ``route()`` function (lines 368-383).
    """
    for rule in build_strong_signal_rules():
        if rule.pattern.search(message):
            return rule
    return None


# ── Simple factual Q&A patterns (no skill needed) ─────────────────────────
# Ported verbatim from lawfirm-profile/scripts/router.py lines 208-214.

_FACTUAL_Q_PATTERNS = [
    re.compile(r"《?[\u4e00-\u9fff]+法》?第\s*\d+\s*条.*是什么"),
    re.compile(r"民法典第\s*\d+\s*条"),
    re.compile(r"什么是\s*\S{2,15}"),
    re.compile(r"^.{0,20}(怎么读|什么意思|如何理解|有什么区别)"),
    re.compile(r"^\s*[Qq]:"),  # plain Q: prefix
]


def is_simple_factual(user_msg: str) -> bool:
    """Quick heuristic: is this just a statute/term lookup?

    Ports ``_is_simple_factual()`` exactly from
    ``lawfirm-profile/scripts/router.py`` (lines 217-224):
    - empty → True
    - len < 12 → True
    - matches any ``_FACTUAL_Q_PATTERNS`` → True
    """
    msg = user_msg.strip()
    if not msg:
        return True
    if len(msg) < 12:
        return True
    return any(p.search(msg) for p in _FACTUAL_Q_PATTERNS)
