"""Wave 0 / Plan 01→04: WeComChannelConfig.from_operator_doc field parity.

Plan 01 scaffolds RED coverage. Plan 04 greens ``from_operator_doc`` mapping
store/doc fields (host enabled + refs) without importing RuntimeFeatureFlags.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from inkstatute_channels_wecom.config import WeComChannelConfig

_CONFIG_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "inkstatute_channels_wecom"
    / "config.py"
)


class WeComFromOperatorDocScaffoldTests(unittest.TestCase):
    """CHAN-02: from_operator_doc materializer (Plan 04)."""

    def test_from_operator_doc_symbol_exists(self) -> None:
        if not hasattr(WeComChannelConfig, "from_operator_doc"):
            self.fail(
                "CHAN-02: WeComChannelConfig.from_operator_doc not implemented "
                "(Plan 04) — map enabled + token/aes/corp refs from Mapping/doc"
            )

    def test_from_operator_doc_field_parity(self) -> None:
        if not hasattr(WeComChannelConfig, "from_operator_doc"):
            self.fail(
                "CHAN-02: WeComChannelConfig.from_operator_doc not implemented (Plan 04)"
            )

        doc = {
            "enabled": True,
            "token_secret_ref": "secret://wecom/token",
            "encoding_aes_key_secret_ref": "secret://wecom/aes",
            "corp_id_ref": "env:WECOM_CORP_ID",
            "metadata": {"source": "operator-store"},
        }
        cfg = WeComChannelConfig.from_operator_doc(doc)
        self.assertIs(cfg.enabled, True)
        self.assertEqual(cfg.token_secret_ref, "secret://wecom/token")
        self.assertEqual(cfg.encoding_aes_key_secret_ref, "secret://wecom/aes")
        self.assertEqual(cfg.corp_id_ref, "env:WECOM_CORP_ID")
        self.assertEqual(cfg.metadata.get("source"), "operator-store")
        # Host knob only — dual-knob AND lives in wecom-service wiring.
        self.assertEqual(cfg.channel_id, "wecom")

    def test_channel_package_does_not_import_runtime_feature_flags(self) -> None:
        tree = ast.parse(_CONFIG_SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("feature_flags", alias.name)
                    self.assertNotIn("platform_runtime", alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertNotIn("feature_flags", module)
                self.assertNotEqual(module, "platform_runtime")
                self.assertFalse(module.startswith("platform_runtime."))
                for alias in node.names:
                    self.assertNotEqual(alias.name, "RuntimeFeatureFlags")


if __name__ == "__main__":
    unittest.main()
