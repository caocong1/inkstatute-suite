"""CFG-02: default-OFF operator_config_enabled refuses package mutate/save."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from platform_runtime.feature_flags import RuntimeFeatureFlags

from inkstatute_operator_config.errors import OperatorConfigDisabledError
from inkstatute_operator_config.flags import require_operator_config_writable
from inkstatute_operator_config.schemas import (
    ChannelsDoc,
    OperatorConfigDocument,
    QQBotChannelDoc,
)
from inkstatute_operator_config.store import OperatorConfigStore


class TestRequireOperatorConfigWritable(unittest.TestCase):
    def test_default_flags_raise_disabled(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaises(OperatorConfigDisabledError):
            require_operator_config_writable(flags)

    def test_enabled_flags_pass(self) -> None:
        flags = RuntimeFeatureFlags(operator_config_enabled=True)
        require_operator_config_writable(flags)


class TestStoreFlagGate(unittest.TestCase):
    def test_save_refuses_when_flag_off_and_creates_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            doc = OperatorConfigDocument(
                channels=ChannelsDoc(
                    qqbot=QQBotChannelDoc(
                        enabled=True,
                        app_id_ref="env:QQBOT_APP_ID",
                    )
                )
            )
            flags = RuntimeFeatureFlags()  # default OFF

            with self.assertRaises(OperatorConfigDisabledError):
                store.save(doc, feature_flags=flags)

            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_save_refuses_before_disk_even_if_path_parent_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "missing" / "operator-config.json"
            store = OperatorConfigStore(path)
            flags = RuntimeFeatureFlags()

            with self.assertRaises(OperatorConfigDisabledError):
                store.save(OperatorConfigDocument(), feature_flags=flags)

            self.assertFalse(path.exists())
            self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
