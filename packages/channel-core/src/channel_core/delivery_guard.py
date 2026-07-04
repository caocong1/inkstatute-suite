"""Delivery-completion guardrails for live task flows."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_FILE_REQUEST_RE = re.compile(
    r"(docx|word|修订稿|修订痕迹|批注|附件|文件|文档|生成.{0,12}(docx|word|文件|文档)|"
    r"(发送|交付|给我).{0,12}(docx|word|文件|文档|附件))",
    re.IGNORECASE,
)
_DELIVERY_MARKER_RE = re.compile(r"(?im)^\s*MEDIA\s*:\s*\S+|/[^\s]+?\.(?:docx|doc|pdf|xlsx)\b")
_PROGRESS_ONLY_RE = re.compile(
    r"(已解析|解析完毕|正在|现在|接下来|开始|将要|准备|处理中|稍等|"
    r"生成.{0,16}(docx|word|文件|文档)|编制.{0,16}(审查|修订|docx|word))",
    re.IGNORECASE,
)
_FINAL_FAILURE_RE = re.compile(r"(无法|不能|未能|失败|报错|出错).{0,20}(生成|发送|交付|完成|处理)")


@dataclass(frozen=True)
class DeliveryCompletionAssessment:
    """Whether an agent answer satisfies the user-visible delivery contract."""

    completed: bool
    reason: str
    issue_code: str | None = None
    requested_file_delivery: bool = False
    progress_only: bool = False

    def as_metadata(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "reason": self.reason,
            "issue_code": self.issue_code,
            "requested_file_delivery": self.requested_file_delivery,
            "progress_only": self.progress_only,
        }


def assess_delivery_completion(
    *,
    user_text: str,
    answer_text: str,
    media_count: int = 0,
    file_count: int = 0,
) -> DeliveryCompletionAssessment:
    """Fail closed when a file-delivery task returns only a progress sentence.

    Hermes one-shot can return a short status update such as "now generating the
    DOCX" even though no final artifact was produced. InkStatute must not mark
    that as completed for ordinary users.
    """

    user_text = user_text or ""
    answer_text = answer_text or ""
    requested_file_delivery = bool(_FILE_REQUEST_RE.search(user_text))
    has_delivery_marker = bool(file_count > 0 or _DELIVERY_MARKER_RE.search(answer_text))
    progress_only = bool(_PROGRESS_ONLY_RE.search(answer_text)) and not bool(_FINAL_FAILURE_RE.search(answer_text))

    if requested_file_delivery and not has_delivery_marker and progress_only:
        return DeliveryCompletionAssessment(
            completed=False,
            reason="agent_returned_progress_without_requested_artifact",
            issue_code="agent_backend_incomplete_output",
            requested_file_delivery=True,
            progress_only=True,
        )

    if media_count > 0 and not has_delivery_marker and progress_only and _FILE_REQUEST_RE.search(answer_text):
        return DeliveryCompletionAssessment(
            completed=False,
            reason="agent_described_artifact_generation_without_artifact",
            issue_code="agent_backend_incomplete_output",
            requested_file_delivery=requested_file_delivery,
            progress_only=True,
        )

    return DeliveryCompletionAssessment(
        completed=True,
        reason="delivery_contract_satisfied",
        requested_file_delivery=requested_file_delivery,
        progress_only=progress_only,
    )


__all__ = ["DeliveryCompletionAssessment", "assess_delivery_completion"]
