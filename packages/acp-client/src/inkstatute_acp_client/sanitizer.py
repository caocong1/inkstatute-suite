"""ReferenceSanitizer — prompt-injection defense for reference file content.

When an agent requests a file via ``fs/read_text_file``, the file's
content is wrapped in unforgeable delimiters before being delivered so
the agent can treat it as untrusted reference data, not as
instructions.  Known prompt-injection patterns are detected and logged
at WARNING level — but **never** is the file content itself logged
(privacy: only path, pattern, and line number are recorded).

Three layers:

1. **Pattern detection** — scan each line for case-insensitive matches
   against :data:`INJECTION_PATTERNS`.
2. **Detection logging** — emit a WARNING with ``extra`` containing
   ``path``, ``pattern``, and ``line_number``.  The log *message* is
   the literal string ``"prompt_injection_detected"`` — no content.
3. **Delimiter wrapping** — wrap the (unchanged) content in
   ``<reference_file>`` / ``--- BEGIN REFERENCE CONTENT ---`` /
   ``--- END REFERENCE CONTENT ---`` / ``</reference_file>`` markers.

The content is always delivered (with delimiters); detection is logged
but does not block delivery.  The agent sees the delimiters and knows
the content is untrusted reference data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Case-insensitive prompt-injection patterns to detect.  The last
#: entry (``<reference_file``) catches delimiter-forgery attempts
#: embedded in the content itself.
INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "new role:",
    "forget everything above",
    "system:",
    "</system>",
    "<reference_file",
)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    """Outcome of :meth:`ReferenceSanitizer.sanitize`.

    Attributes:
        sanitized_content: The content wrapped in unforgeable
            reference delimiters.  The original content is preserved
            verbatim inside the delimiters.
        detected_patterns: List of detection records, one per match.
            Each record is a dict with keys ``pattern`` (the matched
            pattern string) and ``line_number`` (1-based line index).
    """

    sanitized_content: str
    detected_patterns: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------


class ReferenceSanitizer:
    """Wrap reference file content in delimiters and detect injections.

    The sanitizer is stateless aside from its logger and pattern list;
    it is safe to reuse across calls.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("inkstatute_acp_client.sanitizer")
        self._patterns = INJECTION_PATTERNS

    def sanitize(self, content: str, path: str) -> SanitizationResult:
        """Detect injections, log detections, and wrap content in delimiters.

        Args:
            content: The raw file content (already read and
                sandbox-validated by the caller).
            path: The path of the reference file, used for logging
                only (never logged alongside content).

        Returns:
            A :class:`SanitizationResult` with the wrapped content and
            the list of detected patterns.
        """
        # a. Pattern detection — case-insensitive, line by line.
        detected: list[dict[str, Any]] = []
        lines = content.split("\n")
        for line_index, line in enumerate(lines):
            lowered = line.lower()
            for pattern in self._patterns:
                if pattern.lower() in lowered:
                    record = {
                        "pattern": pattern,
                        "line_number": line_index + 1,
                    }
                    detected.append(record)
                    # CRITICAL: log message is the literal event name
                    # only — never include file content (privacy).
                    self._logger.warning(
                        "prompt_injection_detected",
                        extra={
                            "path": path,
                            "pattern": pattern,
                            "line_number": line_index + 1,
                        },
                    )

        # b. Delimiter wrapping — unforgeable markers around content.
        sanitized_content = (
            f'<reference_file path="{path}">\n'
            f"--- BEGIN REFERENCE CONTENT ---\n"
            f"{content}\n"
            f"--- END REFERENCE CONTENT ---\n"
            f"</reference_file>"
        )

        # c. Return result.
        return SanitizationResult(
            sanitized_content=sanitized_content,
            detected_patterns=detected,
        )


__all__ = [
    "INJECTION_PATTERNS",
    "ReferenceSanitizer",
    "SanitizationResult",
]
