"""CFG-01: planted secrets / forbidden keys rejected; refs-only docs pass."""

from __future__ import annotations

import unittest

from inkstatute_operator_config.errors import OperatorConfigValidationError
from inkstatute_operator_config.schemas import (
    CatalogSelectionDoc,
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    VisionPolicyDoc,
    WeComChannelDoc,
)
from inkstatute_operator_config.validate import (
    OperatorConfigValidator,
    validate_document,
)

SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"
BEARER_PLANTED = "Bearer " + ("A" * 20)
PLANTED_RAW = "planted-raw-secret-value-NEVER-ON-CONFIG"

_FORBIDDEN_RAW_KEYS = (
    "api_key",
    "token",
    "token_secret",
    "password",
    "bot_secret",
    "app_secret",
    "encoding_aes_key",
    "aes_key",
    "client_secret",
    "raw_payload",
    "raw_body",
    "secret",
    "private_key",
)

# Schema-parallel channel credential stems that must not appear as raw metadata keys.
_SCHEMA_PARALLEL_RAW_KEYS = ("app_secret", "encoding_aes_key", "token_secret")


class TestValidateDocument(unittest.TestCase):
    def test_default_document_returns_empty_issues(self) -> None:
        issues = validate_document(OperatorConfigDocument())
        self.assertEqual(issues, [])

    def test_valid_refs_only_document_passes(self) -> None:
        doc = OperatorConfigDocument(
            channels=ChannelsDoc(
                qqbot=QQBotChannelDoc(
                    enabled=True,
                    app_id_ref="env:QQBOT_APP_ID",
                    app_secret_ref="secret://qqbot/app-secret",
                    token_secret_ref="QQBOT_TOKEN",
                    bot_secret_ref="env:QQBOT_BOT_SECRET",
                ),
                wecom=WeComChannelDoc(
                    token_secret_ref="env:WECOM_TOKEN",
                    encoding_aes_key_secret_ref="secret://wecom/aes-key",
                    corp_id_ref="WECOM_CORP_ID",
                ),
            ),
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_key_ref="env:OPENAI_API_KEY",
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
        )
        issues = validate_document(doc)
        self.assertEqual(issues, [])

    def test_rejects_forbidden_raw_secret_keys_in_metadata(self) -> None:
        for key in _FORBIDDEN_RAW_KEYS:
            with self.subTest(key=key):
                doc = OperatorConfigDocument(
                    channels=ChannelsDoc(
                        qqbot=QQBotChannelDoc(metadata={key: "should-not-matter"}),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                message = str(ctx.exception)
                self.assertNotIn("should-not-matter", message)
                issues = OperatorConfigValidator().validate(doc)
                self.assertIn("raw_secret_key_forbidden", {i.code for i in issues})

    def test_rejects_schema_parallel_raw_secrets_in_channel_metadata(self) -> None:
        """CFG-01: app_secret / encoding_aes_key / token_secret must not persist via metadata."""
        for key in _SCHEMA_PARALLEL_RAW_KEYS:
            with self.subTest(channel="qqbot", key=key):
                planted = f"raw-{key}-value-NEVER-ON-CONFIG"
                doc = OperatorConfigDocument(
                    channels=ChannelsDoc(
                        qqbot=QQBotChannelDoc(metadata={key: planted}),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                message = str(ctx.exception)
                self.assertNotIn(planted, message)
                issues = OperatorConfigValidator().validate(doc)
                self.assertIn("raw_secret_key_forbidden", {i.code for i in issues})
            with self.subTest(channel="wecom", key=key):
                planted = f"raw-{key}-value-NEVER-ON-CONFIG"
                doc = OperatorConfigDocument(
                    channels=ChannelsDoc(
                        wecom=WeComChannelDoc(metadata={key: planted}),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                self.assertNotIn(planted, str(ctx.exception))

    def test_rejects_planted_sk_marker_without_echo(self) -> None:
        doc = OperatorConfigDocument(
            channels=ChannelsDoc(
                qqbot=QQBotChannelDoc(metadata={"note": SK_PLANTED}),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertNotIn(SK_PLANTED, message)
        self.assertNotIn("sk-", message)
        issues = OperatorConfigValidator().validate(doc)
        self.assertIn("secret_marker_in_field", {i.code for i in issues})

    def test_rejects_bearer_blob_without_echo(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="x",
                    kind="x",
                    metadata={"auth_header": BEARER_PLANTED},
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertNotIn(BEARER_PLANTED, str(ctx.exception))
        self.assertNotIn("AAAA", str(ctx.exception))

    def test_rejects_planted_raw_in_ref_field_without_echo(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_key_ref=PLANTED_RAW,
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertNotIn(PLANTED_RAW, message)
        issues = OperatorConfigValidator().validate(doc)
        self.assertIn("invalid_secret_ref", {i.code for i in issues})

    def test_rejects_sk_in_api_key_ref_without_echo(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_key_ref=SK_PLANTED,
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertNotIn(SK_PLANTED, message)
        self.assertNotIn("sk-", message)

    def test_rejects_password_equals_marker_without_echo(self) -> None:
        planted = "password=" + PLANTED_RAW
        doc = OperatorConfigDocument(
            channels=ChannelsDoc(
                wecom=WeComChannelDoc(metadata={"legacy": planted}),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertNotIn(PLANTED_RAW, message)
        self.assertNotIn("password=", message)

    def test_validator_collects_issues_without_raising(self) -> None:
        doc = OperatorConfigDocument(
            channels=ChannelsDoc(
                qqbot=QQBotChannelDoc(metadata={"api_key": SK_PLANTED}),
            )
        )
        issues = OperatorConfigValidator().validate(doc)
        self.assertGreaterEqual(len(issues), 1)
        blob = " ".join(f"{i.code}:{i.message}" for i in issues)
        self.assertNotIn(SK_PLANTED, blob)
        self.assertNotIn("sk-", blob)


def _openai_provider() -> ProviderDoc:
    return ProviderDoc(
        provider_id="openai",
        kind="openai",
        enabled=True,
        api_base_url="https://api.openai.com/v1",
        api_key_ref="env:OPENAI_API_KEY",
    )


def _anthropic_provider() -> ProviderDoc:
    return ProviderDoc(
        provider_id="anthropic",
        kind="anthropic",
        enabled=True,
        api_base_url="https://api.anthropic.com/v1",
        api_key_ref="env:ANTHROPIC_API_KEY",
    )


def _custom_provider() -> ProviderDoc:
    return ProviderDoc(
        provider_id="custom-1",
        kind="custom",
        enabled=True,
        api_base_url="https://api.example.com/v1",
        api_key_ref="secret://custom/api-key",
        model_allowlist=("local-model-a", "local-model-b"),
    )


class TestProviderRegistryValidation(unittest.TestCase):
    def test_valid_builtin_openai_and_anthropic_providers_pass(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(), _anthropic_provider()),
        )
        self.assertEqual(validate_document(doc), [])

    def test_valid_custom_provider_passes(self) -> None:
        doc = OperatorConfigDocument(providers=(_custom_provider(),))
        self.assertEqual(validate_document(doc), [])

    def test_duplicate_provider_id_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(), _openai_provider()),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("duplicate_provider_id", message)
        issues = OperatorConfigValidator().validate(doc)
        self.assertIn("duplicate_provider_id", {i.code for i in issues})

    def test_unsupported_provider_kind_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(provider_id="x", kind="openai_compatible"),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("unsupported_provider_kind", str(ctx.exception))

    def test_forged_builtin_api_base_url_rejected_without_echo(self) -> None:
        forged = "https://evil.example.com/v1"
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_base_url=forged,
                    api_key_ref="env:OPENAI_API_KEY",
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("builtin_url_mismatch", message)
        self.assertNotIn(forged, message)

    def test_nonempty_builtin_model_allowlist_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_base_url="https://api.openai.com/v1",
                    api_key_ref="env:OPENAI_API_KEY",
                    model_allowlist=("gpt-5",),
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("builtin_allowlist_misuse", str(ctx.exception))

    def test_custom_provider_missing_allowlist_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="custom-1",
                    kind="custom",
                    api_base_url="https://api.example.com/v1",
                    api_key_ref="secret://custom/api-key",
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("custom_provider_requires_allowlist", str(ctx.exception))

    def test_custom_provider_invalid_url_rejected_without_echo(self) -> None:
        bad_urls = (
            "http://api.example.com/v1",  # non-https
            "ftp://api.example.com/v1",  # non-https
            "https://user:pass@api.example.com/v1",  # userinfo
            "https://api.example.com/v1?x=1",  # query
            "https://api.example.com/v1#frag",  # fragment
            "https://127.0.0.1/v1",  # loopback literal IP
            "https://10.0.0.1/v1",  # private literal IP
            "https://169.254.169.254/v1",  # link-local literal IP
            "https://[::1]/v1",  # ipv6 loopback
            "not-a-url",
        )
        for url in bad_urls:
            with self.subTest(url=url):
                doc = OperatorConfigDocument(
                    providers=(
                        ProviderDoc(
                            provider_id="custom-1",
                            kind="custom",
                            api_base_url=url,
                            api_key_ref="secret://custom/api-key",
                            model_allowlist=("local-model-a",),
                        ),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                message = str(ctx.exception)
                self.assertIn("invalid_custom_url", message)
                self.assertNotIn(url, message)


class TestCatalogSelectionValidation(unittest.TestCase):
    def test_unset_catalog_passes(self) -> None:
        doc = OperatorConfigDocument(providers=(_openai_provider(),))
        self.assertEqual(validate_document(doc), [])

    def test_valid_builtin_catalog_selection_passes(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
        )
        self.assertEqual(validate_document(doc), [])

    def test_valid_anthropic_catalog_selection_passes(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_anthropic_provider(),),
            catalog=CatalogSelectionDoc(
                provider_id="anthropic", model_id="claude-opus-4-8"
            ),
        )
        self.assertEqual(validate_document(doc), [])

    def test_valid_custom_catalog_selection_passes(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_custom_provider(),),
            catalog=CatalogSelectionDoc(
                provider_id="custom-1", model_id="local-model-a"
            ),
        )
        self.assertEqual(validate_document(doc), [])

    def test_half_filled_catalog_rejected(self) -> None:
        for selection in (
            CatalogSelectionDoc(provider_id="openai", model_id=None),
            CatalogSelectionDoc(provider_id=None, model_id="gpt-5"),
        ):
            with self.subTest(selection=selection):
                doc = OperatorConfigDocument(
                    providers=(_openai_provider(),), catalog=selection
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                self.assertIn("incomplete_catalog_selection", str(ctx.exception))

    def test_unknown_provider_in_catalog_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            catalog=CatalogSelectionDoc(provider_id="ghost", model_id="gpt-5"),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("unknown_provider", str(ctx.exception))

    def test_builtin_vendor_mismatch_rejected(self) -> None:
        # openai provider selecting an anthropic catalog model.
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            catalog=CatalogSelectionDoc(
                provider_id="openai", model_id="claude-opus-4-8"
            ),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("builtin_model_vendor_mismatch", str(ctx.exception))

    def test_unknown_builtin_model_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-4o"),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertIn("builtin_model_vendor_mismatch", str(ctx.exception))

    def test_custom_model_not_in_allowlist_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_custom_provider(),),
            catalog=CatalogSelectionDoc(
                provider_id="custom-1", model_id="not-allowed-model"
            ),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("custom_model_not_allowed", message)
        self.assertNotIn("not-allowed-model", message)


class TestVisionSelectionValidation(unittest.TestCase):
    def test_absent_vision_pair_passes(self) -> None:
        doc = OperatorConfigDocument(providers=(_openai_provider(),))
        self.assertEqual(validate_document(doc), [])

    def test_partial_vision_pair_remains_valid_draft(self) -> None:
        for vision in (
            VisionPolicyDoc(vision_provider_id="openai", vision_model_id=None),
            VisionPolicyDoc(vision_provider_id=None, vision_model_id="gpt-5"),
        ):
            with self.subTest(vision=vision):
                doc = OperatorConfigDocument(
                    providers=(_openai_provider(),), vision=vision
                )
                self.assertEqual(validate_document(doc), [])

    def test_complete_builtin_vision_pair_passes(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            vision=VisionPolicyDoc(
                vision_provider_id="openai", vision_model_id="gpt-5"
            ),
        )
        self.assertEqual(validate_document(doc), [])

    def test_complete_custom_vision_pair_passes(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_custom_provider(),),
            vision=VisionPolicyDoc(
                vision_provider_id="custom-1", vision_model_id="local-model-b"
            ),
        )
        self.assertEqual(validate_document(doc), [])

    def test_complete_vision_pair_unknown_provider_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            vision=VisionPolicyDoc(
                vision_provider_id="ghost", vision_model_id="gpt-5"
            ),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("unknown_provider", message)
        self.assertIn("vision.vision_provider_id", message)

    def test_complete_vision_pair_builtin_mismatch_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_openai_provider(),),
            vision=VisionPolicyDoc(
                vision_provider_id="openai", vision_model_id="claude-opus-4-8"
            ),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("builtin_model_vendor_mismatch", message)
        self.assertIn("vision.vision_model_id", message)

    def test_complete_vision_pair_custom_not_allowed_rejected(self) -> None:
        doc = OperatorConfigDocument(
            providers=(_custom_provider(),),
            vision=VisionPolicyDoc(
                vision_provider_id="custom-1", vision_model_id="not-allowed"
            ),
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        message = str(ctx.exception)
        self.assertIn("custom_model_not_allowed", message)
        self.assertNotIn("not-allowed", message)


class TestCatalogPublicExports(unittest.TestCase):
    def test_catalog_symbols_importable_from_package(self) -> None:
        import inkstatute_operator_config as pkg

        for name in (
            "BuiltInCatalogEntry",
            "VendorProfile",
            "BUILTIN_VENDOR_PROFILES",
            "BUILTIN_MODEL_CATALOG",
        ):
            self.assertTrue(hasattr(pkg, name), f"missing public export {name}")


if __name__ == "__main__":
    unittest.main()
