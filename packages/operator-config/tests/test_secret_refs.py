"""CFG-01: shape-only secret-ref normalize; planted secrets rejected without echo."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from inkstatute_operator_config.secrets import (
    InvalidSecretRefError,
    normalize_config_secret_ref,
)

PLANTED = "planted-raw-secret-value-NEVER-ON-CONFIG"
SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"

_SECRETS_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "inkstatute_operator_config"
    / "secrets.py"
)


class TestNormalizeConfigSecretRef(unittest.TestCase):
    def test_none_and_blank_return_none(self) -> None:
        self.assertIsNone(normalize_config_secret_ref(None, field="api_key_ref"))
        self.assertIsNone(normalize_config_secret_ref("", field="api_key_ref"))
        self.assertIsNone(normalize_config_secret_ref("   ", field="api_key_ref"))

    def test_accepts_env_prefix(self) -> None:
        self.assertEqual(
            normalize_config_secret_ref("env:MY_API_KEY", field="api_key_ref"),
            "env:MY_API_KEY",
        )

    def test_accepts_bare_env_name(self) -> None:
        self.assertEqual(
            normalize_config_secret_ref("OPENAI_API_KEY", field="api_key_ref"),
            "OPENAI_API_KEY",
        )

    def test_strips_whitespace_around_refs(self) -> None:
        self.assertEqual(
            normalize_config_secret_ref("  env:MY_VAR  ", field="x"),
            "env:MY_VAR",
        )
        self.assertEqual(
            normalize_config_secret_ref("\tsecret://qqbot/bot-secret\n", field="x"),
            "secret://qqbot/bot-secret",
        )

    def test_accepts_generalized_secret_scheme_paths(self) -> None:
        self.assertEqual(
            normalize_config_secret_ref("secret://qqbot/app-id", field="app_id_ref"),
            "secret://qqbot/app-id",
        )
        self.assertEqual(
            normalize_config_secret_ref(
                "secret://providers/openai/api-key", field="api_key_ref"
            ),
            "secret://providers/openai/api-key",
        )
        self.assertEqual(
            normalize_config_secret_ref("secret://wecom/token", field="token_secret_ref"),
            "secret://wecom/token",
        )

    def test_rejects_malformed_secret_scheme_without_echo(self) -> None:
        bad = "secret://" + PLANTED
        with self.assertRaises(InvalidSecretRefError) as ctx:
            normalize_config_secret_ref(bad, field="bot_secret_ref")
        message = str(ctx.exception)
        self.assertNotIn(PLANTED, message)
        self.assertIn("bot_secret_ref", message)

    def test_rejects_empty_secret_scheme(self) -> None:
        with self.assertRaises(InvalidSecretRefError):
            normalize_config_secret_ref("secret://", field="x")
        with self.assertRaises(InvalidSecretRefError):
            normalize_config_secret_ref("secret:///", field="x")

    def test_rejects_planted_raw_secret_without_echo(self) -> None:
        with self.assertRaises(InvalidSecretRefError) as ctx:
            normalize_config_secret_ref(PLANTED, field="bot_secret_ref")
        message = str(ctx.exception)
        self.assertNotIn(PLANTED, message)
        self.assertIn("bot_secret_ref", message)

    def test_rejects_sk_prefix_without_echo(self) -> None:
        with self.assertRaises(InvalidSecretRefError) as ctx:
            normalize_config_secret_ref(SK_PLANTED, field="api_key_ref")
        message = str(ctx.exception)
        self.assertNotIn(SK_PLANTED, message)
        self.assertNotIn("sk-", message)

    def test_rejects_unknown_scheme_without_echo(self) -> None:
        planted = "vault://leak-" + PLANTED
        with self.assertRaises(InvalidSecretRefError) as ctx:
            normalize_config_secret_ref(planted, field="api_key_ref")
        self.assertNotIn(PLANTED, str(ctx.exception))

    def test_rejects_invalid_env_name_suffix(self) -> None:
        with self.assertRaises(InvalidSecretRefError) as ctx:
            normalize_config_secret_ref("env:bad-name!", field="api_key_ref")
        self.assertNotIn("bad-name!", str(ctx.exception))

    def test_secrets_module_does_not_import_qqbot_or_os_environ(self) -> None:
        source = _SECRETS_SRC.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".", 1)[0])
        self.assertNotIn("qqbot_service", imported)
        self.assertNotIn("os", imported)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("resolve_secret_ref", source)


if __name__ == "__main__":
    unittest.main()
