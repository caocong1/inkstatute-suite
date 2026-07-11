"""PROV-03 UI RED contracts for /config/catalog SSR (Plan 76-02).

Wave 0 scaffold: catalog metadata/render/save and CSRF rejection. Catalog page
renders API metadata-driven ``vendor_id`` / ``model_id`` / ``supports_vision``
rows, provider-instance selection, exact copy, HTML escaping, and save
round-trip. Every catalog save POST validates a route-bound CSRF token before
proxying to ``PUT /config/catalog``.

These contracts are intentionally RED until Plans 76-03 and 76-04 implement the
SSR module, CSRF, and catalog route. No live provider, WeCom, QQ, or lawyer-trial
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
_CATALOG_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "catalog.py"
)
_CSRF_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "csrf.py"
)

_FAKE_CATALOG_GET = {
    "data": {
        "provider_id": "primary-openai",
        "model_id": "gpt-5",
    },
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
            "description": "Anthropic multimodal main model",
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
    ],
    "metadata": {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": True,
        "read_only": False,
    },
}


def _make_fake_get(
    return_value: tuple[int, dict[str, Any]] = (200, _FAKE_CATALOG_GET),
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
        if path == "/config/catalog":
            return return_value
        return 200, {"items": [], "count": 0}

    return handle_admin_get


def _try_import_csrf() -> Any:
    try:
        from admin_web_ui import csrf
    except ImportError:
        return None
    return csrf


class CatalogFormScaffoldTests(unittest.TestCase):
    """PROV-03 UI: model catalog SSR + CSRF RED contracts."""

    SECRET = "test-catalog-form-secret"

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
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
            return 200, _FAKE_CATALOG_GET

        self.handle_put = handle_put

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

    def test_catalog_module_exists_with_render_helpers(self) -> None:
        if not _CATALOG_SRC.is_file():
            self.fail(
                "PROV-03: admin_web_ui/catalog.py not implemented (Plan 76-04) — "
                "expected render + parse helpers for /config/catalog SSR form"
            )
        try:
            from admin_web_ui import catalog
        except ImportError as exc:
            self.fail(f"PROV-03: admin_web_ui.catalog import failed (Plan 76-04): {exc}")
        has_render = any(
            hasattr(catalog, name)
            for name in ("render_catalog_page", "render_catalog_form", "render")
        )
        if not has_render:
            self.fail(
                "PROV-03: catalog render helper missing (Plan 76-04) — "
                "UI-SPEC Model Catalog page"
            )

    def test_server_routes_config_catalog_get_and_post(self) -> None:
        src = _SERVER_SRC.read_text(encoding="utf-8")
        if "/config/catalog" not in src:
            self.fail(
                "PROV-03: GET/POST /config/catalog not wired in server.py (Plan 76-04)"
            )

    # --- GET renders metadata-driven catalog rows ---

    def test_get_renders_model_catalog_page(self) -> None:
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Model Catalog", body)
        self.assertIn("Save catalog selection", body)

    def test_get_renders_vendor_id_and_model_id_rows(self) -> None:
        """Catalog rows render vendor_id and model_id from API metadata."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("gpt-5", body)
        self.assertIn("claude-opus-4-8", body)
        self.assertIn("openai", body)
        self.assertIn("anthropic", body)

    def test_get_renders_supports_vision_badges(self) -> None:
        """Each catalog row shows a Vision: supported/not supported badge."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Vision: supported", body)

    def test_get_renders_provider_instance_selection(self) -> None:
        """Catalog page renders provider-instance selection (operator provider_id)."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("primary-openai", body)
        self.assertIn("primary-anthropic", body)

    def test_get_renders_selection_status_line(self) -> None:
        """Selection status line shows the current main model or 'No main model selected'."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        # Current selection is primary-openai / gpt-5.
        self.assertIn("primary-openai", body)
        self.assertIn("gpt-5", body)

    def test_get_renders_no_main_model_selected_when_unset(self) -> None:
        """When no selection is stored, the 'No main model selected' empty state shows."""
        unset = {
            "data": {"provider_id": None, "model_id": None},
            "catalog_entries": _FAKE_CATALOG_GET["catalog_entries"],
            "providers": _FAKE_CATALOG_GET["providers"],
            "metadata": _FAKE_CATALOG_GET["metadata"],
        }
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get((200, unset)),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("No main model selected", body)

    # --- Exact copy (UI-SPEC) ---

    def test_get_renders_exact_ui_spec_copy(self) -> None:
        """Page uses UI-SPEC exact copy for headings, CTA, and restart notice."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertIn("Save catalog selection", body)
        self.assertIn("Main model selection", body)

    # --- HTML escaping ---

    def test_html_escape_on_model_and_provider_values(self) -> None:
        """Dynamic values must be HTML-escaped to prevent XSS."""
        poisoned = {
            "data": {"provider_id": None, "model_id": None},
            "catalog_entries": [
                {
                    "vendor_id": '<script>alert("v")</script>',
                    "model_id": '<script>alert("m")</script>',
                    "supports_vision": True,
                    "description": None,
                }
            ],
            "providers": [],
            "metadata": {"operator_config_enabled": True},
        }
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=_make_fake_get((200, poisoned)),
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        self.assertNotIn('<script>alert("v")</script>', body)
        self.assertNotIn('<script>alert("m")</script>', body)
        self.assertIn("&lt;script&gt;", body)

    # --- POST: CSRF before proxy ---

    def test_post_with_valid_csrf_proxies_put(self) -> None:
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/catalog")
        form = urlencode(
            {
                "csrf_token": token,
                "provider_id": "primary-openai",
                "model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
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
        self.assertEqual(self.put_calls[0]["path"], "/config/catalog")
        self.assertEqual(self.put_calls[0]["body"]["provider_id"], "primary-openai")
        self.assertEqual(self.put_calls[0]["body"]["model_id"], "gpt-5")
        self.assertIn("Catalog selection saved", body)

    def test_post_with_missing_csrf_returns_403_before_proxy(self) -> None:
        form = urlencode(
            {"provider_id": "primary-openai", "model_id": "gpt-5"}
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
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
        """A token bound to /config/providers must not work for catalog save."""
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = self._valid_csrf_token(identity, "/config/providers")
        form = urlencode(
            {
                "csrf_token": token,
                "provider_id": "primary-openai",
                "model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
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

    # --- No nested forms ---

    def test_get_renders_no_nested_forms(self) -> None:
        """Catalog page must contain exactly one <form> (the save form)."""
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
            self._auth(Role.ADMIN),
            feature_flags=self.flags,
            handle_admin_get=self.handle_get,
            read_model=None,
            rbac_secret=self.SECRET,
            method="GET",
            handle_admin_put=self.handle_put,
        )
        self.assertEqual(status, 200)
        form_count = body.count("<form")
        self.assertEqual(form_count, 1)

    # --- RBAC ---

    def test_lawyer_and_viewer_denied_on_catalog(self) -> None:
        for role in (Role.LAWYER, Role.VIEWER):
            status, body, _ = handle_admin_web_ui_request(
                "/config/catalog",
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

    def test_catalog_form_does_not_claim_live_human_gate_closure(self) -> None:
        for path in (_CATALOG_SRC, _SERVER_SRC):
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
        # Seed a provider so the catalog selection can bind to it.
        seed_status, _ = real_handle_admin_put(
            "/config/providers",
            [
                {
                    "provider_id": "primary-openai",
                    "kind": "openai",
                    "enabled": True,
                    "api_base_url": None,
                    "api_key_ref": "env:OPENAI_API_KEY",
                    "model_allowlist": [],
                    "metadata": {},
                }
            ],
            {"Authorization": "Bearer static-admin-token"},
            RuntimeFeatureFlags(
                admin_api_enabled=True,
                operator_config_enabled=True,
            ),
            {"ADMIN_API_TOKEN": "static-admin-token"},
            config_store=store,
        )
        self.assertEqual(seed_status, 200)

        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=False,
        )
        env = {"ADMIN_API_TOKEN": "static-admin-token", "RBAC_TOKEN_SECRET": self.SECRET}
        headers = {"Authorization": "Bearer static-admin-token"}
        identity = Identity(role=Role.ADMIN, tenant_id="default")
        token = self._valid_csrf_token(identity, "/config/catalog")
        form = urlencode(
            {
                "csrf_token": token,
                "provider_id": "primary-openai",
                "model_id": "gpt-5",
            }
        )
        status, body, _ = handle_admin_web_ui_request(
            "/config/catalog",
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
        self.assertIn("Catalog selection saved", body)


if __name__ == "__main__":
    unittest.main()
