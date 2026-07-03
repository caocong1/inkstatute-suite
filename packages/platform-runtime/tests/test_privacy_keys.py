from __future__ import annotations

import unittest

from platform_runtime import ContractLogPrivacyError, InMemoryContractLogStore
from platform_runtime.privacy_keys import (
    ALL_FORBIDDEN_KEYS,
    FORBIDDEN_FULL_TEXT_KEYS,
    FORBIDDEN_RAW_PAYLOAD_KEY,
)


FIXED_NOW = "2026-06-29T03:15:00Z"


class PrivacyKeysTests(unittest.TestCase):
    def test_all_forbidden_keys_contains_11_keys(self) -> None:
        self.assertEqual(len(ALL_FORBIDDEN_KEYS), 11)

    def test_new_backend_fields_are_forbidden(self) -> None:
        for key in ("prompt_content", "completion_text", "function_call_result", "tool_output"):
            with self.subTest(key=key):
                self.assertIn(key, ALL_FORBIDDEN_KEYS)

    def test_existing_keys_remain_forbidden(self) -> None:
        for key in (
            "raw_payload",
            "case_facts",
            "customer_document_text",
            "document_text",
            "full_text",
            "payload_text",
            "raw_text",
        ):
            with self.subTest(key=key):
                self.assertIn(key, ALL_FORBIDDEN_KEYS)

    def test_forbidden_full_text_keys_contains_10_keys(self) -> None:
        self.assertEqual(len(FORBIDDEN_FULL_TEXT_KEYS), 10)

    def test_forbidden_raw_payload_key_is_raw_payload(self) -> None:
        self.assertEqual(FORBIDDEN_RAW_PAYLOAD_KEY, "raw_payload")

    def test_store_rejects_new_backend_fields(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)
        for key in ("prompt_content", "completion_text", "function_call_result", "tool_output"):
            with self.subTest(key=key):
                with self.assertRaises(ContractLogPrivacyError):
                    store.append("run_event", {"run_id": "run-001", key: "sensitive backend text"})

    def test_store_rejects_raw_payload(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)
        with self.assertRaises(ContractLogPrivacyError):
            store.append("channel_message", {"run_id": "run-001", "raw_payload": "secret text"})


if __name__ == "__main__":
    unittest.main()
