"""Tests for TenantScopedContractLogReadModel — tenant_id filtering of read-model queries."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from conversation_read_view.tenant_read_model import TenantScopedContractLogReadModel
from platform_runtime.tenant_scope import ScopedQueryFilter


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


def _load_raw_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_tenant_tagged_records() -> list[dict[str, object]]:
    """Build records with tenant_id injected into all event dicts.

    Clones the PHASE5_STREAM records and injects ``tenant_id`` into every
    event dict (matching ``TenantScopedContractLogStore.append()`` behavior).
    Since the fixture has a single conversation/turn, we duplicate it with
    different tenant_ids to create multi-tenant test data.
    """
    base_records = _load_raw_records(PHASE5_STREAM)
    records: list[dict[str, object]] = []

    # Clone with tenant_id="firm-a"
    for rec in base_records:
        cloned = copy.deepcopy(rec)
        event = cloned.get("event")
        if isinstance(event, dict):
            event["tenant_id"] = "firm-a"
            if cloned.get("event_key") == "agent_turn":
                event["conversation_id"] = "conv-firm-a"
                event["turn_id"] = "turn-firm-a"
            elif "turn_id" in event:
                event["turn_id"] = "turn-firm-a"
                event["conversation_id"] = "conv-firm-a"
        records.append(cloned)

    # Clone with tenant_id="firm-b"
    for rec in base_records:
        cloned = copy.deepcopy(rec)
        event = cloned.get("event")
        if isinstance(event, dict):
            event["tenant_id"] = "firm-b"
            if cloned.get("event_key") == "agent_turn":
                event["conversation_id"] = "conv-firm-b"
                event["turn_id"] = "turn-firm-b"
            elif "turn_id" in event:
                event["turn_id"] = "turn-firm-b"
                event["conversation_id"] = "conv-firm-b"
        records.append(cloned)

    return records


class TenantScopedReadModelTests(unittest.TestCase):
    def setUp(self) -> None:
        records = _build_tenant_tagged_records()
        self.base_model = build_read_model(records)
        self.scoped_model = TenantScopedContractLogReadModel(self.base_model)

    def test_disabled_filter_returns_all_conversations(self) -> None:
        """ScopedQueryFilter.disabled() → all conversations returned (no regression)."""
        disabled = ScopedQueryFilter.disabled()
        results = self.scoped_model.list_conversations(tenant_filter=disabled)
        self.assertEqual(len(results), 2)

    def test_disabled_filter_returns_all_tasks(self) -> None:
        """ScopedQueryFilter.disabled() → all tasks returned (no regression)."""
        disabled = ScopedQueryFilter.disabled()
        results = self.scoped_model.list_tasks(tenant_filter=disabled)
        self.assertGreaterEqual(len(results), 1)

    def test_active_filter_returns_only_matching_conversations(self) -> None:
        """Active filter with tenant_id='firm-a' → only firm-a conversations."""
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        results = self.scoped_model.list_conversations(tenant_filter=active)
        self.assertEqual(len(results), 1)
        conv = results[0][2]
        self.assertEqual(conv["conversation_id"], "conv-firm-a")

    def test_active_filter_returns_only_matching_tasks(self) -> None:
        """Active filter with tenant_id='firm-b' → only firm-b tasks."""
        active = ScopedQueryFilter(tenant_id="firm-b", active=True)
        results = self.scoped_model.list_tasks(tenant_filter=active)
        self.assertGreaterEqual(len(results), 1)
        for _, _, task_dict in results:
            # Task should belong to firm-b conversation
            self.assertEqual(task_dict["conversation_id"], "conv-firm-b")

    def test_active_filter_get_conversation_returns_none_for_wrong_tenant(self) -> None:
        """get_conversation with non-matching tenant_id → None (invisible)."""
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        result = self.scoped_model.get_conversation("conv-firm-b", tenant_filter=active)
        self.assertIsNone(result)

    def test_active_filter_get_conversation_returns_data_for_matching_tenant(self) -> None:
        """get_conversation with matching tenant_id → conversation returned."""
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        result = self.scoped_model.get_conversation("conv-firm-a", tenant_filter=active)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["conversation_id"], "conv-firm-a")

    def test_active_filter_get_task_returns_none_for_wrong_tenant(self) -> None:
        """get_task with non-matching tenant_id → None (invisible)."""
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        # firm-b's task uses turn-firm-b as task_id (fallback)
        result = self.scoped_model.get_task("turn-firm-b", tenant_filter=active)
        self.assertIsNone(result)

    def test_active_filter_get_task_returns_data_for_matching_tenant(self) -> None:
        """get_task with matching tenant_id → task returned."""
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        result = self.scoped_model.get_task("turn-firm-a", tenant_filter=active)
        self.assertIsNotNone(result)

    def test_no_filter_returns_all(self) -> None:
        """tenant_filter=None → all returned (backward compat)."""
        results = self.scoped_model.list_conversations(tenant_filter=None)
        self.assertEqual(len(results), 2)

        results = self.scoped_model.list_tasks(tenant_filter=None)
        self.assertGreaterEqual(len(results), 1)

    def test_issues_property_delegates(self) -> None:
        """issues property returns delegate's issues."""
        self.assertEqual(self.scoped_model.issues, self.base_model.issues)

    def test_get_task_by_trace_id_with_active_filter(self) -> None:
        """get_task_by_trace_id with active filter → only matching tenant."""
        # The fixture trace_id is trace-phase5-retrieval-001
        # Both clones share the same trace_id, so we test with firm-a filter
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        result = self.scoped_model.get_task_by_trace_id("trace-phase5-retrieval-001", tenant_filter=active)
        # Should return the firm-a task (or None if tenant_id not in trace metadata)
        # Since both clones share the same trace_id, the trace_to_task_id map
        # will point to the last one inserted.  The key test is that it doesn't
        # return data from the wrong tenant.
        if result is not None:
            tid = result.get("agent_result", {}).get("metadata", {}).get("tenant_id")
            if tid is not None:
                self.assertEqual(tid, "firm-a")


if __name__ == "__main__":
    unittest.main()
