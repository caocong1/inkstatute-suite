# Phase 75: Channel Config Apply - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 14
**Analogs found:** 13 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/channels/qqbot/.../config.py` | model | transform | (self — extend `from_env` with `from_operator_doc`) | exact |
| `packages/channels/wecom/.../config.py` | model | transform | `packages/channels/qqbot/.../config.py` `from_env` | exact |
| `services/qqbot-service/.../config.py` | model | transform | (self — `QQBotHostConfig.from_env` + refs normalize) | exact |
| `services/qqbot-service/.../wiring.py` | service | transform | (self — `build_qqbot_channel_config` dual-knob AND) | exact |
| `services/wecom-service/.../channel_wiring.py` *(new or thin module)* | service | transform | `services/qqbot-service/.../wiring.py` | role-match |
| `packages/platform-runtime/.../feature_flags.py` | model | request-response | (self — add `wecom_channel_enabled` like `qqbot_channel_enabled`) | exact |
| `services/admin-console-api/.../config_api.py` | controller | request-response | (self — extend `_config_metadata` / channels GET) | exact |
| `services/admin-web-ui/.../dashboard.py` | component | request-response | (self — `_page_template` + `_esc` + nav) | exact |
| `services/admin-web-ui/.../server.py` | controller | request-response | (self GET) + `lawyer-web-chat/.../server.py` `do_POST` | role-match |
| `services/admin-web-ui/.../api_client.py` | utility | request-response | (self — extend with `handle_admin_put` proxy) | exact |
| `packages/channels/qqbot/tests/test_from_operator_doc.py` *(new)* | test | transform | `packages/channels/wecom/tests/test_wecom_channel_adapter.py` `from_env` cases | exact |
| `services/qqbot-service/tests/test_operator_config_apply.py` *(new)* | test | transform | `services/qqbot-service/tests/test_wiring_flag_config.py` | exact |
| `services/admin-web-ui/tests/test_channel_config_form.py` *(new)* | test | request-response | `services/admin-web-ui/tests/test_server.py` + `test_dashboard.py` | exact |
| `services/admin-console-api/tests/test_config_api.py` | test | request-response | (self — extend dual-knob metadata assertions) | exact |

**Package wiring rule:** Keep empty-deps. Hosts/UI import `inkstatute_operator_config` and channel packages via V2 gate `PYTHONPATH` (Phase 74 already added `operator_config_src` to admin-web-ui / admin-console-api gates).

**Out of Phase 75:** provider catalog (76), vision runtime (77), complete CSRF-protected SSR surface (78). Incremental channel SSR forms are in-scope; full CSRF verification is Phase 78.

---

## Pattern Assignments

### `packages/channels/qqbot/.../config.py` (model, transform)

**Analog:** same file — `from_env` (lines 27–36)

**Add `from_operator_doc` beside `from_env`** — copy field mapping, accept `QQBotChannelDoc` (or Mapping with same keys). Do **not** AND platform flags here; adapters must not import `RuntimeFeatureFlags`.

```python
@classmethod
def from_operator_doc(cls, doc: "QQBotChannelDoc | Mapping[str, Any]") -> "QQBotChannelConfig":
    """Materialize channel config from operator-store doc (refs only).

    ``enabled`` is the *host/doc* knob only. Dual-knob AND with
    ``RuntimeFeatureFlags.qqbot_channel_enabled`` lives in host wiring.
    """
    if hasattr(doc, "enabled"):
        return cls(
            channel_id=getattr(doc, "channel_id", "qqbot") or "qqbot",
            enabled=bool(doc.enabled),
            app_id_ref=doc.app_id_ref,
            app_secret_ref=doc.app_secret_ref,
            token_secret_ref=doc.token_secret_ref,
            bot_secret_ref=doc.bot_secret_ref,
            metadata=dict(getattr(doc, "metadata", {}) or {}),
        )
    # Mapping fallback mirrors from_env field names
    return cls(
        channel_id=str(doc.get("channel_id") or "qqbot"),
        enabled=bool(doc.get("enabled", False)),
        app_id_ref=doc.get("app_id_ref") or None,
        app_secret_ref=doc.get("app_secret_ref") or None,
        token_secret_ref=doc.get("token_secret_ref") or None,
        bot_secret_ref=doc.get("bot_secret_ref") or None,
        metadata=dict(doc.get("metadata") or {}),
    )
