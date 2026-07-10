"""PROV-03 API RED contracts for /config/catalog (Plan 76-02).

Wave 0 scaffold: registry-instance to catalog vendor/allowlist binding. Tests
prove that catalog selection is validated against the provider instance's
``kind`` (built-in vendor_id match) or explicit ``model_allowlist`` (custom),
not by comparing ``provider_id`` to ``vendor_id``. Catalog metadata requires
``vendor_id``, ``model_id``, and ``supports_vision`` bool with source-grounded
gpt-5 / claude-opus-4-8 rows.

These contracts are intentionally RED until Plans 76-01 and 76-03 supply the
built-in model catalog tuple, ``model_allowlist`` field, and cross-section
validation. No live provider, WeCom, QQ, or lawyer-trial acceptance is claimed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from admin_console_api.api import handle_admin_get, handle_admin_put
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token


class FakeReadModel:
    """Minimal stub — config handlers do not use the read model."""

    def list_conversations(self, **kwargs: Any) -> list:
        return []

    def list_tasks(self, **kwargs: Any) -> list:
        return []


PLANTED_RAW = "planted-raw-secret-value-NEVER-ON-CONFIG"

_OPENAI_CANONICAL_URL = "https://api.openai.com/v1"
_ANTHROPIC_CANONICAL_URL = "https://api.anthropic.com/v1"


def _json_blob(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def _builtin_openai(provider_id: str = "primary-openai") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "openai",
        "enabled": False,
        "api_base_url": None,
        "api_key_ref": "env:OPENAI_API_KEY",
        "model_allowlist": [],
        "metadata": {},
    }


def _builtin_anthropic(provider_id: str = "primary-anthropic") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "anthropic",
        "enabled": False,
        "api_base_url": None,
        "api_key_ref": "env:ANTHROPIC_API_KEY",
        "model_allowlist": [],
        "metadata": {},
    }


def _custom_provider(
    provider_id: str = "custom-endpoint",
    *,
    allowlist: tuple[str, ...] = ("local-gpt", "local-vision"),
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "custom",
        "enabled": True,
        "api_base_url": "https://custom.example.com/v1",
        "api_key_ref": "env:CUSTOM_API_KEY",
        "model_allowlist": list(allowlist),
        "metadata": {},
    }


def _catalog_selection(
    provider_id: str = "primary-openai",
    model_id: str = "gpt-5",
) -> dict[str, Any]:
    return {"provider_id": provider_id, "model_id": model_id}


class ConfigCatalogScaffoldTests(unittest.TestCase):
    """PROV-03: registry-instance catalog binding + metadata RED contracts."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store_path = Path(self._tmpdir.name) / "operator-config.json"
        self.store = OperatorConfigStore(self.store_path)
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def _put_providers(
        self, providers: list[dict[str, Any]]
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            "/config/providers",
            providers,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )

    def _put_catalog(
        self,
        selection: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            "/config/catalog",
            selection,
            headers or self.headers,
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    def _get_catalog(
        self,
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            "/config/catalog",
            "",
            headers or self.headers,
            self.read_model,
            self.feedback_queue,
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    # --- Catalog metadata: vendor_id, model_id, supports_vision ---

    def test_get_catalog_includes_builtin_model_catalog_metadata(self) -> None:
        """Catalog metadata lists built-in entries with vision capability."""
        status, body = self._get_catalog()
        self.assertEqual(status, 200)
        self.assertIn("catalog_entries", body)
        entries = body["catalog_entries"]
        self.assertIsInstance(entries, list)
        self.assertGreaterEqual(len(entries), 2)
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertIn("vendor_id", entry)
                self.assertIn("model_id", entry)
                self.assertIn("supports_vision", entry)
                self.assertIsInstance(entry["supports_vision"], bool)

    def test_catalog_metadata_contains_source_grounded_rows(self) -> None:
        """Source-grounded gpt-5 (openai) and claude-opus-4-8 (anthropic)."""
        status, body = self._get_catalog()
        self.assertEqual(status, 200)
        entries = body["catalog_entries"]
        by_key = {(e["vendor_id"], e["model_id"]): e for e in entries}
        self.assertIn(("openai", "gpt-5"), by_key)
        self.assertIn(("anthropic", "claude-opus-4-8"), by_key)
        self.assertIs(by_key[("openai", "gpt-5")]["supports_vision"], True)
        self.assertIs(by_key[("anthropic", "claude-opus-4-8")]["supports_vision"], True)

    # --- Valid built-in kind match ---

    def test_valid_builtin_openai_kind_match_accepted(self) -> None:
        """provider_id=primary-openai (kind=openai) + model_id=gpt-5 → 200."""
        self._put_providers([_builtin_openai()])
        status, body = self._put_catalog(_catalog_selection("primary-openai", "gpt-5"))
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["provider_id"], "primary-openai")
        self.assertEqual(body["data"]["model_id"], "gpt-5")

    def test_valid_builtin_anthropic_kind_match_accepted(self) -> None:
        self._put_providers([_builtin_anthropic()])
        status, body = self._put_catalog(
            _catalog_selection("primary-anthropic", "claude-opus-4-8")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["model_id"], "claude-opus-4-8")

    # --- Built-in vendor mismatch ---

    def test_builtin_vendor_mismatch_rejected(self) -> None:
        """openai-kind provider selecting an anthropic-vendor model → 400."""
        self._put_providers([_builtin_openai()])
        status, body = self._put_catalog(
            _catalog_selection("primary-openai", "claude-opus-4-8")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertFalse(self.store_path.exists())

    # --- Missing provider ---

    def test_catalog_selection_missing_provider_rejected(self) -> None:
        """Catalog references a provider_id not in the registry → 400."""
        self._put_providers([_builtin_openai()])
        status, body = self._put_catalog(
            _catalog_selection("nonexistent-provider", "gpt-5")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    # --- Valid custom allowlist selection ---

    def test_valid_custom_allowlist_selection_accepted(self) -> None:
        """Custom provider + model in its allowlist → 200."""
        self._put_providers([_custom_provider()])
        status, body = self._put_catalog(
            _catalog_selection("custom-endpoint", "local-gpt")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["provider_id"], "custom-endpoint")
        self.assertEqual(body["data"]["model_id"], "local-gpt")

    # --- Custom model-not-allowed rejection ---

    def test_custom_model_not_in_allowlist_rejected(self) -> None:
        """Custom provider + model NOT in its allowlist → 400."""
        self._put_providers([_custom_provider()])
        status, body = self._put_catalog(
            _catalog_selection("custom-endpoint", "unauthorized-model")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    # --- provider_id ≠ vendor_id distinction ---

    def test_operator_provider_id_distinct_from_vendor_kind(self) -> None:
        """Registry instance ID (primary-openai) ≠ vendor kind (openai).

        Selection is validated against the provider's kind, not by equality of
        provider_id and vendor_id.
        """
        self._put_providers([_builtin_openai(provider_id="my-openai-instance")])
        status, body = self._put_catalog(
            _catalog_selection("my-openai-instance", "gpt-5")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["provider_id"], "my-openai-instance")

    # --- Vision-pair validation (no Phase 77 form required) ---

    def test_catalog_selection_round_trip_persists_provider_and_model(self) -> None:
        self._put_providers([_builtin_openai()])
        self._put_catalog(_catalog_selection("primary-openai", "gpt-5"))
        get_status, get_body = self._get_catalog()
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["data"]["provider_id"], "primary-openai")
        self.assertEqual(get_body["data"]["model_id"], "gpt-5")

    # --- Refs-only / planted-secret rejection ---

    def test_planted_secret_in_catalog_rejected_without_echo(self) -> None:
        """Catalog body must not smuggle raw secrets."""
        bad = {
            "provider_id": "primary-openai",
            "model_id": "gpt-5",
            "metadata": {"api_key": PLANTED_RAW},
        }
        self._put_providers([_builtin_openai()])
        status, body = self._put_catalog(bad)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(PLANTED_RAW, blob)

    # --- RBAC + flag gate ---

    def test_operator_rbac_put_catalog_allowed(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.OPERATOR, tenant_id="t1")
        headers = {"Authorization": f"Bearer {token}"}
        self._put_providers([_builtin_openai()], )
        # Re-put providers with RBAC headers so the store has them.
        handle_admin_put(
            "/config/providers",
            [_builtin_openai()],
            headers,
            flags,
            self.env,
            config_store=self.store,
            rbac_secret=secret,
        )
        status, body = self._put_catalog(
            _catalog_selection("primary-openai", "gpt-5"),
            headers=headers,
            flags=flags,
        )
        self.assertEqual(status, 200)

    def test_lawyer_and_viewer_denied_put_catalog(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        for role in (Role.LAWYER, Role.VIEWER):
            with self.subTest(role=role):
                token = issue_token(secret, role=role, tenant_id="t1")
                headers = {"Authorization": f"Bearer {token}"}
                status, body = self._put_catalog(
                    _catalog_selection("primary-openai", "gpt-5"),
                    headers=headers,
                    flags=flags,
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")

    def test_flag_off_put_catalog_refused(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        status, body = self._put_catalog(
            _catalog_selection("primary-openai", "gpt-5"), flags=flags
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
        self.assertFalse(self.store_path.exists())

    def test_no_live_acceptance_claim_in_catalog_response(self) -> None:
        """DOC-02: must not claim live WeCom/QQ/lawyer-trial acceptance."""
        self._put_providers([_builtin_openai()])
        status, body = self._put_catalog(_catalog_selection("primary-openai", "gpt-5"))
        self.assertEqual(status, 200)
        blob = _json_blob(body).lower()
        for forbidden in (
            "lawyer trial acceptance complete",
            "live wecom uat passed",
            "live qq openapi acceptance",
        ):
            self.assertNotIn(forbidden, blob)


if __name__ == "__main__":
    unittest.main()
