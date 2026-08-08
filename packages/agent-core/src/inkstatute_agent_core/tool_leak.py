"""Tool-call leak detection, sanitization, and embedded tool-call parsing.

A Python port of the Rust ``tool_leak.rs`` from
``lawyer-desktop/src-tauri/src/llm/tool_leak.rs`` (392 lines).

LLM models sometimes leak tool-call markup (DSML/XML tags) into plain text
instead of using the API ``tool_calls`` field.  This module detects such
leakage, sanitizes leaked content for display, and parses embedded tool-call
blocks back into structured tool calls.

Key behaviours ported verbatim from the Rust source:

* **Full-width character normalisation** — DeepSeek DSML uses U+FF5C ``｜``
  and U+2581 ``▁``; these are mapped to ``|`` and ``_`` before all detection
  and parsing.
* **20+ leak marker patterns** — ``contains_tool_leakage`` checks a normalised
  lowercase copy of the text against every marker from the Rust source.
* **Two-phase sanitization** — Phase 1 removes ``<tool_calls>...</tool_calls>``
  and ``<invoke>...</invoke>`` blocks; Phase 2 filters line-by-line, preserving
  HTML formatting tags (``<br>``, ``<table>``, ``<strong>``, ``<p>``) while
  stripping tool-leak tag lines.
* **Fuzzy tool-name normalisation** — mangled names like ``search_`` are mapped
  to ``search_workspace`` via substring heuristics and bidirectional fallback.
* **Embedded tool-call parsing** — ``<invoke name="...">`` blocks are extracted
  and parsed into structured tool-call dicts with UUID IDs.

No external dependencies — uses only the Python standard library
(``re``, ``json``, ``uuid``).
"""

from __future__ import annotations

import json
import re
import uuid

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Known tool names — mirrors ``KNOWN_TOOLS`` in ``tool_leak.rs:5-16``.
#: Ordered list to preserve iteration order for the bidirectional fallback
#: in :func:`_normalize_tool_name`.
KNOWN_TOOLS: list[str] = [
    "search_workspace",
    "read_chunk",
    "read_file",
    "list_files",
    "get_index_status",
    "read_user_file",
    "fetch_url",
    "generate_docx",
    "select_skill",
    "ask_user",
]

# ---------------------------------------------------------------------------
# Character normalisation
# ---------------------------------------------------------------------------


def normalize_marker_chars(text: str) -> str:
    """Map fullwidth / token-separator characters to ASCII equivalents.

    DeepSeek DSML uses U+FF5C ``｜`` (fullwidth vertical bar) and U+2581 ``▁``
    (lower one eighth block) as token separators.  These are replaced with
    ``|`` and ``_`` so detection and parsing see one canonical form.

    Mirrors ``normalize_marker_chars`` in ``tool_leak.rs:21-23``.
    """
    return text.replace("\uff5c", "|").replace("\u2581", "_")


# ---------------------------------------------------------------------------
# Leak detection
# ---------------------------------------------------------------------------


def contains_tool_leakage(text: str) -> bool:
    """Return ``True`` when *text* contains tool-call markup leakage.

    The text is first normalised (fullwidth chars → ASCII) and lowercased,
    then checked against 20+ marker substrings from the Rust source.

    Mirrors ``contains_tool_leakage`` in ``tool_leak.rs:26-47``.
    """
    lower = normalize_marker_chars(text).lower()
    return (
        "dsml" in lower
        or "tool_calls" in lower
        or "tool_call" in lower
        or "tool_c" in lower
        or "</_calls" in lower
        or "_calls>" in lower
        or "< name=" in lower
        or "<name=" in lower
        or "<invoke" in lower
        or "invoke>" in lower
        or "</invoke" in lower
        or "invoke name=" in lower
        or "invoke=" in lower
        or "parameter name=" in lower
        or "parameter name " in lower
        or "function_call" in lower
        or "<|" in lower
        or "|>" in lower
        or "toolalls" in lower
    )


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------


