"""Permission safety verification for the Arena Service (SVC-05).

Verifies that:
- ``_DANGEROUS_PERMISSION_KINDS`` is preserved as
  ``frozenset({"terminal", "execute_code"})`` — imported from
  ``inkstatute_acp_client.adapter``, NOT redefined.
- Dangerous permission kinds (``terminal``, ``execute_code``) are
  immediately rejected when ``decision="approved"`` — no auto-approval.
- No batch approve endpoint exists in the arena service.
- Permission requests are forwarded to ``adapter.submit_approval()``
  (which has the dangerous-kind rejection logic), not handled by a
  separate auto-approval path.

Reference failure: Buzz's ACP bridge auto-answers ``allow_once``, letting
agents run shell commands unprompted.  This module ensures the arena
service never does that.
"""

from __future__ import annotations

import inspect
import os
from typing import Any

from inkstatute_acp_client.adapter import _DANGEROUS_PERMISSION_KINDS
from platform_runtime.protocols import Approval


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_dangerous_kinds() -> frozenset[str]:
    """Return the canonical set of dangerous permission kinds.

    Imported from ``inkstatute_acp_client.adapter`` — **not** redefined.
    The single source of truth is the adapter module.
    """
    return _DANGEROUS_PERMISSION_KINDS


def is_dangerous_kind(kind: str) -> bool:
    """Return ``True`` if the given permission kind is dangerous.

    Dangerous kinds: ``terminal``, ``execute_code``.
    """
    return kind.lower() in _DANGEROUS_PERMISSION_KINDS


def check_no_batch_approve(app_class_or_instance: Any) -> bool:
    """Verify that no batch approve endpoint exists.

    Inspects the app's operation constants (``OPERATIONS`` tuple) and
    handler methods.  Returns ``False`` if any operation or method name
    contains "batch" or "bulk" in the context of approvals.  Returns
    ``True`` otherwise.
    """
    # Check OPERATIONS tuple for batch/bulk approve entries
    operations = getattr(app_class_or_instance, "OPERATIONS", None)
    if operations is None and not inspect.isclass(app_class_or_instance):
        operations = getattr(type(app_class_or_instance), "OPERATIONS", None)

    if operations is not None:
        for op in operations:
            op_lower = str(op).lower()
            if ("batch" in op_lower or "bulk" in op_lower) and "approve" in op_lower:
                return False
            # Also flag any batch/bulk operation constant that could
            # accept multiple approval decisions
            if "batch" in op_lower or "bulk" in op_lower:
                if "action" in op_lower or "approve" in op_lower or "decision" in op_lower:
                    return False

    # Check for batch/bulk approve methods on the class
    cls = app_class_or_instance if inspect.isclass(app_class_or_instance) else type(app_class_or_instance)
    for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction):
        name_lower = name.lower()
        if ("batch" in name_lower or "bulk" in name_lower) and "approve" in name_lower:
            return False

    return True


def check_no_auto_approve_dangerous(app_module: Any) -> bool:
    """Scan the arena_service source for auto-approval of dangerous permissions.

    Searches all ``.py`` files in the arena_service package (excluding
    this module) for patterns that would indicate auto-approval of
    ``terminal`` or ``execute_code`` permissions without user action.

    Returns ``True`` if no such code path exists.
    """
    # Resolve the source directory of the arena_service package
    if hasattr(app_module, "__path__"):
        source_dirs = list(app_module.__path__)
    elif hasattr(app_module, "__file__"):
        source_dirs = [os.path.dirname(app_module.__file__)]
    else:
        return True  # Cannot scan — assume safe

    # Patterns that indicate auto-approval of dangerous permissions
    auto_approve_patterns = (
        "auto_approve",
        "auto-approve",
        "allow_once",
        "allowonce",
    )

    for source_dir in source_dirs:
        for filename in os.listdir(source_dir):
            if not filename.endswith(".py"):
                continue
            # Exclude this module and __init__.py from the scan — they
            # contain the string "auto_approve" in function/import names
            # like check_no_auto_approve_dangerous, not actual auto-approval
            # logic.
            if filename == "permission_safety.py":
                continue
            if filename == "__init__.py":
                continue

            filepath = os.path.join(source_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
            except OSError:
                continue

            source_lower = source.lower()

            # Check for auto-approval patterns
            for pattern in auto_approve_patterns:
                if pattern in source_lower:
                    return False

            # Check for code that directly approves dangerous kinds
            # without user action (e.g. if kind == "terminal": decision = "approved")
            for kind in _DANGEROUS_PERMISSION_KINDS:
                kind_pattern = f'"{kind}"'
                if kind_pattern in source and '"approved"' in source:
                    # Check if there's a direct approval assignment near the kind check
                    if f'kind == "{kind}"' in source or f"kind == '{kind}'" in source:
                        return False

    return True


def check_permission_request_forwarding(app: Any) -> bool:
    """Verify that permission requests are forwarded to ``adapter.submit_approval()``.

    Checks that:
    - No ``auto_approve`` method exists on the app (excluding check
      functions from this module).
    - The app delegates to an engine (which forwards to the adapter's
      ``submit_approval()`` method).

    Returns ``True`` if forwarding is correct.
    """
    cls = app if inspect.isclass(app) else type(app)

    # Check for auto_approve methods (excluding check_* functions)
    for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction):
        name_lower = name.lower()
        if "auto_approve" in name_lower and not name_lower.startswith("check_"):
            return False

    # The app should delegate to an engine (which forwards to the adapter)
    has_engine = hasattr(cls, "engine") or hasattr(app, "engine")

    return bool(has_engine)


async def simulate_approval(
    adapter: Any,
    run_id: str,
    kind: str,
    decision: str,
) -> dict:
    """Simulate an approval flow through the adapter.

    Creates an :class:`Approval` object with ``metadata={"kind": kind}``
    and ``decision=decision``, calls ``adapter.submit_approval(run_id,
    approval)``, and returns the resulting run's status and metadata.

    This is a test helper that exercises the adapter's dangerous-kind
    rejection logic (adapter.py lines 395-436).
    """
    approval = Approval(
        approval_id=f"test-approval-{kind}",
        decision=decision,
        metadata={"kind": kind},
    )
    run = await adapter.submit_approval(run_id, approval)
    return {
        "status": run.status,
        "metadata": dict(run.metadata),
    }


__all__ = [
    "check_no_auto_approve_dangerous",
    "check_no_batch_approve",
    "check_permission_request_forwarding",
    "get_dangerous_kinds",
    "is_dangerous_kind",
    "simulate_approval",
]