```

**Field SoT:** `packages/operator-config/.../schemas.py` `QQBotChannelDoc` (lines 24–38) — identical `*_ref` names. Prefer importing the doc type only under `TYPE_CHECKING` or accept Mapping to avoid hard package dep from channel → operator-config (channels stay `dependencies = []`).

**Secondary analog:** Architecture Pattern 1 (`.planning/research/ARCHITECTURE.md` lines 134–141).

---

### `packages/channels/wecom/.../config.py` (model, transform)

**Analog:** `packages/channels/qqbot/.../config.py` `from_env` + WeCom self `from_env` (lines 27–34)

Mirror QQBot: add `from_operator_doc` mapping `WeComChannelDoc` fields (`token_secret_ref`, `encoding_aes_key_secret_ref`, `corp_id_ref`, `enabled`). Keep `from_env` for env fallback.

```python
@classmethod
def from_operator_doc(cls, doc: Mapping[str, Any] | object) -> "WeComChannelConfig":
    # enabled = doc knob only; platform AND in wecom host wiring
    ...
```

---

### `services/qqbot-service/.../config.py` + `wiring.py` (model/service, transform)

**Analog:** `QQBotHostConfig.from_env` (config.py lines 28–49) + `build_qqbot_channel_config` (wiring.py lines 48–65)

**Dual-knob AND (locked — never collapse):**

```python
# wiring.py lines 59–65 — KEEP THIS SHAPE
return QQBotChannelConfig(
    enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
    app_id_ref=host_config.app_id_ref,
    app_secret_ref=host_config.app_secret_ref,
    token_secret_ref=host_config.token_secret_ref,
    bot_secret_ref=host_config.bot_secret_ref,
)
```

**Phase 75 apply path:** Prefer operator store → host config → dual-knob factory; env remains fallback when store missing/empty.

Suggested host helper (new method on `QQBotHostConfig` or thin loader):

```python
@classmethod
def from_operator_channels(cls, channels: ChannelsDoc | Mapping[str, Any]) -> "QQBotHostConfig":
    qq = channels.qqbot if hasattr(channels, "qqbot") else channels["qqbot"]
    return cls(
        enabled=bool(getattr(qq, "enabled", False)),
        app_id_ref=normalize_config_secret_ref(getattr(qq, "app_id_ref", None), field="app_id_ref"),
        # ... same refs as from_env
    )
```

Then wiring:

```python
# Prefer: store.load() → HostConfig.from_operator_channels → build_qqbot_channel_config
# Fallback: HostConfig.from_env(env) when no store / load fails closed to defaults
host = QQBotHostConfig.from_operator_channels(document.channels)
channel_config = build_qqbot_channel_config(flags=flags, host_config=host)
```

**Do not** resolve secrets in apply/materialize — keep `resolve_secret_ref` at live-injection edge only (`wiring.py` lines 106–107).

**Restart vs hot-reload:** Document restart-to-apply in host README unless plan proves safe in-process reload (CONTEXT locked).

---

### `services/wecom-service/.../channel_wiring.py` (service, transform) — likely new

**Analog:** `services/qqbot-service/src/qqbot_service/wiring.py` `build_qqbot_channel_config`

WeCom host today has no dual-knob factory (channel package `enabled` only). Phase 75 should introduce the same AND pattern:

```python
def build_wecom_channel_config(
    *,
    flags: RuntimeFeatureFlags,
    host_enabled: bool,
    doc: WeComChannelConfig | Mapping[str, Any],
) -> WeComChannelConfig:
    base = WeComChannelConfig.from_operator_doc(doc)  # or from_env fallback
    return WeComChannelConfig(
        enabled=bool(flags.wecom_channel_enabled and host_enabled and base.enabled),
        # OR: host_enabled == doc.enabled; AND with platform flag only once
        token_secret_ref=base.token_secret_ref,
        encoding_aes_key_secret_ref=base.encoding_aes_key_secret_ref,
        corp_id_ref=base.corp_id_ref,
        metadata=base.metadata,
    )
