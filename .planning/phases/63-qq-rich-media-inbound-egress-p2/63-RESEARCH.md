# Phase 63: QQ Rich Media Inbound + Egress (P2) - Research

**Researched:** 2026-07-09
**Domain:** QQ Bot OpenAPI rich media (inbound `attachments[]` → `AttachmentRef`; egress two-step upload → `msg_type=7`)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints:
- Reference-only policy: `raw_payload_ref`, no raw payload storage
- Two-step upload: `POST /v2/.../files` → `file_info` → `msg_type=7` for DOCX/PDF
- Retry + sanitized evidence collection on egress failures
- Reuse Phase 61 TokenManager + Phase 62 MessageTransport patterns
- `dependencies = []`; no wecom_service imports
- Do not modify frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, or channel-core modules
- Prefer extending normalization.py / sender.py rather than new channel-core modules

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EGRESS-05 | Parse inbound `attachments[]` (image/voice/video/file) into `AttachmentRef` with reference-only policy (no raw payload storage; URL as `raw_payload_ref` concept) | Extend `normalize_message_event` + `_attachments_from_event`; fixtures with attachments; `uri=qqbot-media://…`; never store live URL/bytes on AttachmentRef |
| EGRESS-06 | Two-step upload `POST /v2/.../files` → `file_info` → `msg_type=7` for DOCX/PDF; retry + evidence | `upload_rich_media` + `build_media_envelope` + `send_rich_media` in `sender.py`; extend transport twin; retry 304082/304083; sanitized evidence in DeliveryResult.metadata |
</phase_requirements>

## Summary

Phase 63 closes the QQ rich-media gap left by Phase 60 (text-only normalization) and Phase 62 (text/markdown/keyboard egress). Inbound: C2C/GROUP_AT events already carry `attachments[]` in official docs and empty arrays in fixtures — extend `normalization.py` so each attachment becomes a frozen `AttachmentRef` with opaque `qqbot-media://` URI, stable `attachment_id`, and metadata that records reference-only status without embedding live download URLs or bytes. Egress: DOCX/PDF legal delivery requires the official two-step flow — POST scene-scoped `/v2/.../files` with `file_type=4` to obtain `file_info` (+ TTL), then POST `/v2/.../messages` with `msg_type=7` and `media.file_info`, reusing Phase 61 `TokenManager` and Phase 62 retry/auth patterns.

Official QQ docs confirm upload endpoints, `file_type` 1–4, `file_info`/`ttl` response fields, and send-side `msg_type=7` + `media`. Transient rich-media codes `304082` / `304083` must join the retry map. Privacy anti-feature from milestone research is binding: never put time-limited attachment URLs or media bytes into contract events — only refs/hashes.

**Primary recommendation:** Extend `normalization.py` (inbound AttachmentRef mapping) and `sender.py` (upload + media envelope + send_rich_media with Fake/Urllib transport twin); wire `adapter.deliver()` for `delivery_type in {"file","image"}` behind injectable transport; keep `dependencies = []` and fixture-default `network_io=False`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parse `attachments[]` → `AttachmentRef` | API / Backend (`normalization.py`) | platform-contract dataclass (frozen, read-only) | Pure mapping; no Protocol/schema edits |
| Reference-only privacy (no URL/bytes in events) | API / Backend (channel package) | — | AGENTS.md + FEATURES anti-feature; WeCom analog `wecom-media://` |
| AgentTurn.message_type when media present | API / Backend (`normalization.py`) | — | Use existing MessageType enum values only |
| Rich media upload POST `/files` | API / Backend (`sender.py`) | TokenManager | Scene-scoped OpenAPI; injectable transport |
| Media send envelope `msg_type=7` | API / Backend (`sender.py`) | — | Channel-local payload; strip audit keys |
| Retry + sanitized evidence | API / Backend (`sender.py` + `adapter.deliver`) | — | Extend Phase 62 retry map; evidence in DeliveryResult.metadata |
| `ChannelAdapter.deliver()` file routing | API / Backend (`adapter.py`) | — | Metadata `delivery_type`; no Protocol change |
| Capability flags `supports_files` / images | API / Backend (`adapter.capabilities`) | — | Existing ChannelCapabilitySet fields; metadata only for extras |
| Live network / smoke evidence | Deferred (Phase 65/67) | — | CI stays Fake*Transport |

