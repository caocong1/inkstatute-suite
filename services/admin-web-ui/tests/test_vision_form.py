"""VIS-01 UI RED contracts for /config/vision SSR (Plan 77-04).

Wave 3 scaffold: vision routing-mode selector, vision provider/model selectors,
vision probe, and route-bound CSRF. The page renders API metadata-driven
provider IDs and built-in catalog models, enforces refs-only / no-secret
boundaries, and posts to the dedicated /config/vision save route and
/config/providers/probe probe route.

No live provider, WeCom, QQ, or lawyer-trial acceptance is claimed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

from admin_web_ui.server import handle_admin_web_ui_request
from admin_web_ui.vision import (
    BLANK_OPTION,
    CUSTOM_PROVIDER_NOTE,
    ERROR_FLAG_OFF,
    ERROR_FORBIDDEN,
    ERROR_GENERIC,
    ERROR_VALIDATION,
    NO_PROVIDERS_NOTE,
    PAGE_TITLE,
    PRIMARY_CTA,
    PROBE_BUTTON_LABEL,
    RESTART_NOTICE,
    ROUTING_MODE_OPTION_ALWAYS,
    ROUTING_MODE_OPTION_AUTO,
    ROUTING_MODE_OPTION_MAIN_ONLY,
    SUCCESS_FLASH,
    VISION_STATUS_NOT_CONFIGURED,
    VISION_STATUS_NOT_REQUIRED,
    parse_vision_form,
    render_vision_page,
)
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Identity, Role, issue_token


_VISION_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "vision.py"
)
_SERVER_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
)

_FAKE_CATALOG = {
    "data": {"provider_id": "primary-openai", "model_id": "gpt-5"},
    "catalog_entries": [
        {
            "vendor_id": "openai",
            "model_id": "gpt-5",
            "supports_vision": True,
            "description": "OpenAI multimodal main model",
        },
        {
            "vendor_id": "anthropic",
            "model_id": "claude-opus-4-8",
            "supports_vision": True,
            "description": "Anthropic multimodal model",
        },
    ],
    "providers": [
        {
            "provider_id": "primary-openai",
            "kind": "openai",
            "enabled": True,
            "api_base_url": "https://api.openai.com/v1",
            "api_key_ref": "env:OPENAI_API_KEY",
            "model_allowlist": [],
            "metadata": {},
        },
        {
            "provider_id": "primary-anthropic",
            "kind": "anthropic",
            "enabled": False,
            "api_base_url": "https://api.anthropic.com/v1",
            "api_key_ref": "env:ANTHROPIC_API_KEY",
            "model_allowlist": [],
            "metadata": {},
        },
        {
            "provider_id": "custom-endpoint",
            "kind": "custom",
            "enabled": False,
            "api_base_url": "https://custom.example.com/v1",
            "api_key_ref": "env:CUSTOM_API_KEY",
            "model_allowlist": ["local-vision"],
            "metadata": {},
        },
    ],
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
        "apply_semantics": "restart_required",
    },
}

_FAKE_VISION_AUTO = {
    "data": {
        "routing_mode": "auto",
        "main_model_id": "gpt-5",
        "vision_model_id": "claude-opus-4-8",
        "vision_provider_id": "primary-anthropic",
    },
    "providers": _FAKE_CATALOG["providers"],
    "catalog_entries": _FAKE_CATALOG["catalog_entries"],
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
        "apply_semantics": "restart_required",
        "routing_modes": ["auto", "always_preprocess", "main_only"],
        "vision_configured": True,
        "vision_status": "configured",
    },
}

_FAKE_VISION_MAIN_ONLY = {
    "data": {
        "routing_mode": "main_only",
        "main_model_id": "gpt-5",
        "vision_model_id": None,
        "vision_provider_id": None,
    },
    "providers": _FAKE_CATALOG["providers"],
    "catalog_entries": _FAKE_CATALOG["catalog_entries"],
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
        "apply_semantics": "restart_required",
        "routing_modes": ["auto", "always_preprocess", "main_only"],
        "vision_configured": False,
        "vision_status": "not_configured",
    },
}

_FAKE_VISION_UNSET = {
    "data": {
        "routing_mode": None,
        "main_model_id": "gpt-5",
        "vision_model_id": None,
        "vision_provider_id": None,
    },
    "providers": _FAKE_CATALOG["providers"],
    "catalog_entries": _FAKE_CATALOG["catalog_entries"],
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
        "apply_semantics": "restart_required",
        "routing_modes": ["auto", "always_preprocess", "main_only"],
        "vision_configured": False,
        "vision_status": "not_configured",
    },
}


def _make_fake_get() -> Any:
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
        if path == "/config/vision":
            return 200, _FAKE_VISION_AUTO
        if path == "/config/catalog":
            return 200, _FAKE_CATALOG
        if path == "/config/providers":
            return 200, _FAKE_CATALOG  # providers list is in catalog fixture
        return 200, {"items": [], "count": 0}

    return handle_admin_get


def _make_fake_get_main_only() -> Any:
    get = _make_fake_get()

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
        if path == "/config/vision":
            return 200, _FAKE_VISION_MAIN_ONLY
        return get(
            path,
            query,
            headers,
            read_model,
            feedback_queue,
            feature_flags,
            env,
            rbac_secret,
            config_store=config_store,
        )

    return handle_admin_get


def _make_fake_get_unset() -> Any:
    get = _make_fake_get()

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
        if path == "/config/vision":
            return 200, _FAKE_VISION_UNSET
        return get(
            path,
            query,
            headers,
            read_model,
            feedback_queue,
            feature_flags,
            env,
            rbac_secret,
            config_store=config_store,
        )

    return handle_admin_get


class VisionRenderTests(unittest.TestCase):
    """Direct SSR render/parse contracts."""

    def test_vision_module_exists_with_render_helpers(self) -> None:
        if not _VISION_SRC.is_file():
            self.fail(
                "VIS-01: admin_web_ui/vision.py not implemented (Plan 77-04)"
            )
        self.assertTrue(callable(render_vision_page))
        self.assertTrue(callable(parse_vision_form))

    def test_render_defaults_to_auto_when_routing_mode_unset(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_UNSET,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn("Vision Config", body)
        self.assertIn(ROUTING_MODE_OPTION_AUTO, body)
        self.assertIn("selected", body.lower())
        self.assertIn(VISION_STATUS_NOT_CONFIGURED, body)
        self.assertIn(PRIMARY_CTA, body)
        self.assertIn(PROBE_BUTTON_LABEL, body)

    def test_render_main_only_disables_vision_controls(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_MAIN_ONLY,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn(ROUTING_MODE_OPTION_MAIN_ONLY, body)
        self.assertIn(VISION_STATUS_NOT_REQUIRED, body)
        self.assertIn("disabled", body.lower())
        # Probe button disabled
        probe_match = re.search(
            r'<button[^>]*type="submit"[^>]*>.*Probe vision connection.*</button>',
            body,
        )
        self.assertIsNotNone(probe_match)
        self.assertIn("disabled", probe_match.group(0).lower())

    def test_render_auto_with_complete_vision_pair(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn("primary-anthropic", body)
        self.assertIn("claude-opus-4-8", body)
        self.assertIn(PROBE_BUTTON_LABEL, body)
        # Probe button not disabled
        probe_match = re.search(
            r'<button[^>]*type="submit"[^>]*>.*Probe vision connection.*</button>',
            body,
        )
        self.assertIsNotNone(probe_match)
        self.assertNotIn("disabled", probe_match.group(0).lower())

    def test_routing_mode_options_in_fixed_order(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_UNSET,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        auto_pos = body.find(ROUTING_MODE_OPTION_AUTO)
        always_pos = body.find(ROUTING_MODE_OPTION_ALWAYS)
        main_pos = body.find(ROUTING_MODE_OPTION_MAIN_ONLY)
        self.assertGreater(auto_pos, -1)
        self.assertGreater(always_pos, -1)
        self.assertGreater(main_pos, -1)
        self.assertLess(auto_pos, always_pos)
        self.assertLess(always_pos, main_pos)

    def test_provider_select_shows_registry_ids_not_vendor_ids(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_UNSET,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn("primary-openai", body)
        self.assertIn("primary-anthropic", body)
        self.assertIn("custom-endpoint", body)
        # Built-in vendor IDs should not be selectable options.
        # They may appear as escaped text, but not as option values/text.
        option_values = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>', body)
        self.assertIn("primary-openai", option_values)
        self.assertNotIn("openai", option_values)
        self.assertNotIn("anthropic", option_values)

    def test_model_select_filters_by_provider_kind(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        # The selected provider is anthropic, so anthropic model should appear.
        self.assertIn("claude-opus-4-8", body)

    def test_custom_provider_shows_only_blank_with_note(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        api_data = {
            "data": {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_model_id": None,
                "vision_provider_id": "custom-endpoint",
            },
            "providers": _FAKE_CATALOG["providers"],
            "catalog_entries": _FAKE_CATALOG["catalog_entries"],
            "metadata": _FAKE_VISION_AUTO["metadata"],
        }
        body = render_vision_page(
            api_data,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn(CUSTOM_PROVIDER_NOTE, body)
        self.assertIn(BLANK_OPTION, body)

    def test_no_providers_shows_blank_and_note(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        api_data = {
            "data": {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_model_id": None,
                "vision_provider_id": None,
            },
            "metadata": _FAKE_VISION_AUTO["metadata"],
        }
        body = render_vision_page(
            api_data,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertIn(NO_PROVIDERS_NOTE, body)

    def test_main_model_id_is_hidden_input(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertRegex(body, r'<input[^>]*type="hidden"[^>]*name="main_model_id"[^>]*>')

    def test_parse_vision_form_normalizes_empty_to_none(self) -> None:
        form = {
            "routing_mode": "auto",
            "vision_provider_id": "",
            "vision_model_id": "",
            "main_model_id": "gpt-5",
        }
        parsed = parse_vision_form(form)
        self.assertEqual(parsed["routing_mode"], "auto")
        self.assertIsNone(parsed["vision_provider_id"])
        self.assertIsNone(parsed["vision_model_id"])
        self.assertEqual(parsed["main_model_id"], "gpt-5")

    def test_no_secrets_paths_or_raw_bytes_in_html(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        lower = body.lower()
        self.assertNotIn("api_key_ref", lower)
        self.assertNotIn("api_base_url", lower)
        self.assertNotIn("secret://", lower)
        self.assertNotIn("/home/", lower)
        self.assertNotIn(".inkstatute", lower)
        self.assertNotIn("image/png", lower)
        self.assertNotIn("raw image", lower)

    def test_html_escape_on_dynamic_values(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        poisoned = dict(_FAKE_VISION_AUTO)
        poisoned["data"] = {
            "routing_mode": "auto",
            "main_model_id": "gpt-5",
            "vision_model_id": '"><script>alert("m")</script>',
            "vision_provider_id": '<script>alert("p")</script>',
        }
        body = render_vision_page(
            poisoned,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        self.assertNotIn('<script>alert("p")</script>', body)
        self.assertNotIn('<script>alert("m")</script>', body)
        self.assertIn("&lt;script&gt;", body)

    def test_save_and_probe_forms_are_siblings_not_nested(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        forms = re.findall(r'<form[^>]*>|</form>', body)
        depth = 0
        max_depth = 0
        for tag in forms:
            if not tag.startswith("</"):
                depth += 1
                max_depth = max(max_depth, depth)
            else:
                depth -= 1
        self.assertEqual(max_depth, 1, "Nested <form> elements detected")

    def test_save_form_posts_to_vision_and_probe_to_probe(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
        )
        save_form = re.search(r'<form[^>]*action="/config/vision"[^>]*>', body)
        probe_form = re.search(
            r'<form[^>]*action="/config/providers/probe"[^>]*>', body
        )
        self.assertIsNotNone(save_form)
        self.assertIsNotNone(probe_form)
        self.assertIn('name="target"', body)
        self.assertIn('value="vision"', body)
        self.assertIn('name="return_to"', body)

    def test_read_only_disables_all_controls(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
            read_only=True,
        )
        selects = re.findall(r'<select[^>]*>', body)
        for sel in selects:
            self.assertIn("disabled", sel, sel)
        buttons = re.findall(r'<button[^>]*>', body)
        for btn in buttons:
            self.assertIn("disabled", btn, btn)

    def test_render_respects_error_and_flash(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        body = render_vision_page(
            _FAKE_VISION_AUTO,
            identity=identity,
            csrf_token="vision-token",
            probe_csrf_token="probe-token",
            error_message=ERROR_VALIDATION,
            flash=SUCCESS_FLASH,
        )
        self.assertIn(ERROR_VALIDATION, body)
        self.assertIn(SUCCESS_FLASH, body)

    def test_vision_form_does_not_claim_live_human_gate_closure(self) -> None:
        for path in (_VISION_SRC, _SERVER_SRC):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("lawyer trial acceptance complete", text)
            self.assertNotIn("live wecom uat passed", text)


class VisionRouteTests(unittest.TestCase):
    """Route + CSRF contracts through handle_admin_web_ui_request."""

    SECRET = "test-vision-form-secret"

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        self.handle_get = _make_fake_get()
        self.put_calls: list[dict[str, Any]] = []
        self.probe_calls: list[dict[str, Any]] = []

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
            return 200, _FAKE_VISION_AUTO

        self.handle_put = handle_put

        def handle_probe(
            path: str,
            body: Any,
            headers: Mapping[str, str] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            *,
            config_store: Any = None,
            rbac_secret: str | None = None,
            resolver: Any = None,
            opener: Any = None,
        ) -> tuple[int, dict[str, Any]]:
            del headers, feature_flags, env, config_store, rbac_secret
            del resolver, opener
            self.probe_calls.append({"path": path, "body": body})
            return 200, {"data": {"target": body.get("target"), "status": "ok"}}

        self.handle_probe = handle_probe

    def _auth(self, role: Role) -> dict[str, str]:
        token = issue_token(self.SECRET, role=role, tenant_id="tenant-1")
        return {"Authorization": f"Bearer {token}"}

    def _valid_csrf_token(self, identity: Identity, route: str) -> str:
        from admin_web_ui import csrf

        return csrf.issue_csrf_token(
            identity=identity, route=route, signing_key=self.SECRET
        )

    def test_get_vision_renders_page_and_csrf_tokens(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Vision Config", body)
        self.assertIn("Save vision config", body)
        self.assertIn("Probe vision connection", body)

    def test_get_vision_main_only_disables_vision_controls(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get_main_only(),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Vision model not required (main only)", body)

    def test_post_with_valid_csrf_proxies_put(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/vision")
        form = urlencode(
            {
                "csrf_token": token,
                "routing_mode": "auto",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
                "main_model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
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
        self.assertEqual(self.put_calls[0]["path"], "/config/vision")
        self.assertEqual(self.put_calls[0]["body"]["routing_mode"], "auto")
        self.assertIn("Vision config saved", body)

    def test_post_with_missing_csrf_returns_403_before_proxy(self) -> None:
        form = urlencode(
            {
                "routing_mode": "auto",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
                "main_model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.put_calls, [])

    def test_post_with_mismatched_route_csrf_returns_403(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers/probe")
        form = urlencode(
            {
                "csrf_token": token,
                "routing_mode": "auto",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
                "main_model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.put_calls, [])

    def test_post_with_different_identity_csrf_returns_403(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-2")
        token = self._valid_csrf_token(identity, "/config/vision")
        form = urlencode(
            {
                "csrf_token": token,
                "routing_mode": "auto",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
                "main_model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.put_calls, [])

    def test_lawyer_and_viewer_denied_on_vision(self) -> None:
        for role in (Role.LAWYER, Role.VIEWER):
            status, body, _ = handle_admin_web_ui_request(
                "/config/vision",
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

    def test_flag_off_renders_read_only_with_error(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=False,
            rbac_enabled=True,
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn(ERROR_FLAG_OFF, body)
        self.assertIn("disabled", body.lower())

    def test_vision_probe_posts_to_probe_route_with_return_to_vision(self) -> None:
        identity = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers/probe")
        form = urlencode(
            {"csrf_token": token, "target": "vision", "return_to": "vision"}
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers/probe",
            self._auth(Role.OPERATOR),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="POST",
            body=form.encode("utf-8"),
            handle_admin_put=self.handle_put,
            handle_config_probe=self.handle_probe,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(self.probe_calls), 1)
        self.assertEqual(self.probe_calls[0]["body"]["target"], "vision")
        self.assertIn("Vision Config", body)

    def test_nav_contains_vision_config_link(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/vision",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn('Vision Config</a>', body)
        self.assertIn('href="/config/vision"', body)