```

**Prefer:** `enabled = flags.wecom_channel_enabled AND doc.enabled` (doc is the host knob), matching QQ after WR-02 fix. Do not invent a third toggle.

**No analog for full WeCom host factory** — wecom-service has ingress/delivery modules but no `build_*_wired_runtime`. Keep Phase 75 thin: materialize config + document apply semantics; do not rebuild WeCom ingress.

---

### `packages/platform-runtime/.../feature_flags.py` (model, modify)

**Analog:** same file — `qqbot_channel_enabled: bool = False` (line 23)

CHAN-03 requires equivalent WeCom platform flag. Add:

```python
wecom_channel_enabled: bool = False  # default OFF; dual-knob with WeComChannelConfig/doc.enabled
```

Extend `packages/platform-runtime/tests/test_feature_flags.py` with default-False assertion (M2/M3 style). Adapters still must not import flags.

---

### `services/admin-console-api/.../config_api.py` (controller, modify)

**Analog:** same file — `handle_config_get` / `handle_config_put` / `_config_metadata` (lines 30–100, 163–169)

**Reuse Phase 74 section PUT for CHAN-01/02** — `/config/channels` already round-trips qqbot+wecom refs (`test_config_api.py` `_VALID_CHANNELS`). Phase 75 extends **visibility** of dual-knob effective state (CHAN-03), not a new route.

**Enrich channels responses** (GET and successful PUT) with allowlisted booleans only:

```python
def _config_metadata(feature_flags: RuntimeFeatureFlags) -> dict[str, Any]:
    return {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": bool(feature_flags.operator_config_enabled),
        "read_only": False,
        # CHAN-03 — platform knobs (never collapse into data.*.enabled)
        "qqbot_channel_enabled": bool(feature_flags.qqbot_channel_enabled),
        "wecom_channel_enabled": bool(getattr(feature_flags, "wecom_channel_enabled", False)),
    }


def _channels_effective(data: dict[str, Any], flags: RuntimeFeatureFlags) -> dict[str, Any]:
    """Attach effective enablement without mutating stored doc.enabled."""
    qq = data.get("qqbot") or {}
    we = data.get("wecom") or {}
    return {
        "qqbot": {
            "platform_flag": bool(flags.qqbot_channel_enabled),
            "host_enabled": bool(qq.get("enabled", False)),
            "effective_enabled": bool(
                flags.qqbot_channel_enabled and qq.get("enabled", False)
            ),
        },
        "wecom": {
            "platform_flag": bool(getattr(flags, "wecom_channel_enabled", False)),
            "host_enabled": bool(we.get("enabled", False)),
            "effective_enabled": bool(
                getattr(flags, "wecom_channel_enabled", False) and we.get("enabled", False)
            ),
        },
    }
```

Return shape:

```python
return 200, {
    "data": payload["channels"],           # refs-only store projection
    "effective": _channels_effective(...), # dual-knob view (CHAN-03)
    "metadata": _config_metadata(flags),
}
```

**Secrets (CHAN-04):** Keep `document_to_payload` only — never call `resolve_secret_ref`. Planted-raw tests already in `test_config_api.py`; extend if new fields added.

**Do not** put dual-knob AND into `data.qqbot.enabled` — that would collapse knobs and break store round-trip.

---

### `services/admin-web-ui/.../dashboard.py` (component, modify)

**Analog:** same file — `_page_template` (lines 68–132), `_esc` (18–20), nav (71–78), section renderers

**Incremental channel SSR form** (CONTEXT: “when present”; Phase 78 owns full CSRF):

1. Add nav entry `("/config/channels", "Channels")`.
2. Add `title_map` + renderer `_render_channels_section`.
3. Show **three** enablement rows per channel (platform / host / effective) — never a single bypass checkbox that writes both knobs.
4. Credential inputs are text fields for `*_ref` only; labels say `env:…` / `secret://…`.
5. All dynamic values through `_esc` / boundary; keep CSP-compatible inline CSS (no scripts required for MVP form POST).

