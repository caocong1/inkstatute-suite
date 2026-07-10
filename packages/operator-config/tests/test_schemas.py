"""CFG-01: frozen refs-only OperatorConfigDocument shapes and defaults."""

from __future__ import annotations

import unittest
from dataclasses import fields, is_dataclass

from inkstatute_operator_config.schemas import (
    CatalogSelectionDoc,
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    VisionPolicyDoc,
    WeComChannelDoc,
)


def _credential_field_names(cls: type) -> list[str]:
    """Return field names that look like credential carriers (must end with _ref)."""
    names: list[str] = []
    for f in fields(cls):
        name = f.name
        # Non-credential structural fields
        if name in {
            "channel_id",
            "enabled",
            "metadata",
            "provider_id",
            "kind",
            "api_base_url",
            "model_allowlist",
            "model_id",
            "routing_mode",
            "main_model_id",
            "vision_model_id",
            "vision_provider_id",
            "schema_version",
            "channels",
            "providers",
            "catalog",
            "vision",
            "qqbot",
            "wecom",
        }:
            continue
        names.append(name)
    return names


class TestOperatorConfigDocumentDefaults(unittest.TestCase):
    def test_root_defaults(self) -> None:
        doc = OperatorConfigDocument()
        self.assertTrue(is_dataclass(doc))
        self.assertEqual(doc.schema_version, 1)
        self.assertIsInstance(doc.channels, ChannelsDoc)
        self.assertIsInstance(doc.catalog, CatalogSelectionDoc)
        self.assertIsInstance(doc.vision, VisionPolicyDoc)
        self.assertEqual(doc.providers, ())

    def test_qqbot_channel_defaults_enabled_false_and_refs_none(self) -> None:
        ch = QQBotChannelDoc()
        self.assertEqual(ch.channel_id, "qqbot")
        self.assertIs(ch.enabled, False)
        self.assertIsNone(ch.app_id_ref)
        self.assertIsNone(ch.app_secret_ref)
        self.assertIsNone(ch.token_secret_ref)
        self.assertIsNone(ch.bot_secret_ref)

    def test_wecom_channel_defaults_enabled_false_and_refs_none(self) -> None:
        ch = WeComChannelDoc()
        self.assertEqual(ch.channel_id, "wecom")
        self.assertIs(ch.enabled, False)
        self.assertIsNone(ch.token_secret_ref)
        self.assertIsNone(ch.encoding_aes_key_secret_ref)
        self.assertIsNone(ch.corp_id_ref)

    def test_provider_defaults_enabled_false_and_api_key_ref(self) -> None:
        p = ProviderDoc(provider_id="p1", kind="custom")
        self.assertIs(p.enabled, False)
        self.assertIsNone(p.api_key_ref)
        self.assertIsNone(p.api_base_url)
        self.assertEqual(p.model_allowlist, ())
        self.assertFalse(hasattr(p, "api_key"))

    def test_provider_model_allowlist_is_tuple(self) -> None:
        p = ProviderDoc(
            provider_id="custom-1",
            kind="custom",
            model_allowlist=("gpt-5", "gpt-4o-mini"),
        )
        self.assertIsInstance(p.model_allowlist, tuple)
        self.assertEqual(p.model_allowlist, ("gpt-5", "gpt-4o-mini"))

    def test_catalog_selection_stub_fields_only(self) -> None:
        c = CatalogSelectionDoc()
        names = {f.name for f in fields(c)}
        self.assertEqual(names, {"provider_id", "model_id"})
        self.assertIsNone(c.provider_id)
        self.assertIsNone(c.model_id)

    def test_vision_policy_stub_fields(self) -> None:
        v = VisionPolicyDoc()
        names = {f.name for f in fields(v)}
        self.assertEqual(
            names,
            {"routing_mode", "main_model_id", "vision_model_id", "vision_provider_id"},
        )
        self.assertIsNone(v.routing_mode)
        self.assertIsNone(v.main_model_id)
        self.assertIsNone(v.vision_model_id)
        self.assertIsNone(v.vision_provider_id)
        self.assertNotIn("vision_routing_enabled", names)

    def test_vision_policy_supports_complete_provider_model_pair(self) -> None:
        v = VisionPolicyDoc(
            vision_provider_id="vision-vendor",
            vision_model_id="gpt-5",
        )
        self.assertEqual(v.vision_provider_id, "vision-vendor")
        self.assertEqual(v.vision_model_id, "gpt-5")

    def test_credential_attrs_end_with_ref(self) -> None:
        for cls in (QQBotChannelDoc, WeComChannelDoc, ProviderDoc):
            for name in _credential_field_names(cls):
                self.assertTrue(
                    name.endswith("_ref"),
                    f"{cls.__name__}.{name} must end with _ref",
                )

    def test_no_hermes_authority_fields(self) -> None:
        forbidden_substrings = (
            "hermes_home",
            "hermes_profile",
            "profile_filesystem",
            "profile_path",
            "gateway_",
        )
        for cls in (
            QQBotChannelDoc,
            WeComChannelDoc,
            ProviderDoc,
            CatalogSelectionDoc,
            VisionPolicyDoc,
            ChannelsDoc,
            OperatorConfigDocument,
        ):
            for f in fields(cls):
                lower = f.name.lower()
                for needle in forbidden_substrings:
                    self.assertNotIn(
                        needle,
                        lower,
                        f"{cls.__name__}.{f.name} looks like Hermes authority",
                    )

    def test_channels_nested_qqbot_and_wecom(self) -> None:
        channels = ChannelsDoc()
        self.assertIsInstance(channels.qqbot, QQBotChannelDoc)
        self.assertIsInstance(channels.wecom, WeComChannelDoc)
        self.assertIs(channels.qqbot.enabled, False)
        self.assertIs(channels.wecom.enabled, False)

    def test_documents_are_frozen(self) -> None:
        doc = OperatorConfigDocument()
        with self.assertRaises(Exception):
            doc.schema_version = 2  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
