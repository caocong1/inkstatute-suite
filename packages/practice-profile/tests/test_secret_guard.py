"""Tests for secret detection (secret_guard.py)."""

from __future__ import annotations

import unittest

from inkstatute_practice_profile import SecretDetectedError, validate_no_secrets


class SecretDetectedErrorTests(unittest.TestCase):
    def test_is_value_error_subclass(self) -> None:
        self.assertTrue(issubclass(SecretDetectedError, ValueError))

    def test_has_field_path_and_pattern_name(self) -> None:
        err = SecretDetectedError("a.b.c", "test_pattern")
        self.assertEqual(err.field_path, "a.b.c")
        self.assertEqual(err.pattern_name, "test_pattern")

    def test_str_does_not_include_secret_text(self) -> None:
        err = SecretDetectedError("config.api_key", "api_key_or_secret")
        msg = str(err)
        self.assertIn("config.api_key", msg)
        self.assertIn("api_key_or_secret", msg)
        # The actual secret value should never appear
        self.assertNotIn("sk-abc123", msg)


class ValidateNoSecretsTests(unittest.TestCase):
    def test_api_key_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({"api_key": "sk-abc123"})
        self.assertIn("api_key", ctx.exception.pattern_name)
        self.assertIn("secret", ctx.exception.pattern_name)

    def test_access_token_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"access_token": "abc123def456"})

    def test_secret_key_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"secret_key": "somevalue"})

    def test_nested_password_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({"config": {"password": "hunter2"}})
        self.assertIn("config.password", ctx.exception.field_path)

    def test_pem_private_key_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
            })

    def test_aes_key_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"aes_key": "somevalue"})

    def test_encoding_aes_key_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"encoding_aes_key": "somevalue"})

    def test_password_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"password": "supersecret123"})

    def test_passwd_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"passwd": "supersecret123"})

    def test_pwd_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({"pwd": "supersecret123"})

    def test_env_secret_hermes_home_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({
                "env_config": "HERMES_HOME=/path/to/secrets",
            })

    def test_env_secret_acp_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({
                "env_config": "ACP_API_KEY=somevalue",
            })

    def test_env_secret_agent_rejected(self) -> None:
        with self.assertRaises(SecretDetectedError):
            validate_no_secrets({
                "env_config": "AGENT_TOKEN=abc123",
            })

    def test_normal_profile_data_passes(self) -> None:
        validate_no_secrets({
            "org_name": "某律师事务所",
            "risk_appetite": "平衡型",
            "entity_type": "有限责任公司",
            "role": "律师",
            "revision_tone": "半正式",
            "jurisdiction_identification": "中国大陆法律",
        })

    def test_empty_data_passes(self) -> None:
        validate_no_secrets({})

    def test_nested_dict_traversal(self) -> None:
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({
                "level1": {"level2": {"api_key": "sk-test"}},
            })
        self.assertIn("level1.level2.api_key", ctx.exception.field_path)

    def test_list_traversal(self) -> None:
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({"list": [{"token": "abc"}]})
        self.assertIn("list.0.token", ctx.exception.field_path)

    def test_deeply_nested_list_in_dict(self) -> None:
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({
                "data": {"items": [{"config": {"secret": "value"}}]},
            })
        self.assertIn("data.items.0.config.secret", ctx.exception.field_path)

    def test_no_secret_value_in_error_attributes(self) -> None:
        secret_value = "sk-abc123def456"
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({"api_key": secret_value})
        error_str = str(ctx.exception)
        self.assertNotIn(secret_value, error_str)
        self.assertNotIn(secret_value, ctx.exception.field_path)
        self.assertNotIn(secret_value, ctx.exception.pattern_name)

    def test_no_secret_value_in_error_for_password(self) -> None:
        secret_value = "hunter2supersecret"
        with self.assertRaises(SecretDetectedError) as ctx:
            validate_no_secrets({"password": secret_value})
        error_str = str(ctx.exception)
        self.assertNotIn(secret_value, error_str)


if __name__ == "__main__":
    unittest.main()