```python
def _render_channels_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    channels = data.get("data") or {}
    effective = data.get("effective") or {}
    # Render dual-knob table from effective.qqbot / effective.wecom
    # Render <form method="post" action="/config/channels"> with host enabled + *_ref fields
    # Platform flag: read-only display (operators flip RuntimeFeatureFlags outside this form
    #   OR separate clearly labeled controls that do not overwrite each other)
    ...
```

**Form field naming:** mirror API section body (`qqbot.enabled`, `qqbot.app_id_ref`, …) so POST handler can build the same dict as `test_config_api._VALID_CHANNELS`.

**Secondary HTML form analog:** `services/lawyer-web-chat/.../server.py` `_render_login_page` (lines 380–407) for `<form method="post">` + stdlib server `do_POST` — but prefer `urllib.parse.parse_qs` for urlencoded admin forms (lawyer login currently expects JSON).

---

### `services/admin-web-ui/.../server.py` + `api_client.py` (controller/utility, modify)

**Analog GET:** `handle_admin_web_ui_request` (server.py lines 61–166) — flag → route → RBAC → proxy → render.

**Analog POST:** `LawyerWebChatServer.do_POST` (lawyer-web-chat server.py lines 474–491) — read `Content-Length`, pass body to testable handler.

**Extend admin UI:**

```python
_SECTION_MAP = {
    ...
    "/config/channels": "channels",
}

# GET /config/channels → client.proxy(handle_admin_get, "/config/channels", ...)
# POST /config/channels → parse form → client.proxy_put(handle_admin_put, "/config/channels", body, ...)
# Guard path for RBAC: "/config" (matrix already ADMIN+OPERATOR from Phase 74)
```

**api_client.py extension:**

```python
HandleAdminPut = Callable[..., tuple[int, dict[str, Any]]]

def proxy_put(
    self,
    handle_admin_put: HandleAdminPut,
    path: str,
    body: Mapping[str, Any],
    identity: Identity,
    *,
    feature_flags: Any,
    config_store: Any = None,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
    auth_header: str | None = None,
) -> tuple[int, dict[str, Any]]:
    headers: dict[str, str] = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    return handle_admin_put(
        path, body, headers, feature_flags, env,
        config_store=config_store, rbac_secret=rbac_secret,
    )
```

**CSRF:** Phase 78 owns complete verification. MVP may ship POST without CSRF token but must not claim CSRF-complete; document honesty in SUMMARY.

**Empty-deps:** Inject `handle_admin_put` + `OperatorConfigStore` the same way GET injects `handle_admin_get` (server attributes / handler kwargs).

---

### Tests

| New/extended test | Analog | Must prove |
|-------------------|--------|------------|
| `test_from_operator_doc.py` (qqbot + wecom) | wecom `test_from_env_*` | Doc → config field parity; default `enabled=False`; no flag import in channel package |
| `test_operator_config_apply.py` / extend `test_wiring_flag_config.py` | wiring dual-knob tests lines 51–105 | Store/doc ON + flag OFF → disabled; flag ON + doc OFF → disabled; both ON → enabled; refs copied; no secret resolve in materialize |
| `test_config_api.py` | self `_VALID_CHANNELS` | GET/PUT include `effective` with both knobs; response never contains planted raw secrets; `data.*.enabled` still host knob only |
| `test_channel_config_form.py` | `test_server.py` / `test_dashboard.py` | GET renders dual-knob labels; POST proxies PUT; lawyer/viewer 403; html.escape on refs; no resolved secret echo |
| `test_feature_flags.py` | self | `wecom_channel_enabled` defaults False |

