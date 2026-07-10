"""SSR /config/channels dual-knob form + POST proxy (Phase 75 Plan 05).

Proves GET HTML with dual-knob labels + ``Save channel config`` CTA and POST
that proxies ``handle_admin_put``. Lawyer/viewer denied via RBAC ``/config``.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
CSRF completeness is Phase 78 — do not claim it here.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

from admin_console_api.api import handle_admin_get as real_handle_admin_get
from admin_console_api.api import handle_admin_put as real_handle_admin_put
from admin_web_ui.api_client import AdminApiClient
from admin_web_ui.channels import (
    PRIMARY_CTA,
    RESTART_NOTICE,
    SUCCESS_FLASH,
    parse_channels_form,
    render_channels_page,
)
from admin_web_ui.server import handle_admin_web_ui_request
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Identity, Role, issue_token

_SERVER_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
)
_API_CLIENT_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "api_client.py"
)
_CHANNELS_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "channels.py"
)

_FAKE_CHANNELS_GET = {
    "data": {
        "qqbot": {
            "channel_id": "qqbot",
            "enabled": True,
            "app_id_ref": "env:QQBOT_APP_ID",
            "app_secret_ref": "secret://qqbot/app-secret",
            "token_secret_ref": None,
            "bot_secret_ref": None,
            "metadata": {},
        },
        "wecom": {
            "channel_id": "wecom",
            "enabled": False,
            "token_secret_ref": "env:WECOM_TOKEN",
            "encoding_aes_key_secret_ref": None,
            "corp_id_ref": None,
            "metadata": {},
        },
    },
    "effective": {
        "qqbot": {
            "platform_flag": True,
            "host_enabled": True,
            "effective_enabled": True,
            "refs_configured": {
                "app_id_ref": True,
                "app_secret_ref": True,
                "token_secret_ref": False,
                "bot_secret_ref": False,
            },
        },
        "wecom": {
            "platform_flag": False,
            "host_enabled": False,
            "effective_enabled": False,
            "refs_configured": {
                "token_secret_ref": True,
                "encoding_aes_key_secret_ref": False,
                "corp_id_ref": False,
            },
        },
    },
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
        "apply_semantics": "restart_required",
    },
}


def _make_fake_get(
    return_value: tuple[int, dict[str, Any]] = (200, _FAKE_CHANNELS_GET),
) -> Any:
    def handle_admin_get(
        path: str,
        query: str | Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        read_model: Any = None,
        feedback_queue: list[dict[str, Any]] | None = None,
        feature_flags: Any = None,
        env: Mapping[str, str] | None = None,
        rbac_secret: str | None = None,
        *,
        config_store: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        del query, headers, read_model, feedback_queue, feature_flags, env
        del rbac_secret, config_store
        if path == "/config/channels":
            return return_value
        return 200, {"items": [], "count": 0}

    return handle_admin_get


class ChannelsFormScaffoldTests(unittest.TestCase):
    """CHAN-01/02/03 UI: incremental channels SSR form (Plan 05)."""

    def test_channels_module_exists_with_render_helpers(self) -> None:
        if not _CHANNELS_SRC.is_file():
            self.fail(
                "CHAN-01/02: admin_web_ui/channels.py not implemented (Plan 05) — "
                "expected render + parse helpers for /config/channels SSR form"
            )
        try:
            from admin_web_ui import channels
        except ImportError as exc:
            self.fail(f"CHAN-01/02: admin_web_ui.channels import failed (Plan 05): {exc}")
        has_render = any(
            hasattr(channels, name)
            for name in (
                "render_channels_page",
                "render_channels_form",
                "render",
            )
        )
        if not has_render:
            self.fail(
                "CHAN-01/02: channels render helper missing (Plan 05) — "
                "UI-SPEC dual-knob Channel Config page"
            )

    def test_server_routes_config_channels_get_and_post(self) -> None:
        src = _SERVER_SRC.read_text(encoding="utf-8")
        if "/config/channels" not in src:
            self.fail(
                "CHAN-01/02: GET/POST /config/channels not wired in server.py (Plan 05)"
            )
        render_src = src
        if _CHANNELS_SRC.is_file():
            render_src = _CHANNELS_SRC.read_text(encoding="utf-8") + "\n" + src
        if "Save channel config" not in render_src:
            self.fail(
                "CHAN-03: channels HTML/CTA missing 'Save channel config' (Plan 05 UI-SPEC)"
            )
        for needle in ("platform", "host", "effective", "wecom_channel_enabled"):
            if needle not in render_src:
                self.fail(
                    f"CHAN-03: channels form missing dual-knob label {needle!r} "
                    "(Plan 05 UI-SPEC)"
                )

    def test_api_client_proxy_put_exists_for_post(self) -> None:
        try:
            from admin_web_ui.api_client import AdminApiClient as Client
        except ImportError:
            self.fail("AdminApiClient missing")
        if not hasattr(Client, "proxy_put"):
            api_src = _API_CLIENT_SRC.read_text(encoding="utf-8")
            if "proxy_put" not in api_src and "def proxy_put" not in api_src:
                self.fail(
                    "CHAN-01/02: AdminApiClient.proxy_put not implemented (Plan 05) — "
                    "POST /config/channels must proxy handle_admin_put"
                )
            self.fail(
                "CHAN-01/02: AdminApiClient.proxy_put not implemented (Plan 05) — "
                "POST /config/channels must proxy handle_admin_put"
            )

    def test_channels_form_does_not_claim_live_human_gate_closure(self) -> None:
        """CONTEXT locked: scaffolds must not auto-close carried human gates."""
        for path in (_CHANNELS_SRC, _SERVER_SRC):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("lawyer trial acceptance complete", text)
            self.assertNotIn("live wecom uat passed", text)


class ChannelsFormBehaviorTests(unittest.TestCase):
    """Behavioral proofs for dual-knob SSR + POST proxy."""

    SECRET = "test-channels-form-secret"

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
            qqbot_channel_enabled=True,
            wecom_channel_enabled=False,
        )
        self.handle_get = _make_fake_get()
        self.put_calls: list[dict[str, Any]] = []

        def handle_put(
            path: str,
            body: Any,
            headers: Mapping[str, str] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            *,
            config_store: Any = None,
            rbac_secret: str | None = None,
            read_model: Any = None,
            feedback_queue: list[dict[str, Any]] | None = None,
        ) -> tuple[int, dict[str, Any]]:
            del headers, feature_flags, env, config_store, rbac_secret
            del read_model, feedback_queue
            self.put_calls.append({"path": path, "body": body})
            out = dict(_FAKE_CHANNELS_GET)
            if isinstance(body, Mapping):
                out["data"] = {
                    "qqbot": dict(body.get("qqbot") or {}),
                    "wecom": dict(body.get("wecom") or {}),
                }
            return 200, out

        self.handle_put = handle_put

    def _auth(self, role: Role) -> dict[str, str]:
        token = issue_token(self.SECRET, role=role, tenant_id="tenant-1")
        return {"Authorization": f"Bearer {token}"}

    def test_get_renders_dual_knob_and_restart_notice(self) -> None:
        status, body, _headers = handle_admin_web_ui_request(
            "/config/channels",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Channel Config", body)
        self.assertIn(PRIMARY_CTA, body)
        self.assertIn("qqbot_channel_enabled", body)
        self.assertIn("wecom_channel_enabled", body)
        self.assertIn("Host enabled", body)
        self.assertIn("platform", body.lower())
        self.assertIn("Effective:", body)
        self.assertIn(RESTART_NOTICE.split(";")[0], body)
        self.assertIn('autocomplete="off"', body)
        self.assertIn('type="text"', body)
        self.assertNotIn("force_enable", body)
        self.assertNotIn("Enable live IO bypass", body)
        self.assertNotIn("channel_delivery_enabled", body)

    def test_post_proxies_put_and_shows_restart_flash(self) -> None:
        form = urlencode(
            {
                "csrf_token": "test-csrf",
                "qqbot.enabled": "1",
                "qqbot.app_id_ref": "env:QQBOT_APP_ID",
                "qqbot.app_secret_ref": "secret://qqbot/app-secret",
                "wecom.token_secret_ref": "env:WECOM_TOKEN",
            }
        )
        status, body, _headers = handle_admin_web_ui_request(
            "/config/channels",
            self._auth(Role.OPERATOR),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(self.put_calls), 1)
        self.assertEqual(self.put_calls[0]["path"], "/config/channels")
        put_body = self.put_calls[0]["body"]
        self.assertTrue(put_body["qqbot"]["enabled"])
        self.assertFalse(put_body["wecom"]["enabled"])
        self.assertEqual(put_body["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")
        self.assertIn(SUCCESS_FLASH, body)

    def test_lawyer_and_viewer_denied_on_channels(self) -> None:
        for role in (Role.LAWYER, Role.VIEWER):
            status, body, _headers = handle_admin_web_ui_request(
                "/config/channels",
                self._auth(role),
                feature_flags=self.flags,
                handle_admin_get=self.handle_get,
                read_model=None,
                rbac_secret=self.SECRET,
                method="GET",
                handle_admin_put=self.handle_put,
            )
            self.assertEqual(status, 403, msg=f"role={role}")
            self.assertIn("permission", body.lower())

    def test_post_on_sessions_remains_method_not_allowed(self) -> None:
        status, _body, _headers = handle_admin_web_ui_request(
            "/sessions",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=b"",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 405)

    def test_empty_post_does_not_wipe_channel_config(self) -> None:
        """CR-01: empty/marker-less POST must not proxy a wipe PUT."""
        status, body, _headers = handle_admin_web_ui_request(
            "/config/channels",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=b"",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.put_calls, [])
        self.assertIn("Invalid secret reference", body)

        status2, _body2, _ = handle_admin_web_ui_request(
            "/config/channels",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=b"csrf_token=only",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status2, 400)
        self.assertEqual(self.put_calls, [])

    def test_post_preserves_existing_channel_metadata(self) -> None:
        """WR-01: SSR Save must not clear API-set channel metadata."""
        seeded = {
            "data": {
                "qqbot": {
                    **_FAKE_CHANNELS_GET["data"]["qqbot"],
                    "metadata": {"source": "api-seed", "note": "keep-me"},
                },
                "wecom": {
                    **_FAKE_CHANNELS_GET["data"]["wecom"],
                    "metadata": {"tier": "ops"},
                },
            },
            "effective": _FAKE_CHANNELS_GET["effective"],
            "metadata": _FAKE_CHANNELS_GET["metadata"],
        }
        self.handle_get = _make_fake_get((200, seeded))
        form = urlencode(
            {
                "csrf_token": "test-csrf",
                "qqbot.enabled": "1",
                "qqbot.app_id_ref": "env:QQBOT_APP_ID",
                "wecom.token_secret_ref": "env:WECOM_TOKEN",
            }
        )
        status, _body, _ = handle_admin_web_ui_request(
            "/config/channels",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(self.put_calls), 1)
        put_body = self.put_calls[0]["body"]
        self.assertEqual(
            put_body["qqbot"]["metadata"],
            {"source": "api-seed", "note": "keep-me"},
        )
        self.assertEqual(put_body["wecom"]["metadata"], {"tier": "ops"})

    def test_max_channels_post_bytes_constant(self) -> None:
        """WR-04: POST body size cap is exported for the HTTP handler."""
        from admin_web_ui.server import MAX_CHANNELS_POST_BYTES

        self.assertGreaterEqual(MAX_CHANNELS_POST_BYTES, 1024)
        self.assertLessEqual(MAX_CHANNELS_POST_BYTES, 1024 * 1024)

    def test_html_escape_on_ref_values(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="t1")
        data = {
            "data": {
                "qqbot": {
                    "channel_id": "qqbot",
                    "enabled": False,
                    "app_id_ref": '<script>alert("x")</script>',
                    "app_secret_ref": None,
                    "token_secret_ref": None,
                    "bot_secret_ref": None,
                    "metadata": {},
                },
                "wecom": {
                    "channel_id": "wecom",
                    "enabled": False,
                    "token_secret_ref": None,
                    "encoding_aes_key_secret_ref": None,
                    "corp_id_ref": None,
                    "metadata": {},
                },
            },
            "effective": {
                "qqbot": {
                    "platform_flag": False,
                    "host_enabled": False,
                    "effective_enabled": False,
                    "refs_configured": {"app_id_ref": True},
                },
                "wecom": {
                    "platform_flag": False,
                    "host_enabled": False,
                    "effective_enabled": False,
                    "refs_configured": {},
                },
            },
            "metadata": {"operator_config_enabled": True},
        }
        html = render_channels_page(data, identity=identity)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_parse_channels_form_builds_section_body(self) -> None:
        parsed = parse_channels_form(
            {
                "qqbot.enabled": ["1"],
                "qqbot.app_id_ref": ["env:FOO"],
                "qqbot.app_secret_ref": [""],
                "wecom.enabled": [],
                "wecom.token_secret_ref": ["env:TOKEN"],
            }
        )
        self.assertEqual(parsed["qqbot"]["channel_id"], "qqbot")
        self.assertTrue(parsed["qqbot"]["enabled"])
        self.assertEqual(parsed["qqbot"]["app_id_ref"], "env:FOO")
        self.assertIsNone(parsed["qqbot"]["app_secret_ref"])
        self.assertFalse(parsed["wecom"]["enabled"])
        self.assertEqual(parsed["wecom"]["token_secret_ref"], "env:TOKEN")

    def test_proxy_put_injects_authorization(self) -> None:
        captured: dict[str, Any] = {}

        def handle_put(
            path: str,
            body: Any,
            headers: Mapping[str, str] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            *,
            config_store: Any = None,
            rbac_secret: str | None = None,
        ) -> tuple[int, dict[str, Any]]:
            captured["headers"] = dict(headers or {})
            captured["path"] = path
            captured["body"] = body
            return 200, {"ok": True}

        client = AdminApiClient()
        identity = Identity(role=Role.ADMIN, tenant_id="t1")
        status, data = client.proxy_put(
            handle_put,
            "/config/channels",
            {"qqbot": {}, "wecom": {}},
            identity,
            feature_flags=self.flags,
            auth_header="Bearer abc.def",
        )
        self.assertEqual(status, 200)
        self.assertEqual(captured["headers"].get("Authorization"), "Bearer abc.def")
        self.assertTrue(data.get("ok"))

    def test_integration_temp_store_round_trip(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = OperatorConfigStore(Path(tmp.name) / "operator-config.json")
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=False,
            qqbot_channel_enabled=True,
            wecom_channel_enabled=True,
        )
        env = {"ADMIN_API_TOKEN": "static-admin-token"}
        headers = {"Authorization": "Bearer static-admin-token"}
        form = urlencode(
            {
                "qqbot.enabled": "1",
                "qqbot.app_id_ref": "env:QQ_APP_ID",
                "qqbot.app_secret_ref": "env:QQ_APP_SECRET",
                "wecom.enabled": "1",
                "wecom.token_secret_ref": "env:WECOM_TOKEN",
                "wecom.encoding_aes_key_secret_ref": "env:WECOM_AES",
                "wecom.corp_id_ref": "env:WECOM_CORP",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/channels",
            headers,
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            handle_admin_put=real_handle_admin_put,
            read_model=None,
            env=env,
            method="POST",
            body=form.encode("utf-8"),
            config_store=store,
        )
        self.assertEqual(status, 200)
        self.assertIn(SUCCESS_FLASH, body)
        get_status, get_body, _ = handle_admin_web_ui_request(
            "/config/channels",
            headers,
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            handle_admin_put=real_handle_admin_put,
            read_model=None,
            env=env,
            method="GET",
            config_store=store,
        )
        self.assertEqual(get_status, 200)
        self.assertIn("env:QQ_APP_ID", get_body)
        self.assertIn("wecom_channel_enabled", get_body)
        self.assertIn("Effective: enabled", get_body)


if __name__ == "__main__":
    unittest.main()
