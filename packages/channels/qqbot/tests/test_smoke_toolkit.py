"""Wave 0 + Plans 01–03 coverage for the QQBot one-click smoke toolkit.

Classes map to SMOKE-01..04. Plan 01 greens dry-run classes; Plan 02 greens
evidence/runbook; Plan 03 greens live fail-closed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke_test.py"
RUNBOOK_PATH = REPO_ROOT / "runbook" / "SMOKE_TEST_RUNBOOK.md"
FIXTURE_INTERACTION = (
    REPO_ROOT / "packages" / "channels" / "qqbot" / "fixtures" / "qqbot_interaction_create.json"
)

# Public DEMO BotSecret (official docs) — must not appear in sanitized evidence.
DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"

_REQUIRED_RUNBOOK_HEADINGS = (
    "credential",
    "dry-run",
    "live",
    "expected",
    "evidence",
)


def _load_smoke_module():
    """Load scripts/smoke_test.py as a module (path bootstrap inside the script)."""
    if not SMOKE_SCRIPT.is_file():
        raise FileNotFoundError(f"missing smoke CLI: {SMOKE_SCRIPT}")
    spec = importlib.util.spec_from_file_location("inkstatute_smoke_test", SMOKE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["inkstatute_smoke_test"] = module
    spec.loader.exec_module(module)
    return module


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    # Strip live credential env so dry-run / fail-closed tests are hermetic.
    for key in list(merged):
        if key.startswith("INKSTATUTE_QQBOT_"):
            if env is None or key not in env:
                merged.pop(key, None)
    return subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


class TestDryRunNoNetwork(unittest.TestCase):
    """SMOKE-02: dry-run uses Fake transports; no live host / env required."""

    def test_dry_run_cli_exits_zero(self) -> None:
        result = _run_cli("--dry-run")
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_dry_run_uses_fake_transports_only(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        evidence = outcome["evidence"]
        self.assertEqual(evidence.get("mode"), "dry-run")
        self.assertTrue(evidence.get("not_live_acceptance", True))
        self.assertEqual(outcome.get("transport"), "fake")
        self.assertNotIn("UrllibMessageTransport", outcome.get("transport_class", ""))
        self.assertNotIn("UrllibTokenTransport", outcome.get("token_transport_class", ""))
        # Fake path must not require live credential env vars.
        for key in (
            "INKSTATUTE_QQBOT_APP_ID",
            "INKSTATUTE_QQBOT_CLIENT_SECRET",
            "INKSTATUTE_QQBOT_BOT_SECRET",
        ):
            self.assertNotIn(key, os.environ)


class TestDryRunEgress(unittest.TestCase):
    """SMOKE-01: text msg_type=0 and keyboard msg_type=2 recorded ok."""

    def test_text_and_keyboard_steps_ok(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        steps = outcome["evidence"]["steps"]
        self.assertTrue(steps["send_text"]["ok"])
        self.assertEqual(steps["send_text"]["msg_type"], 0)
        self.assertTrue(steps["send_keyboard"]["ok"])
        self.assertEqual(steps["send_keyboard"]["msg_type"], 2)
        actions = steps["send_keyboard"].get("actions") or []
        self.assertIn("up", actions)
        self.assertIn("down", actions)
        self.assertGreaterEqual(outcome.get("fake_send_count", 0), 2)


class TestDryRunCallback(unittest.TestCase):
    """SMOKE-01: fixture INTERACTION → normalize + idempotency_key; no ACK PUT."""

    def test_fixture_interaction_normalized(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run", callback_json=FIXTURE_INTERACTION)
        steps = outcome["evidence"]["steps"]
        self.assertTrue(steps["callback"]["ok"])
        self.assertEqual(steps["callback"].get("status"), "normalized")
        self.assertTrue(steps["callback"].get("idempotency_key_present"))
        self.assertEqual(outcome.get("callback_put_count", 0), 0)


class TestEvidenceSanitized(unittest.TestCase):
    """SMOKE-04: serialized evidence must not leak secrets, tokens, raw content, URLs."""

    def test_sanitize_removes_ban_list(self) -> None:
        smoke = _load_smoke_module()
        self.assertTrue(
            hasattr(smoke, "sanitize_evidence"),
            "sanitize_evidence helper required (Plan 02)",
        )
        dirty = {
            "Authorization": "QQBot fixture-token",
            "access_token": "fixture-token",
            "bot_secret": DEMO_BOT_SECRET,
            "client_secret": "fixture-secret",
            "content": "raw user legal payload should not leak",
            "attachment_url": "https://example.com/file.pdf",
            "nested": {
                "url": "http://cdn.example/a.bin",
                "access_token": "nested-tok",
                "note": "leaked fixture-secret under allowlisted key",
            },
        }
        clean = smoke.sanitize_evidence(dirty)
        serialized = json.dumps(clean, ensure_ascii=False)
        banned = (
            "Authorization",
            "access_token",
            DEMO_BOT_SECRET,
            "fixture-token",
            "fixture-secret",
            "raw user legal payload",
            "https://",
            "http://",
        )
        for token in banned:
            self.assertNotIn(token, serialized, msg=f"banned token still present: {token!r}")


class TestEvidenceSchema(unittest.TestCase):
    """SMOKE-04: evidence schema stamps mode, not_live_acceptance, step ok flags."""

    def test_dry_run_evidence_schema(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        evidence = smoke.sanitize_evidence(outcome["evidence"])
        self.assertEqual(evidence.get("schema"), "inkstatute.qqbot.smoke_evidence.v1")
        self.assertEqual(evidence.get("mode"), "dry-run")
        self.assertIs(evidence.get("not_live_acceptance"), True)
        steps = evidence["steps"]
        for name in (
            "signature",
            "send_text",
            "send_keyboard",
            "callback",
            "adapter_ack",
            "session_ingress",
            "adapter_deliver",
        ):
            self.assertIn(name, steps)
            self.assertTrue(steps[name].get("ok"), msg=f"step {name} not ok")


class TestProtocolEvidenceSanitized(unittest.TestCase):
    """SMOKE-02: Protocol-path evidence allowlist + sanitization."""

    _PROTOCOL_STEPS = ("adapter_ack", "session_ingress", "adapter_deliver")
    _ACK_KEYS = frozenset({"ok", "http_status", "op", "accepted"})
    _INGRESS_KEYS = frozenset({"ok", "ingress_action", "run_id_present", "branch"})
    _DELIVER_KEYS = frozenset({"ok", "deliver_accepted", "boundary_action"})

    def test_schema_stamps_protocol_steps(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        evidence = smoke.sanitize_evidence(outcome["evidence"])
        self.assertEqual(evidence.get("schema"), "inkstatute.qqbot.smoke_evidence.v1")
        self.assertEqual(evidence.get("mode"), "dry-run")
        self.assertIs(evidence.get("not_live_acceptance"), True)
        steps = evidence["steps"]
        for name in self._PROTOCOL_STEPS:
            self.assertIn(name, steps)
            self.assertTrue(steps[name].get("ok"))
        # Full RESEARCH allowlist keys must survive sanitize (not ok-only).
        ack = steps["adapter_ack"]
        self.assertEqual(set(ack.keys()), self._ACK_KEYS)
        self.assertIn("http_status", ack)
        self.assertIn("op", ack)
        self.assertIn("accepted", ack)
        ingress = steps["session_ingress"]
        self.assertEqual(set(ingress.keys()), self._INGRESS_KEYS)
        deliver = steps["adapter_deliver"]
        self.assertEqual(set(deliver.keys()), self._DELIVER_KEYS)

    def test_protocol_dirty_payload_stripped(self) -> None:
        smoke = _load_smoke_module()
        dirty = {
            "schema": "inkstatute.qqbot.smoke_evidence.v1",
            "mode": "dry-run",
            "not_live_acceptance": True,
            "steps": {
                "adapter_ack": {
                    "ok": True,
                    "http_status": 200,
                    "op": 12,
                    "accepted": True,
                    "Authorization": "QQBot fixture-token",
                    "access_token": "fixture-token",
                    "bot_secret": DEMO_BOT_SECRET,
                    "content": "raw legal payload must not leak",
                    "body": '{"secret":true}',
                    "calls": [{"url": "https://api.example/v2/users"}],
                },
                "session_ingress": {
                    "ok": True,
                    "ingress_action": "accepted",
                    "run_id_present": True,
                    "branch": "message",
                    "url": "http://cdn.example/a.bin",
                    "payload": {"openid": "should-drop"},
                },
                "adapter_deliver": {
                    "ok": True,
                    "deliver_accepted": True,
                    "boundary_action": "allow",
                    "envelope": {"content": "nope"},
                    "client_secret": "fixture-secret",
                },
            },
        }
        clean = smoke.sanitize_evidence(dirty)
        serialized = json.dumps(clean, ensure_ascii=False)
        banned = (
            "Authorization",
            "access_token",
            DEMO_BOT_SECRET,
            "fixture-token",
            "fixture-secret",
            "raw legal payload",
            "https://",
            "http://",
            "should-drop",
        )
        for token in banned:
            self.assertNotIn(token, serialized, msg=f"banned token still present: {token!r}")
        steps = clean["steps"]
        self.assertEqual(set(steps["adapter_ack"].keys()), self._ACK_KEYS)
        self.assertEqual(set(steps["session_ingress"].keys()), self._INGRESS_KEYS)
        self.assertEqual(set(steps["adapter_deliver"].keys()), self._DELIVER_KEYS)
        self.assertIs(clean.get("not_live_acceptance"), True)


class TestRunbookExists(unittest.TestCase):
    """SMOKE-03: runbook/SMOKE_TEST_RUNBOOK.md with required section headings."""

    def test_runbook_file_and_sections(self) -> None:
        self.assertTrue(
            RUNBOOK_PATH.is_file(),
            f"missing runbook: {RUNBOOK_PATH}",
        )
        text = RUNBOOK_PATH.read_text(encoding="utf-8").lower()
        for heading in _REQUIRED_RUNBOOK_HEADINGS:
            self.assertIn(heading, text, msg=f"runbook missing section cue: {heading!r}")


class TestProtocolPathDryRun(unittest.TestCase):
    """SMOKE-01: dry-run must exercise host Protocol path (Phase 71)."""

    _PROTOCOL_STEPS = ("adapter_ack", "session_ingress", "adapter_deliver")

    def test_dry_run_evidence_includes_protocol_steps(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        steps = outcome["evidence"]["steps"]
        for name in self._PROTOCOL_STEPS:
            self.assertIn(name, steps, msg=f"missing Protocol step: {name}")
            self.assertTrue(steps[name].get("ok"), msg=f"Protocol step {name} not ok")

    def test_dry_run_uses_host_webhook_helpers(self) -> None:
        source = SMOKE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("handle_qqbot_webhook_request", source)
        self.assertIn("build_qqbot_wired_runtime", source)
        self.assertRegex(
            source,
            r"from qqbot_service\.webhook import|qqbot_service\.webhook",
        )
        self.assertRegex(
            source,
            r"from qqbot_service\.wiring import|qqbot_service\.wiring",
        )

    def test_dry_run_fake_only_no_urllib(self) -> None:
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        self.assertEqual(outcome.get("transport"), "fake")
        self.assertTrue(
            str(outcome.get("transport_class", "")).startswith("Fake"),
            msg=f"expected Fake* message transport, got {outcome.get('transport_class')!r}",
        )
        self.assertTrue(
            str(outcome.get("token_transport_class", "")).startswith("Fake"),
            msg=f"expected Fake* token transport, got {outcome.get('token_transport_class')!r}",
        )
        self.assertNotIn("Urllib", str(outcome.get("transport_class", "")))
        self.assertNotIn("Urllib", str(outcome.get("token_transport_class", "")))
        # Dry-run branch must not construct Urllib* (live path may still import symbols).
        source = SMOKE_SCRIPT.read_text(encoding="utf-8")
        # Isolate dry-run function body roughly: between run_smoke dry branch and _run_smoke_live.
        dry_marker = 'if mode == "live":'
        live_def = "def _run_smoke_live("
        dry_start = source.find("def run_smoke(")
        live_start = source.find(live_def)
        self.assertGreater(dry_start, -1)
        self.assertGreater(live_start, dry_start)
        dry_section = source[dry_start:live_start]
        self.assertNotIn("UrllibMessageTransport(", dry_section)
        self.assertNotIn("UrllibTokenTransport(", dry_section)
        self.assertIn(dry_marker, dry_section)

    def test_protocol_path_required_for_success(self) -> None:
        """Leaf-only evidence is insufficient — Protocol steps must be ok for success."""
        smoke = _load_smoke_module()
        outcome = smoke.run_smoke(mode="dry-run")
        steps = outcome["evidence"]["steps"]
        protocol_ok = all(
            isinstance(steps.get(name), dict) and steps[name].get("ok") is True
            for name in self._PROTOCOL_STEPS
        )
        self.assertTrue(
            protocol_ok,
            "dry-run success requires adapter_ack/session_ingress/adapter_deliver ok "
            "(leaf steps alone are insufficient)",
        )


class TestProtocolPathCiHonesty(unittest.TestCase):
    """SMOKE-01/02 closure: CI dry-run honesty + runbook Protocol documentation."""

    def test_cli_dry_run_exits_zero(self) -> None:
        result = _run_cli("--dry-run")
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence.get("mode"), "dry-run")
        self.assertIs(evidence.get("not_live_acceptance"), True)
        for name in ("adapter_ack", "session_ingress", "adapter_deliver"):
            self.assertTrue(evidence["steps"][name].get("ok"), msg=name)

    def test_source_imports_host_helpers(self) -> None:
        source = SMOKE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("qqbot_service.webhook", source)
        self.assertIn("qqbot_service.wiring", source)
        self.assertIn("handle_qqbot_webhook_request", source)
        self.assertIn("build_qqbot_wired_runtime", source)
        self.assertIn("adapter_ack", source)
        self.assertIn("session_ingress", source)
        self.assertIn("adapter_deliver", source)
        # Dry-run must not construct Urllib* (live path may still reference symbols).
        dry_start = source.find("def run_smoke(")
        live_start = source.find("def _run_smoke_live(")
        self.assertGreater(dry_start, -1)
        self.assertGreater(live_start, dry_start)
        dry_section = source[dry_start:live_start]
        self.assertNotIn("UrllibMessageTransport(", dry_section)
        self.assertNotIn("UrllibTokenTransport(", dry_section)

    def test_runbook_documents_protocol_path(self) -> None:
        self.assertTrue(RUNBOOK_PATH.is_file(), f"missing runbook: {RUNBOOK_PATH}")
        text = RUNBOOK_PATH.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("verify_and_ack", lower)
        self.assertIn("ingress", lower)
        self.assertIn("deliver", lower)
        self.assertIn("protocol", lower)
        self.assertIn("not_live_acceptance", lower)
        self.assertIn("adapter_ack", lower)
        self.assertIn("session_ingress", lower)
        self.assertIn("adapter_deliver", lower)

    def test_callback_json_fixture_still_dry_run_safe(self) -> None:
        result = _run_cli("--dry-run", "--callback-json", str(FIXTURE_INTERACTION))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        evidence = json.loads(result.stdout)
        self.assertIs(evidence.get("not_live_acceptance"), True)
        self.assertTrue(evidence["steps"]["callback"].get("ok"))
        self.assertTrue(evidence["steps"]["callback"].get("ack_skipped", True))


class TestLiveEnvFailClosed(unittest.TestCase):
    """SMOKE-01 live gate: --live without env exits non-zero; no secret echo."""

    def test_live_without_env_fails_closed(self) -> None:
        # Plant a fake secret in env that must never be printed if partially read.
        planted = "SUPER_SECRET_SHOULD_NOT_PRINT_9f3a"
        result = _run_cli(
            "--live",
            env={
                # Intentionally incomplete — fail closed before any network.
                "INKSTATUTE_QQBOT_APP_ID": planted,
            },
        )
        self.assertNotEqual(result.returncode, 0)
        combined = (result.stdout or "") + (result.stderr or "")
        self.assertNotIn(planted, combined)
        self.assertNotIn(DEMO_BOT_SECRET, combined)
        # Missing-key message names keys only (never values).
        self.assertIn("INKSTATUTE_QQBOT_CLIENT_SECRET", combined)
        self.assertIn("INKSTATUTE_QQBOT_BOT_SECRET", combined)
        self.assertIn("INKSTATUTE_QQBOT_USER_OPENID", combined)
        self.assertIn("INKSTATUTE_QQBOT_REPLY_MSG_ID", combined)
        self.assertNotIn("Authorization", combined)

    def test_load_live_credentials_helper_and_urllib_wiring(self) -> None:
        """Plan 03: named loader + Urllib transports only behind validated --live."""
        smoke = _load_smoke_module()
        self.assertTrue(
            hasattr(smoke, "load_live_credentials"),
            "load_live_credentials required for live fail-closed env injection",
        )
        source = SMOKE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("UrllibTokenTransport", source)
        self.assertIn("UrllibMessageTransport", source)
        self.assertIn("ack_interaction", source)
        self.assertNotIn("wecom_service", source)
        # ADAPTER-03/04: smoke orchestrator stays QQ-only (Task 2 regression cue).
        self.assertEqual(source.count("wecom_service"), 0)
        # Cleared env must fail closed via the named loader (no network).
        saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("INKSTATUTE_QQBOT_")}
        try:
            with self.assertRaises(SystemExit) as ctx:
                smoke.load_live_credentials()
            msg = str(ctx.exception)
            self.assertIn("INKSTATUTE_QQBOT_APP_ID", msg)
            for value in saved.values():
                self.assertNotIn(value, msg)
        finally:
            os.environ.update(saved)


if __name__ == "__main__":
    unittest.main()
