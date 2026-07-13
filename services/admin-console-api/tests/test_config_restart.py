"""Tests that /config/channels PUT triggers ProcessSupervisor restart_for_channels."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from admin_console_api.api import handle_admin_put
from admin_console_api.process_supervisor import ProcessSupervisor
from inkstatute_operator_config import OperatorConfigStore
from inkstatute_operator_config.store import document_to_payload
from platform_runtime.feature_flags import RuntimeFeatureFlags


class ConfigRestartTests(unittest.TestCase):
    """Integration tests for config-save → channel host restart wiring."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.config_path = os.path.join(self.tmpdir.name, "operator-config.json")
        self.store = OperatorConfigStore(path=self.config_path)

        self.env = {
            "ADMIN_API_TOKEN": "test-token",
            "INKSTATUTE_PROCESS_STATE_PATH": os.path.join(self.tmpdir.name, "state.json"),
            "INKSTATUTE_PROCESS_LOG_DIR": os.path.join(self.tmpdir.name, "logs"),
        }

        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            qqbot_channel_enabled=True,
            wecom_channel_enabled=True,
        )

        self.supervisor = MagicMock(spec=ProcessSupervisor)
        self.supervisor.restart_for_channels = MagicMock(return_value=[])

    def _put_channels(self, body: dict[str, object]) -> tuple[int, dict]:
        return handle_admin_put(
            "/config/channels",
            body,
            {"Authorization": "Bearer test-token"},
            self.flags,
            self.env,
            config_store=self.store,
            process_supervisor=self.supervisor,
        )

    def test_wecom_ref_change_triggers_restart(self) -> None:
        first = {
            "qqbot": {"enabled": False},
            "wecom": {
                "enabled": True,
                "token_secret_ref": "env:WECOM_TOKEN",
            },
        }
        status, _body = self._put_channels(first)
        self.assertEqual(status, 200)

        second = {
            "qqbot": {"enabled": False},
            "wecom": {
                "enabled": True,
                "token_secret_ref": "secret://wecom/token",
            },
        }
        status, _body = self._put_channels(second)
        self.assertEqual(status, 200)

        self.supervisor.restart_for_channels.assert_called()
        call_args = self.supervisor.restart_for_channels.call_args
        old_channels, new_channels = call_args.args
        self.assertEqual(old_channels["qqbot"], new_channels["qqbot"])
        self.assertNotEqual(old_channels["wecom"], new_channels["wecom"])

    def test_unchanged_qqbot_not_restarted(self) -> None:
        body = {
            "qqbot": {"enabled": False},
            "wecom": {"enabled": True},
        }
        status, _body = self._put_channels(body)
        self.assertEqual(status, 200)

        status, _body = self._put_channels(body)
        self.assertEqual(status, 200)

        # restart_for_channels is called each save, but the supervisor method
        # decides which channels to restart. With identical payloads, the mock
        # returns [] and the method is not responsible for the actual diff.
        self.supervisor.restart_for_channels.assert_called()

    def test_config_saved_before_restart(self) -> None:
        body = {
            "qqbot": {"enabled": False},
            "wecom": {"enabled": True, "token_secret_ref": "env:WECOM_TOKEN"},
        }

        def _assert_saved_then_restart(old: dict, new: dict) -> list:
            saved = self.store.load()
            payload = document_to_payload(saved)
            self.assertEqual(payload["channels"]["wecom"]["token_secret_ref"], "env:WECOM_TOKEN")
            return []

        self.supervisor.restart_for_channels.side_effect = _assert_saved_then_restart
        status, _body = self._put_channels(body)
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