## Project Constraints (from AGENTS.md / ROADMAP)

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- Contract logs prefer `raw_payload_ref`; must not store sensitive full text by default. `[VERIFIED: AGENTS.md]`
- Keep changes scoped to the active GSD phase; do not introduce new services/DBs/queues. `[VERIFIED: AGENTS.md]`
- Prefer structured parsers/validators over ad hoc string parsing. `[VERIFIED: AGENTS.md]`
- `dependencies = []` for qqbot package; no `wecom_service` imports. `[VERIFIED: packages/channels/qqbot/pyproject.toml, test_no_wecom_import.py]`
- Frozen ChannelAdapter / BackendAdapter / platform-contract / channel-core must not be modified. `[VERIFIED: ROADMAP ADAPTER-04]`
- Prefer extending `normalization.py` / `sender.py` rather than new channel-core modules. `[VERIFIED: 63-CONTEXT.md]`

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `urllib.request` + `urllib.error` | 3.11+ (env 3.14.6) | HTTPS POST upload + message | Same as Phase 61/62; preserves `dependencies = []` `[VERIFIED: sender.py, token_manager.py]` |
| `asyncio.to_thread` | stdlib 3.11+ | Non-blocking urllib | Proven in TokenManager / MessageTransport `[VERIFIED: sender.py:319]` |
| `hashlib` | stdlib | Stable `attachment_id` from URL/filename without storing URL | Already used in normalization `_stable_id` `[VERIFIED: normalization.py:96]` |
| `json` | stdlib | Request/response bodies | Existing pattern |
| `platform_contract.events.AttachmentRef` | in-repo (frozen) | Contract attachment shape | `attachment_id`, `kind`, `uri`, optional `name`/`mime_type`/`metadata` `[VERIFIED: events.py:40-46]` |
| Phase 61 `TokenManager` | in-repo | `Authorization: QQBot {token}` | Required by ROADMAP |
| Phase 62 `MessageTransport` / retry helpers | in-repo | Message POST + transient/terminal classification | Extend for upload + rich-media codes |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.IsolatedAsyncioTestCase` | stdlib | Async upload/send/retry tests | Same as `test_sender.py` / `test_token_manager.py` |
| `contract_test_suite.schema_validation.validate_event` | in-repo | AgentTurn+attachments schema check | Already used in `test_normalization.py` |
| `channel_core.output_policy` | in-repo | Optional companion text on media sends | Only if adapter attaches caption; media path itself has no user text body |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib urllib + to_thread | `httpx` | Rejected — `dependencies = []` locked; Phase 61/62 already solved async HTTP without httpx `[VERIFIED: CONTEXT, pyproject.toml]` |
| New `rich_media.py` module | Extend `sender.py` + `normalization.py` | CONTEXT prefers extend existing files; keep surface small |
| Store live QQ `url` on `AttachmentRef.uri` | Opaque `qqbot-media://{id}` | Live URLs are time-limited + PII-bearing; FEATURES anti-feature forbids storing them `[CITED: .planning/research/FEATURES.md]` |
| `file_data` base64 upload always | Prefer host-provided HTTPS `url` for upload | Avoids loading legal document bytes into channel process; `file_data` only as explicit metadata opt-in for fixtures |
| WeCom `media_id` / `build_file_send_envelope` | QQ `file_info` + `msg_type=7` | Forbidden import; different protocol `[VERIFIED: wecom_service/sender.py]` |

**Installation:** none — no new packages.

**Version verification:** No third-party packages. Python `>=3.11` already required by `packages/channels/qqbot/pyproject.toml`. `[VERIFIED: pyproject.toml]` Env probe: Python 3.14.6; qqbot unittest suite 197 tests OK baseline.

