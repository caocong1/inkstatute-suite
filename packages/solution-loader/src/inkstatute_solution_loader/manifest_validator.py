"""Manifest validator for neutral SolutionPackageManifest objects.

Rejects:
1. Legal-only top-level keys (legal data belongs in industry_context).
2. Raw payload / secret-named top-level keys (use raw_payload_ref and
   secret_ref templates).
3. Secret marker patterns inside string fields.
4. solution_id values with path separators, dots, or whitespace.
5. version values that don't match SemVer-ish pattern.
6. materialize_targets entries outside {hermes, codex, provider_model}.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from platform_runtime import Issue, SolutionPackageManifest


_LEGAL_ONLY_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "lawyer",
        "legal",
        "lawfirm",
        "attorney",
        "counsel",
        "law_firm",
        "attorneys_at_law",
        "case_id",
        "case_no",
    }
)

_RAW_PAYLOAD_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "raw_payload",
        "raw_body",
        "callback_body",
        "secret",
        "token",
        "password",
        "api_key",
        "private_key",
    }
)

_SECRET_MARKER_RE = re.compile(
    r"(sk-|secret\s*=|password\s*=|bearer\s+[A-Za-z0-9_\-]{16,})",
    re.IGNORECASE,
)
_HEX_BLOB_RE = re.compile(r"\b[A-Fa-f0-9]{32,}\b")

_SOLUTION_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.]+)?$")

_ALLOWED_MATERIALIZE_TARGETS: frozenset[str] = frozenset(
    {"hermes", "codex", "provider_model"}
)


class ManifestValidator:
    """Validates a ``SolutionPackageManifest`` against platform neutrality rules."""

    def validate(self, manifest: SolutionPackageManifest) -> list[Issue]:
        issues: list[Issue] = []

        # 1. Legal-only top-level keys
        # SolutionPackageManifest allows extra fields via metadata; but we want to
        # validate the *fields that exist on the manifest* (not arbitrary dict keys).
        # SolutionPackageManifest has known fields: solution_id, version, manifest_ref, metadata.
        # Reject if any of those fields carries a legal-only value at top-level
        # (e.g., solution_id == "lawfirm_legal" is OK because "lawfirm_legal" is a
        # solution_id, not a top-level key). The "top-level keys" interpretation
        # here means: if a future manifest layer exposes arbitrary keys, refuse them.
        # For the dataclass shape, we check: metadata keys.
        metadata = manifest.metadata or {}
        for key in metadata:
            if key.lower() in _LEGAL_ONLY_TOP_LEVEL_KEYS:
                issues.append(
                    Issue(
                        path=f"metadata.{key}",
                        code="legal_only_top_level_forbidden",
                        message=(
                            f"metadata key {key!r} is legal-only; legal-specific "
                            "data must live in industry_context, not metadata"
                        ),
                        severity="error",
                    )
                )

        # 2. Raw payload / secret-named metadata keys
        for key in metadata:
            if key.lower() in _RAW_PAYLOAD_TOP_LEVEL_KEYS:
                issues.append(
                    Issue(
                        path=f"metadata.{key}",
                        code="raw_payload_or_secret_top_level_forbidden",
                        message=(
                            f"metadata key {key!r} is raw-payload or secret-named; "
                            "use raw_payload_ref or secret_ref templates"
                        ),
                        severity="error",
                    )
                )

        # 3. Secret marker patterns in string fields
        for field_path, value in (
            ("solution_id", manifest.solution_id),
            ("version", manifest.version),
            ("manifest_ref", manifest.manifest_ref or ""),
        ):
            issues.extend(self._scan_string(field_path, value))

        # 4. solution_id format
        if manifest.solution_id and not _SOLUTION_ID_RE.match(manifest.solution_id):
            issues.append(
                Issue(
                    path="solution_id",
                    code="solution_id_invalid_format",
                    message=(
                        f"solution_id {manifest.solution_id!r} must match "
                        f"{_SOLUTION_ID_RE.pattern}"
                    ),
                    severity="error",
                )
            )

        # 5. version format
        if manifest.version and not _SEMVER_RE.match(manifest.version):
            issues.append(
                Issue(
                    path="version",
                    code="version_invalid_format",
                    message=(
                        f"version {manifest.version!r} must match semver pattern"
                    ),
                    severity="error",
                )
            )

        # 6. materialize_targets entries
        targets = metadata.get("materialize_targets")
        if isinstance(targets, (list, tuple)):
            for i, target in enumerate(targets):
                if target not in _ALLOWED_MATERIALIZE_TARGETS:
                    issues.append(
                        Issue(
                            path=f"metadata.materialize_targets[{i}]",
                            code="undeclared_materialize_target",
                            message=(
                                f"materialize_target {target!r} not in allowed "
                                f"{sorted(_ALLOWED_MATERIALIZE_TARGETS)}"
                            ),
                            severity="error",
                        )
                    )

        return issues

    @staticmethod
    def _scan_string(path: str, value: str) -> list[Issue]:
        issues: list[Issue] = []
        if not value:
            return issues
        if _SECRET_MARKER_RE.search(value):
            issues.append(
                Issue(
                    path=path,
                    code="secret_marker_in_field",
                    message=f"value of {path!r} contains a secret marker pattern",
                    severity="error",
                )
            )
        if _HEX_BLOB_RE.search(value):
            issues.append(
                Issue(
                    path=path,
                    code="hex_blob_in_field",
                    message=f"value of {path!r} contains a hex blob (possible token)",
                    severity="error",
                )
            )
        return issues


def validate_manifest_dict(manifest_dict: Mapping[str, object]) -> list[Issue]:
    """Convenience helper: validate a plain dict against the same rule set.

    Useful when reading manifest.json before constructing the dataclass.
    """

    issues: list[Issue] = []

    # Top-level key scan (catches arbitrary dict-based manifests).
    for key in manifest_dict:
        if key.lower() in _LEGAL_ONLY_TOP_LEVEL_KEYS:
            issues.append(
                Issue(
                    path=str(key),
                    code="legal_only_top_level_forbidden",
                    message=(
                        f"top-level key {key!r} is legal-only; legal-specific data "
                        "must live in industry_context"
                    ),
                    severity="error",
                )
            )
        if key.lower() in _RAW_PAYLOAD_TOP_LEVEL_KEYS:
            issues.append(
                Issue(
                    path=str(key),
                    code="raw_payload_top_level_forbidden",
                    message=(
                        f"top-level key {key!r} is raw_payload or secret-named"
                    ),
                    severity="error",
                )
            )

    # Recursive scan for legal-only or raw-payload keys in nested dicts.
    def _walk(prefix: str, value: object) -> None:
        if isinstance(value, Mapping):
            for k, v in value.items():
                sub = f"{prefix}.{k}" if prefix else str(k)
                if k.lower() in _LEGAL_ONLY_TOP_LEVEL_KEYS:
                    issues.append(
                        Issue(
                            path=sub,
                            code="legal_only_key_forbidden",
                            message=f"nested legal-only key {k!r} at {sub}",
                            severity="error",
                        )
                    )
                if k.lower() in _RAW_PAYLOAD_TOP_LEVEL_KEYS:
                    issues.append(
                        Issue(
                            path=sub,
                            code="raw_payload_or_secret_key_forbidden",
                            message=f"nested raw-payload/secret key {k!r} at {sub}",
                            severity="error",
                        )
                    )
                _walk(sub, v)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                _walk(f"{prefix}[{i}]", v)
        elif isinstance(value, str):
            if _SECRET_MARKER_RE.search(value):
                issues.append(
                    Issue(
                        path=prefix,
                        code="secret_marker_in_field",
                        message=f"string at {prefix!r} contains secret marker",
                        severity="error",
                    )
                )
            if _HEX_BLOB_RE.search(value):
                issues.append(
                    Issue(
                        path=prefix,
                        code="hex_blob_in_field",
                        message=f"string at {prefix!r} contains hex blob",
                        severity="error",
                    )
                )

    _walk("", manifest_dict)
    return issues