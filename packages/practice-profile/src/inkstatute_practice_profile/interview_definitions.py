"""Commercial-legal cold-start interview step definitions.

Defines the 5-step interview as :class:`InterviewStep` objects, each
containing 2-4 :class:`ElicitationQuestion` objects.  The questions are
derived from the ``commercial-legal/skills/cold-start-interview/SKILL.md``
and ``commercial-legal/skills/_shared/practice-profile-schema.md`` source
files.

Step order (from SKILL.md):
1. ``identity-team`` — identity, practice environment, team structure, integrations
2. ``review-stance`` — risk appetite, 甲方/乙方 stance
3. ``escalation-rules`` — amount thresholds, auto-escalation triggers
4. ``document-style`` — output format, tone, citation preferences
5. ``jurisdiction-profile`` — governing law, local regulations

Each step is validated by :func:`validate_question_count` at import
time to enforce the 2-4 question constraint from ASK-USER-PROTOCOL.md.
"""

from __future__ import annotations

from platform_contract.elicitation import validate_question_count
from platform_contract.unified_events import ElicitationOption, ElicitationQuestion

from .interview import InterviewStep


# ---------------------------------------------------------------------------
# Step 1: identity-team (4 questions)
# ---------------------------------------------------------------------------

_IDENTITY_TEAM_QUESTIONS: list[ElicitationQuestion] = [
    ElicitationQuestion(
        id="identity-team.company_name",
        question="您所在的公司或律所名称是什么？",
    ),
    ElicitationQuestion(
        id="identity-team.entity_type",
        question="您的实体类型是？",
        options=[
            ElicitationOption(label="有限责任公司", value="有限责任公司"),
            ElicitationOption(label="股份有限公司", value="股份有限公司"),
            ElicitationOption(label="合伙企业", value="合伙企业"),
            ElicitationOption(label="个人独资企业", value="个人独资企业"),
            ElicitationOption(label="其他", value="其他"),
        ],
    ),
    ElicitationQuestion(
        id="identity-team.team_size",
        question="您的合同团队规模大约是多少人？",
    ),
    ElicitationQuestion(
        id="identity-team.counterparty_type",
        question="您主要处理的交易对手类型是？",
        options=[
            ElicitationOption(label="大客户", value="大客户"),
            ElicitationOption(label="中小企业", value="中小企业"),
            ElicitationOption(label="个人", value="个人"),
            ElicitationOption(label="混合", value="混合"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Step 2: review-stance (2 questions)
# ---------------------------------------------------------------------------

_REVIEW_STANCE_QUESTIONS: list[ElicitationQuestion] = [
    ElicitationQuestion(
        id="review-stance.risk_appetite",
        question="您团队的整体风险偏好是？",
        options=[
            ElicitationOption(label="保守型", value="保守型"),
            ElicitationOption(label="平衡型", value="平衡型"),
            ElicitationOption(label="进取型", value="进取型"),
        ],
    ),
    ElicitationQuestion(
        id="review-stance.primary_side",
        question="您在合同审查中主要代表哪一方？",
        options=[
            ElicitationOption(label="甲方（买方/委托方）", value="甲方"),
            ElicitationOption(label="乙方（卖方/受托方）", value="乙方"),
            ElicitationOption(label="两方都有", value="both"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Step 3: escalation-rules (2 questions)
# ---------------------------------------------------------------------------

_ESCALATION_RULES_QUESTIONS: list[ElicitationQuestion] = [
    ElicitationQuestion(
        id="escalation-rules.junior_threshold",
        question="助理/初级律师可独立审批的金额上限是多少？（如 ¥50万）",
    ),
    ElicitationQuestion(
        id="escalation-rules.auto_escalation_triggers",
        question="无论金额大小，以下哪些情况必须自动升级？（可多选）",
        allow_multiple=True,
        options=[
            ElicitationOption(label="无限责任条款", value="无限责任条款"),
            ElicitationOption(label="知识产权全部转让", value="知识产权全部转让"),
            ElicitationOption(label="管辖法律为境外法律", value="管辖法律为境外法律"),
            ElicitationOption(label="其他", value="其他"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Step 4: document-style (2 questions)
# ---------------------------------------------------------------------------

_DOCUMENT_STYLE_QUESTIONS: list[ElicitationQuestion] = [
    ElicitationQuestion(
        id="document-style.revision_tone",
        question="您偏好的修订语气是？",
        options=[
            ElicitationOption(label="温和但有立场", value="温和但有立场"),
            ElicitationOption(label="严格", value="严格"),
            ElicitationOption(label="灵活", value="灵活"),
        ],
    ),
    ElicitationQuestion(
        id="document-style.citation_preference",
        question="您偏好的引用风格是？",
        options=[
            ElicitationOption(label="含法条引用", value="含法条引用"),
            ElicitationOption(label="含案例引用", value="含案例引用"),
            ElicitationOption(label="半正式", value="半正式"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Step 5: jurisdiction-profile (2 questions)
# ---------------------------------------------------------------------------

_JURISDICTION_PROFILE_QUESTIONS: list[ElicitationQuestion] = [
    ElicitationQuestion(
        id="jurisdiction-profile.governing_law",
        question="您主要适用的管辖法律是？",
        options=[
            ElicitationOption(label="中国大陆法律", value="中国大陆法律"),
            ElicitationOption(label="其他", value="其他"),
        ],
    ),
    ElicitationQuestion(
        id="jurisdiction-profile.special_zones",
        question="您的业务涉及哪些特别管辖区域？（可多选）",
        allow_multiple=True,
        options=[
            ElicitationOption(label="经济特区", value="经济特区"),
            ElicitationOption(label="民族自治地方", value="民族自治地方"),
            ElicitationOption(label="自贸区", value="自贸区"),
            ElicitationOption(label="港澳台", value="港澳台"),
            ElicitationOption(label="无", value="无"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Assembled step list
# ---------------------------------------------------------------------------

COMMERCIAL_LEGAL_INTERVIEW_STEPS: list[InterviewStep] = [
    InterviewStep(
        step_id="identity-team",
        intro="让我们了解您的团队和执业环境",
        questions=_IDENTITY_TEAM_QUESTIONS,
    ),
    InterviewStep(
        step_id="review-stance",
        intro="让我们确认您的审查立场和风险偏好",
        questions=_REVIEW_STANCE_QUESTIONS,
    ),
    InterviewStep(
        step_id="escalation-rules",
        intro="让我们配置升级矩阵和自动升级规则",
        questions=_ESCALATION_RULES_QUESTIONS,
    ),
    InterviewStep(
        step_id="document-style",
        intro="让我们设置您的文书风格和输出偏好",
        questions=_DOCUMENT_STYLE_QUESTIONS,
    ),
    InterviewStep(
        step_id="jurisdiction-profile",
        intro="让我们确认您的管辖法律和特别区域",
        questions=_JURISDICTION_PROFILE_QUESTIONS,
    ),
]


# ---------------------------------------------------------------------------
# Validate all steps at import time (enforce 2-4 question constraint)
# ---------------------------------------------------------------------------

for _step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
    validate_question_count(_step.questions)


__all__ = [
    "COMMERCIAL_LEGAL_INTERVIEW_STEPS",
]