## Package Legitimacy Audit

> Phase installs **no** external packages (`dependencies = []` preserved).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 was available; no candidate packages to audit.*

## Architecture Patterns

### System Architecture Diagram

```text
INBOUND (EGRESS-05)
  Gateway envelope {op,t,d}
        │
        ▼
  parse_envelope → QQBotEvent
        │
        ▼
  normalize_message_event
        │
        ├─ content / @-strip (existing)
        ├─ _attachments_from_event(d.attachments)
        │         │
        │         ├─ content_type → kind (image|voice|video|file)
        │         ├─ attachment_id = stable hash (url|filename|index)
        │         ├─ uri = qqbot-media://{attachment_id}   ← NEVER live URL
        │         ├─ metadata.raw_payload_ref = payload_ref
        │         ├─ metadata.source_status = media_reference_only
        │         ├─ metadata.bytes_stored = False
        │         └─ optional: asr_refer_text, size, content_type (no url)
        └─ AgentTurn(attachments=[...], message_type=derived)

EGRESS (EGRESS-06)
  ChannelDelivery (delivery_type=file|image,
                   metadata: scene, openids, msg_id, msg_seq,
                   file_url OR artifact_ref URL, file_type, filename)
        │
        ▼
  QQBotChannelAdapter.deliver()
        │
        ├─ check_passive_reply_window (reuse Phase 62)
        ├─ upload_rich_media(scene, openids, file_type=4, url=…)
        │         │
        │         ├─ TokenManager.get_token()
        │         ├─ POST /v2/users|{groups}/{id}/files
        │         ├─ → {file_uuid, file_info, ttl}
        │         └─ transient 304082/304083 → retry; 401 → invalidate once
        ├─ build_media_envelope(file_info, msg_id, msg_seq)
        │         → msg_type=7, media={file_info}, strip audit keys
        └─ send_message(...)  OR send_rich_media (upload+send atomic)
                  │
                  └─ evidence (sanitized): attempts, status, qq_code,
                     file_uuid_hash, ttl, issue_code — no tokens/URLs/bytes
```

### Recommended Project Structure

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── normalization.py   # EXTEND — attachments → AttachmentRef
├── sender.py          # EXTEND — upload + media envelope + rich send
├── adapter.py         # EXTEND — deliver() file/image path; capabilities
├── token_manager.py   # REUSE
└── ...

packages/channels/qqbot/tests/
├── test_normalization.py          # EXTEND — attachment fixtures + schema
├── test_sender.py                 # EXTEND — upload/retry/media envelope
├── test_qqbot_channel_adapter.py  # EXTEND — deliver file path
├── test_no_wecom_import.py        # already covers sender/normalization
└── ...

packages/channels/qqbot/fixtures/
├── qqbot_c2c_message_with_attachments.json   # NEW
└── qqbot_group_at_message_with_attachments.json  # NEW (optional)
```

### Pattern 1: Reference-only AttachmentRef mapping (WeCom analog, QQ fields)

**What:** Map each QQ attachment object to `AttachmentRef` without storing live `url` or bytes.
**When to use:** Always inside `normalize_message_event` when `d.attachments` is a non-empty list.
**Example:**

```python
# Analog: wecom_service/normalization.py _attachments — DO NOT import wecom_service.
# QQ fields: https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/event.html
# Privacy: FEATURES.md anti-feature — never store attachment URL/bytes in contract events.

from platform_contract.events import AttachmentRef

_CONTENT_TYPE_KIND = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "voice": "voice",
    "video/mp4": "video",
    "file": "file",
}

def _kind_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return "file"
    lowered = content_type.strip().lower()
    if lowered in _CONTENT_TYPE_KIND:
        return _CONTENT_TYPE_KIND[lowered]
    if lowered.startswith("image/"):
        return "image"
    if lowered.startswith("video/"):
        return "video"
    if lowered.startswith("audio/") or lowered == "voice":
        return "voice"
    return "file"

