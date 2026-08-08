"""Unit tests for Arena Service permission safety (SVC-05).

Verifies that:
- ``_DANGEROUS_PERMISSION_KINDS`` is preserved as
  ``frozenset({"terminal", "execute_code"})`` — imported, not redefined.
- Dangerous kinds are immediately rejected (no auto-approval).
- No batch approve endpoint exists in ``ArenaServiceApp``.
- Permission requests are forwarded to ``adapter.submit_approval()``.
- Simulated approval of ``terminal`` is rejected; ``read_file`` is approved.
"""

from __future__ import annotations

import inspect
import unittest

from arena_service import app as app_module
from arena_service.app import ArenaServiceApp, OPERATIONS
from arena_service.auth import ArenaServiceAuth
from arena_service.config import ArenaServiceConfig
from arena_service.permission_safety import (
    check_no_auto_approve_dangerous,
    check_no_batch_approve,
    check_permission_request_forwarding,
    get_dangerous_kinds,
    is_dangerous_kind,
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
        backend_id="test-backend",
        command=("echo", "dummy"),
    )
    adapter = ACPBackendAdapter(config)
    run = Run(
        run_id=run_id,
        status=AsyncTaskState.RUNNING,
        turn_id="turn-1",
        solution_id="sol-1",
        metadata={"backend_id": "test-backend"},
    )
    adapter._runs[run_id] = run
    return adapter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class PermissionSafetyTests(unittest.IsolatedAsyncioTestCase):
    """SVC-05: Permission security verification tests."""

    # -- Test 1: _DANGEROUS_PERMISSION_KINDS preserved --
    def test_dangerous_kinds_preserved(self) -> None:
        """Test 1: ``_DANGEROUS_PERMISSION_KINDS`` equals frozenset({"terminal", "execute_code"})."""
        self.assertEqual(_DANGEROUS_PERMISSION_KINDS, frozenset({"terminal", "execute_code"}))

    # -- Test 2: is_dangerous_kind --
    def test_is_dangerous_kind_terminal(self) -> None:
        """Test 2a: ``is_dangerous_kind("terminal")`` returns True."""
        self.assertTrue(is_dangerous_kind("terminal"))

    def test_is_dangerous_kind_execute_code(self) -> None:
        """Test 2b: ``is_dangerous_kind("execute_code")`` returns True."""
        self.assertTrue(is_dangerous_kind("execute_code"))

    def test_is_dangerous_kind_read_file(self) -> None:
        """Test 2c: ``is_dangerous_kind("read_file")`` returns False."""
        self.assertFalse(is_dangerous_kind("read_file"))

    def test_is_dangerous_kind_web_search(self) -> None:
        """Test 2d: ``is_dangerous_kind("web_search")`` returns False."""
        self.assertFalse(is_dangerous_kind("web_search"))

    # -- Test 3: check_no_batch_approve --
    def test_check_no_batch_approve(self) -> None:
        """Test 3: ``check_no_batch_approve(ArenaServiceApp)`` returns True."""
        self.assertTrue(check_no_batch_approve(ArenaServiceApp))

    # -- Test 4: check_no_auto_approve_dangerous --
    def test_check_no_auto_approve_dangerous(self) -> None:
        """Test 4: ``check_no_auto_approve_dangerous(app_module)`` returns True."""
        self.assertTrue(check_no_auto_approve_dangerous(app_module))

    # -- Test 5: check_permission_request_forwarding --
    def test_check_permission_request_forwarding(self) -> None:
        """Test 5: ``check_permission_request_forwarding(app)`` returns True."""
        app = _make_app()
        self.assertTrue(check_permission_request_forwarding(app))

    # -- Test 6: get_dangerous_kinds returns canonical set --
    def test_get_dangerous_kinds(self) -> None:
        """Test 6: ``get_dangerous_kinds()`` returns frozenset({"terminal", "execute_code"})."""
        kinds = get_dangerous_kinds()
        self.assertEqual(kinds, frozenset({"terminal", "execute_code"}))
        self.assertIsInstance(kinds, frozenset)

    # -- Test 7: simulate_approval rejects terminal --
    async def test_simulate_approval_terminal_rejected(self) -> None:
        """Test 7: terminal kind with approved decision is rejected."""
        adapter = _make_acp_adapter_with_run()
        result = await simulate_approval(adapter, "acp-run-001", kind="terminal", decision="approved")
        self.assertEqual(result["status"], AsyncTaskState.WAITING_FOR_USER)
        self.assertEqual(result["metadata"].get("approval_rejected"), "dangerous_permission_terminal")
        self.assertFalse(result["metadata"].get("approval_decision_recorded", False))

    # -- Test 8: simulate_approval approves read_file --
    async def test_simulate_approval_read_file_approved(self) -> None:
        """Test 8: read_file kind with approved decision is approved normally."""
        adapter = _make_acp_adapter_with_run()
        result = await simulate_approval(adapter, "acp-run-001", kind="read_file", decision="approved")
        self.assertTrue(result["metadata"].get("approval_decision_recorded", False))
        self.assertEqual(result["metadata"].get("approval_decision"), "approved")

    # -- Test 9: ArenaServiceApp has no batch operation constant --
    def test_no_batch_operation_constant(self) -> None:
        """Test 9: ArenaServiceApp OPERATIONS has no batch/bulk constants."""
        for op in OPERATIONS:
            op_lower = str(op).lower()
            self.assertNotIn("batch", op_lower, f"Operation {op} contains 'batch'")
            self.assertNotIn("bulk", op_lower, f"Operation {op} contains 'bulk'")
        # Also verify no OPERATION_BATCH_APPROVE constant exists
        self.assertFalse(hasattr(app_module, "OPERATION_BATCH_APPROVE"))
        self.assertFalse(hasattr(app_module, "OPERATION_BULK_APPROVE"))

    # -- Additional: _DANGEROUS_PERMISSION_KINDS is imported, not redefined --
    def test_dangerous_kinds_imported_not_redefined(self) -> None:
        """Verify _DANGEROUS_PERMISSION_KINDS is imported from adapter, not redefined."""
        from arena_service import permission_safety as ps_module
        source = inspect.getsource(ps_module)
        # The module should import _DANGEROUS_PERMISSION_KINDS, not define it
        self.assertIn("from inkstatute_acp_client.adapter import", source)
        self.assertIn("_DANGEROUS_PERMISSION_KINDS", source)
        # Should NOT contain a redefinition (assignment)
        # Look for "_DANGEROUS_PERMISSION_KINDS = frozenset" or "_DANGEROUS_PERMISSION_KINDS: frozenset"
        self.assertNotIn("_DANGEROUS_PERMISSION_KINDS = frozenset", source)
        self.assertNotIn("_DANGEROUS_PERMISSION_KINDS: frozenset", source)

    # -- Additional: get_dangerous_kinds returns the same object as the adapter --
    def test_get_dangerous_kinds_is_same_object(self) -> None:
        """get_dangerous_kinds() returns the exact same frozenset from the adapter."""
        from inkstatute_acp_client.adapter import _DANGEROUS_PERMISSION_KINDS as adapter_kinds
        self.assertIs(get_dangerous_kinds(), adapter_kinds)


if __name__ == "__main__":
    unittest.main()