def sanitize_assistant_content(text: str) -> str:
    """Strip tool-call markup from assistant text for display / persistence.

    Two-phase approach:

    1. **Block removal** — ``<tool_calls>...</tool_calls>`` and
       ``<invoke>...</invoke>`` blocks are removed (case-insensitive).
    2. **Line filtering** — lines containing leak markers are dropped;
       ``<...>`` lines matching known tool-leak tag prefixes are dropped;
       all other lines (including HTML formatting tags) are preserved.

    Mirrors ``sanitize_assistant_content`` in ``tool_leak.rs:50-121``.
    """
    s = text

    # Phase 1a: Remove <tool_calls>...</tool_calls> blocks
    while True:
        start = _find_case_insensitive(s, "<tool_calls")
        if start is None:
            break
        end = _find_case_insensitive(s[start:], "</tool_calls>")
        if end is not None:
            s = s[:start] + s[start + end + len("</tool_calls>") :]
            continue
        break

    # Phase 1b: Remove <invoke>...</invoke> blocks
    while True:
        start = _find_case_insensitive(s, "<invoke")
        if start is None:
            break
        end = _find_case_insensitive(s[start:], "</invoke>")
        if end is not None:
            s = s[:start] + s[start + end + len("</invoke>") :]
            continue
        # No closing tag — look for next <invoke block
        next_rel = _find_case_insensitive(s[start + 7 :], "<invoke")
        if next_rel is not None:
            s = s[:start] + s[start + 7 + next_rel :]
            continue
        # No next block — remove from start to end of string
        s = s[:start]
        break

    # Phase 2: Line-by-line filtering
    out: list[str] = []
    for line in s.split("\n"):
        trimmed = line.strip()
        # Detect markers on a normalised copy but keep original line when clean
        lower = normalize_marker_chars(trimmed).lower()
        if (
            "dsml" in lower
            or "tool_calls" in lower
            or "tool_call" in lower
            or "tool_c" in lower
            or "</_calls" in lower
            or "_calls>" in lower
            or "< name=" in lower
            or "<name=" in lower
            or "invoke name=" in lower
            or "invoke=" in lower
            or "parameter name=" in lower
            or "parameter name " in lower
            or "invoke>" in lower
            or "</invoke" in lower
            or "function_call" in lower
            or "toolalls" in lower
            or "<|" in lower
            or "|>" in lower
        ):
            continue
        # Only strip <...> lines matching known tool-leak tags, not all HTML
        if trimmed.startswith("<") and trimmed.endswith(">"):
            inner = trimmed[1:-1].strip().lower()
            inner_stripped = inner[1:] if inner.startswith("/") else inner
            if (
                inner_stripped.startswith("tool_call")
                or inner_stripped.startswith("_call")
                or inner_stripped.startswith("invoke")
                or inner_stripped.startswith("parameter")
                or inner_stripped.startswith("name=")
                or inner_stripped.startswith("function_call")
                or inner_stripped.startswith("dsml")
            ):
                continue
        out.append(line)

    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_case_insensitive(hay: str, needle: str) -> int | None:
    """Return the character index of *needle* in *hay* (case-insensitive).

    Returns ``None`` if not found.  Mirrors ``find_case_insensitive`` in
    ``tool_leak.rs:127-129``.
    """
    idx = hay.lower().find(needle.lower())
    return idx if idx != -1 else None


def normalize_tool_name(raw: str) -> str:
    """Normalise a (possibly mangled) tool name to a canonical known tool name.

    1. Exact match against :data:`KNOWN_TOOLS`.
    2. Substring heuristics (search+workspace, read+chunk, etc.).
    3. Bidirectional fallback — if the name contains or is contained by any
       known tool name, return that known tool.
    4. Otherwise return the trimmed raw name.

    Mirrors ``normalize_tool_name`` in ``tool_leak.rs:131-164``.
    """
    n = raw.strip().strip('"').strip("'").lower()
    if not n:
        return raw.strip()
    if n in KNOWN_TOOLS:
        return n
    if "search" in n and ("work" in n or "space" in n or "pace" in n):
        return "search_workspace"
    if "read" in n and "chunk" in n:
        return "read_chunk"
    if "read" in n and "file" in n:
        return "read_file"
    if "list" in n and "file" in n:
        return "list_files"
    if "index" in n and "status" in n:
        return "get_index_status"
    for known in KNOWN_TOOLS:
        if known in n or n in known:
            return known
    return raw.strip()


def _parse_parameter_value(block: str, param_name: str) -> str | None:
    """Extract the value of a ``<parameter name="...">value</parameter>`` tag.

    Handles both double and single quoted attribute values.  The value is
    delimited by ``<`` (closing tag start) or, if no closing tag, by ``\\n``
    or ``|``.

    Mirrors ``parse_parameter_value`` in ``tool_leak.rs:166-188``.
    """
    patterns = [f'name="{param_name}"', f"name='{param_name}'"]
    for pat in patterns:
        idx = _find_case_insensitive(block, pat)
        if idx is not None:
            rest = block[idx + len(pat) :]
            rest = rest.lstrip()
            gt = rest.find(">")
            if gt != -1:
                after = rest[gt + 1 :]
                lt = after.find("<")
                if lt != -1:
                    return after[:lt].strip()
                # No closing < — delimit by newline or pipe
                nl_pos = after.find("\n")
                pipe_pos = after.find("|")
                candidates = [p for p in [nl_pos, pipe_pos] if p != -1]
                end = min(candidates) if candidates else len(after)
                return after[:end].strip()
    return None