def _attachment_ref_from_qq(
    item: Mapping[str, Any],
    *,
    index: int,
    payload_ref: str | None,
) -> AttachmentRef | None:
    if not isinstance(item, Mapping):
        return None
    content_type = _optional_string(item.get("content_type"))
    filename = _optional_string(item.get("filename"))
    url = _optional_string(item.get("url"))
    # Hash inputs for stable id — do NOT put url into AttachmentRef.uri
    attachment_id = _stable_id(
        "qqbot-att",
        url or filename or content_type or "",
        index,
    )
    kind = _kind_from_content_type(content_type)
    metadata: dict[str, Any] = {
        "raw_payload_ref": payload_ref,
        "source_status": "media_reference_only",
        "bytes_stored": False,
        "content_type": content_type,
    }
    asr = _optional_string(item.get("asr_refer_text"))
    if asr:
        metadata["asr_refer_text"] = asr
    size = item.get("size")
    if isinstance(size, int) and not isinstance(size, bool):
        metadata["size"] = size
    return AttachmentRef(
        attachment_id=attachment_id,
        kind=kind,
        uri=f"qqbot-media://{attachment_id}",
        name=filename,
        mime_type=content_type if content_type and "/" in content_type else None,
        metadata={k: v for k, v in metadata.items() if v is not None},
    )
```

**message_type derivation:** Frozen `MessageType` enum is `text|file|image|voice|button_callback` — **no `video`**. `[VERIFIED: enums.py:48-54, common.schema.json]`. Recommendation:
- No attachments → keep `"text"` (existing).
- Else pick primary from first attachment kind: `image→image`, `voice→voice`, `file→file`, `video→file` (AttachmentRef.kind stays `"video"`).
- If text content also present, still set message_type from primary attachment when attachments exist (media-bearing turn); keep `content` for caption/ASR text. For voice with `asr_refer_text` and empty content, optionally copy ASR into `content` (FEATURES low-complexity passthrough) — **recommend yes** when `content` empty and ASR present.

### Pattern 2: Two-step rich media egress (upload → file_info → msg_type=7)

**What:** Upload then send; DOCX/PDF use `file_type=4`.
**When to use:** `delivery_type in {"file","image"}` (Phase 63 scope: legal DOCX/PDF = file; image optional same path with `file_type=1`).
**Official shapes:** `[CITED: bot.q.qq.com/.../rich-media.html, .../send.html]`

```python
# Upload body (C2C): POST https://api.sgroup.qq.com/v2/users/{openid}/files
# Group: POST .../v2/groups/{group_openid}/files
{
  "file_type": 4,          # 1 image, 2 video, 3 voice, 4 file (DOCX/PDF)
  "url": "https://host-provided/artifact.docx",  # preferred
  # "file_data": "<base64>"  # optional; avoid for production legal bytes
}

# Upload response
{"file_uuid": "...", "file_info": "...", "ttl": 3600}  # ttl=0 → long-lived

# Send body (after strip_for_wire)
{
  "msg_type": 7,
  "media": {"file_info": "<from upload>"},
  "msg_id": "...",
  "msg_seq": 1,
  "content": ""   # group send docs mark content required for text; media may need companion ""
}
```

**Transport extension:** Prefer extending `MessageTransport` with `post_json(url, authorization, body)` **or** add parallel `FileUploadTransport` Protocol + `FakeFileUploadTransport` + methods on `UrllibMessageTransport` that reuse the same `_blocking_post`. Keep Fake injectable for CI. Do **not** add httpx.

**Retry:** Reuse `_BACKOFF_SECONDS`, 401 invalidate-once, terminal set from Phase 62. Add transient QQ codes **304082** and **304083** (official “upload/convert media info fail, retry”). `[CITED: send.html error table]`

**Evidence (sanitized):** On success/failure, `DeliveryResult.metadata` should collect:
- `rich_media_stage`: `upload` | `send`
- `attempts`, `send_status_code`, `send_qq_code`
- `file_uuid_hash` (sha256 truncated — not raw uuid if treated sensitive; uuid alone is OK as opaque id)
- `ttl` (integer)
- `issue_code`: e.g. `qqbot_rich_media_upload_failed` / `qqbot_send_failed`
- **Never:** Authorization header, access_token, upload `url`, `file_data`, attachment download URLs, document bytes

### Pattern 3: Adapter deliver routing

**What:** Branch on `_delivery_type` without Protocol changes.
**When to use:** Always in `deliver()`.

```python
# Pseudocode — extend existing deliver() after window gate
if delivery_type in {"file", "image"}:
    file_url = _optional_string(metadata.get("file_url") or metadata.get("media_url"))
    file_type = _int_or_default(metadata.get("file_type"), 4 if delivery_type == "file" else 1)
    # upload → build_media_envelope → send_message
