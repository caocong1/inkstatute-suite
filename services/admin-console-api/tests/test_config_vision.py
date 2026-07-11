"""VIS-01 API RED+green contracts for /config/vision (Plan 77-02).

Wave 2 scaffold: vision routing_mode metadata, empty-string normalization,
routing_mode enum + vision completeness enforcement (Plan 77-01 validator),
planted-secret rejection, refs-only safety, and apply_semantics. Tests prove
that the vision section GET/PUT emits ``routing_modes`` list and
``vision_configured``/``vision_status`` metadata for the SSR consumer, that
empty-string vision fields normalize to None before persistence, and that
invalid routing_mode or incomplete vision pairs (auto/always_preprocess) are
rejected with 400 invalid_config without echoing rejected values.

No live provider, WeCom, QQ, or lawyer-trial acceptance is claimed.
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
SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"


def _json_blob(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def _builtin_openai(provider_id: str = "primary-openai") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "openai",
        "enabled": True,
        "api_base_url": None,
        "api_key_ref": "env:OPENAI_API_KEY",
        "model_allowlist": [],
        "metadata": {},
    }


def _builtin_anthropic(provider_id: str = "primary-anthropic") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "anthropic",
        "enabled": True,
        "api_base_url": None,
        "api_key_ref": "env:ANTHROPIC_API_KEY",
        "model_allowlist": [],
        "metadata": {},
    }


def _vision_body(
    *,
    routing_mode: str | None = None,
    main_model_id: str | None = None,
    vision_provider_id: str | None = None,
    vision_model_id: str | None = None,
) -> dict[str, Any]:
    return {
        "routing_mode": routing_mode,
        "main_model_id": main_model_id,
        "vision_provider_id": vision_provider_id,
        "vision_model_id": vision_model_id,
    }


class ConfigVisionApiTests(unittest.TestCase):
    """VIS-01: vision routing_mode metadata, normalization, and validation."""

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

    def _put_providers(self, providers: list[dict[str, Any]]) -> None:
        status, _ = handle_admin_put(
            "/config/providers",
            providers,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200, f"provider seed failed: {providers}")

    def _put_catalog(self, provider_id: str, model_id: str) -> None:
        status, _ = handle_admin_put(
            "/config/catalog",
            {"provider_id": provider_id, "model_id": model_id},
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200, f"catalog seed failed: {provider_id}/{model_id}")

    def _put_vision(
        self,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
        rbac_secret: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            "/config/vision",
            body,
            headers or self.headers,
            flags or self.flags,
            self.env,
            config_store=self.store,
            rbac_secret=rbac_secret,
        )

    def _get_vision(
        self,
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
        rbac_secret: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            "/config/vision",
            "",
            headers or self.headers,
            self.read_model,
            self.feedback_queue,
            flags or self.flags,
            self.env,
            config_store=self.store,
            rbac_secret=rbac_secret,
        )

    # --- GET metadata: routing_modes, vision_configured, vision_status ---

    def test_get_vision_default_store_returns_none_fields_and_metadata(self) -> None:
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        self.assertIsNone(body["data"]["routing_mode"])
        self.assertIsNone(body["data"]["main_model_id"])
        self.assertIsNone(body["data"]["vision_model_id"])
        self.assertIsNone(body["data"]["vision_provider_id"])
        meta = body["metadata"]
        self.assertIs(meta["admin_api"], True)
        self.assertIs(meta["config_surface"], True)
        self.assertIs(meta["operator_config_enabled"], True)
        self.assertIs(meta["read_only"], False)
        self.assertEqual(meta["apply_semantics"], "restart_required")
        self.assertEqual(meta["routing_modes"], ["auto", "always_preprocess", "main_only"])
        self.assertIs(meta["vision_configured"], False)
        self.assertEqual(meta["vision_status"], "not_configured")

    def test_get_vision_metadata_routing_modes_is_static_list(self) -> None:
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        self.assertEqual(
            body["metadata"]["routing_modes"],
            ["auto", "always_preprocess", "main_only"],
        )

    # --- PUT main_only with blank vision fields succeeds ---

    def test_put_main_only_with_blank_vision_fields_succeeds(self) -> None:
        status, body = self._put_vision(
            _vision_body(routing_mode="main_only")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "main_only")
        self.assertIsNone(body["data"]["vision_provider_id"])
        self.assertIsNone(body["data"]["vision_model_id"])
        self.assertIsNone(body["data"]["main_model_id"])
        self.assertEqual(body["metadata"]["apply_semantics"], "restart_required")
        self.assertIs(body["metadata"]["vision_configured"], False)
        self.assertEqual(body["metadata"]["vision_status"], "not_configured")

    def test_put_main_only_persists_routing_mode(self) -> None:
        self._put_vision(_vision_body(routing_mode="main_only"))
        doc = self.store.load()
        self.assertEqual(doc.vision.routing_mode, "main_only")
        self.assertIsNone(doc.vision.vision_provider_id)
        self.assertIsNone(doc.vision.vision_model_id)

    # --- PUT auto with complete valid vision pair succeeds ---

    def test_put_auto_with_complete_vision_pair_succeeds(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="auto",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id="claude-opus-4-8",
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "auto")
        self.assertEqual(body["data"]["vision_provider_id"], "primary-anthropic")
        self.assertEqual(body["data"]["vision_model_id"], "claude-opus-4-8")
        self.assertIs(body["metadata"]["vision_configured"], True)
        self.assertEqual(body["metadata"]["vision_status"], "configured")

    def test_put_always_preprocess_with_complete_vision_pair_succeeds(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="always_preprocess",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id="claude-opus-4-8",
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "always_preprocess")

    # --- PUT auto with absent vision pair fails ---

    def test_put_auto_with_absent_vision_pair_fails(self) -> None:
        self._put_providers([_builtin_openai()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(routing_mode="auto", main_model_id="gpt-5")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    # --- PUT auto with partial vision pair fails ---

    def test_put_auto_with_partial_vision_pair_fails(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="auto",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id=None,
            )
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    def test_put_always_preprocess_with_partial_vision_pair_fails(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="always_preprocess",
                main_model_id="gpt-5",
                vision_provider_id=None,
                vision_model_id="claude-opus-4-8",
            )
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    # --- PUT invalid routing_mode fails without echo ---

    def test_put_invalid_routing_mode_fails_without_echo(self) -> None:
        self._put_providers([_builtin_openai()])
        self._put_catalog("primary-openai", "gpt-5")
        bad_mode = "hybrid"
        status, body = self._put_vision(
            _vision_body(routing_mode=bad_mode, main_model_id="gpt-5")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(bad_mode, blob)

    # --- PUT unexpected key (planted secret) rejected ---

    def test_put_unexpected_key_rejected(self) -> None:
        status, body = self._put_vision(
            {
                "routing_mode": "main_only",
                "main_model_id": None,
                "vision_provider_id": None,
                "vision_model_id": None,
                "api_key": PLANTED_RAW,
            }
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(PLANTED_RAW, blob)

    def test_put_planted_token_key_rejected(self) -> None:
        status, body = self._put_vision(
            {
                "routing_mode": "main_only",
                "main_model_id": None,
                "vision_provider_id": None,
                "vision_model_id": None,
                "token": PLANTED_RAW,
            }
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    def test_put_planted_password_key_rejected(self) -> None:
        status, body = self._put_vision(
            {
                "routing_mode": "main_only",
                "main_model_id": None,
                "vision_provider_id": None,
                "vision_model_id": None,
                "password": PLANTED_RAW,
            }
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

    # --- PUT empty-string normalization to None ---

    def test_put_empty_string_fields_normalize_to_none(self) -> None:
        status, body = self._put_vision(
            {
                "routing_mode": "",
                "main_model_id": "",
                "vision_provider_id": "",
                "vision_model_id": "",
            }
        )
        self.assertEqual(status, 200)
        self.assertIsNone(body["data"]["routing_mode"])
        self.assertIsNone(body["data"]["main_model_id"])
        self.assertIsNone(body["data"]["vision_provider_id"])
        self.assertIsNone(body["data"]["vision_model_id"])
        doc = self.store.load()
        self.assertIsNone(doc.vision.routing_mode)
        self.assertIsNone(doc.vision.main_model_id)
        self.assertIsNone(doc.vision.vision_provider_id)
        self.assertIsNone(doc.vision.vision_model_id)

    def test_put_empty_string_routing_mode_with_complete_pair_normalizes(self) -> None:
        """Empty routing_mode → None (draft-tolerant); complete pair stays."""
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            {
                "routing_mode": "",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
            }
        )
        self.assertEqual(status, 200)
        self.assertIsNone(body["data"]["routing_mode"])
        self.assertEqual(body["data"]["vision_provider_id"], "primary-anthropic")
        self.assertIs(body["metadata"]["vision_configured"], True)

    # --- GET after PUT returns saved data and vision_configured ---

    def test_get_after_put_returns_saved_data_and_vision_configured(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        self._put_vision(
            _vision_body(
                routing_mode="auto",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id="claude-opus-4-8",
            )
        )
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "auto")
        self.assertEqual(body["data"]["vision_provider_id"], "primary-anthropic")
        self.assertEqual(body["data"]["vision_model_id"], "claude-opus-4-8")
        self.assertIs(body["metadata"]["vision_configured"], True)
        self.assertEqual(body["metadata"]["vision_status"], "configured")

    def test_get_after_main_only_save_shows_not_configured(self) -> None:
        self._put_vision(_vision_body(routing_mode="main_only"))
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "main_only")
        self.assertIs(body["metadata"]["vision_configured"], False)
        self.assertEqual(body["metadata"]["vision_status"], "not_configured")

    # --- main_only accepts any vision pair shape (absent/partial/complete) ---

    def test_main_only_accepts_partial_vision_pair(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="main_only",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id=None,
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "main_only")

    def test_main_only_accepts_complete_vision_pair(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="main_only",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id="claude-opus-4-8",
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "main_only")

    # --- Refs-only safety: no secrets/refs/URLs in responses ---

    def test_get_vision_response_has_no_secrets_or_refs(self) -> None:
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        blob = _json_blob(body)
        for forbidden in ("api_key_ref", "api_base_url", "sk-", "secret"):
            self.assertNotIn(forbidden, blob.lower())

    def test_put_vision_response_has_no_secrets_or_refs(self) -> None:
        self._put_providers([_builtin_openai(), _builtin_anthropic()])
        self._put_catalog("primary-openai", "gpt-5")
        status, body = self._put_vision(
            _vision_body(
                routing_mode="auto",
                main_model_id="gpt-5",
                vision_provider_id="primary-anthropic",
                vision_model_id="claude-opus-4-8",
            )
        )
        self.assertEqual(status, 200)
        blob = _json_blob(body)
        for forbidden in ("api_key_ref", "api_base_url", "sk-", "secret"):
            self.assertNotIn(forbidden, blob.lower())

    # --- apply_semantics present on both GET and PUT ---

    def test_apply_semantics_restart_required_on_get(self) -> None:
        status, body = self._get_vision()
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["apply_semantics"], "restart_required")

    def test_apply_semantics_restart_required_on_put(self) -> None:
        status, body = self._put_vision(_vision_body(routing_mode="main_only"))
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["apply_semantics"], "restart_required")

    # --- Flag-off refusal and RBAC denial ---

    def test_flag_off_put_refused(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        status, body = self._put_vision(
            _vision_body(routing_mode="main_only"), flags=flags
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
        self.assertFalse(self.store_path.exists())

    def test_lawyer_and_viewer_denied_put(self) -> None:
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
                status, body = self._put_vision(
                    _vision_body(routing_mode="main_only"),
                    headers=headers,
                    flags=flags,
                    rbac_secret=secret,
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")

    def test_operator_rbac_put_allowed(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.OPERATOR, tenant_id="t1")
        headers = {"Authorization": f"Bearer {token}"}
        status, body = self._put_vision(
            _vision_body(routing_mode="main_only"),
            headers=headers,
            flags=flags,
            rbac_secret=secret,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["routing_mode"], "main_only")

    # --- No live acceptance claim ---

    def test_no_live_acceptance_claim_in_vision_response(self) -> None:
        status, body = self._put_vision(_vision_body(routing_mode="main_only"))
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
