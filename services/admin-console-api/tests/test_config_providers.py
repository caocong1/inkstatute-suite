"""PROV-01/PROV-02 API RED contracts for /config/providers (Plan 76-02).

Wave 0 scaffold: canonical built-in vendor persistence, custom provider
allowlist round-trip, planted-secret rejection, duplicate ID rejection, forged
built-in URL rejection, non-empty built-in allowlist rejection, and refs-safe
``probe_targets`` metadata.

These contracts are intentionally RED until Plans 76-01 and 76-03 supply the
operator-config ``model_allowlist`` field, built-in vendor profile enforcement,
duplicate ``provider_id`` validation, and the probe handler. No live provider,
WeCom, QQ, or lawyer-trial acceptance is claimed.
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


SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"
PLANTED_RAW = "planted-raw-secret-value-NEVER-ON-CONFIG"

_OPENAI_CANONICAL_URL = "https://api.openai.com/v1"
_ANTHROPIC_CANONICAL_URL = "https://api.anthropic.com/v1"
_FORGED_URL = "https://evil.example.com/v1"


def _json_blob(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def _builtin_openai(provider_id: str = "primary-openai") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "openai",
        "enabled": False,
        "api_base_url": None,  # built-in: server fills canonical URL
        "api_key_ref": "env:OPENAI_API_KEY",
        "model_allowlist": [],  # built-in: must be empty
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


class ConfigProvidersScaffoldTests(unittest.TestCase):
    """PROV-01/02: canonical built-ins, custom allowlist, refs-only, RBAC."""

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
        self,
        providers: list[dict[str, Any]],
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            "/config/providers",
            providers,
            headers or self.headers,
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    def _get_providers(
        self,
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            "/config/providers",
            "",
            headers or self.headers,
            self.read_model,
            self.feedback_queue,
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    # --- PROV-01: canonical built-in vendor persistence ---

    def test_builtin_openai_persists_canonical_url_and_empty_allowlist(self) -> None:
        status, body = self._put_providers([_builtin_openai()])
        self.assertEqual(status, 200)
        entry = body["data"][0]
        self.assertEqual(entry["kind"], "openai")
        self.assertEqual(entry["api_base_url"], _OPENAI_CANONICAL_URL)
        self.assertEqual(entry["model_allowlist"], [])
        self.assertEqual(entry["api_key_ref"], "env:OPENAI_API_KEY")

        get_status, get_body = self._get_providers()
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["data"][0]["api_base_url"], _OPENAI_CANONICAL_URL)
        self.assertEqual(get_body["data"][0]["model_allowlist"], [])

    def test_builtin_anthropic_persists_canonical_url_and_empty_allowlist(self) -> None:
        status, body = self._put_providers([_builtin_anthropic()])
        self.assertEqual(status, 200)
        entry = body["data"][0]
        self.assertEqual(entry["kind"], "anthropic")
        self.assertEqual(entry["api_base_url"], _ANTHROPIC_CANONICAL_URL)
        self.assertEqual(entry["model_allowlist"], [])

    def test_builtin_vendor_with_forged_api_base_url_rejected(self) -> None:
        """Built-in kind must not accept an arbitrary (forged) api_base_url."""
        forged = dict(_builtin_openai())
        forged["api_base_url"] = _FORGED_URL
        status, body = self._put_providers([forged])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(_FORGED_URL, blob)
        self.assertFalse(self.store_path.exists())

    def test_builtin_vendor_with_non_empty_allowlist_rejected(self) -> None:
        """Built-in kind must ship an empty model_allowlist (catalog is preset)."""
        bad = dict(_builtin_openai())
        bad["model_allowlist"] = ["gpt-5", "gpt-4o"]
        status, body = self._put_providers([bad])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertFalse(self.store_path.exists())

    # --- PROV-02: custom provider allowlist round-trip ---

    def test_custom_provider_allowlist_round_trip(self) -> None:
        status, body = self._put_providers([_custom_provider()])
        self.assertEqual(status, 200)
        entry = body["data"][0]
        self.assertEqual(entry["kind"], "custom")
        self.assertEqual(entry["api_base_url"], "https://custom.example.com/v1")
        self.assertEqual(entry["model_allowlist"], ["local-gpt", "local-vision"])

        get_status, get_body = self._get_providers()
        self.assertEqual(get_status, 200)
        self.assertEqual(
            get_body["data"][0]["model_allowlist"], ["local-gpt", "local-vision"]
        )

    def test_custom_provider_empty_allowlist_rejected(self) -> None:
        """PROV-02: custom providers require an explicit non-empty allowlist."""
        bad = _custom_provider(allowlist=())
        status, body = self._put_providers([bad])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertFalse(self.store_path.exists())

    # --- Refs-only / planted-secret rejection ---

    def test_planted_sk_rejected_without_echo(self) -> None:
        bad = _custom_provider()
        bad["api_key_ref"] = SK_PLANTED
        status, body = self._put_providers([bad])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(SK_PLANTED, blob)
        self.assertNotIn("sk-", blob)
        self.assertFalse(self.store_path.exists())

    def test_planted_raw_secret_in_metadata_rejected_without_echo(self) -> None:
        bad = _custom_provider()
        bad["metadata"] = {"api_key": PLANTED_RAW}
        status, body = self._put_providers([bad])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(PLANTED_RAW, blob)
        self.assertFalse(self.store_path.exists())

    # --- Duplicate provider_id rejection ---

    def test_duplicate_provider_id_rejected(self) -> None:
        """UI-SPEC: server-side rejection of duplicate registry IDs."""
        providers = [
            _builtin_openai(provider_id="dupe-id"),
            _custom_provider(provider_id="dupe-id"),
        ]
        status, body = self._put_providers(providers)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        # Error message exposes codes@paths only — never the duplicate value.
        self.assertNotIn("dupe-id", blob)
        self.assertFalse(self.store_path.exists())

    # --- probe_targets metadata (refs-safe) ---

    def test_get_providers_includes_probe_targets_metadata(self) -> None:
        """probe_targets lists only configured target status/provider/model IDs."""
        self._put_providers([_builtin_openai(), _custom_provider()])
        get_status, get_body = self._get_providers()
        self.assertEqual(get_status, 200)
        self.assertIn("probe_targets", get_body)
        targets = get_body["probe_targets"]
        self.assertIsInstance(targets, dict)
        # main and vision keys present; values are refs-safe status dicts.
        for target in ("main", "vision"):
            with self.subTest(target=target):
                self.assertIn(target, targets)
                entry = targets[target]
                self.assertIsInstance(entry, dict)
                # status is a generic code, not a secret or response body.
                self.assertIn("status", entry)
                self.assertIsInstance(entry["status"], str)
                # provider_id / model_id are stored refs-only IDs (or None).
                self.assertIn("provider_id", entry)
                self.assertIn("model_id", entry)
                # No resolved secret, URL, or header leaks into metadata.
                for forbidden in ("api_key", "authorization", "secret", "body"):
                    self.assertNotIn(forbidden, json.dumps(entry).lower())

    # --- RBAC + flag gate ---

    def test_operator_rbac_put_providers_allowed(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.OPERATOR, tenant_id="t1")
        headers = {"Authorization": f"Bearer {token}"}
        status, body = self._put_providers(
            [_builtin_openai()], headers=headers, flags=flags
        )
        self.assertEqual(status, 200)

    def test_lawyer_and_viewer_denied_put_providers(self) -> None:
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
                status, body = self._put_providers(
                    [_builtin_openai()], headers=headers, flags=flags
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")

    def test_flag_off_put_providers_refused(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        status, body = self._put_providers([_builtin_openai()], flags=flags)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
        self.assertFalse(self.store_path.exists())

    def test_providers_metadata_config_surface(self) -> None:
        status, body = self._put_providers([_builtin_openai()])
        self.assertEqual(status, 200)
        self.assertIs(body["metadata"]["config_surface"], True)
        self.assertIs(body["metadata"]["read_only"], False)

    def test_no_live_acceptance_claim_in_providers_response(self) -> None:
        """DOC-02: must not claim live WeCom/QQ/lawyer-trial acceptance."""
        status, body = self._put_providers([_builtin_openai()])
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
