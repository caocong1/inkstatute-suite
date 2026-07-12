"""Build a runtime vision resolver from operator config (VIS-02/03/04).

The resolver is a plain ``Callable[[RunRequest], VisionRoutingDecision]`` so
``platform-runtime`` can stay free of ``operator-config`` imports.  Config
secrets, raw image bytes, and provider model names are never read here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

from platform_runtime import RunRequest, VisionRoute, VisionRouter, VisionRoutingDecision

from .catalog import BUILTIN_MODEL_CATALOG, builtin_catalog_entry
from .schemas import CatalogSelectionDoc, OperatorConfigDocument, VisionPolicyDoc


class _LoadableStore(Protocol):
    """Duck-typed store accepted by ``build_vision_resolver``."""

    path: Any

    def load(self) -> OperatorConfigDocument: ...


def _default_document() -> OperatorConfigDocument:
    return OperatorConfigDocument()


def _load_document(store: _LoadableStore | None) -> OperatorConfigDocument:
    if store is None:
        return _default_document()
    try:
        path = store.path if isinstance(store.path, Path) else Path(str(store.path))
        if path.is_file():
            return store.load()
    except (AttributeError, OSError):
        pass
    return _default_document()


def _find_provider_kind(
    catalog: CatalogSelectionDoc, document: OperatorConfigDocument
) -> str | None:
    """Map an operator catalog selection to a built-in vendor kind."""

    provider_id = catalog.provider_id
    if not provider_id:
        return None
    # First: if the provider_id is itself a built-in vendor id, use it.
    if provider_id in {entry.vendor_id for entry in BUILTIN_MODEL_CATALOG}:
        return provider_id
    # Second: resolve via the operator provider registry.
    for provider in document.providers:
        if provider.provider_id == provider_id:
            return provider.kind or None
    return None


def _resolve_main_supports_vision(
    catalog: CatalogSelectionDoc, document: OperatorConfigDocument
) -> bool:
    """Return whether the selected main model is in the built-in vision catalog."""

    vendor_id = _find_provider_kind(catalog, document)
    if not vendor_id or not catalog.model_id:
        return False
    entry = builtin_catalog_entry(vendor_id, catalog.model_id)
    if entry is None:
        return False
    return entry.supports_vision


def _backend_supports_vision(backend: Any) -> bool:
    try:
        return bool(getattr(backend.capabilities(), "supports_vision", False))
    except Exception:  # noqa: BLE001 - backend capabilities are optional
        return False


def _attachment_image_count(turn: Any) -> int:
    """Count image attachments without reading raw bytes."""

    count = 0
    attachments = getattr(turn, "attachments", None) or ()
    for attachment in attachments:
        if getattr(attachment, "kind", None) == "image":
            count += 1
            continue
        mime_type = getattr(attachment, "mime_type", None)
        if mime_type and str(mime_type).lower().startswith("image/"):
            count += 1
    return count


class VisionResolver:
    """Resolve a ``RunRequest`` to a ``VisionRoutingDecision`` using config."""

    def __init__(
        self,
        document: OperatorConfigDocument,
        *,
        backend: Any | None = None,
        vision_runner: Any | None = None,
    ) -> None:
        self._vision = document.vision
        self._catalog = document.catalog
        self._document = document
        self._backend = backend
        self._vision_runner = vision_runner

        main_supports_vision = _resolve_main_supports_vision(
            self._catalog, self._document
        )
        backend_supports_vision = (
            _backend_supports_vision(backend) if backend is not None else None
        )
        if backend_supports_vision is False:
            main_supports_vision = False
        self._main_supports_vision = main_supports_vision
        self._backend_supports_vision = backend_supports_vision or False

    def __call__(self, req: RunRequest) -> VisionRoutingDecision:
        vision_pair_configured = bool(
            self._vision.vision_provider_id
            and self._vision.vision_model_id
            and self._vision_runner is not None
        )
        decision = VisionRouter().decide(
            req.turn,
            self._vision,
            main_supports_vision=self._main_supports_vision,
            vision_pair_configured=vision_pair_configured,
        )
        metadata = dict(decision.metadata)
        metadata["main_supports_vision"] = self._main_supports_vision
        metadata["backend_supports_vision"] = self._backend_supports_vision
        if self._vision.vision_provider_id:
            metadata["vision_provider_id"] = self._vision.vision_provider_id
        if self._vision.vision_model_id:
            metadata["vision_model_id"] = self._vision.vision_model_id
        metadata["image_count"] = _attachment_image_count(req.turn)
        return VisionRoutingDecision(
            route=decision.route,
            notice=decision.notice,
            reason=decision.reason,
            metadata=metadata,
        )


def build_vision_resolver(
    *,
    store: _LoadableStore | None = None,
    backend: Any | None = None,
    vision_runner: Any | None = None,
) -> Callable[[RunRequest], VisionRoutingDecision]:
    """Build a vision resolver from operator config.

    ``store`` is the operator-config store. When the store path exists, the
    document is loaded and used to resolve the vision policy, catalog, and
    provider mapping. When the store is missing or None, the resolver defaults
    to a blank policy with no vision support, so image-bearing turns fail-closed.

    ``backend`` is the main runtime backend; its ``capabilities().supports_vision``
    can override the catalog-derived ``main_supports_vision`` to False.

    ``vision_runner`` is the optional vision backend. It is only considered
    configured when the operator config has a complete vision pair.
    """

    document = _load_document(store)
    return VisionResolver(
        document,
        backend=backend,
        vision_runner=vision_runner,
    )


__all__ = ["VisionResolver", "build_vision_resolver"]
