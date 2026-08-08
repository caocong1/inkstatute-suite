"""Tests for the operator-config backend selection resolver (Phase 103-03).

Covers:
- ``BackendSelectionDoc`` schema defaults and validation
- ``resolve_backend_id`` resolution order (default, tenant override, None)
- ``load_backend_selection`` loading from a store (present, missing, None)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from platform_runtime.feature_flags import RuntimeFeatureFlags

from inkstatute_operator_config import (
    BackendSelectionDoc,
    OperatorConfigDocument,
    OperatorConfigStore,
    load_backend_selection,
    resolve_backend_id,
)
from inkstatute_operator_config.store import document_from_payload


def _enabled_flags() -> RuntimeFeatureFlags:
    return RuntimeFeatureFlags(operator_config_enabled=True)


class TestBackendSelectionDoc(unittest.TestCase):
    """Tests for the BackendSelectionDoc schema dataclass."""

    def test_default_backend_id_is_inkstatute(self) -> None:
        """Default backend_id must be 'inkstatute'."""
        doc = BackendSelectionDoc()
        self.assertEqual(doc.default_backend_id, "inkstatute")

    def test_default_backend_overrides_is_empty(self) -> None:
        """Default backend_overrides must be an empty dict."""
        doc = BackendSelectionDoc()
        self.assertEqual(doc.backend_overrides, {})

    def test_backend_selection_doc_validates(self) -> None:
        """BackendSelectionDoc accepts custom default and overrides."""
        doc = BackendSelectionDoc(
            default_backend_id="hermes",
            backend_overrides={"tenant-a": "inkstatute"},
        )
        self.assertEqual(doc.default_backend_id, "hermes")
        self.assertEqual(doc.backend_overrides["tenant-a"], "inkstatute")

    def test_backend_selection_doc_is_frozen(self) -> None:
        """BackendSelectionDoc must be frozen (immutable)."""
        doc = BackendSelectionDoc()
        with self.assertRaises((AttributeError, Exception)):
            doc.default_backend_id = "hermes"  # type: ignore[misc]


class TestResolveBackendId(unittest.TestCase):
    """Tests for the resolve_backend_id resolver function."""

    def test_missing_selection_returns_default(self) -> None:
        """When selection is None, return 'inkstatute' (hard default)."""
        self.assertEqual(resolve_backend_id(None, None), "inkstatute")

    def test_default_backend_id_is_inkstatute(self) -> None:
        """A default BackendSelectionDoc resolves to 'inkstatute'."""
        selection = BackendSelectionDoc()
        self.assertEqual(resolve_backend_id(None, selection), "inkstatute")

    def test_custom_default_backend_id(self) -> None:
        """A custom default_backend_id is returned when no override applies."""
        selection = BackendSelectionDoc(default_backend_id="hermes")
        self.assertEqual(resolve_backend_id(None, selection), "hermes")
        self.assertEqual(resolve_backend_id("tenant-x", selection), "hermes")

    def test_tenant_override_takes_precedence(self) -> None:
        """Tenant-specific overrides take precedence over the default."""
        selection = BackendSelectionDoc(
            default_backend_id="hermes",
            backend_overrides={"tenant-a": "inkstatute", "tenant-b": "codex"},
        )
        self.assertEqual(resolve_backend_id("tenant-a", selection), "inkstatute")
        self.assertEqual(resolve_backend_id("tenant-b", selection), "codex")
        # Unmatched tenant falls through to default
        self.assertEqual(resolve_backend_id("tenant-c", selection), "hermes")

    def test_none_tenant_uses_default(self) -> None:
        """When tenant_id is None, the default is used (no override lookup)."""
        selection = BackendSelectionDoc(
            default_backend_id="hermes",
            backend_overrides={"tenant-a": "inkstatute"},
        )
        self.assertEqual(resolve_backend_id(None, selection), "hermes")

    def test_empty_tenant_id_uses_default(self) -> None:
        """When tenant_id is empty string, the default is used."""
        selection = BackendSelectionDoc(
            default_backend_id="hermes",
            backend_overrides={"tenant-a": "inkstatute"},
        )
        self.assertEqual(resolve_backend_id("", selection), "hermes")


class TestLoadBackendSelection(unittest.TestCase):
    """Tests for load_backend_selection loading from a store."""

    def test_none_store_returns_none(self) -> None:
        """When store is None, load_backend_selection returns None."""
        self.assertIsNone(load_backend_selection(None))

    def test_missing_store_file_returns_none(self) -> None:
        """When the store file does not exist, returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            self.assertIsNone(load_backend_selection(store))

    def test_load_backend_selection_from_store(self) -> None:
        """A store with a backend_selection section returns the doc."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            # Write a config with backend_selection
            payload = {
                "schema_version": 1,
                "channels": {},
                "providers": [],
                "catalog": {},
                "vision": {},
                "backend_selection": {
                    "default_backend_id": "hermes",
                    "backend_overrides": {"tenant-a": "inkstatute"},
                },
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            store = OperatorConfigStore(path)
            selection = load_backend_selection(store)
            self.assertIsNotNone(selection)
            assert selection is not None  # for type checker
            self.assertEqual(selection.default_backend_id, "hermes")
            self.assertEqual(selection.backend_overrides, {"tenant-a": "inkstatute"})

    def test_load_backend_selection_defaults_when_absent(self) -> None:
        """A store without a backend_selection section defaults to inkstatute."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            payload = {
                "schema_version": 1,
                "channels": {},
                "providers": [],
                "catalog": {},
                "vision": {},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            store = OperatorConfigStore(path)
            selection = load_backend_selection(store)
            self.assertIsNotNone(selection)
            assert selection is not None
            self.assertEqual(selection.default_backend_id, "inkstatute")
            self.assertEqual(selection.backend_overrides, {})

    def test_round_trip_through_store(self) -> None:
        """A document with backend_selection round-trips through save/load."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            doc = OperatorConfigDocument(
                backend_selection=BackendSelectionDoc(
                    default_backend_id="hermes",
                    backend_overrides={"tenant-a": "inkstatute"},
                ),
            )
            store.save(doc, feature_flags=_enabled_flags())
            loaded = store.load()
            self.assertEqual(loaded.backend_selection.default_backend_id, "hermes")
            self.assertEqual(
                loaded.backend_selection.backend_overrides,
                {"tenant-a": "inkstatute"},
            )

    def test_document_from_payload_parses_backend_selection(self) -> None:
        """document_from_payload parses the backend_selection section."""
        payload = {
            "schema_version": 1,
            "channels": {},
            "providers": [],
            "catalog": {},
            "vision": {},
            "backend_selection": {
                "default_backend_id": "codex",
                "backend_overrides": {"t1": "hermes"},
            },
        }
        doc = document_from_payload(payload)
        self.assertEqual(doc.backend_selection.default_backend_id, "codex")
        self.assertEqual(doc.backend_selection.backend_overrides, {"t1": "hermes"})


if __name__ == "__main__":
    unittest.main()