---

## Shared Patterns

### Dual-knob AND (never collapse)
**Source:** `services/qqbot-service/src/qqbot_service/wiring.py` lines 48–65 + `test_wiring_flag_config.py` WR-02 cases  
**Apply to:** QQ apply path, WeCom apply path, API `effective` view, SSR form display  
- Platform flag and host/doc `enabled` are independent.
- Effective = `A AND B`.
- UI must show both + effective; must not offer a single control that sets both True.

### Refs-only credentials + process-edge resolve
**Source:** `inkstatute_operator_config.secrets.normalize_config_secret_ref` + `qqbot_service.secrets.resolve_secret_ref`  
**Apply to:** store/API/UI fields; host live injection only  
- Accept `env:NAME`, `secret://…`, bare env keys.
- Errors never echo rejected values.
- GET/PUT/SSR never call resolve.

### Section-scoped `/config/channels` API
**Source:** `admin_console_api/config_api.py` Phase 74  
**Apply to:** CHAN-01/02 mutate surface  
- Body = channels object (or single unwrap); no full-document wipe.
- RBAC ADMIN+OPERATOR already on `/config`.
- PUT refuses when `operator_config_enabled` False.

### Admin Web UI SSR conventions
**Source:** `admin_web_ui/dashboard.py` + `server.py`  
**Apply to:** channel page  
- `html.escape` all dynamic content; CSP `default-src 'self'`.
- Testable `handle_*_request` function (not only `BaseHTTPRequestHandler`).
- Proxy through admin-console-api; UI never opens the JSON store directly for authority (may inject store only as API dependency).

### Empty-deps + PYTHONPATH
**Source:** `scripts/run_v2_gates.py` admin-web-ui / qqbot-service / wecom-service gates  
**Apply to:** any new imports of operator-config from hosts/UI  
- Do not add package deps to `pyproject.toml` `dependencies = []` packages.
- Extend gate PYTHONPATH if wecom/qqbot tests import operator-config.

### Restart-to-apply honesty (MVP)
**Source:** CONTEXT locked + ARCHITECTURE hot-reload note  
**Apply to:** host README / SUMMARY  
- Document that channel apply requires process restart unless plan proves safe reload.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `services/wecom-service/.../channel_wiring.py` (full wired runtime) | service | transform | No WeCom equivalent of `build_qqbot_wired_runtime`; copy **dual-knob mapping only**, do not invent a full WeCom runtime factory in Phase 75 |

Admin-web-ui has **no existing mutate form** — use dashboard escape/nav + lawyer-web-chat `do_POST` skeleton + Phase 74 `handle_admin_put` as the composed pattern.

---

## Metadata

**Analog search scope:** `packages/channels/{qqbot,wecom}/`, `packages/operator-config/`, `packages/platform-runtime/feature_flags.py`, `services/{qqbot-service,wecom-service,admin-console-api,admin-web-ui,lawyer-web-chat}/`, `.planning/phases/74-admin-config-api-rbac/74-PATTERNS.md`, `.planning/research/{ARCHITECTURE,FEATURES}.md`, `75-CONTEXT.md`  
**Files scanned:** ~30 primary sources  
**Pattern extraction date:** 2026-07-10

### Key planner takeaways
1. **Apply path:** `OperatorConfigDocument.channels` → `*ChannelConfig.from_operator_doc` → host `build_*_channel_config` with **flag AND doc.enabled**; env `from_env` remains fallback.
2. **API:** Reuse Phase 74 `/config/channels`; add `effective` dual-knob projection — do not collapse into `data.*.enabled`.
3. **WeCom platform flag:** Add `wecom_channel_enabled` default False (QQ already has `qqbot_channel_enabled`).
4. **SSR:** Extend admin-web-ui dashboard/server with `/config/channels` GET form + POST→`handle_admin_put`; CSRF completeness deferred to Phase 78.
5. **Secrets:** refs-only end-to-end; resolve only in qqbot (and future wecom) process-edge live injection.
