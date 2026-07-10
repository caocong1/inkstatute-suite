"""Operator config document validation: Hermes ban-list + refs-only (CFG-01/03).

Fail-closed validators. Error messages never echo rejected secret values.
Does not write to disk and does not treat Hermes filesystem as config authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from .errors import OperatorConfigValidationError
from .schemas import OperatorConfigDocument
from .secrets import InvalidSecretRefError, normalize_config_secret_ref

__all__ = [
    "OperatorConfigValidator",
    "ValidationIssue",
    "validate_document",
]

# CFG-03 — Hermes filesystem / profile authority (RESEARCH + PLAN).
FORBIDDEN_PATH_SUBSTRINGS: tuple[str, ...] = (
    "/.hermes",
    "~/.hermes",
    ".hermes/",
    "\\.hermes",
)

FORBIDDEN_HERMES_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "hermes_home",
        "hermes_profile_path",
        "hermes_config_path",
        "profile_filesystem_path",
    }
)

# CFG-01 — raw credential / payload keys (require *_ref instead).
FORBIDDEN_RAW_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "token",
        "password",
        "bot_secret",
        "raw_payload",
        "raw_body",
        "secret",
        "private_key",
    }
)

_SECRET_MARKER_RE = re.compile(
    r"(sk-|secret\s*=|password\s*=|bearer\s+[A-Za-z0-9_\-]{16,})",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Structured validation finding (messages must not echo secrets)."""

    path: str
    code: str
    message: str
    severity: str = "error"


class OperatorConfigValidator:
    """Validate an ``OperatorConfigDocument`` against refs-only + Hermes bans."""

    def validate(self, doc: OperatorConfigDocument) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        issues.extend(self._check_credential_refs(doc))
        issues.extend(self._walk_value("", asdict(doc)))
        return issues

    def _check_credential_refs(
        self, doc: OperatorConfigDocument
    ) -> list[ValidationIssue]:
        pairs: list[tuple[str, str | None]] = [
            ("channels.qqbot.app_id_ref", doc.channels.qqbot.app_id_ref),
            ("channels.qqbot.app_secret_ref", doc.channels.qqbot.app_secret_ref),
            ("channels.qqbot.token_secret_ref", doc.channels.qqbot.token_secret_ref),
            ("channels.qqbot.bot_secret_ref", doc.channels.qqbot.bot_secret_ref),
            ("channels.wecom.token_secret_ref", doc.channels.wecom.token_secret_ref),
            (
                "channels.wecom.encoding_aes_key_secret_ref",
                doc.channels.wecom.encoding_aes_key_secret_ref,
            ),
            ("channels.wecom.corp_id_ref", doc.channels.wecom.corp_id_ref),
        ]
        for index, provider in enumerate(doc.providers):
            pairs.append(
                (f"providers[{index}].api_key_ref", provider.api_key_ref)
            )
        issues: list[ValidationIssue] = []
        for path, value in pairs:
            try:
                normalize_config_secret_ref(value, field=path)
            except InvalidSecretRefError:
                issues.append(
                    ValidationIssue(
                        path=path,
                        code="invalid_secret_ref",
                        message=f"invalid secret reference shape for {path}",
                        severity="error",
                    )
                )
        return issues

    def _walk_value(self, path: str, value: object) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_str = str(key)
                child_path = f"{path}.{key_str}" if path else key_str
                key_lower = key_str.lower()
                if key_lower in FORBIDDEN_HERMES_FIELD_NAMES:
                    issues.append(
                        ValidationIssue(
                            path=child_path,
                            code="hermes_field_forbidden",
                            message=(
                                f"field {key_str!r} asserts Hermes filesystem "
                                "authority and is forbidden"
                            ),
                            severity="error",
                        )
                    )
                if key_lower in FORBIDDEN_RAW_SECRET_KEYS:
                    issues.append(
                        ValidationIssue(
                            path=child_path,
                            code="raw_secret_key_forbidden",
                            message=(
                                f"field {key_str!r} is a raw secret/payload key; "
                                "use a *_ref field instead"
                            ),
                            severity="error",
                        )
                    )
                issues.extend(self._walk_value(child_path, child))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, child in enumerate(value):
                child_path = f"{path}[{index}]"
                issues.extend(self._walk_value(child_path, child))
        elif isinstance(value, str):
            issues.extend(self._scan_string(path, value))
        return issues

    @staticmethod
    def _scan_string(path: str, value: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not value:
            return issues
        if _has_hermes_path_authority(value):
            issues.append(
                ValidationIssue(
                    path=path,
                    code="hermes_path_forbidden",
                    message=(
                        f"value of {path!r} asserts Hermes filesystem authority"
                    ),
                    severity="error",
                )
            )
        if _SECRET_MARKER_RE.search(value):
            issues.append(
                ValidationIssue(
                    path=path,
                    code="secret_marker_in_field",
                    message=(
                        f"value of {path!r} contains a secret marker pattern"
                    ),
                    severity="error",
                )
            )
        return issues


def _has_hermes_path_authority(value: str) -> bool:
    """True when a string asserts Hermes home/profile filesystem authority."""
    lowered = value.lower()
    normalized = lowered.replace("\\", "/")
    for needle in FORBIDDEN_PATH_SUBSTRINGS:
        if needle.lower().replace("\\", "/") in normalized:
            return True
        if needle.lower() in lowered:
            return True
    if normalized.rstrip("/").endswith(".hermes"):
        return True
    return False


def validate_document(doc: OperatorConfigDocument) -> list[ValidationIssue]:
    """Validate ``doc``; raise on any error-severity issue (fail-closed).

    Returns the (empty) issue list when the document is valid. Invalid documents
    raise ``OperatorConfigValidationError`` with codes/paths only — never the
    rejected secret or Hermes path value.
    """
    if not isinstance(doc, OperatorConfigDocument):
        raise TypeError("validate_document expects OperatorConfigDocument")
    issues = OperatorConfigValidator().validate(doc)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        summary = ", ".join(f"{e.code}@{e.path}" for e in errors[:8])
        raise OperatorConfigValidationError(
            f"operator config validation failed ({len(errors)} error(s)): {summary}"
        )
    return issues
