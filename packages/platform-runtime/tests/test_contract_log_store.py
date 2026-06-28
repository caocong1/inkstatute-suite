from __future__ import annotations

import unittest

from platform_runtime import ContractLogPrivacyError, InMemoryContractLogStore


FIXED_NOW = "2026-06-29T03:15:00Z"


class InMemoryContractLogStoreTests(unittest.TestCase):
    def test_append_assigns_monotonic_sequences(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)

        first = store.append("run", {"run_id": "run-001", "status": "queued"})
        second = store.append("run_event", {"run_id": "run-001", "event_id": "evt-001"})

        self.assertEqual([first.seq, second.seq], [0, 1])
        self.assertEqual([entry.seq for entry in store.entries()], [0, 1])

    def test_entries_are_copy_safe(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)
        store.append("run", {"run_id": "run-001", "metadata": {"safe_summary": "stored by ref"}})

        returned = store.entries()
        returned[0].event["metadata"]["safe_summary"] = "mutated"

        self.assertEqual(
            store.entries()[0].event["metadata"]["safe_summary"],
            "stored by ref",
        )

    def test_rejects_top_level_raw_payload(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)

        with self.assertRaisesRegex(ContractLogPrivacyError, "forbidden raw_payload"):
            store.append("channel_message", {"run_id": "run-001", "raw_payload": "secret text"})

    def test_rejects_nested_raw_payload(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)

        with self.assertRaisesRegex(ContractLogPrivacyError, r"metadata.raw_payload"):
            store.append(
                "channel_message",
                {"run_id": "run-001", "metadata": {"raw_payload": "secret text"}},
            )

    def test_raw_payload_ref_and_reference_fields_are_allowed(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)

        entry = store.append(
            "channel_message",
            {
                "run_id": "run-001",
                "turn_id": "turn-001",
                "result_id": "result-001",
                "artifact_id": "artifact-001",
                "raw_payload_ref": "fixture://payloads/channel-message-001",
                "content_sha256": "0" * 64,
                "metadata": {"safe_summary": "synthetic fixture request"},
            },
        )

        self.assertEqual(entry.event["raw_payload_ref"], "fixture://payloads/channel-message-001")

    def test_entries_for_run_filters_copy_safe_entries(self) -> None:
        store = InMemoryContractLogStore(clock=lambda: FIXED_NOW)
        store.append("run", {"run_id": "run-001", "status": "queued"})
        store.append("run", {"run_id": "run-002", "status": "queued"})

        entries = store.entries_for_run("run-001")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].event["run_id"], "run-001")


if __name__ == "__main__":
    unittest.main()
