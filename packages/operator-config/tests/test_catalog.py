"""PROV-01/03: canonical built-in vendor profiles and model catalog integrity."""

from __future__ import annotations

import unittest
from dataclasses import fields, is_dataclass

from inkstatute_operator_config.catalog import (
    BUILTIN_MODEL_CATALOG,
    BUILTIN_VENDOR_PROFILES,
    BuiltInCatalogEntry,
    VendorProfile,
    builtin_catalog_entry,
    builtin_vendor_profile,
)


class TestVendorProfiles(unittest.TestCase):
    def test_vendor_profile_is_frozen_slotted_dataclass(self) -> None:
        self.assertTrue(is_dataclass(VendorProfile))
        names = {f.name for f in fields(VendorProfile)}
        self.assertEqual(names, {"vendor_id", "api_base_url", "default_key_ref_env"})
        profile = VendorProfile("openai", "https://api.openai.com/v1", "OPENAI_API_KEY")
        with self.assertRaises(Exception):
            profile.vendor_id = "x"  # type: ignore[misc]

    def test_builtin_vendor_profiles_exact(self) -> None:
        self.assertEqual(len(BUILTIN_VENDOR_PROFILES), 2)
        ids = [p.vendor_id for p in BUILTIN_VENDOR_PROFILES]
        self.assertEqual(ids, ["openai", "anthropic"])

        openai = builtin_vendor_profile("openai")
        self.assertIsNotNone(openai)
        assert openai is not None  # for type checkers
        self.assertEqual(openai.api_base_url, "https://api.openai.com/v1")
        self.assertEqual(openai.default_key_ref_env, "OPENAI_API_KEY")

        anthropic = builtin_vendor_profile("anthropic")
        self.assertIsNotNone(anthropic)
        assert anthropic is not None
        self.assertEqual(anthropic.api_base_url, "https://api.anthropic.com/v1")
        self.assertEqual(anthropic.default_key_ref_env, "ANTHROPIC_API_KEY")

    def test_vendor_profile_field_named_vendor_id_not_provider_id(self) -> None:
        names = {f.name for f in fields(VendorProfile)}
        self.assertIn("vendor_id", names)
        self.assertNotIn("provider_id", names)

    def test_unknown_vendor_profile_returns_none(self) -> None:
        self.assertIsNone(builtin_vendor_profile("custom"))
        self.assertIsNone(builtin_vendor_profile("openai_compatible"))


class TestModelCatalog(unittest.TestCase):
    def test_catalog_entry_is_frozen_slotted_dataclass(self) -> None:
        self.assertTrue(is_dataclass(BuiltInCatalogEntry))
        names = {f.name for f in fields(BuiltInCatalogEntry)}
        self.assertEqual(
            names, {"vendor_id", "model_id", "supports_vision", "description"}
        )
        entry = BuiltInCatalogEntry("openai", "gpt-5", True)
        with self.assertRaises(Exception):
            entry.model_id = "x"  # type: ignore[misc]

    def test_catalog_entry_field_named_vendor_id_not_provider_id(self) -> None:
        names = {f.name for f in fields(BuiltInCatalogEntry)}
        self.assertIn("vendor_id", names)
        self.assertNotIn("provider_id", names)

    def test_builtin_model_catalog_source_grounded_rows(self) -> None:
        self.assertEqual(len(BUILTIN_MODEL_CATALOG), 2)
        openai_entry = builtin_catalog_entry("openai", "gpt-5")
        self.assertIsNotNone(openai_entry)
        assert openai_entry is not None
        self.assertEqual(openai_entry.vendor_id, "openai")
        self.assertEqual(openai_entry.model_id, "gpt-5")
        self.assertIs(openai_entry.supports_vision, True)

        anthropic_entry = builtin_catalog_entry("anthropic", "claude-opus-4-8")
        self.assertIsNotNone(anthropic_entry)
        assert anthropic_entry is not None
        self.assertEqual(anthropic_entry.vendor_id, "anthropic")
        self.assertEqual(anthropic_entry.model_id, "claude-opus-4-8")
        self.assertIs(anthropic_entry.supports_vision, True)

    def test_every_catalog_entry_has_explicit_bool_supports_vision(self) -> None:
        """Phase 77 depends on required boolean supports_vision (no None default)."""
        for entry in BUILTIN_MODEL_CATALOG:
            with self.subTest(vendor=entry.vendor_id, model=entry.model_id):
                self.assertIsInstance(entry.supports_vision, bool)
                # The dataclass field must not default to None.
                field_obj = next(
                    f for f in fields(BuiltInCatalogEntry) if f.name == "supports_vision"
                )
                self.assertNotEqual(field_obj.default, None)

    def test_unknown_catalog_entry_returns_none(self) -> None:
        self.assertIsNone(builtin_catalog_entry("openai", "gpt-4o"))
        self.assertIsNone(builtin_catalog_entry("custom", "gpt-5"))


if __name__ == "__main__":
    unittest.main()
