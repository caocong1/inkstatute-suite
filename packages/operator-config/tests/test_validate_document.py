"""CFG-01: planted secrets / forbidden keys rejected; refs-only docs pass."""

from __future__ import annotations

import unittest

from inkstatute_operator_config.errors import OperatorConfigValidationError
from inkstatute_operator_config.schemas import (
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
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


if __name__ == "__main__":
    unittest.main()
