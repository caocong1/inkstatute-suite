"""Operator config document validation: Hermes ban-list + refs-only (CFG-01/03).

Fail-closed validators. Error messages never echo rejected secret values.
Does not write to disk and does not treat Hermes filesystem as config authority.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from .catalog import (
    BUILTIN_VENDOR_IDS,
    builtin_catalog_entry,
    builtin_vendor_profile,
)
from .errors import OperatorConfigValidationError
from .schemas import OperatorConfigDocument
from .secrets import InvalidSecretRefError, normalize_config_secret_ref

__all__ = [
    "FORBIDDEN_HERMES_FIELD_NAMES",
    "FORBIDDEN_PATH_SUBSTRINGS",
    "FORBIDDEN_RAW_SECRET_KEYS",
    "OperatorConfigValidator",
    "ValidationIssue",
    "validate_document",
]

# Provider kinds accepted by the registry (PROV-01/02).
_SUPPORTED_PROVIDER_KINDS: frozenset[str] = frozenset(
    {"openai", "anthropic", "custom"}
)

# VIS-01 — vision routing modes accepted by the operator config validator.
# ``auto`` (multimodal main if supports_vision, else vision→main mix),
# ``always_preprocess`` (always vision→main mix), ``main_only`` (never invoke
# vision). ``None`` (unset) preserves the Phase 76 draft-tolerant behavior.
_SUPPORTED_ROUTING_MODES: frozenset[str] = frozenset(
    {"auto", "always_preprocess", "main_only"}
)

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
# Includes schema-parallel channel credential stems (app_secret, token_secret,
# encoding_aes_key) so metadata cannot smuggle the non-_ref form of those fields.
FORBIDDEN_RAW_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "token",
        "token_secret",
        "password",
        "bot_secret",
        "app_secret",
        "encoding_aes_key",
        "aes_key",
        "client_secret",
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
        issues.extend(self._check_provider_registry(doc))
        issues.extend(self._check_catalog_selection(doc))
        issues.extend(self._check_vision_selection(doc))
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

    def _check_provider_registry(
        self, doc: OperatorConfigDocument
    ) -> list[ValidationIssue]:
        """Provider invariants: unique ids, supported kinds, canonical built-ins,
        explicit custom HTTPS + non-empty allowlist (PROV-01/02)."""
        issues: list[ValidationIssue] = []
        seen: set[str] = set()
        for index, provider in enumerate(doc.providers):
            base = f"providers[{index}]"
            pid = provider.provider_id
            if pid:
                if pid in seen:
                    issues.append(
                        ValidationIssue(
                            path=f"{base}.provider_id",
                            code="duplicate_provider_id",
                            message="duplicate provider_id in registry",
                            severity="error",
                        )
                    )
                else:
                    seen.add(pid)
            if provider.kind not in _SUPPORTED_PROVIDER_KINDS:
                issues.append(
                    ValidationIssue(
                        path=f"{base}.kind",
                        code="unsupported_provider_kind",
                        message="provider kind must be openai, anthropic, or custom",
                        severity="error",
                    )
                )
                continue
            if provider.kind in BUILTIN_VENDOR_IDS:
                profile = builtin_vendor_profile(provider.kind)
                if profile is None or provider.api_base_url != profile.api_base_url:
                    issues.append(
                        ValidationIssue(
                            path=f"{base}.api_base_url",
                            code="builtin_url_mismatch",
                            message=(
                                "built-in provider api_base_url must match the "
                                "canonical vendor profile"
                            ),
                            severity="error",
                        )
                    )
                if provider.model_allowlist:
                    issues.append(
                        ValidationIssue(
                            path=f"{base}.model_allowlist",
                            code="builtin_allowlist_misuse",
                            message=(
                                "built-in providers must keep an empty model_allowlist"
                            ),
                            severity="error",
                        )
                    )
            elif provider.kind == "custom":
                if not _is_valid_custom_base_url(provider.api_base_url):
                    issues.append(
                        ValidationIssue(
                            path=f"{base}.api_base_url",
                            code="invalid_custom_url",
                            message=(
                                "custom provider api_base_url must be a public HTTPS "
                                "URL without userinfo, query, or fragment"
                            ),
                            severity="error",
                        )
                    )
                if not provider.model_allowlist:
                    issues.append(
                        ValidationIssue(
                            path=f"{base}.model_allowlist",
                            code="custom_provider_requires_allowlist",
                            message=(
                                "custom providers require a non-empty model_allowlist"
                            ),
                            severity="error",
                        )
                    )
        return issues

    def _check_catalog_selection(
        self, doc: OperatorConfigDocument
    ) -> list[ValidationIssue]:
        """Main catalog selection: fully absent or fully populated + resolvable."""
        return self._resolve_selection_pair(
            doc,
            provider_id=doc.catalog.provider_id,
            model_id=doc.catalog.model_id,
            provider_path="catalog.provider_id",
            model_path="catalog.model_id",
            allow_partial=False,
        )

    def _check_vision_selection(
        self, doc: OperatorConfigDocument
    ) -> list[ValidationIssue]:
        """Vision routing policy: routing_mode enum + pair completeness (VIS-01).

        First validates ``routing_mode`` against ``_SUPPORTED_ROUTING_MODES``.
        When the mode requires a vision step (``auto``/``always_preprocess``),
        the vision provider/model pair must be complete. ``main_only`` and an
        unset (``None``) mode remain draft-tolerant. A complete pair (any mode)
        is still resolved against the operator registry by the same rules as the
        main catalog selection. Messages expose codes/paths only — never the
        rejected routing_mode value or secret contents.
        """
        issues: list[ValidationIssue] = []
        routing_mode = doc.vision.routing_mode
        if routing_mode is not None and routing_mode not in _SUPPORTED_ROUTING_MODES:
            issues.append(
                ValidationIssue(
                    path="vision.routing_mode",
                    code="unsupported_routing_mode",
                    message=(
                        "vision routing_mode must be one of auto, "
                        "always_preprocess, or main_only"
                    ),
                    severity="error",
                )
            )
            # An unsupported routing mode is fail-closed: do not attempt
            # completeness enforcement under an unknown mode. A complete pair
            # is still resolved below so registry errors are surfaced too.
        elif routing_mode in ("auto", "always_preprocess"):
            issues.extend(
                self._check_vision_completeness(
                    doc.vision.vision_provider_id,
                    doc.vision.vision_model_id,
                )
            )
        # ``main_only`` and ``None`` preserve the Phase 76 draft-tolerant
        # behavior: absent/partial/complete pairs are all persisted drafts.
        # A complete pair (any mode) is resolved against the registry.
        issues.extend(
            self._resolve_selection_pair(
                doc,
                provider_id=doc.vision.vision_provider_id,
                model_id=doc.vision.vision_model_id,
                provider_path="vision.vision_provider_id",
                model_path="vision.vision_model_id",
                allow_partial=True,
            )
        )
        return issues

    def _check_vision_completeness(
        self, vision_provider_id: str | None, vision_model_id: str | None
    ) -> list[ValidationIssue]:
        """Enforce a complete vision pair when the routing mode requires vision.

        Emits ``incomplete_vision_selection`` at the missing field path
        (``vision.vision_provider_id`` when only the model is present,
        ``vision.vision_model_id`` when the provider is present or both are
        absent). Messages never echo the present field value.
        """
        has_provider = bool(vision_provider_id)
        has_model = bool(vision_model_id)
        if has_provider and has_model:
            return []
        missing_path = (
            "vision.vision_provider_id"
            if has_model
            else "vision.vision_model_id"
        )
        return [
            ValidationIssue(
                path=missing_path,
                code="incomplete_vision_selection",
                message=(
                    "vision routing_mode requires both vision_provider_id and "
                    "vision_model_id to be set"
                ),
                severity="error",
            )
        ]

    def _resolve_selection_pair(
        self,
        doc: OperatorConfigDocument,
        *,
        provider_id: str | None,
        model_id: str | None,
        provider_path: str,
        model_path: str,
        allow_partial: bool,
    ) -> list[ValidationIssue]:
        """Resolve a provider/model selection against the operator registry.

        Built-in selections require a catalog entry whose ``vendor_id`` equals
        the provider ``kind``; custom selections require ``model_id`` membership
        in the provider ``model_allowlist``. Messages expose codes/paths only.
        """
        has_provider = bool(provider_id)
        has_model = bool(model_id)
        if not has_provider and not has_model:
            return []
        if has_provider != has_model:
            if allow_partial:
                return []
            return [
                ValidationIssue(
                    path=provider_path if has_provider else model_path,
                    code="incomplete_catalog_selection",
                    message=(
                        "catalog selection must set both provider_id and model_id "
                        "or neither"
                    ),
                    severity="error",
                )
            ]
        # Both present: resolve the provider instance.
        matches = [
            provider for provider in doc.providers if provider.provider_id == provider_id
        ]
        if len(matches) != 1:
            return [
                ValidationIssue(
                    path=provider_path,
                    code="unknown_provider",
                    message=(
                        "selected provider_id does not resolve to exactly one "
                        "provider instance"
                    ),
                    severity="error",
                )
            ]
        provider = matches[0]
        if provider.kind in BUILTIN_VENDOR_IDS:
            entry = builtin_catalog_entry(provider.kind, model_id)
            if entry is None:
                return [
                    ValidationIssue(
                        path=model_path,
                        code="builtin_model_vendor_mismatch",
                        message=(
                            "selected model is not a built-in catalog entry for "
                            "this vendor kind"
                        ),
                        severity="error",
                    )
                ]
        elif provider.kind == "custom":
            if model_id not in provider.model_allowlist:
                return [
                    ValidationIssue(
                        path=model_path,
                        code="custom_model_not_allowed",
                        message=(
                            "selected model is not in the provider model_allowlist"
                        ),
                        severity="error",
                    )
                ]
        # Unsupported kinds are already reported by _check_provider_registry.
        return []

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


def _is_valid_custom_base_url(url: str | None) -> bool:
    """Structural public-HTTPS check for custom provider ``api_base_url``.

    Rejects non-HTTPS schemes, missing hostnames, userinfo, query/fragment, and
    unsafe literal IP addresses (loopback/private/link-local/multicast/reserved/
    unspecified). DNS-name resolution remains the API probe plan's responsibility.
    Never raises — returns False for any malformed shape.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    # Reject userinfo (``user:pass@host``) — credentials must stay refs-only.
    if "@" in parsed.netloc:
        return False
    if parsed.query or parsed.fragment:
        return False
    # Reject unsafe literal IP addresses; DNS names are accepted here.
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    return True


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
