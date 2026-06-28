from __future__ import annotations

import unittest

from feedback_service.classification import FEEDBACK_CATEGORIES, classify_feedback_event


class FeedbackClassificationTests(unittest.TestCase):
    def test_classification_covers_all_prd_categories(self) -> None:
        cases = {
            "rating": {"event_type": "rating", "action": "up"},
            "correction": {"event_type": "correction", "action": "down"},
            "fact_missing": {"event_type": "correction", "labels": ["fact_missing"]},
            "citation_error": {"event_type": "correction", "message": "Citation is wrong."},
            "route_mismatch": {"event_type": "route_mismatch", "route_mismatch": True},
            "format_issue": {"event_type": "correction", "labels": ["format_issue"]},
            "compliance_issue": {"event_type": "correction", "message": "Compliance issue."},
            "skill_candidate": {
                "event_type": "skill_candidate",
                "skill_candidate": {"detected": True, "requires_human_review": True},
            },
        }

        self.assertEqual(set(cases), FEEDBACK_CATEGORIES)
        for expected, event in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify_feedback_event(event).category, expected)

    def test_route_mismatch_requires_human_review_and_no_auto_modify(self) -> None:
        classification = classify_feedback_event({"event_type": "correction", "route_mismatch": True})

        self.assertEqual(classification.category, "route_mismatch")
        self.assertTrue(classification.requires_human_review)
        self.assertTrue(classification.no_auto_modify)


if __name__ == "__main__":
    unittest.main()

