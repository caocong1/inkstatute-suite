"""PROV-04 API RED contracts for POST /config/providers/probe (Plan 76-02).

Wave 0 scaffold: stored main/vision target resolution, resolver/opener-injected
SSRF matrix, disabled redirects, vendor auth dialects, no-body/no-save, flag +
RBAC gates. The probe accepts only ``target=main|vision``, resolves stored
provider/model pairs, and returns generic status codes — never response bodies,
resolved secrets, or Authorization headers.

These contracts are intentionally RED until Plans 76-01 and 76-03 supply the
``VisionPolicyDoc.vision_provider_id`` linkage, the probe handler, and the
resolver/opener injection seams. All tests use fake stores, injected DNS
resolvers, and opener fakes — no live provider, DNS, network, WeCom, QQ, or
lawyer-trial acceptance is performed or claimed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Mapping

from admin_console_api.api import handle_admin_put
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token


class FakeReadModel:
    def list_conversations(self, **kwargs: Any) -> list:
        return []

    def list_tasks(self, **kwargs: Any) -> list:
        return []


SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"

_OPENAI_CANONICAL_URL = "https://api.openai.com/v1"
_ANTHROPIC_CANONICAL_URL = "https://api.anthropic.com/v1"


# ---------------------------------------------------------------------------
# Deterministic socket.getaddrinfo-shaped resolver results.
# ---------------------------------------------------------------------------

_PUBLIC_ADDR = ("93.184.216.34", 443, 0, 0, ("93.184.216.34", 443))
_LOOPBACK_ADDR = ("127.0.0.1", 443, 0, 0, ("127.0.0.1", 443))
_PRIVATE_10 = ("10.0.0.1", 443, 0, 0, ("10.0.0.1", 443))
_PRIVATE_172 = ("172.16.0.1", 443, 0, 0, ("172.16.0.1", 443))
_PRIVATE_192 = ("192.168.1.1", 443, 0, 0, ("192.168.1.1", 443))
_LINK_LOCAL = ("169.254.169.254", 443, 0, 0, ("169.254.169.254", 443))
_MULTICAST = ("224.0.0.1", 443, 0, 0, ("224.0.0.1", 443))
_RESERVED = ("240.0.0.1", 443, 0, 0, ("240.0.0.1", 443))
_UNSPECIFIED = ("0.0.0.0", 443, 0, 0, ("0.0.0.0", 443))


def _resolver_returning(addrinfo: tuple) -> Callable[..., list]:
    """A fake socket.getaddrinfo that always returns the given addrinfo."""

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list:
        return [addrinfo]

    return fake_getaddrinfo


class _FakeResponse:
    """A status-only HTTP response fake that fails if read() is called.

    The probe must never read the response body (PROV-04: no body logging).
    """

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self._read_called = False

    def read(self) -> bytes:
        self._read_called = True
        raise AssertionError("probe must not call response.read() (no body logging)")

    def close(self) -> None:
        pass

    def getheader(self, name: str, default: Any = None) -> Any:
        return default

    def getheaders(self) -> list[tuple[str, str]]:
        return []


class _RecordingOpener:
    """A fake urllib.request.urlopen that records requests and refuses redirects.

    Records the URL, headers, and timeout of each call. Returns a status-only
    ``_FakeResponse``. Raises if ``read()`` is called on the response. Redirect
    responses are never followed — the probe must disable redirects so
    credentials cannot cross origins.
    """

    def __init__(
        self,
        *,
        response_status: int = 200,
        redirect: bool = False,
        raise_error: Exception | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response_status = response_status
        self._redirect = redirect
        self._raise_error = raise_error

    def __call__(self, url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        self.calls.append(
            {
                "url": url,
                "args": args,
                "kwargs": dict(kwargs),
                "headers": dict(kwargs.get("headers", {}) or {}),
            }
        )
        if self._raise_error is not None:
            raise self._raise_error
        if self._redirect:
            # A redirect response must never be followed by the probe.
            raise AssertionError(
                "probe must disable redirects — credentials must not cross origins"
            )
        return _FakeResponse(self._response_status)


# ---------------------------------------------------------------------------
# Provider/catalog/vision document seeds.
# ---------------------------------------------------------------------------


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


def _custom_provider(provider_id: str = "custom-endpoint") -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "kind": "custom",
        "enabled": True,
        "api_base_url": "https://custom.example.com/v1",
        "api_key_ref": "env:CUSTOM_API_KEY",
        "model_allowlist": ["local-gpt"],
        "metadata": {},
    }


def _catalog(provider_id: str, model_id: str) -> dict[str, Any]:
    return {"provider_id": provider_id, "model_id": model_id}


def _vision(vision_provider_id: str, vision_model_id: str) -> dict[str, Any]:
    return {
        "routing_mode": None,
        "main_model_id": None,
        "vision_provider_id": vision_provider_id,
        "vision_model_id": vision_model_id,
    }


def _try_import_probe() -> Any:
    """Import the probe handler; return None if the module does not exist yet."""
    try:
        from admin_console_api.probe import handle_config_probe
    except ImportError:
        return None
    return handle_config_probe


class ConfigProbeScaffoldTests(unittest.TestCase):
    """PROV-04: stored target resolution + SSRF-safe non-destructive probe."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store_path = Path(self._tmpdir.name) / "operator-config.json"
        self.store = OperatorConfigStore(self.store_path)
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
        )
        self.env = {
            "ADMIN_API_TOKEN": "test-token",
            "OPENAI_API_KEY": "planted-openai-key-NEVER-LOGGED",
            "ANTHROPIC_API_KEY": "planted-anthropic-key-NEVER-LOGGED",
            "CUSTOM_API_KEY": "planted-custom-key-NEVER-LOGGED",
        }
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []
        self.resolver = _resolver_returning(_PUBLIC_ADDR)
        self.opener = _RecordingOpener()

    def _seed_main(
        self,
        provider: dict[str, Any],
        model_id: str,
    ) -> None:
        """Seed providers + catalog selection for a main target probe."""
        handle_admin_put(
            "/config/providers",
            [provider],
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        handle_admin_put(
            "/config/catalog",
            _catalog(provider["provider_id"], model_id),
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )

    def _seed_vision(
        self,
        *,
        main_provider: dict[str, Any],
        main_model_id: str,
        vision_provider: dict[str, Any],
        vision_model_id: str,
    ) -> None:
        """Seed providers + catalog + vision for a vision target probe."""
        handle_admin_put(
            "/config/providers",
            [main_provider, vision_provider],
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        handle_admin_put(
            "/config/catalog",
            _catalog(main_provider["provider_id"], main_model_id),
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        handle_admin_put(
            "/config/vision",
            _vision(vision_provider["provider_id"], vision_model_id),
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )

    def _probe(
        self,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        flags: RuntimeFeatureFlags | None = None,
        resolver: Callable[..., list] | None = None,
        opener: Callable[..., Any] | None = None,
        rbac_secret: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        handle_config_probe = _try_import_probe()
        if handle_config_probe is None:
            self.fail(
                "PROV-04: admin_console_api.probe.handle_config_probe not "
                "implemented (Plan 76-03) — expected POST /config/providers/probe "
                "with resolver/opener injection seams"
            )
        return handle_config_probe(
            "/config/providers/probe",
            body,
            headers or self.headers,
            flags or self.flags,
            self.env,
            config_store=self.store,
            rbac_secret=rbac_secret,
            resolver=resolver or self.resolver,
            opener=opener or self.opener,
        )

    # --- Target selector: main resolves catalog.provider_id/model_id ---

    def test_target_main_resolves_stored_catalog_provider_and_model(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        status, body = self._probe({"target": "main"})
        self.assertEqual(status, 200)
        self.assertEqual(self.opener.calls[0]["url"], _OPENAI_CANONICAL_URL + "/models")
        result = body["data"]
        self.assertIn(result["status"], ("ok", "fail"))
        self.assertEqual(result["target"], "main")
        self.assertEqual(result["provider_id"], "primary-openai")
        self.assertEqual(result["model_id"], "gpt-5")

    def test_target_vision_resolves_stored_vision_provider_and_model(self) -> None:
        self._seed_vision(
            main_provider=_builtin_openai(),
            main_model_id="gpt-5",
            vision_provider=_builtin_anthropic(),
            vision_model_id="claude-opus-4-8",
        )
        status, body = self._probe({"target": "vision"})
        self.assertEqual(status, 200)
        self.assertEqual(self.opener.calls[0]["url"], _ANTHROPIC_CANONICAL_URL + "/models")
        result = body["data"]
        self.assertEqual(result["target"], "vision")
        self.assertEqual(result["provider_id"], "primary-anthropic")
        self.assertEqual(result["model_id"], "claude-opus-4-8")

    # --- Unknown target / extra selector fields rejected before side effects ---

    def test_unknown_target_rejected_before_resolver_or_opener(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        opener = _RecordingOpener()
        status, body = self._probe({"target": "unknown"}, opener=opener)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertEqual(opener.calls, [])

    def test_extra_selector_fields_rejected(self) -> None:
        """No arbitrary provider_id, URL, ref, header, or model override."""
        self._seed_main(_builtin_openai(), "gpt-5")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main", "provider_id": "evil", "url": "https://evil.example.com"},
            opener=opener,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertEqual(opener.calls, [])

    def test_missing_target_rejected(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        opener = _RecordingOpener()
        status, body = self._probe({}, opener=opener)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        self.assertEqual(opener.calls, [])

    # --- Absent / partial vision → generic not_configured, zero side effects ---

    def test_absent_vision_returns_generic_not_configured(self) -> None:
        """No vision config → not_configured with zero resolver/opener/save calls."""
        self._seed_main(_builtin_openai(), "gpt-5")
        opener = _RecordingOpener()
        save_count_before = 0
        status, body = self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])
        # No store.save occurred (file mtime unchanged).
        mtime = self.store_path.stat().st_mtime if self.store_path.exists() else 0
        self.assertEqual(self.store_path.stat().st_mtime, mtime)

    def test_partial_vision_provider_only_returns_not_configured(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        # Seed partial vision: vision_provider_id set, vision_model_id missing.
        handle_admin_put(
            "/config/vision",
            {"routing_mode": None, "main_model_id": None,
             "vision_provider_id": "primary-anthropic", "vision_model_id": None},
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        opener = _RecordingOpener()
        status, body = self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    def test_partial_vision_model_only_returns_not_configured(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        handle_admin_put(
            "/config/vision",
            {"routing_mode": None, "main_model_id": None,
             "vision_provider_id": None, "vision_model_id": "claude-opus-4-8"},
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        opener = _RecordingOpener()
        status, body = self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    def test_absent_and_partial_vision_return_identical_generic_result(self) -> None:
        """Absent and both partial pairs return the same generic not_configured."""
        self._seed_main(_builtin_openai(), "gpt-5")
        results: list[str] = []
        for vision_body in (
            {"routing_mode": None, "main_model_id": None,
             "vision_provider_id": None, "vision_model_id": None},
            {"routing_mode": None, "main_model_id": None,
             "vision_provider_id": "primary-anthropic", "vision_model_id": None},
            {"routing_mode": None, "main_model_id": None,
             "vision_provider_id": None, "vision_model_id": "claude-opus-4-8"},
        ):
            handle_admin_put(
                "/config/vision",
                vision_body,
                self.headers,
                self.flags,
                self.env,
                config_store=self.store,
            )
            opener = _RecordingOpener()
            status, body = self._probe({"target": "vision"}, opener=opener)
            self.assertEqual(status, 200)
            results.append(json.dumps(body["data"], sort_keys=True))
        self.assertEqual(len(set(results)), 1)
        self.assertIn("not_configured", results[0])

    # --- Fully configured vision parity with main ---

    def test_configured_vision_probed_same_as_main(self) -> None:
        """Vision target traverses the same SSRF/auth/no-body path as main."""
        self._seed_vision(
            main_provider=_builtin_openai(),
            main_model_id="gpt-5",
            vision_provider=_custom_provider(),
            vision_model_id="local-gpt",
        )
        status, body = self._probe({"target": "vision"})
        self.assertEqual(status, 200)
        self.assertEqual(self.opener.calls[0]["url"], "https://custom.example.com/v1/models")
        result = body["data"]
        self.assertEqual(result["target"], "vision")
        self.assertEqual(result["provider_id"], "custom-endpoint")

    # --- Flag + RBAC gates ---

    def test_flag_off_probe_refused(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"}, flags=flags, opener=opener
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
        self.assertEqual(opener.calls, [])

    def test_admin_and_operator_allowed(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        self._seed_main(_builtin_openai(), "gpt-5")
        for role in (Role.ADMIN, Role.OPERATOR):
            with self.subTest(role=role):
                token = issue_token(secret, role=role, tenant_id="t1")
                headers = {"Authorization": f"Bearer {token}"}
                opener = _RecordingOpener()
                status, body = self._probe(
                    {"target": "main"}, headers=headers, flags=flags, opener=opener,
                    rbac_secret=secret,
                )
                self.assertEqual(status, 200)

    def test_lawyer_and_viewer_denied(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        self._seed_main(_builtin_openai(), "gpt-5")
        for role in (Role.LAWYER, Role.VIEWER):
            with self.subTest(role=role):
                token = issue_token(secret, role=role, tenant_id="t1")
                headers = {"Authorization": f"Bearer {token}"}
                opener = _RecordingOpener()
                status, body = self._probe(
                    {"target": "main"}, headers=headers, flags=flags, opener=opener,
                    rbac_secret=secret,
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")
                self.assertEqual(opener.calls, [])

    # --- No store.save, no response body read, generic result codes ---

    def test_probe_does_not_mutate_store(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        mtime_before = self.store_path.stat().st_mtime
        self._probe({"target": "main"})
        self.assertEqual(self.store_path.stat().st_mtime, mtime_before)

    def test_probe_result_is_generic_status_only(self) -> None:
        """Result contains only generic codes — never body, secret, or header."""
        self._seed_main(_builtin_openai(), "gpt-5")
        status, body = self._probe({"target": "main"})
        self.assertEqual(status, 200)
        blob = json.dumps(body, ensure_ascii=False).lower()
        for forbidden in (
            "planted-openai-key",
            "authorization",
            "bearer",
            "x-api-key",
            "response_body",
            "body",
            "sk-",
        ):
            self.assertNotIn(forbidden, blob)
        self.assertIn(body["data"]["status"], ("ok", "fail", "not_configured"))

    # --- SSRF matrix: scheme, userinfo, redirects, unsafe IP classes ---

    def test_non_https_custom_url_rejected(self) -> None:
        """Custom probe URLs must be HTTPS only.

        The store validation (Plan 76-01) rejects non-HTTPS custom URLs at PUT
        time, so the provider is never persisted. The probe sees an empty store
        and returns not_configured — the URL is never reached.
        """
        provider = _custom_provider()
        provider["api_base_url"] = "http://custom.example.com/v1"
        self._seed_main(provider, "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe({"target": "main"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    def test_url_with_userinfo_rejected(self) -> None:
        """Custom URLs with userinfo are rejected at PUT time by store validation.

        The probe never sees the URL because the provider is not persisted.
        """
        provider = _custom_provider()
        provider["api_base_url"] = "https://user:pass@custom.example.com/v1"
        self._seed_main(provider, "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe({"target": "main"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    def test_redirect_response_makes_zero_credential_forwarding(self) -> None:
        """A redirect response must not forward credentials to a new origin."""
        self._seed_main(_builtin_openai(), "gpt-5")
        opener = _RecordingOpener(redirect=True)
        status, body = self._probe({"target": "main"}, opener=opener)
        # Probe must treat redirect as a failure, not follow it.
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "fail")

    def test_loopback_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_LOOPBACK_ADDR),
            opener=opener,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_private_10_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_PRIVATE_10),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_private_172_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_PRIVATE_172),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_private_192_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_PRIVATE_192),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_link_local_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_LINK_LOCAL),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_multicast_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_MULTICAST),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_reserved_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_RESERVED),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    def test_unspecified_address_makes_zero_opener_calls(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        opener = _RecordingOpener()
        status, body = self._probe(
            {"target": "main"},
            resolver=_resolver_returning(_UNSPECIFIED),
            opener=opener,
        )
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    # --- Auth dialect headers ---

    def test_openai_probe_uses_bearer_header(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        status, body = self._probe({"target": "main"})
        headers = self.opener.calls[0]["headers"]
        auth = headers.get("Authorization") or headers.get("authorization")
        self.assertIsNotNone(auth)
        self.assertTrue(auth.startswith("Bearer "))
        # Never log the resolved key in the response.
        self.assertNotIn("planted-openai-key", json.dumps(body))

    def test_custom_probe_uses_bearer_header(self) -> None:
        self._seed_main(_custom_provider(), "local-gpt")
        self._probe({"target": "main"})
        headers = self.opener.calls[0]["headers"]
        auth = headers.get("Authorization") or headers.get("authorization")
        self.assertIsNotNone(auth)
        self.assertTrue(auth.startswith("Bearer "))

    def test_anthropic_probe_uses_x_api_key_and_version_header(self) -> None:
        self._seed_main(_builtin_anthropic(), "claude-opus-4-8")
        self._probe({"target": "main"})
        headers = self.opener.calls[0]["headers"]
        api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
        self.assertIsNotNone(api_key)
        version = headers.get("anthropic-version") or headers.get("Anthropic-Version")
        self.assertEqual(version, "2023-06-01")
        # Anthropic must NOT use Bearer.
        auth = headers.get("Authorization") or headers.get("authorization")
        self.assertIsNone(auth)

    # --- Missing ref fail-closed ---

    def test_missing_api_key_ref_fail_closes_without_network(self) -> None:
        """Blank api_key_ref → fail result without any opener call."""
        provider = _builtin_openai()
        provider["api_key_ref"] = None
        self._seed_main(provider, "gpt-5")
        opener = _RecordingOpener()
        # Remove the env key so resolution fails.
        env = dict(self.env)
        env.pop("OPENAI_API_KEY", None)
        handle_config_probe = _try_import_probe()
        if handle_config_probe is None:
            self.fail(
                "PROV-04: admin_console_api.probe.handle_config_probe not "
                "implemented (Plan 76-03)"
            )
        status, body = handle_config_probe(
            "/config/providers/probe",
            {"target": "main"},
            self.headers,
            self.flags,
            env,
            config_store=self.store,
            rbac_secret=None,
            resolver=self.resolver,
            opener=opener,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "fail")
        self.assertEqual(opener.calls, [])

    # --- No live acceptance claim ---

    def test_probe_response_does_not_claim_live_acceptance(self) -> None:
        self._seed_main(_builtin_openai(), "gpt-5")
        status, body = self._probe({"target": "main"})
        self.assertEqual(status, 200)
        blob = json.dumps(body, ensure_ascii=False).lower()
        for forbidden in (
            "lawyer trial acceptance complete",
            "live wecom uat passed",
            "live qq openapi acceptance",
            "live provider reachability",
        ):
            self.assertNotIn(forbidden, blob)


class ConfigProbeVisionRoutingModeTests(unittest.TestCase):
    """VIS-01 (Plan 77-02): vision probe integration after a routing_mode save.

    Proves that the existing Phase 76 vision probe path continues to resolve
    the stored vision pair after a Phase 77 routing_mode save, that
    ``main_only`` with no vision pair returns ``not_configured`` with zero
    side effects, and that a partial vision pair under ``auto`` is rejected at
    PUT time so the probe is never reached (validation gates probe availability).
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store_path = Path(self._tmpdir.name) / "operator-config.json"
        self.store = OperatorConfigStore(self.store_path)
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
        )
        self.env = {
            "ADMIN_API_TOKEN": "test-token",
            "OPENAI_API_KEY": "planted-openai-key-NEVER-LOGGED",
            "ANTHROPIC_API_KEY": "planted-anthropic-key-NEVER-LOGGED",
        }
        self.headers = {"Authorization": "Bearer test-token"}
        self.resolver = _resolver_returning(_PUBLIC_ADDR)
        self.opener = _RecordingOpener()

    def _put(self, path: str, body: Any) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            path,
            body,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )

    def _probe(
        self,
        body: dict[str, Any],
        *,
        resolver: Callable[..., list] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        handle_config_probe = _try_import_probe()
        if handle_config_probe is None:
            self.fail(
                "PROV-04: admin_console_api.probe.handle_config_probe not "
                "implemented (Plan 76-03)"
            )
        return handle_config_probe(
            "/config/providers/probe",
            body,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
            rbac_secret=None,
            resolver=resolver or self.resolver,
            opener=opener or self.opener,
        )

    def _seed_registry_and_catalog(self) -> None:
        """Seed providers + catalog so a complete vision pair can resolve."""
        self._put("/config/providers", [_builtin_openai(), _builtin_anthropic()])
        self._put(
            "/config/catalog",
            _catalog("primary-openai", "gpt-5"),
        )

    # --- Vision probe after routing_mode="auto" save with complete pair ---

    def test_vision_probe_after_auto_save_resolves_stored_vision_pair(self) -> None:
        self._seed_registry_and_catalog()
        put_status, _ = self._put(
            "/config/vision",
            {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
            },
        )
        self.assertEqual(put_status, 200)
        opener = _RecordingOpener()
        status, body = self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(opener.calls[0]["url"], _ANTHROPIC_CANONICAL_URL + "/models")
        result = body["data"]
        self.assertIn(result["status"], ("ok", "fail"))
        self.assertEqual(result["target"], "vision")
        self.assertEqual(result["provider_id"], "primary-anthropic")
        self.assertEqual(result["model_id"], "claude-opus-4-8")
        # No-body / no-secret invariant preserved.
        blob = json.dumps(body, ensure_ascii=False).lower()
        self.assertNotIn("planted-anthropic-key", blob)
        self.assertNotIn("authorization", blob)

    def test_vision_probe_after_auto_save_calls_opener_once(self) -> None:
        self._seed_registry_and_catalog()
        self._put(
            "/config/vision",
            {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
            },
        )
        opener = _RecordingOpener()
        self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(len(opener.calls), 1)

    def test_vision_probe_after_auto_save_uses_anthropic_auth_dialect(self) -> None:
        self._seed_registry_and_catalog()
        self._put(
            "/config/vision",
            {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
            },
        )
        opener = _RecordingOpener()
        self._probe({"target": "vision"}, opener=opener)
        headers = opener.calls[0]["headers"]
        api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
        self.assertIsNotNone(api_key)
        version = headers.get("anthropic-version") or headers.get("Anthropic-Version")
        self.assertEqual(version, "2023-06-01")
        auth = headers.get("Authorization") or headers.get("authorization")
        self.assertIsNone(auth)

    # --- Vision probe after routing_mode="main_only" with no vision pair ---

    def test_vision_probe_after_main_only_save_returns_not_configured(self) -> None:
        self._seed_registry_and_catalog()
        put_status, _ = self._put(
            "/config/vision",
            {
                "routing_mode": "main_only",
                "main_model_id": "gpt-5",
                "vision_provider_id": None,
                "vision_model_id": None,
            },
        )
        self.assertEqual(put_status, 200)
        opener = _RecordingOpener()
        resolver = _resolver_returning(_PUBLIC_ADDR)
        status, body = self._probe(
            {"target": "vision"}, resolver=resolver, opener=opener
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    # --- Partial vision pair under auto rejected at PUT time (probe never reached)

    def test_partial_vision_pair_under_auto_rejected_at_put_time(self) -> None:
        """Plan 77-01 validation rejects auto + partial pair; probe never reached."""
        self._seed_registry_and_catalog()
        put_status, put_body = self._put(
            "/config/vision",
            {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": None,
            },
        )
        self.assertEqual(put_status, 400)
        self.assertEqual(put_body["error"]["code"], "invalid_config")
        # The partial pair was not persisted, so a vision probe sees no pair.
        opener = _RecordingOpener()
        status, body = self._probe({"target": "vision"}, opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "not_configured")
        self.assertEqual(opener.calls, [])

    # --- Vision probe does not mutate the store after a routing_mode save ---

    def test_vision_probe_after_auto_save_does_not_mutate_store(self) -> None:
        self._seed_registry_and_catalog()
        self._put(
            "/config/vision",
            {
                "routing_mode": "auto",
                "main_model_id": "gpt-5",
                "vision_provider_id": "primary-anthropic",
                "vision_model_id": "claude-opus-4-8",
            },
        )
        mtime_before = self.store_path.stat().st_mtime
        self._probe({"target": "vision"})
        self.assertEqual(self.store_path.stat().st_mtime, mtime_before)


if __name__ == "__main__":
    unittest.main()
