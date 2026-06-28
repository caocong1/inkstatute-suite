from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.boundary_checks import (
    BoundaryAllowlistPolicy,
    assert_neutral_boundary_allowlist,
)
from contract_test_suite.paths import REPO_ROOT


class BoundaryAllowlistTests(unittest.TestCase):
    def test_allows_backend_mode_enum_values(self) -> None:
        policy = BoundaryAllowlistPolicy()
        path = REPO_ROOT / "packages/platform-contract/src/platform_contract/agent_adapter.py"

        self.assertTrue(policy.is_concrete_name_allowed(path, "hermes", REPO_ROOT))
        self.assertTrue(policy.is_concrete_name_allowed(path, "codex", REPO_ROOT))
        self.assertTrue(policy.is_concrete_name_allowed(path, "provider_model", REPO_ROOT))
        assert_neutral_boundary_allowlist(REPO_ROOT)

    def test_allows_channel_enum_values(self) -> None:
        policy = BoundaryAllowlistPolicy()
        path = REPO_ROOT / "packages/platform-contract/src/platform_contract/enums.py"

        for name in ("wecom", "qqbot", "web", "desktop"):
            self.assertTrue(policy.is_concrete_name_allowed(path, name, REPO_ROOT))

    def test_allows_architecture_examples_and_concrete_package_contexts(self) -> None:
        policy = BoundaryAllowlistPolicy()

        self.assertTrue(
            policy.is_concrete_name_allowed(
                REPO_ROOT / "docs/architecture/adr/ADR-0007-boundary-scan-allowlist.md",
                "lawfirm",
                REPO_ROOT,
            )
        )
        self.assertTrue(
            policy.is_concrete_name_allowed(
                REPO_ROOT / "packages/channels/wecom/adapter.py",
                "wecom",
                REPO_ROOT,
            )
        )
        self.assertTrue(
            policy.is_concrete_name_allowed(
                REPO_ROOT / "packages/backends/hermes/adapter.py",
                "hermes",
                REPO_ROOT,
            )
        )

    def test_rejects_non_allowlisted_concrete_names_in_neutral_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = _neutral_source_path(root, "bad.py")
            source.write_text('BACKEND = "hermes"\n', encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "concrete_name_not_allowlisted"):
                assert_neutral_boundary_allowlist(root)

    def test_rejects_private_hermes_paths_in_neutral_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = _neutral_source_path(root, "bad.py")
            source.write_text('PROFILE_PATH = "~/.hermes/profiles/lawfirm"\n', encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "private_hermes_path"):
                assert_neutral_boundary_allowlist(root)

    def test_rejects_wecom_payload_internals_in_neutral_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = _neutral_source_path(root, "bad.py")
            source.write_text('payload_field = "ToUserName"\n', encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "wecom_payload_internal"):
                assert_neutral_boundary_allowlist(root)

    def test_rejects_raw_payload_but_allows_raw_payload_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = _fixture_path(root, "fixture.json")
            fixture.write_text(json.dumps({"raw_payload": "blocked"}), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "raw_payload_field"):
                assert_neutral_boundary_allowlist(root)

            fixture.write_text(json.dumps({"raw_payload_ref": "fixture://raw/example"}), encoding="utf-8")
            assert_neutral_boundary_allowlist(root)

    def test_rejects_plaintext_secret_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = _fixture_path(root, "fixture.json")
            secret_like_value = "sk-" + "1234567890abcdefghijklmnop"
            fixture.write_text(json.dumps({"api_key": secret_like_value}), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "secret_value"):
                assert_neutral_boundary_allowlist(root)

    def test_rejects_runtime_db_log_and_media_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = _fixture_path(root, "fixture.json")
            fixture.write_text(json.dumps({"status_ref": "logs/runtime.log"}), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "runtime_artifact_path"):
                assert_neutral_boundary_allowlist(root)

    def test_rejects_legal_required_top_level_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            schema = _schema_path(root, "bad.schema.json")
            schema.write_text(
                json.dumps(
                    {
                        "title": "BadNeutralSchema",
                        "type": "object",
                        "properties": {"jurisdiction": {"type": "string"}},
                        "required": ["jurisdiction"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AssertionError, "forbidden_required_field"):
                assert_neutral_boundary_allowlist(root)


def _neutral_source_path(root: Path, filename: str) -> Path:
    source_dir = root / "packages/platform-contract/src/platform_contract"
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir / filename


def _schema_path(root: Path, filename: str) -> Path:
    schema_dir = root / "packages/platform-contract/src/platform_contract/schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    return schema_dir / filename


def _fixture_path(root: Path, filename: str) -> Path:
    fixture_dir = root / "packages/platform-contract/fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    return fixture_dir / filename


if __name__ == "__main__":
    unittest.main()
