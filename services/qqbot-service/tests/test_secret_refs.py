"""SAFE-02: host config stores secret refs only; values resolve at process edge."""

from __future__ import annotations

import unittest
from dataclasses import asdict

from qqbot_service import QQBotHostConfig, resolve_secret_ref
from qqbot_service.secrets import InvalidSecretRefError


PLANTED = "planted-raw-secret-value-NEVER-ON-CONFIG"


class TestQQBotHostConfigRefsOnly(unittest.TestCase):
    def test_defaults_enabled_false_and_refs_none(self) -> None:
        cfg = QQBotHostConfig()
        self.assertIs(cfg.enabled, False)
        self.assertIsNone(cfg.app_id_ref)
        self.assertIsNone(cfg.app_secret_ref)
        self.assertIsNone(cfg.token_secret_ref)
        self.assertIsNone(cfg.bot_secret_ref)

    def test_from_env_reads_ref_keys_only(self) -> None:
        cfg = QQBotHostConfig.from_env(
            {
                "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true",
                "INKSTATUTE_QQBOT_APP_ID_REF": "secret://qqbot/app-id",
                "INKSTATUTE_QQBOT_APP_SECRET_REF": "secret://qqbot/app-secret",
                "INKSTATUTE_QQBOT_TOKEN_SECRET_REF": "secret://qqbot/token",
                "INKSTATUTE_QQBOT_BOT_SECRET_REF": "secret://qqbot/bot-secret",
            }
        )
        self.assertIs(cfg.enabled, True)
        self.assertEqual(cfg.app_id_ref, "secret://qqbot/app-id")
        self.assertEqual(cfg.app_secret_ref, "secret://qqbot/app-secret")
        self.assertEqual(cfg.token_secret_ref, "secret://qqbot/token")
        self.assertEqual(cfg.bot_secret_ref, "secret://qqbot/bot-secret")

    def test_from_env_ignores_planted_raw_secret_keys(self) -> None:
        cfg = QQBotHostConfig.from_env(
            {
                "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "1",
                "INKSTATUTE_QQBOT_BOT_SECRET": PLANTED,
                "INKSTATUTE_QQBOT_CLIENT_SECRET": PLANTED,
                "INKSTATUTE_QQBOT_APP_ID": PLANTED,
                "INKSTATUTE_QQBOT_APP_SECRET_REF": "env:MY_APP_SECRET",
                "INKSTATUTE_QQBOT_BOT_SECRET_REF": "secret://qqbot/bot-secret",
            }
        )
        values = set(asdict(cfg).values())
        self.assertNotIn(PLANTED, values)
        self.assertEqual(cfg.bot_secret_ref, "secret://qqbot/bot-secret")
        self.assertEqual(cfg.app_secret_ref, "env:MY_APP_SECRET")
        self.assertIsNone(cfg.app_id_ref)

    def test_asdict_contains_no_planted_secret(self) -> None:
        cfg = QQBotHostConfig.from_env(
            {
                "INKSTATUTE_QQBOT_BOT_SECRET": PLANTED,
                "INKSTATUTE_QQBOT_BOT_SECRET_REF": "secret://qqbot/bot-secret",
            }
        )
        rendered = str(asdict(cfg))
        self.assertNotIn(PLANTED, rendered)

    def test_from_env_rejects_raw_secret_planted_in_ref_key(self) -> None:
        with self.assertRaises(InvalidSecretRefError) as ctx:
            QQBotHostConfig.from_env(
                {
                    "INKSTATUTE_QQBOT_BOT_SECRET_REF": PLANTED,
                }
            )
        message = str(ctx.exception)
        self.assertNotIn(PLANTED, message)
        self.assertIn("INKSTATUTE_QQBOT_BOT_SECRET_REF", message)

    def test_from_env_rejects_unknown_secret_scheme(self) -> None:
        with self.assertRaises(InvalidSecretRefError):
            QQBotHostConfig.from_env(
                {
                    "INKSTATUTE_QQBOT_APP_ID_REF": "vault://nope",
                }
            )


class TestResolveSecretRef(unittest.TestCase):
    def test_none_and_empty_return_none(self) -> None:
        self.assertIsNone(resolve_secret_ref(None, {"A": "x"}))
        self.assertIsNone(resolve_secret_ref("", {"A": "x"}))

    def test_env_prefix(self) -> None:
        self.assertEqual(
            resolve_secret_ref("env:MY_VAR", {"MY_VAR": "s3cret"}),
            "s3cret",
        )

    def test_direct_env_key_name(self) -> None:
        self.assertEqual(
            resolve_secret_ref("MY_VAR", {"MY_VAR": "s3cret"}),
            "s3cret",
        )

    def test_secret_scheme_bot_secret(self) -> None:
        self.assertEqual(
            resolve_secret_ref(
                "secret://qqbot/bot-secret",
                {"INKSTATUTE_QQBOT_BOT_SECRET": "s3cret"},
            ),
            "s3cret",
        )

    def test_secret_scheme_app_id_and_app_secret(self) -> None:
        env = {
            "INKSTATUTE_QQBOT_APP_ID": "app-id-value",
            "INKSTATUTE_QQBOT_CLIENT_SECRET": "client-secret-value",
            "INKSTATUTE_QQBOT_TOKEN": "token-value",
        }
        self.assertEqual(
            resolve_secret_ref("secret://qqbot/app-id", env),
            "app-id-value",
        )
        self.assertEqual(
            resolve_secret_ref("secret://qqbot/app-secret", env),
            "client-secret-value",
        )
        self.assertEqual(
            resolve_secret_ref("secret://qqbot/token", env),
            "token-value",
        )

    def test_unknown_ref_fail_closed(self) -> None:
        self.assertIsNone(resolve_secret_ref("secret://qqbot/unknown", {"X": "y"}))
        self.assertIsNone(resolve_secret_ref("vault://nope", {"X": "y"}))

    def test_missing_mapping_returns_none(self) -> None:
        self.assertIsNone(
            resolve_secret_ref("secret://qqbot/bot-secret", {})
        )

    def test_config_unchanged_after_resolve(self) -> None:
        cfg = QQBotHostConfig(
            enabled=False,
            bot_secret_ref="secret://qqbot/bot-secret",
        )
        before = asdict(cfg)
        value = resolve_secret_ref(
            cfg.bot_secret_ref,
            {"INKSTATUTE_QQBOT_BOT_SECRET": PLANTED},
        )
        self.assertEqual(value, PLANTED)
        self.assertEqual(asdict(cfg), before)
        self.assertNotIn(PLANTED, set(asdict(cfg).values()))


if __name__ == "__main__":
    unittest.main()
