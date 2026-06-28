from __future__ import annotations

from pathlib import Path
import unittest

from feedback_service.wecom_normalizer import (
    FeedbackNormalizationIssue,
    NormalizedFeedbackBatch,
    normalize_wecom_feedback_records,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]


class FeedbackServiceScaffoldTests(unittest.TestCase):
    def test_normalizer_is_importable_and_returns_batch(self) -> None:
        batch = normalize_wecom_feedback_records([], [], now="2026-06-28T03:20:00Z")

        self.assertIsInstance(batch, NormalizedFeedbackBatch)
        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues, [])

    def test_issue_dataclass_is_exported(self) -> None:
        issue = FeedbackNormalizationIssue(code="sample", message="sample issue")

        self.assertEqual(issue.code, "sample")
        self.assertIsNone(issue.feedback_ref)

    def test_pyproject_declares_no_runtime_dependencies(self) -> None:
        text = (SERVICE_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("dependencies = []", text)

    def test_readme_defers_phase6_scope_and_legal_skill_modification(self) -> None:
        text = (SERVICE_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Phase 6 owns APIs", text)
        self.assertIn("does not automatically modify legal skills", text)


if __name__ == "__main__":
    unittest.main()
