"""Shared multi-provider error normalization for provider_model runners.

This module provides the shared :func:`normalize_provider_error` function
that all three provider runners (OpenAI, Anthropic, Ollama) use to normalize
provider-specific exceptions into platform-contract :class:`ErrorInfo`
records.

The normalization uses:
- **String-based class-name detection** for SDK errors (OpenAI, Anthropic) —
  the SDKs cannot be imported at module top level (lazy import invariant).
- **HTTP status-code detection** for HTTP errors (Ollama) — via
  ``getattr(exc, "status_code", None)``.

All errors map to :class:`ErrorCategory.RUNTIME_ERROR` — the existing enum
has only ``CONTRACT_ERROR``, ``RUNTIME_ERROR``, ``CHANNEL_ERROR``, and
provider errors are runtime errors. Provider-specific detail goes in
``ErrorInfo.details`` (e.g., ``{"provider": "anthropic"}``).
"""

from __future__ import annotations

import re

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo, JsonObject

# ---------------------------------------------------------------------------
# Error message sanitization
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*")
_MODEL_RE = re.compile(r"\b(?:gpt|claude|gemini|llama)[-\w]*", re.IGNORECASE)


def sanitize_error_message(msg: str) -> str:
    """Strip URLs, tokens, file paths, and model names from an error message.

    This ensures that provider API error messages never leak sensitive
    information (API endpoints, auth tokens, file system paths, model names)
    into platform-visible output.
    """

    sanitized = _URL_RE.sub("[url_redacted]", msg)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    sanitized = _PATH_RE.sub("[redacted]", sanitized)
    sanitized = _MODEL_RE.sub("[model_redacted]", sanitized)
    return sanitized


# ---------------------------------------------------------------------------
# Provider error normalization
# ---------------------------------------------------------------------------


def normalize_provider_error(
    exc: Exception,
    stage: str,
    *,
    provider: str = "unknown",
) -> ErrorInfo:
    """Normalize a provider exception into a sanitized :class:`ErrorInfo`.

    Works for all three providers:
    - **OpenAI**: string-based class-name detection (``RateLimitError``,
      ``AuthenticationError``, ``APIConnectionError``, ``APIStatusError``).
    - **Anthropic**: string-based class-name detection (same patterns).
    - **Ollama**: HTTP status-code detection via ``exc.status_code``
      (429 → rate limit, 401/403 → auth, 5xx → API error).

    All errors map to :class:`ErrorCategory.RUNTIME_ERROR`. The provider
    name is included in ``ErrorInfo.details``.

    Parameters
    ----------
    exc : Exception
        The provider exception to normalize.
    stage : str
        The pipeline stage where the error occurred (e.g., ``"completion"``).
    provider : str
        The provider name (``"openai"``, ``"anthropic"``, ``"ollama"``).

    Returns
    -------
    ErrorInfo
        A sanitized error info with category, code, message, stage,
        retryable flag, and provider details.
    """

    exc_name = type(exc).__name__
    status_code = getattr(exc, "status_code", None)

    details: JsonObject = {"provider": provider}
    if status_code is not None:
        details["status_code"] = status_code

    if status_code == 429 or "RateLimit" in exc_name:
        code = "provider_model_rate_limit"
        retryable: bool | None = True
    elif status_code in (401, 403) or "Authentication" in exc_name or "Auth" in exc_name:
        code = "provider_model_auth_error"
        retryable = False
    elif (
        "Connection" in exc_name
        or "Timeout" in exc_name
        or "timeout" in exc_name.lower()
        or "connect" in exc_name.lower()
    ):
        code = "provider_model_connection_error"
        retryable = True
    elif status_code is not None and status_code >= 500:
        code = "provider_model_api_error"
        retryable = None
    elif "APIStatus" in exc_name or "API" in exc_name:
        code = "provider_model_api_error"
        retryable = None
    else:
        code = "provider_model_unknown_error"
        retryable = None

    message = sanitize_error_message(str(exc))

    return ErrorInfo(
        category=ErrorCategory.RUNTIME_ERROR,
        code=code,
        message=message,
        stage=stage,
        retryable=retryable,
        details=details,
    )


__all__ = [
    "sanitize_error_message",
    "normalize_provider_error",
]
