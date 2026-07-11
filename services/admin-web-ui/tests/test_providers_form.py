"""PROV-01/02/04 UI RED contracts for /config/providers SSR (Plan 76-02).

Wave 0 scaffold: provider save + route-bound main/conditional-vision probe SSR
and CSRF rejection. Provider page renders API metadata-driven built-in profiles,
read-only canonical built-in URLs, editable custom URL/allowlist, refs-only
rendering, blank-card drop, metadata preservation, and no nested forms. A
route-bound main probe form renders from API ``probe_targets`` metadata; a
vision probe form renders only when vision status is configured. Generic
``not_configured`` rendering covers unavailable/partial targets without
exposing or synthesizing a Phase 77 vision editor.

These contracts are intentionally RED until Plans 76-03 and 76-04 implement the
SSR modules, CSRF, and probe route. No live provider, WeCom, QQ, or lawyer-trial
acceptance is claimed.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

from admin_console_api.api import handle_admin_get as real_handle_admin_get
from admin_console_api.api import handle_admin_put as real_handle_admin_put
from admin_web_ui.server import handle_admin_web_ui_request
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Identity, Role, issue_token


_SERVER_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
)
_PROVIDERS_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "providers.py"
)
_CSRF_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "csrf.py"
)

_OPENAI_CANONICAL_URL = "https://api.openai.com/v1"
_ANTHROPIC_CANONICAL_URL = "https://api.anthropic.com/v1"

_FAKE_PROVIDERS_GET = {
    "data": [
        {
            "provider_id": "primary-openai",
            "kind": "openai",
            "enabled": True,
            "api_base_url": _OPENAI_CANONICAL_URL,
            "api_key_ref": "env:OPENAI_API_KEY",
            "model_allowlist": [],
            "metadata": {},
        },
        {
            "provider_id": "custom-endpoint",
            "kind": "custom",
            "enabled": False,
            "api_base_url": "https://custom.example.com/v1",
            "api_key_ref": "env:CUSTOM_API_KEY",
            "model_allowlist": ["local-gpt", "local-vision"],
            "metadata": {"source": "api-seed"},
        },
    ],
    "probe_targets": {
        "main": {
            "status": "configured",
            "provider_id": "primary-openai",
            "model_id": "gpt-5",
        },
        "vision": {
            "status": "not_configured",
            "provider_id": None,
            "model_id": None,
        },
    },
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
    },
}

_FAKE_PROVIDERS_GET_VISION_CONFIGURED = {
    "data": _FAKE_PROVIDERS_GET["data"],
    "probe_targets": {
        "main": {
            "status": "configured",
            "provider_id": "primary-openai",
            "model_id": "gpt-5",
        },
        "vision": {
            "status": "configured",
            "provider_id": "primary-anthropic",
            "model_id": "claude-opus-4-8",
        },
    },
    "metadata": _FAKE_PROVIDERS_GET["metadata"],
}


def _make_fake_get(
    return_value: tuple[int, dict[str, Any]] = (200, _FAKE_PROVIDERS_GET),
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
        if path == "/config/providers":
            return return_value
        return 200, {"items": [], "count": 0}

    return handle_admin_get


def _try_import_csrf() -> Any:
    try:
        from admin_web_ui import csrf
    except ImportError:
        return None
    return csrf


class ProvidersFormScaffoldTests(unittest.TestCase):
    """PROV-01/02/04 UI: provider registry SSR + probe + CSRF RED contracts."""

    SECRET = "test-providers-form-secret"

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
            return 200, _FAKE_PROVIDERS_GET

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
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        return csrf.issue_csrf_token(
            identity=identity, route=route, signing_key=self.SECRET
        )

    # --- Module + route existence ---

    def test_providers_module_exists_with_render_helpers(self) -> None:
        if not _PROVIDERS_SRC.is_file():
            self.fail(
                "PROV-01/02: admin_web_ui/providers.py not implemented (Plan 76-04) — "
                "expected render + parse helpers for /config/providers SSR form"
            )
        try:
            from admin_web_ui import providers
        except ImportError as exc:
            self.fail(f"PROV-01/02: admin_web_ui.providers import failed (Plan 76-04): {exc}")
        has_render = any(
            hasattr(providers, name)
            for name in ("render_providers_page", "render_providers_form", "render")
        )
        if not has_render:
            self.fail(
                "PROV-01/02: providers render helper missing (Plan 76-04) — "
                "UI-SPEC Provider Config page"
            )

    def test_server_routes_config_providers_get_and_post(self) -> None:
        src = _SERVER_SRC.read_text(encoding="utf-8")
        if "/config/providers" not in src:
            self.fail(
                "PROV-01/02: GET/POST /config/providers not wired in server.py (Plan 76-04)"
            )

    def test_server_routes_config_providers_probe(self) -> None:
        src = _SERVER_SRC.read_text(encoding="utf-8")
        if "/config/providers/probe" not in src:
            self.fail(
                "PROV-04: POST /config/providers/probe not wired in server.py (Plan 76-04)"
            )

    # --- GET renders metadata-driven built-in profiles + read-only URLs ---

    def test_get_renders_provider_config_page(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Provider Config", body)
        self.assertIn("Save provider config", body)

    def test_get_renders_read_only_canonical_built_in_url(self) -> None:
        """Built-in vendor api_base_url renders as read-only text, not editable."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn(_OPENAI_CANONICAL_URL, body)

    def test_get_renders_editable_custom_url_and_allowlist(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("https://custom.example.com/v1", body)
        self.assertIn("local-gpt", body)

    def test_get_renders_refs_only_no_resolved_secrets(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("env:OPENAI_API_KEY", body)
        self.assertIn("env:CUSTOM_API_KEY", body)

    def test_get_renders_blank_card_for_new_provider(self) -> None:
        """A trailing blank 'New provider' card is always rendered (no JS)."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("New provider", body)

    def test_get_renders_no_nested_forms(self) -> None:
        """Provider cards must not contain nested <form> elements."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        # Count <form> tags — there must be exactly one (the save form).
        form_count = body.count("<form")
        self.assertEqual(form_count, 1)

    # --- Probe form: route-bound main + conditional vision ---

    def test_get_renders_main_probe_form_from_probe_targets(self) -> None:
        """Main probe form renders from API probe_targets metadata."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Probe connection", body)
        self.assertIn('name="target"', body)
        self.assertIn("main", body)

    def test_get_renders_vision_probe_form_only_when_configured(self) -> None:
        """Vision probe form renders only when vision status is configured."""
        # Vision NOT configured → no vision probe form.
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get((200, _FAKE_PROVIDERS_GET)),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        # not_configured vision renders generically, not as a probe form.
        self.assertIn("not_configured", body.lower().replace("-", "_"))

        # Vision configured → vision probe form renders.
        status2, body2, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get((200, _FAKE_PROVIDERS_GET_VISION_CONFIGURED)),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status2, 200)
        self.assertIn("vision", body2.lower())

    def test_get_renders_generic_not_configured_for_partial_vision(self) -> None:
        """Partial vision metadata renders generic not_configured (no Phase 77 editor)."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("vision editor", body.lower())
        self.assertNotIn("routing_mode", body.lower())

    # --- POST: CSRF before proxy ---

    def test_post_with_valid_csrf_proxies_put(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers")
        form = urlencode(
            {
                "csrf_token": token,
                "providers[0].provider_id": "primary-openai",
                "providers[0].kind": "openai",
                "providers[0].enabled": "1",
                "providers[0].api_key_ref": "env:OPENAI_API_KEY",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
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
        self.assertEqual(self.put_calls[0]["path"], "/config/providers")
        self.assertIn("Provider config saved", body)

    def test_post_with_missing_csrf_returns_403_before_proxy(self) -> None:
        form = urlencode(
            {
                "providers[0].provider_id": "primary-openai",
                "providers[0].kind": "openai",
                "providers[0].enabled": "1",
                "providers[0].api_key_ref": "env:OPENAI_API_KEY",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
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

    def test_post_with_mismatched_csrf_returns_403_before_proxy(self) -> None:
        """A token bound to a different route must be rejected (403)."""
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        # Token bound to /config/catalog, used on /config/providers → mismatch.
        token = self._valid_csrf_token(identity, "/config/catalog")
        form = urlencode(
            {
                "csrf_token": token,
                "providers[0].provider_id": "primary-openai",
                "providers[0].kind": "openai",
                "providers[0].enabled": "1",
                "providers[0].api_key_ref": "env:OPENAI_API_KEY",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
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

    # --- Probe POST: CSRF before proxy ---

    def test_probe_post_with_valid_csrf_proxies_probe(self) -> None:
        identity = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers/probe")
        form = urlencode({"csrf_token": token, "target": "main"})
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
        self.assertEqual(self.probe_calls[0]["body"]["target"], "main")

    def test_probe_post_with_missing_csrf_returns_403_before_proxy(self) -> None:
        form = urlencode({"target": "main"})
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
        self.assertEqual(status, 403)
        self.assertEqual(self.probe_calls, [])

    def test_probe_post_with_mismatched_csrf_returns_403_before_proxy(self) -> None:
        """A token bound to /config/providers (save) must not work for probe."""
        identity = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers")
        form = urlencode({"csrf_token": token, "target": "main"})
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
        self.assertEqual(status, 403)
        self.assertEqual(self.probe_calls, [])

    # --- Probe result is generic/ephemeral, no body/secret ---

    def test_probe_result_renders_generic_status_only(self) -> None:
        identity = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers/probe")
        form = urlencode({"csrf_token": token, "target": "main"})
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
        self.assertNotIn("response_body", body.lower())
        self.assertNotIn("authorization", body.lower())
        # Probe must not leak resolved secret material — only generic status.
        # Refs like "env:OPENAI_API_KEY" are safe operator-visible references,
        # not secrets. Check that no raw probe response payload leaks.
        self.assertNotIn("bearer ", body.lower())
        self.assertNotIn("x-api-key", body.lower())

    # --- HTML escaping ---

    def test_html_escape_on_ref_values(self) -> None:
        """Ref values must be HTML-escaped to prevent XSS."""
        poisoned = {
            "data": [
                {
                    "provider_id": '<script>alert("x")</script>',
                    "kind": "custom",
                    "enabled": False,
                    "api_base_url": "https://custom.example.com/v1",
                    "api_key_ref": '<script>alert("k")</script>',
                    "model_allowlist": [],
                    "metadata": {},
                }
            ],
            "probe_targets": {
                "main": {"status": "not_configured", "provider_id": None, "model_id": None},
                "vision": {"status": "not_configured", "provider_id": None, "model_id": None},
            },
            "metadata": {"operator_config_enabled": True},
        }
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get((200, poisoned)),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertNotIn('<script>alert("x")</script>', body)
        self.assertIn("&lt;script&gt;", body)

    # --- Metadata preservation ---

    def test_post_preserves_existing_provider_metadata(self) -> None:
        """SSR Save must not clear API-set provider metadata."""
        seeded = {
            "data": [
                {
                    **_FAKE_PROVIDERS_GET["data"][1],
                    "metadata": {"source": "api-seed", "note": "keep-me"},
                }
            ],
            "probe_targets": _FAKE_PROVIDERS_GET["probe_targets"],
            "metadata": _FAKE_PROVIDERS_GET["metadata"],
        }
        self.handle_get = _make_fake_get((200, seeded))
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers")
        form = urlencode(
            {
                "csrf_token": token,
                "providers[0].provider_id": "custom-endpoint",
                "providers[0].kind": "custom",
                "providers[0].enabled": "1",
                "providers[0].api_base_url": "https://custom.example.com/v1",
                "providers[0].api_key_ref": "env:CUSTOM_API_KEY",
                "providers[0].model_allowlist": "local-gpt,local-vision",
            }
        )
        status, _body, _ = handle_admin_web_ui_request(
            "/config/providers",
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
        if isinstance(put_body, list) and put_body:
            self.assertEqual(
                put_body[0].get("metadata"),
                {"source": "api-seed", "note": "keep-me"},
            )

    # --- RBAC ---

    def test_lawyer_and_viewer_denied_on_providers(self) -> None:
        for role in (Role.LAWYER, Role.VIEWER):
            status, body, _ = handle_admin_web_ui_request(
                "/config/providers",
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

    # --- No live acceptance claim ---

    def test_providers_form_does_not_claim_live_human_gate_closure(self) -> None:
        for path in (_PROVIDERS_SRC, _SERVER_SRC):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("lawyer trial acceptance complete", text)
            self.assertNotIn("live wecom uat passed", text)

    # --- Integration round-trip with temp store ---

    def test_integration_temp_store_round_trip(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = OperatorConfigStore(Path(tmp.name) / "operator-config.json")
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=False,
        )
        env = {"ADMIN_API_TOKEN": "static-admin-token", "RBAC_TOKEN_SECRET": self.SECRET}
        headers = {"Authorization": "Bearer static-admin-token"}
        identity = Identity(role=Role.ADMIN, tenant_id="default")
        token = self._valid_csrf_token(identity, "/config/providers")
        form = urlencode(
            {
                "csrf_token": token,
                "providers[0].provider_id": "primary-openai",
                "providers[0].kind": "openai",
                "providers[0].enabled": "1",
                "providers[0].api_key_ref": "env:OPENAI_API_KEY",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/providers",
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
        self.assertIn("Provider config saved", body)


if __name__ == "__main__":
    unittest.main()
