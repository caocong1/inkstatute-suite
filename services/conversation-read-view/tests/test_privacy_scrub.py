from __future__ import annotations

import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.privacy import find_forbidden_key_path, scrub_contract_payload
from platform_runtime.privacy_keys import ALL_FORBIDDEN_KEYS


class PrivacyScrubTests(unittest.TestCase):
    def test_scrub_rejects_new_backend_fields_at_read_time(self) -> None:
        for key in ("prompt_content", "completion_text", "function_call_result", "tool_output"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    scrub_contract_payload({key: "sensitive"})

    def test_scrub_rejects_existing_full_text_keys_at_read_time(self) -> None:
        for key in ("case_facts", "document_text", "full_text"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    scrub_contract_payload({key: "sensitive"})

    def test_scrub_preserves_safe_ref_fields(self) -> None:
        result = scrub_contract_payload({"raw_payload_ref": "fixture://raw/example"})
        self.assertEqual(result["raw_payload_ref"], "fixture://raw/example")

    def test_all_api_response_paths_apply_scrub(self) -> None:
        class FakeReadModel:
            def get_conversation(self, conversation_id: str):
                return {"conversation_id": "c1", "case_facts": "sensitive"}

            def get_task(self, identifier: str):
                return {"turn_id": "t1", "prompt_content": "sensitive"}

            def get_task_by_trace_id(self, identifier: str):
                return None

        read_model = FakeReadModel()

        with self.assertRaises(ValueError):
            handle_get("/conversations/c1", "", read_model)

        with self.assertRaises(ValueError):
            handle_get("/tasks/t1", "", read_model)

    def test_unified_keys_match_between_store_and_read(self) -> None:
        for key in ALL_FORBIDDEN_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    scrub_contract_payload({key: "sensitive"})

    def test_find_forbidden_key_path_detects_all_forbidden_keys(self) -> None:
        for key in ALL_FORBIDDEN_KEYS:
            with self.subTest(key=key):
                self.assertEqual(find_forbidden_key_path({key: "sensitive"}), key)


if __name__ == "__main__":
    unittest.main()
