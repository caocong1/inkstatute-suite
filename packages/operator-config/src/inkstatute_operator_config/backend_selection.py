"""Backend selection resolver — per-tenant backend routing (Phase 103).

The self-built agent core (``inkstatute``) is the default backend but has no
architectural privilege.  This resolver reads the operator-config
``BackendSelectionDoc`` and returns the effective ``backend_id`` for a given
tenant.  Swapping ``backend_id`` from ``hermes`` to ``inkstatute`` (or any
other ACP-speaking backend) requires zero changes to channel or UI code —
only an operator-config change.

Resolution order:
1. If ``selection`` is ``None``, return ``"inkstatute"`` (hard default).
2. If ``tenant_id`` is present in ``backend_overrides``, return the mapped
   value (tenant-specific override takes precedence).
3. Otherwise return ``selection.default_backend_id``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .schemas import BackendSelectionDoc, OperatorConfigDocument

__all__ = [
    "BackendSelectionDoc",
    "load_backend_selection",
    "resolve_backend_id",
]


class _LoadableStore(Protocol):
    """Duck-typed store accepted by ``load_backend_selection``."""

    path: Any

    def load(self) -> OperatorConfigDocument: ...


def resolve_backend_id(
    tenant_id: str | None,
    selection: BackendSelectionDoc | None,
) -> str:
    """Resolve the effective ``backend_id`` for a tenant.

    Args:
        tenant_id: The tenant identifier (may be ``None`` for unscoped runs).
        selection: The ``BackendSelectionDoc`` from operator config, or
            ``None`` when no backend selection is configured.

    Returns:
        The resolved backend_id string.  When ``selection`` is ``None``,
        returns ``"inkstatute"`` (the hard default).
    """
    if selection is None:
        return "inkstatute"
    if tenant_id and tenant_id in selection.backend_overrides:
        return selection.backend_overrides[tenant_id]
    return selection.default_backend_id


def _default_document() -> OperatorConfigDocument:
    return OperatorConfigDocument()


def load_backend_selection(
    store: _LoadableStore | None,
) -> BackendSelectionDoc | None:
    """Load the ``BackendSelectionDoc`` from an operator-config store.

    When the store is ``None`` or the store file does not exist, returns
    ``None`` (the resolver then falls back to the hard default
    ``"inkstatute"``).  When the store loads successfully, returns the
    document's ``backend_selection`` field.

    Args:
        store: The operator-config store (or ``None``).

    Returns:
        The ``BackendSelectionDoc`` from the document, or ``None`` when
        no store is available.
    """
    if store is None:
        return None
    try:
        path = store.path if isinstance(store.path, Path) else Path(str(store.path))
        if not path.is_file():
            return None
        document = store.load()
    except (AttributeError, OSError):
        return None
    return document.backend_selection