elif delivery_type == "card":
    ...
```

Update `capabilities()`: `supports_files=True`, `supports_images=True` (voice/video send out of Phase 63 success criteria — leave `supports_voice=False` unless implementing voice egress; inbound voice still parses). Keep `fixture_only` / `network_io` metadata semantics from Phase 62.

### Anti-Patterns to Avoid

- **Storing live `url` on `AttachmentRef.uri` or in metadata:** Violates reference-only policy and FEATURES anti-feature; URLs expire and may leak legal content.
- **Importing `wecom_service.build_file_send_envelope`:** Breaks `test_no_wecom_import.py`.
- **Editing MessageType enum to add `video`:** Frozen platform-contract — map video → AttachmentRef.kind=`video`, message_type=`file`.
- **Skipping upload and sending raw URL as media:** Official API requires `file_info` from upload for `msg_type=7`.
- **Logging tokens or file_data in evidence:** Smoke/Phase 67 will enforce sanitized evidence; start clean here.
- **New channel-core module for QQ-only media:** CONTEXT says prefer extend normalization/sender.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Attachment contract shape | Custom dict schema | `platform_contract.events.AttachmentRef` | Frozen dataclass + JSON Schema `$defs/attachment_ref` |
| Bearer token cache/refresh | New token client | Phase 61 `TokenManager` | Single-flight + margin already proven |
| Message POST + retry | Ad hoc urllib loops | Phase 62 `send_message` / `_is_transient` | Extend code sets; don't fork |
| Stable IDs | Random UUIDs per parse | Existing `_stable_id` / hashlib | Deterministic fixture replay |
| Output boundary on captions | Custom filters | `apply_output_policy` | Already wired for text/markdown |
| Owned notices on window expiry | Custom copy | `build_owned_notice` | Phase 62 pattern |

**Key insight:** Rich media is mostly composition of existing TokenManager + MessageTransport + AttachmentRef — the novel pieces are opaque URI mapping and the upload step, not a new stack.

## Common Pitfalls

### Pitfall 1: Putting QQ attachment URL into AttachmentRef.uri
**What goes wrong:** Contract logs / AgentTurn carry time-limited URLs with legal document content; privacy gate fails; URLs die on replay.
**Why it happens:** REQUIREMENTS wording “URL stored as `raw_payload_ref`” is easy to misread as “put URL string in the ref field.”
**How to avoid:** Interpret as reference-only policy: live URL never persisted; `uri=qqbot-media://{id}`; `metadata.raw_payload_ref` = existing payload ref (fixture:// or host ref). Assert `url` absent from asdict(AttachmentRef) in tests.
**Warning signs:** Tests that `assertEqual(att.uri, "https://...")`.

### Pitfall 2: Forgetting group companion `content` on media send
**What goes wrong:** Group OpenAPI marks `content` required for message send; media-only body may 4xx.
**Why it happens:** C2C `content` is optional; group docs differ.
**How to avoid:** Mirror Phase 62 markdown pattern — set `"content": ""` on media envelopes.
**Warning signs:** Group FakeMessageTransport bodies missing `content`.

