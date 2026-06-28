from __future__ import annotations

import unittest

from conversation_read_view.privacy import (
    find_forbidden_raw_payload_path,
    scrub_contract_payload,
)


class PrivacyHelperTests(unittest.TestCase):
    def test_raw_payload_key_is_rejected_but_ref_is_preserved(self) -> None:
        self.assertEqual(
            find_forbidden_raw_payload_path({"metadata": {"raw_payload": {"body": "blocked"}}}),
            "metadata.raw_payload",
        )

        accepted = scrub_contract_payload({"metadata": {"raw_payload_ref": "fixture://raw/example"}})

        self.assertEqual(accepted["metadata"]["raw_payload_ref"], "fixture://raw/example")

    def test_nested_raw_payload_key_reports_list_path(self) -> None:
        self.assertEqual(
            find_forbidden_raw_payload_path({"events": [{"raw_payload": "blocked"}]}),
            "events[0].raw_payload",
        )

    def test_scrub_contract_payload_raises_for_exact_raw_payload(self) -> None:
        with self.assertRaises(ValueError):
            scrub_contract_payload({"raw_payload": {"secret": "blocked"}})


if __name__ == "__main__":
    unittest.main()

