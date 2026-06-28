from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contract_test_suite.privacy_scan import (
    assert_privacy_clean,
    default_privacy_data_paths,
    scan_privacy_targets,
)


class PrivacyGateTests(unittest.TestCase):
    def test_data_raw_payload_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fixture.json"
            path.write_text('{"raw_payload": "blocked"}', encoding="utf-8")

            issues = scan_privacy_targets([path], mode="data")

        self.assertEqual([issue.code for issue in issues], ["raw_payload_field"])

    def test_raw_payload_ref_passes_data_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fixture.json"
            path.write_text('{"raw_payload_ref": "fixture://raw/example"}', encoding="utf-8")

            assert_privacy_clean([path], mode="data")

    def test_source_guard_string_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "validator.py"
            path.write_text('if key == "raw_payload":\n    raise ValueError("guard")\n', encoding="utf-8")

            assert_privacy_clean([path], mode="source")

    def test_secret_like_string_fails_with_redacted_summary(self) -> None:
        secret = "sk-1234567890abcdefghijklmnop"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fixture.json"
            path.write_text(f'{{"api_key": "{secret}"}}', encoding="utf-8")

            with self.assertRaises(AssertionError) as raised:
                assert_privacy_clean([path], mode="data")

        self.assertIn("secret_value", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))

    def test_default_privacy_data_paths_are_clean(self) -> None:
        assert_privacy_clean(default_privacy_data_paths(), mode="data")


if __name__ == "__main__":
    unittest.main()