### Pitfall 3: Not retrying 304082/304083
**What goes wrong:** Transient QQ media pull/convert failures surface as hard delivery failures.
**Why it happens:** Phase 62 terminal/transient sets omit these codes.
**How to avoid:** Add both to `_TRANSIENT_QQ_CODES`; cover with Fake upload/send queue tests.
**Warning signs:** Single-attempt failure on 304082 in unit tests.

### Pitfall 4: Loading DOCX/PDF bytes into channel package by default
**What goes wrong:** Memory pressure + accidental logging of legal payloads; harder to keep evidence sanitized.
**Why it happens:** Docs allow `file_data` base64 as alternative to `url`.
**How to avoid:** Prefer metadata `file_url` (host-reachable HTTPS). Accept `file_data` only when explicitly provided for fixture/offline tests; never write bytes to DeliveryResult.metadata.
**Warning signs:** `file_data` keys in evidence or fixtures committed with real documents.

### Pitfall 5: Treating MessageType as extensible for video
**What goes wrong:** Temptation to edit frozen enums/schemas → ADAPTER-04 failure.
**Why it happens:** QQ `content_type` includes video; enum has no video.
**How to avoid:** `AttachmentRef.kind="video"`; `AgentTurn.message_type="file"`.
**Warning signs:** Diffs under `packages/platform-contract/`.

### Pitfall 6: Skipping passive-reply window on file deliver
**What goes wrong:** Over-window file sends fail at QQ with opaque errors; no interim notice.
**Why it happens:** New deliver branch forgets Phase 62 gate.
**How to avoid:** Keep window check before upload when `msg_id` present (same as text path).
**Warning signs:** File deliver tests without window-expiry case.

## Code Examples

### Inbound: wire attachments into normalize_message_event

```python
# Extend normalize_message_event after content resolution:
attachments = _attachments_from_event(d, payload_ref=payload_ref or event.raw_payload_ref)
message_type = _message_type_from_attachments(attachments, default="text")
if message_type == "voice" and not content:
    # optional ASR passthrough from first voice attachment metadata
    for att in attachments:
        asr = att.metadata.get("asr_refer_text") if isinstance(att.metadata, dict) else None
        if asr:
            content = str(asr)
            break

return AgentTurn(
    ...,
    message_type=message_type,
    content=content if content else None,
    attachments=attachments,
    metadata={...},
)
```

### Egress: media envelope + upload URL builder

```python
def wire_files_url_for_scene(
    scene: str,
    *,
    user_openid: str | None = None,
    group_openid: str | None = None,
) -> str:
    if scene == "c2c":
        safe = _require_openid(user_openid or "", label="user_openid")
        return f"{_API_BASE}/v2/users/{safe}/files"
    if scene == "group":
        safe = _require_openid(group_openid or "", label="group_openid")
        return f"{_API_BASE}/v2/groups/{safe}/files"
    raise SendError("unsupported QQ Bot scene")


def build_media_envelope(
    *,
    file_info: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    # No user text → no output_policy content; still carry msg_id/msg_seq
    return {
        "msg_id": msg_id,
        "msg_seq": msg_seq,
        "msg_type": 7,
        "media": {"file_info": file_info},
        "content": "",
    }
```

### Sanitized evidence helper

