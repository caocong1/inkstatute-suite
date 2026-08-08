"""GATE-05: Permission safety CI gate test for the Arena Service.

This is the CI gate test that runs in the ``arena-permission-safety`` gate.
It verifies the permission safety invariants that must NEVER regress:

- ``_DANGEROUS_PERMISSION_KINDS`` is preserved as
  ``frozenset({"terminal", "execute_code"})`` — imported from
  ``inkstatute_acp_client.adapter``, NOT redefined.
- No batch approve endpoint exists in ``ArenaServiceApp.OPERATIONS``.
- No code path in ``arena_service`` auto-approves ``terminal`` or
  ``execute_code`` permissions.
- ``terminal`` and ``execute_code`` approvals are rejected (run →
  ``WAITING_FOR_USER`` with ``metadata.approval_rejected`` set).
- Non-dangerous permissions (e.g. ``read_file``) are approved normally.
- ``_DANGEROUS_PERMISSION_KINDS`` is imported (not redefined) from the
  adapter module.

Reference failure: Buzz's ACP bridge auto-answers ``allow_once``, letting
agents run shell commands unprompted.  This gate ensures the arena
service never does that.
"""

from __future__ import annotations

import inspect
import unittest

from arena_service import app as app_module
from arena_service import permission_safety as ps_module
from arena_service.app import ArenaServiceApp, OPERATIONS
from arena_service.auth import ArenaServiceAuth
from arena_service.config import ArenaServiceConfig
from arena_service.permission_safety import (
    check_no_auto_approve_dangerous,
    check_no_batch_approve,
    simulate_approval,
)
from inkstatute_acp_client.adapter import (
    ACPBackendAdapter,
    ACPBackendConfig,
    _DANGEROUS_PERMISSION_KINDS,
)
from platform_contract.enums import AsyncTaskState
from platform_runtime.protocols import Run


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_app() -> ArenaServiceApp:
    """Create an ArenaServiceApp with a dummy config and auth."""
    config = ArenaServiceConfig()
    auth = ArenaServiceAuth(config)
    return ArenaServiceApp(config=config, auth=auth)


def _make_acp_adapter_with_run(run_id: str = "acp-run-001") -> ACPBackendAdapter:
    """Create an ACPBackendAdapter with a pre-populated run for approval tests.

    The adapter is constructed with a dummy config (no subprocess spawned).
    A Run is injected directly into ``_runs`` so ``submit_approval`` can
    be called without a full ``submit_run`` cycle.
    """
    config = ACPBackendConfig(
        backend_id="gate05-backend",
        command=("echo", "dummy"),
    )
    adapter = ACPBackendAdapter(config)
    run = Run(
        run_id=run_id,
        status=AsyncTaskState.RUNNING,
        turn_id="turn-1",
        solution_id="sol-1",
        metadata={"backend_id": "gate05-backend"},
    )
    adapter._runs[run_id] = run
    return adapter


# ---------------------------------------------------------------------------
# GATE-05: Permission safety gate tests
# ---------------------------------------------------------------------------


class PermissionSafetyGateTests(unittest.IsolatedAsyncioTestCase):
    """GATE-05: Permission safety CI gate tests.

    These tests run in the ``arena-permission-safety`` gate and verify
    that the permission safety invariants are never violated.
    """

    # -- Test 1: _DANGEROUS_PERMISSION_KINDS preserved --
    def test_dangerous_kinds_preserved(self) -> None:
        """``_DANGEROUS_PERMISSION_KINDS`` equals frozenset({"terminal", "execute_code"})."""
        self.assertEqual(
            _DANGEROUS_PERMISSION_KINDS,
            frozenset({"terminal", "execute_code"}),
        )

    # -- Test 2: No batch approve endpoint --
    def test_no_batch_approve_endpoint(self) -> None:
        """No operation name in OPERATIONS contains 'batch' or 'bulk'."""
        for op in OPERATIONS:
            op_lower = str(op).lower()
            self.assertNotIn("batch", op_lower, f"Operation {op} contains 'batch'")
            self.assertNotIn("bulk", op_lower, f"Operation {op} contains 'bulk'")
        self.assertTrue(check_no_batch_approve(ArenaServiceApp))

    # -- Test 3: No auto-approve of dangerous permissions --
    def test_no_auto_approve_dangerous(self) -> None:
        """check_no_auto_approve_dangerous(arena_service_module) returns True."""
        self.assertTrue(check_no_auto_approve_dangerous(app_module))

    # -- Test 4: terminal rejected --
    async def test_terminal_rejected(self) -> None:
        """terminal kind with approved decision is rejected (WAITING_FOR_USER)."""
        adapter = _make_acp_adapter_with_run()
        result = await simulate_approval(
            adapter, "acp-run-001", kind="terminal", decision="approved"
        )
        self.assertEqual(result["status"], AsyncTaskState.WAITING_FOR_USER)
        rejected = result["metadata"].get("approval_rejected", "")
        self.assertIn("terminal", rejected)

    # -- Test 5: execute_code rejected --
    async def test_execute_code_rejected(self) -> None:
        """execute_code kind with approved decision is rejected (WAITING_FOR_USER)."""
        adapter = _make_acp_adapter_with_run()
        result = await simulate_approval(
            adapter, "acp-run-001", kind="execute_code", decision="approved"
        )
        self.assertEqual(result["status"], AsyncTaskState.WAITING_FOR_USER)
        rejected = result["metadata"].get("approval_rejected", "")
        self.assertIn("execute_code", rejected)

    # -- Test 6: read_file approved normally --
    async def test_read_file_approved(self) -> None:
        """read_file kind with approved decision is approved normally."""
        adapter = _make_acp_adapter_with_run()
        result = await simulate_approval(
            adapter, "acp-run-001", kind="read_file", decision="approved"
        )
        self.assertTrue(result["metadata"].get("approval_decision_recorded", False))

    # -- Test 7: OPERATIONS has no batch/bulk operation --
    def test_operations_no_batch_bulk(self) -> None:
        """ArenaServiceApp.OPERATIONS does not contain batch/bulk operations."""
        for op in OPERATIONS:
            op_lower = str(op).lower()
            self.assertNotIn("batch", op_lower)
            self.assertNotIn("bulk", op_lower)

    # -- Test 8: _DANGEROUS_PERMISSION_KINDS imported, not redefined --
    def test_dangerous_kinds_imported_not_redefined(self) -> None:
        """permission_safety module imports _DANGEROUS_PERMISSION_KINDS, not redefines it."""
        source = inspect.getsource(ps_module)
        self.assertIn("from inkstatute_acp_client.adapter import", source)
        self.assertIn("_DANGEROUS_PERMISSION_KINDS", source)
        # Should NOT contain a local redefinition
        self.assertNotIn("_DANGEROUS_PERMISSION_KINDS = frozenset", source)
        self.assertNotIn("_DANGEROUS_PERMISSION_KINDS: frozenset", source)


if __name__ == "__main__":
    unittest.main()
