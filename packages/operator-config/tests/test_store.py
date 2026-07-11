"""CFG-01: atomic OperatorConfigStore persist + round-trip when flag ON."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from platform_runtime.feature_flags import RuntimeFeatureFlags

from inkstatute_operator_config.errors import (
    OperatorConfigStoreError,
    OperatorConfigValidationError,
)
from inkstatute_operator_config.schemas import (
    CatalogSelectionDoc,
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    VisionPolicyDoc,
    WeComChannelDoc,
)
from inkstatute_operator_config.store import (
    OperatorConfigStore,
    default_operator_config_path,
    document_from_payload,
)


def _enabled_flags() -> RuntimeFeatureFlags:
    return RuntimeFeatureFlags(operator_config_enabled=True)


def _refs_only_doc() -> OperatorConfigDocument:
    return OperatorConfigDocument(
        schema_version=1,
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
        catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
        vision=VisionPolicyDoc(routing_mode="main_only"),
    )


class TestOperatorConfigStore(unittest.TestCase):
    def test_load_missing_returns_default_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            loaded = store.load()
            self.assertIsInstance(loaded, OperatorConfigDocument)
            self.assertEqual(loaded.schema_version, 1)
            self.assertFalse(loaded.channels.qqbot.enabled)
            self.assertEqual(loaded.providers, ())

    def test_atomic_round_trip_when_flag_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            doc = _refs_only_doc()
            store.save(doc, feature_flags=_enabled_flags())

            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

            loaded = store.load()
            self.assertEqual(loaded.schema_version, doc.schema_version)
            self.assertTrue(loaded.channels.qqbot.enabled)
            self.assertEqual(loaded.channels.qqbot.app_id_ref, "env:QQBOT_APP_ID")
            self.assertEqual(
                loaded.channels.qqbot.app_secret_ref, "secret://qqbot/app-secret"
            )
            self.assertEqual(loaded.channels.wecom.corp_id_ref, "WECOM_CORP_ID")
            self.assertEqual(len(loaded.providers), 1)
            self.assertEqual(loaded.providers[0].api_key_ref, "env:OPENAI_API_KEY")
            self.assertEqual(loaded.catalog.model_id, "gpt-5")
            self.assertEqual(loaded.vision.routing_mode, "main_only")

            raw = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(raw)
            self.assertNotIn("sk-", serialized)
            self.assertNotIn("planted", serialized.lower())

    def test_save_uses_os_replace_sibling_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            replace_calls: list[tuple[str, str]] = []
            real_replace = os.replace

            def _tracking_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                replace_calls.append((str(src), str(dst)))
                real_replace(src, dst)

            with mock.patch("inkstatute_operator_config.store.os.replace", side_effect=_tracking_replace):
                store.save(_refs_only_doc(), feature_flags=_enabled_flags())

            self.assertEqual(len(replace_calls), 1)
            src, dst = replace_calls[0]
            self.assertEqual(Path(dst), path)
            self.assertEqual(Path(src), path.with_suffix(path.suffix + ".tmp"))

    def test_gitignore_covers_operator_config_tmp_sibling(self) -> None:
        """WR-04: atomic-write .tmp siblings must be gitignored like the store file."""
        root = Path(__file__).resolve().parents[3]
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".inkstatute/operator-config.json.tmp", gitignore)
        self.assertIn("operator-config.json.tmp", gitignore)

    def test_save_rejects_invalid_document_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            bad = OperatorConfigDocument(
                channels=ChannelsDoc(
                    qqbot=QQBotChannelDoc(
                        metadata={"api_key": "should-not-persist"},
                    )
                )
            )
            with self.assertRaises(OperatorConfigValidationError):
                store.save(bad, feature_flags=_enabled_flags())
            self.assertFalse(path.exists())

    def test_save_rejects_schema_parallel_raw_secrets_without_writing(self) -> None:
        """CR-01: app_secret / encoding_aes_key / token_secret in metadata must not persist."""
        for key in ("app_secret", "encoding_aes_key", "token_secret"):
            with self.subTest(key=key):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "operator-config.json"
                    store = OperatorConfigStore(path)
                    planted = f"raw-{key}-should-not-persist"
                    bad = OperatorConfigDocument(
                        channels=ChannelsDoc(
                            qqbot=QQBotChannelDoc(metadata={key: planted}),
                        )
                    )
                    with self.assertRaises(OperatorConfigValidationError) as ctx:
                        store.save(bad, feature_flags=_enabled_flags())
                    self.assertNotIn(planted, str(ctx.exception))
                    self.assertFalse(path.exists())

    def test_default_path_helper_reads_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configured = Path(tmp) / "custom-config.json"
            with mock.patch.dict(
                os.environ,
                {"INKSTATUTE_OPERATOR_CONFIG_PATH": str(configured)},
                clear=False,
            ):
                self.assertEqual(default_operator_config_path(), configured)

    def test_load_rejects_invalid_document_fail_closed(self) -> None:
        """WR-01: corrupted/hand-edited store with raw secrets must not load as SoT."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            planted = "raw-app-secret-should-not-load"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "channels": {
                            "qqbot": {
                                "channel_id": "qqbot",
                                "enabled": False,
                                "metadata": {"app_secret": planted},
                            },
                            "wecom": {"channel_id": "wecom", "enabled": False},
                        },
                        "providers": [],
                        "catalog": {},
                        "vision": {},
                    }
                ),
                encoding="utf-8",
            )
            store = OperatorConfigStore(path)
            with self.assertRaises(OperatorConfigValidationError) as ctx:
                store.load()
            self.assertNotIn(planted, str(ctx.exception))

    def test_document_from_payload_rejects_non_object_metadata(self) -> None:
        """WR-03: metadata string/list must raise OperatorConfigStoreError, not ValueError."""
        with self.assertRaises(OperatorConfigStoreError) as ctx:
            document_from_payload(
                {
                    "channels": {
                        "qqbot": {"metadata": "not-an-object"},
                        "wecom": {},
                    }
                }
            )
        self.assertIn("metadata", str(ctx.exception))
        self.assertIsInstance(ctx.exception, OperatorConfigStoreError)

    def test_document_from_payload_rejects_non_numeric_schema_version(self) -> None:
        with self.assertRaises(OperatorConfigStoreError) as ctx:
            document_from_payload({"schema_version": "not-a-number"})
        self.assertIn("schema_version", str(ctx.exception))

    def test_document_from_payload_rejects_non_object_provider_items(self) -> None:
        """WR-03: corrupt provider list items must not be silently dropped."""
        with self.assertRaises(OperatorConfigStoreError) as ctx:
            document_from_payload(
                {
                    "providers": [
                        {"provider_id": "ok", "kind": "ok"},
                        "dropped-silently-before",
                    ]
                }
            )
        self.assertIn("providers[1]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