```python
def _rich_media_evidence(
    *,
    stage: str,
    attempts: int,
    status_code: int | None = None,
    qq_code: int | None = None,
    file_uuid: str | None = None,
    ttl: int | None = None,
    issue_code: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "rich_media_stage": stage,
        "attempts": attempts,
    }
    if status_code is not None:
        out["send_status_code"] = status_code
    if qq_code is not None:
        out["send_qq_code"] = qq_code
    if file_uuid:
        out["file_uuid_hash"] = hashlib.sha256(file_uuid.encode()).hexdigest()[:16]
    if ttl is not None:
        out["ttl"] = ttl
    if issue_code:
        out["issue_code"] = issue_code
    return out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QQ fixtures `attachments: []` ignored | Parse into AttachmentRef | Phase 63 | EGRESS-05 |
| Text/markdown/keyboard only egress | + upload + msg_type=7 | Phase 63 | EGRESS-06 DOCX/PDF |
| WeCom MediaId → wecom-media:// | QQ url → qqbot-media:// (opaque) | v1.8 design | Cross-channel ref parity |
| Milestone research suggested httpx | Stdlib urllib (Phases 61–62 locked) | 2026-07-09 | No new deps |

**Deprecated/outdated:**
- Using `httpx` for QQBot package HTTP — superseded by `dependencies = []` + urllib twin.
- Storing attachment URLs in contract logs — explicitly an anti-feature.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Group media send accepts empty-string `content` companion like markdown | Pattern 2 | May need omit vs `""` — verify with Fake shape tests; live confirm in Phase 67 |
| A2 | Host always supplies HTTPS `file_url` for DOCX/PDF upload (channel does not fetch artifact storage itself) | Pattern 2 | If host only has local paths, need deferred storage adapter — out of scope; fail closed with issue_code |
| A3 | Voice ASR passthrough into `content` when empty is desired in Phase 63 | Pattern 1 | Harmless if deferred; FEATURES marks LOW complexity |
| A4 | `supports_images=True` in capabilities is acceptable even if image egress is secondary to DOCX/PDF | Adapter | Capability advertising only; no Protocol change |

**If this table is empty:** N/A — assumptions listed above need planner awareness, not user blockers for discuss-skipped mode.

## Open Questions (RESOLVED)

1. **Should inbound video set `message_type="file"` or keep `"text"` when caption exists?**
   - **RESOLVED (planner 2026-07-09):** Primary from first attachment (`video→file`); keep caption in `content`. Frozen MessageType has no `video`; AttachmentRef.kind stays `"video"`.

2. **Does Phase 63 update `adapter.capabilities` flags now or wait for Phase 65?**
   - **RESOLVED (planner 2026-07-09):** Set `supports_files=True` and `supports_images=True` in Phase 63 when deliver file/image path exists; keep `fixture_only` / `network_io=False` metadata until Phase 65 live IO. Leave `supports_voice=False` (voice egress out of scope).

3. **Exact evidence schema for Phase 67 smoke toolkit**
   - **RESOLVED (planner 2026-07-09):** Stabilize evidence keys in `_rich_media_evidence` / DeliveryResult.metadata as Pattern 2: `rich_media_stage`, `attempts`, `send_status_code`, `send_qq_code`, `file_uuid_hash`, `ttl`, `issue_code`. Never tokens, upload URLs, `file_data`, or attachment download URLs. Phase 67 may formalize a shared helper later without renaming these keys.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | qqbot package | ✓ | 3.14.6 | — |
| stdlib urllib / asyncio | upload + send | ✓ | stdlib | — |
| platform-contract AttachmentRef | inbound mapping | ✓ | in-repo | — |
| channel-core output_policy | caption policy (optional) | ✓ | in-repo | — |
| Live QQ OpenAPI | real upload/send | ✗ (CI) | — | FakeFileUploadTransport / FakeMessageTransport |
| slopcheck | package audit | ✓ | 0.6.1 | N/A (no installs) |

**Missing dependencies with no fallback:** none for CI implementation.

**Missing dependencies with fallback:** Live QQ network — Fake transports for all automated tests; live deferred to Phase 65/67 human gate.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib) + IsolatedAsyncioTestCase |
| Config file | `packages/channels/qqbot/pyproject.toml` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_normalization packages.channels.qqbot.tests.test_sender -v` |
| Full suite command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EGRESS-05 | attachments[] → AttachmentRef; no live URL/bytes; schema valid | unit | `… test_normalization.AttachmentRefTests -v` | ❌ Wave 0 |
| EGRESS-05 | message_type image/voice/file (+ video→file); ASR optional | unit | same | ❌ Wave 0 |
| EGRESS-06 | upload POST files URL + body file_type=4; returns file_info | unit | `… test_sender.RichMediaUploadTests -v` | ❌ Wave 0 |
| EGRESS-06 | build_media_envelope msg_type=7 + media.file_info | unit | `… test_sender.SenderEnvelopeTests` (extend) | ✅ extend |
| EGRESS-06 | retry 304082/304083; 401 invalidate; sanitized evidence | unit | `… test_sender.RichMediaRetryTests -v` | ❌ Wave 0 |
| EGRESS-06 | adapter.deliver file path upload→send; window gate | unit | `… test_qqbot_channel_adapter -v` | ✅ extend |
| ADAPTER-04 | no wecom import; dependencies=[]; no contract edits | unit | `… test_no_wecom_import test_v1_8_safety_baseline test_contract_freeze_not_violated -v` | ✅ |