def _extract_quoted_attr(block: str, attr: str) -> str | None:
    """Extract a quoted attribute value following *attr* in *block*.

    Mirrors ``extract_quoted_attr`` in ``tool_leak.rs:190-199``.
    """
    idx = _find_case_insensitive(block, attr)
    if idx is None:
        return None
    rest = block[idx + len(attr) :].lstrip()
    if not rest:
        return None
    quote = rest[0]
    if quote != '"' and quote != "'":
        return None
    name_end = rest[1:].find(quote)
    if name_end == -1:
        return None
    return rest[1 : 1 + name_end]


def _extract_invoke_name(block: str) -> str | None:
    """Extract the tool name from an invoke header only.

    Handles ``invoke name="x"`` and the mangled ``invoke="x"`` variant seen
    in DSML leakage, while avoiding ``<parameter name="...">`` fields inside
    the block.

    Mirrors ``extract_invoke_name`` in ``tool_leak.rs:201-213``.
    """
    invoke_idx = _find_case_insensitive(block, "invoke")
    if invoke_idx is None:
        return None
    rest = block[invoke_idx:]
    gt = rest.find(">")
    nl = rest.find("\n")
    candidates = [p for p in [gt, nl] if p != -1]
    header_end = min(candidates) if candidates else len(rest)
    header = rest[:header_end]
    return _extract_quoted_attr(header, "name=") or _extract_quoted_attr(
        header, "invoke="
    )


def _parse_invoke_block(block: str) -> tuple[str, dict] | None:
    """Parse a complete invoke block into ``(tool_name, args_dict)``.

    Numeric parameters (``k``, ``max_chars``) are converted to ``int``.
    All other parameters are kept as strings.

    Mirrors ``parse_invoke_block`` in ``tool_leak.rs:215-244``.
    """
    raw_name = _extract_invoke_name(block)
    if raw_name is None:
        return None
    tool_name = normalize_tool_name(raw_name)

    args: dict[str, str | int] = {}
    for key in [
        "query",
        "k",
        "chunk_id",
        "relative_path",
        "max_chars",
        "pattern",
        "path",
        "url",
        "skill_name",
        "reason",
    ]:
        v = _parse_parameter_value(block, key)
        if v is not None:
            if key in ("k", "max_chars"):
                try:
                    args[key] = int(v)
                except ValueError:
                    pass
            else:
                args[key] = v

    return (tool_name, args)


# ---------------------------------------------------------------------------
# Embedded tool-call parsing
# ---------------------------------------------------------------------------


def parse_embedded_tool_calls(content: str) -> list[dict]:
    """Parse ``<invoke name="...">`` / DSML-style tool blocks from *content*.

    Returns a list of tool-call dicts, each with keys ``id``, ``type``,
    and ``function`` (containing ``name`` and ``arguments`` as a JSON string).
    Only tools in :data:`KNOWN_TOOLS` or starting with ``mcp_`` are accepted.

    Mirrors ``parse_embedded_tool_calls`` in ``tool_leak.rs:247-287``.
    """
    content = normalize_marker_chars(content)
    calls: list[dict] = []
    lower = content.lower()
    search_from = 0

    while search_from < len(content):
        rel = lower.find("invoke", search_from)
        if rel == -1:
            break
        start = rel

        # Find block end: closing </invoke>, or next <invoke, or end of content
        close_rel = lower.find("</invoke>", start)
        if close_rel != -1:
            block_end = close_rel + len("</invoke>")
        else:
            next_invoke_rel = lower.find("<invoke", start)
            if next_invoke_rel != -1:
                block_end = next_invoke_rel
            else:
                block_end = len(content)

        block = content[start : min(block_end, len(content))]
        result = _parse_invoke_block(block)
        if result is not None:
            name, args = result
            if name in KNOWN_TOOLS or name.startswith("mcp_"):
                calls.append(
                    {
                        "id": f"embedded_{uuid.uuid4()}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                )

        search_from = max(block_end, start + 6)

    return calls


__all__ = [
    "KNOWN_TOOLS",
    "normalize_marker_chars",
    "contains_tool_leakage",
    "sanitize_assistant_content",
    "normalize_tool_name",
    "parse_embedded_tool_calls",
]
