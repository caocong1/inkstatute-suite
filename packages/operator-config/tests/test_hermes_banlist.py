"""CFG-03: Hermes filesystem/profile authority rejected by validate_document."""

from __future__ import annotations

import unittest
from pathlib import Path

from inkstatute_operator_config import (
    OperatorConfigValidator as PublicValidator,
    ValidationIssue as PublicIssue,
    validate_document as public_validate_document,
)
from inkstatute_operator_config.errors import OperatorConfigValidationError
from inkstatute_operator_config.schemas import (
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    WeComChannelDoc,
)
from inkstatute_operator_config.validate import (
    FORBIDDEN_HERMES_FIELD_NAMES,
    FORBIDDEN_PATH_SUBSTRINGS,
    OperatorConfigValidator,
    validate_document,
)

_PKG_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "inkstatute_operator_config"
)

# Path / field matrix from RESEARCH + PLAN (CFG-03).
_FORBIDDEN_PATH_CASES = (
    ("tilde_hermes", "~/.hermes/profiles/lawfirm"),
    ("slash_dot_hermes", "/home/ops/.hermes/config.yaml"),
    ("dot_hermes_slash", "relative/.hermes/profiles/x"),
    ("windows_backslash_hermes", "C:\\Users\\ops\\.hermes\\profiles\\lawfirm"),
    ("bare_hermes_dir", "/var/lib/.hermes"),
)

_FORBIDDEN_FIELD_CASES = (
    "hermes_home",
    "hermes_profile_path",
    "hermes_config_path",
    "profile_filesystem_path",
)


class TestHermesBanlist(unittest.TestCase):
    def test_default_document_passes(self) -> None:
        issues = validate_document(OperatorConfigDocument())
        self.assertEqual(issues, [])

    def test_public_exports_include_validator_surface(self) -> None:
        self.assertIs(public_validate_document, validate_document)
        self.assertIs(PublicValidator, OperatorConfigValidator)
        self.assertTrue(issubclass(PublicIssue, object))

    def test_banlist_constants_cover_research_needles(self) -> None:
        joined = " ".join(FORBIDDEN_PATH_SUBSTRINGS)
        self.assertIn("~/.hermes", joined)
        self.assertIn("/.hermes", joined)
        self.assertIn(".hermes/", joined)
        for name in _FORBIDDEN_FIELD_CASES:
            self.assertIn(name, FORBIDDEN_HERMES_FIELD_NAMES)

    def test_rejects_hermes_path_substrings_in_metadata(self) -> None:
        for label, planted in _FORBIDDEN_PATH_CASES:
            with self.subTest(label=label):
                doc = OperatorConfigDocument(
                    channels=ChannelsDoc(
                        qqbot=QQBotChannelDoc(metadata={"profile_hint": planted}),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                message = str(ctx.exception)
                self.assertNotIn(planted, message)
                issues = OperatorConfigValidator().validate(doc)
                codes = {i.code for i in issues}
                self.assertIn("hermes_path_forbidden", codes)

    def test_rejects_forbidden_hermes_field_names_in_metadata(self) -> None:
        for field_name in _FORBIDDEN_FIELD_CASES:
            with self.subTest(field=field_name):
                doc = OperatorConfigDocument(
                    channels=ChannelsDoc(
                        wecom=WeComChannelDoc(
                            metadata={field_name: "/var/inkstatute/config.json"}
                        ),
                    )
                )
                with self.assertRaises(OperatorConfigValidationError) as ctx:
                    validate_document(doc)
                self.assertNotIn("/var/inkstatute/config.json", str(ctx.exception))
                issues = OperatorConfigValidator().validate(doc)
                codes = {i.code for i in issues}
                self.assertIn("hermes_field_forbidden", codes)

    def test_rejects_nested_hermes_authority_in_provider_metadata(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    metadata={
                        "nested": {
                            "hermes_profile_path": "~/.hermes/profiles/lawfirm",
                        }
                    },
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError):
            validate_document(doc)
        issues = OperatorConfigValidator().validate(doc)
        codes = {i.code for i in issues}
        self.assertTrue(
            {"hermes_field_forbidden", "hermes_path_forbidden"} & codes
        )

    def test_rejects_hermes_path_in_non_metadata_string_field(self) -> None:
        doc = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    api_base_url="file://~/.hermes/profiles/lawfirm",
                ),
            )
        )
        with self.assertRaises(OperatorConfigValidationError) as ctx:
            validate_document(doc)
        self.assertNotIn("~/.hermes", str(ctx.exception))

    def test_package_src_has_no_hermes_home_writer(self) -> None:
        """Ban-list constants may mention hermes; Path.home() writers must not."""
        offenders: list[str] = []
        for path in sorted(_PKG_SRC.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "Path.home()" in text:
                offenders.append(f"{path.name}: Path.home()")
            # Writer-style join of home + .hermes (not ban-list string literals alone).
            if "Path.home()" in text and ".hermes" in text:
                offenders.append(f"{path.name}: Path.home()+.hermes writer")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