### Sampling Rate

- **Per task commit:** quick run (normalization + sender rich-media classes)
- **Per wave merge:** full qqbot discover suite (baseline 197 tests + new)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] Fixture `qqbot_c2c_message_with_attachments.json` (image + file + voice samples; synthetic URLs never asserted as stored)
- [ ] `AttachmentRefTests` in `test_normalization.py` (or dedicated class) — RED before implementation
- [ ] `RichMediaUploadTests` / `RichMediaRetryTests` in `test_sender.py`
- [ ] Adapter deliver file/image cases + evidence key assertions
- [ ] Assert `AttachmentRef.uri` starts with `qqbot-media://` and asdict has no `https://` attachment URLs

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | TokenManager bearer; never log token |
| V3 Session Management | no | N/A for this phase |
| V4 Access Control | partial | Openid path validation `_OPENID_RE`; host allowlist `api.sgroup.qq.com` |
| V5 Input Validation | yes | Structured attachment mapping; reject non-Mapping items; openid regex |
| V6 Cryptography | no new | Ed25519 already Phase 59; no new crypto |

### Known Threat Patterns for QQ rich media

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Legal document bytes in logs/evidence | Information Disclosure | Reference-only AttachmentRef; sanitized evidence helper; no file_data in metadata |
| SSRF via attacker-controlled upload URL | Tampering / Info Disclosure | Channel accepts host-provided URL only; production host must allowlist artifact origins (document as host duty; channel validates URL is https + non-empty) `[ASSUMED: host allowlist]` |
| Token leak in SendError / evidence | Information Disclosure | Reuse `_sanitize_send_error`; never include Authorization |
| Openid path injection | Tampering | Existing `_OPENID_RE` on files URL builder |
| Storing expired QQ CDN URLs | Information Disclosure | Opaque `qqbot-media://` only |

## Sources

### Primary (HIGH confidence)

- [Official QQ rich-media upload](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/rich-media.html) — `/v2/users/{openid}/files`, `/v2/groups/{group_openid}/files`, `file_type` 1–4, `file_info`/`ttl`
- [Official QQ send message](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html) — `msg_type=7`, `media.file_info`, errors 304082/304083
- [Official QQ events](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/event.html) — `attachments[]` fields (`content_type`, `filename`, `url`, `asr_refer_text`, …)
- `packages/platform-contract/.../events.py` — `AttachmentRef` / `AgentTurn.attachments`
- `packages/platform-contract/.../schemas/common.schema.json` — `$defs/attachment_ref`, `message_type` enum
- Phase 61/62 implementations — `token_manager.py`, `sender.py`, `adapter.py`
- `.planning/research/FEATURES.md` — rich media inbound/egress notes + URL storage anti-feature

### Secondary (MEDIUM confidence)

- `.planning/research/STACK.md` — msg_type 7 mapping table (pre-phase; httpx recommendation superseded)
- WeCom `_attachments` / `build_file_send_envelope` — pattern analog only (no import)

### Tertiary (LOW confidence)

- Group media `content: ""` companion requirement — inferred from Phase 62 markdown + group content-required docs; confirm in tests/live later

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; reuse verified Phase 61/62 stack
- Architecture: HIGH — official QQ docs + existing AttachmentRef/WeCom analog
- Pitfalls: HIGH — privacy anti-feature and frozen enum constraints verified in-repo

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days; QQ OpenAPI stable)
