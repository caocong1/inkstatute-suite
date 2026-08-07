"""Secret detection for practice profile data on write.

Practice profiles are business configuration (risk positions, escalation
thresholds, document style preferences) — they must never contain
secrets.  :func:`validate_no_secrets` scans profile data recursively
and raises :class:`SecretDetectedError` if any field matches a secret
pattern.

The error message **never** includes the matched secret text — only the
dotted field path and the pattern name.  This follows the reference-
first principle from
``packages/acp-event-bridge/src/inkstatute_acp_event_bridge/privacy_scan.py``.

Pattern categories (focused subset for practice profile fields):

- **Key-name patterns** — detect secret-like field names:
  ``api_key``, ``access_token``, ``secret_key``, ``password``,
  ``passwd``, ``pwd``, ``aes_key``, ``encoding_aes_key``, ``token``,
  ``secret``, ``key``, ``private_key``.
- **Value patterns** — detect secret-like content in string values:
  PEM private key blocks, ``HERMES_HOME``/``ACP_*``/``AGENT_*`` env
  secret assignments.
"""

from __future__ import annotations

import re
from typing import Any

from platform_contract.events import JsonObject


# ---------------------------------------------------------------------------
# SecretDetectedError
# ---------------------------------------------------------------------------


class SecretDetectedError(ValueError):
    """Raised when a secret pattern is detected in practice profile data.

    The error message and attributes **never** include the actual
    secret value — only the field path and the pattern name that
    triggered the detection.

    Attributes
    ----------
    field_path
        Dotted path to the field containing the detected pattern
        (e.g. ``"config.password"`` or ``"list.0.token"``).
    pattern_name
        Name of the secret pattern that matched (e.g.
        ``"api_key_or_secret"``, ``"pem_private_key"``).
    """

    def __init__(self, field_path: str, pattern_name: str) -> None:
        self.field_path = field_path
        self.pattern_name = pattern_name
        super().__init__(
            f"secret pattern '{pattern_name}' detected at field path "
            f"'{field_path}' — secret value redacted"
        )


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

#: Key-name patterns — checked against the field key (not the value).
#: Order matters: more specific patterns are checked first.
_KEY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("password_assignment",
     re.compile(r"(?:password|passwd|pwd)", re.IGNORECASE)),
    ("aes_key_reference",
     re.compile(r"(?:aes[_-]?key|encoding[_-]?aes[_-]?key)", re.IGNORECASE)),
    ("api_key_or_secret",
     re.compile(
         r"(?:api[_-]?key|access[_-]?token|secret[_-]?key"
         r"|client[_-]?secret|refresh[_-]?token)",
         re.IGNORECASE,
     )),
    ("generic_secret_key",
     re.compile(
         r"(?:^|[_-])(?:token|secret|key)(?:$|[_-])",
         re.IGNORECASE,
     )),
)

#: Value patterns — checked against string field values.
_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pem_private_key",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("env_secret_assignment",
     re.compile(
         r"(?:HERMES_HOME|ACP_[A-Z_]+|AGENT_[A-Z_]+)\s*[:=]\s*\S+"
     )),
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_no_secrets(data: JsonObject) -> None:
    """Validate that *data* contains no secret patterns.

    Recursively traverses nested dicts and lists, checking all string
    values and field keys.  Raises :class:`SecretDetectedError` if any
    field matches a secret pattern.

    Parameters
    ----------
    data
        The practice profile data to validate (a :type:`JsonObject`).

    Raises
    ------
    SecretDetectedError
        If a secret pattern is detected.  The error never includes the
        actual secret value.
    """
    _scan_dict(data, "")


def _scan_dict(obj: dict[str, Any], path_prefix: str) -> None:
    """Recursively scan a dict for secret patterns.

    For each key, checks the key name against key-name patterns, then
    recurses into nested dicts and lists.
    """
    for key, value in obj.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else str(key)

        # Check key name against key-name patterns.
        for pattern_name, pattern in _KEY_PATTERNS:
            if pattern.search(key):
                raise SecretDetectedError(current_path, pattern_name)

        # Check value.
        if isinstance(value, str):
            _scan_string(value, current_path)
        elif isinstance(value, dict):
            _scan_dict(value, current_path)
        elif isinstance(value, list):
            _scan_list(value, current_path)


def _scan_list(items: list[Any], path_prefix: str) -> None:
    """Recursively scan a list for secret patterns."""
    for i, item in enumerate(items):
        item_path = f"{path_prefix}.{i}"
        if isinstance(item, str):
            _scan_string(item, item_path)
        elif isinstance(item, dict):
            _scan_dict(item, item_path)
        elif isinstance(item, list):
            _scan_list(item, item_path)


def _scan_string(value: str, field_path: str) -> None:
    """Scan a string value against value patterns."""
    for pattern_name, pattern in _VALUE_PATTERNS:
        if pattern.search(value):
            raise SecretDetectedError(field_path, pattern_name)


__all__ = [
    "SecretDetectedError",
    "validate_no_secrets",
]
