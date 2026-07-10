"""Wave 0 / Plan 01→05: SSR /config/channels dual-knob form + POST proxy.

Plan 01 scaffolds RED coverage. Plan 05 greens GET HTML with dual-knob labels
+ ``Save channel config`` CTA and POST that proxies ``handle_admin_put``.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
CSRF completeness is Phase 78 — do not claim it here.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_SERVER_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
)
_API_CLIENT_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "api_client.py"
)
_CHANNELS_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "channels.py"
)


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
        # Dual-knob CTA copy must appear in render path (channels module or server).
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
            from admin_web_ui.api_client import AdminApiClient
        except ImportError:
            self.fail("AdminApiClient missing")
        if not hasattr(AdminApiClient, "proxy_put"):
            # Also accept source-level presence before class attribute lands.
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


if __name__ == "__main__":
    unittest.main()
