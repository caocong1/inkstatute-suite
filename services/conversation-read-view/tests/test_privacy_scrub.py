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


class ForbiddenKeyFakeReadModel:
    """Fake read model that returns forbidden keys in every new endpoint path."""

    def get_conversation(self, conversation_id: str):
        return {"conversation_id": "c1", "case_facts": "sensitive"}

    def get_task(self, identifier: str):
        return {"turn_id": "t1", "prompt_content": "sensitive"}

    def get_task_by_trace_id(self, identifier: str):
        return None

    def list_conversations(self, **kwargs):
        return [("c1", "2026-01-01T00:00:00Z", {"conversation_id": "c1", "case_facts": "sensitive"})]

    def list_tasks(self, **kwargs):
        return [("t1", "2026-01-01T00:00:00Z", {"task_id": "t1", "completion_text": "sensitive"})]

    def get_trace_reconstruction(self, trace_id: str):
        return {
            "trace_id": trace_id,
            "turn_id": "t1",
            "task_id": "t1",
            "conversation_id": "c1",
            "events": [
                {
                    "event_key": "agent_turn",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "seq": 0,
                    "event": {"turn_id": "t1", "document_text": "sensitive"},
                }
            ],
            "metadata": {
                "derived_from_contract_log": True,
                "event_count": 1,
                "reconstruction_complete": True,
            },
        }


class NewEndpointPrivacyScrubTests(unittest.TestCase):
    """Verify all 4 new endpoints raise ValueError on forbidden keys."""

    def test_list_conversations_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/conversations", "", read_model)

    def test_list_tasks_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/tasks", "", read_model)

    def test_trace_reconstruction_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/traces/trace-001", "", read_model)

    def test_export_json_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/export?resource=conversations&format=json", "", read_model)

    def test_export_csv_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/export?resource=conversations&format=csv", "", read_model)

    def test_export_tasks_json_raises_on_forbidden_key(self) -> None:
        read_model = ForbiddenKeyFakeReadModel()
        with self.assertRaises(ValueError):
            handle_get("/export?resource=tasks&format=json", "", read_model)

    def test_all_forbidden_keys_raise_on_new_endpoints(self) -> None:
        for key in ALL_FORBIDDEN_KEYS:
            with self.subTest(key=key):

                class _Model:
                    def list_conversations(self, **kwargs):
                        return [("c1", "2026-01-01T00:00:00Z", {"conversation_id": "c1", key: "sensitive"})]

                    def list_tasks(self, **kwargs):
                        return []

                    def get_trace_reconstruction(self, trace_id: str):
                        return None

                    def get_conversation(self, conversation_id: str):
                        return None

                    def get_task(self, identifier: str):
                        return None

                    def get_task_by_trace_id(self, identifier: str):
                        return None

                with self.assertRaises(ValueError):
                    handle_get("/conversations", "", _Model())

    def test_trace_endpoint_raises_on_forbidden_key_in_event(self) -> None:
        class _TraceModel:
            def get_trace_reconstruction(self, trace_id: str):
                return {
                    "trace_id": trace_id,
                    "turn_id": "t1",
                    "task_id": "t1",
                    "conversation_id": "c1",
                    "events": [
                        {
                            "event_key": "agent_turn",
                            "occurred_at": "2026-01-01T00:00:00Z",
                            "seq": 0,
                            "event": {"turn_id": "t1", "raw_payload": "sensitive"},
                        }
                    ],
                    "metadata": {
                        "derived_from_contract_log": True,
                        "event_count": 1,
                        "reconstruction_complete": True,
                    },
                }

            def get_conversation(self, conversation_id: str):
                return None

            def get_task(self, identifier: str):
                return None

            def get_task_by_trace_id(self, identifier: str):
                return None

            def list_conversations(self, **kwargs):
                return []

            def list_tasks(self, **kwargs):
                return []

        with self.assertRaises(ValueError):
            handle_get("/traces/trace-001", "", _TraceModel())

    def test_export_metadata_is_scrubbed(self) -> None:
        class _NestedModel:
            def list_conversations(self, **kwargs):
                return [
                    (
                        "c1",
                        "2026-01-01T00:00:00Z",
                        {
                            "conversation_id": "c1",
                            "metadata": {"raw_payload": "sensitive"},
                        },
                    )
                ]

            def list_tasks(self, **kwargs):
                return []

            def get_trace_reconstruction(self, trace_id: str):
                return None

            def get_conversation(self, conversation_id: str):
                return None

            def get_task(self, identifier: str):
                return None

            def get_task_by_trace_id(self, identifier: str):
                return None

        with self.assertRaises(ValueError):
            handle_get("/export?resource=conversations&format=json", "", _NestedModel())


if __name__ == "__main__":
    unittest.main()
