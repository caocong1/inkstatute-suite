# Operator Config Runbook

Step-by-step operator guide for the InkStatute Operator Config Console (`services/admin-web-ui`).

> The admin console edits configuration. It does not perform live acceptance. Phase 5 WeCom UAT, Phase 8 lawyer trial, and QQ live acceptance remain carried human gates.

---

## 1. Purpose and prerequisites

This runbook covers changing channel, provider, catalog, and vision configuration through the SSR web UI. All changes are stored in the operator config store as refs and take effect after a runtime restart (MVP — no hot-reload).

**Prerequisites:**

- Operator role (`admin` or `operator`) in RBAC.
- `admin_web_ui_enabled` and `operator_config_enabled` feature flags are ON.
- `ADMIN_CONFIG_EDITORS_ENABLED=1` if your deployment gates config editing through env.
- A valid RBAC token in the `Authorization` header.

**Health checks:**

```bash
# Admin Web UI health (requires RBAC token if rbac_enabled)
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://$ADMIN_WEB_UI_HOST:$ADMIN_WEB_UI_PORT/health

# Admin Console API health
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://$ADMIN_CONSOLE_API_URL/health
```

Expected: HTTP 200 and a JSON health body. If the UI returns 503, check `admin_web_ui_enabled`.

---

## 2. Navigating the admin console

- **Dashboard** (`/`) — links to Sessions, Tasks, Feedback, Health, Gates, and the four Config pages.
- **Gate Status** (`/gates`) — automated gate cards plus a "Carried human gates" card.
- Every config page shows a gate-honesty notice at the top.

All pages are server-side rendered with `html.escape` and a strict CSP. No JavaScript is required.

---

## 3. Channel Config

Path: `/config/channels`

### Dual-knob: platform flag and host enabled

- **Platform flag** (`qqbot_channel_enabled` / `wecom_channel_enabled`) is read-only in the UI. It is set through the runtime feature flags or environment.
- **Host enabled** (`channels.qqbot.enabled` / `channels.wecom.enabled`) is editable. It is the operator-controlled switch stored in the operator config store.
- **Effective** enablement = `platform_flag AND host_enabled`. Both must be ON for live IO.

### Secret refs

Use refs only. Examples:

```text
env:INKSTATUTE_QQBOT_APP_ID
secret://qqbot/app-secret
```

Do not paste raw token values into the form fields.

### Fields

| Channel | Field | Ref shape |
|---------|-------|-----------|
| QQBot | `app_id_ref` | `env:INKSTATUTE_QQBOT_APP_ID` |
| QQBot | `app_secret_ref` | `env:INKSTATUTE_QQBOT_APP_SECRET` |
| QQBot | `token_secret_ref` | `env:INKSTATUTE_QQBOT_TOKEN` |
| QQBot | `bot_secret_ref` | `env:INKSTATUTE_QQBOT_BOT_SECRET` |
| WeCom | `token_secret_ref` | `env:INKSTATUTE_WECOM_TOKEN` |
| WeCom | `encoding_aes_key_secret_ref` | `env:INKSTATUTE_WECOM_ENCODING_AES_KEY` |
| WeCom | `corp_id_ref` | `env:INKSTATUTE_WECOM_CORP_ID` |

### Save

1. Set the host enabled checkbox(es) as required.
2. Fill in the ref fields.
3. Click **Save channel config**.
4. Restart QQ/WeCom hosts to apply (the UI shows a restart notice).

---

## 4. Provider Config

Path: `/config/providers`

### Built-in vendors

- **OpenAI** — canonical `api_base_url` is read-only (`https://api.openai.com/v1`). Provide `api_key_ref`.
- **Anthropic** — canonical `api_base_url` is read-only (`https://api.anthropic.com/v1`). Provide `api_key_ref`.
- Built-in vendors use a preset catalog; the model allowlist is not editable.

### Custom OpenAI-compatible provider

- Set kind to `custom`.
- Enter a `provider_id` (e.g., `custom-endpoint`).
- Enter `api_base_url` (e.g., `https://custom.example.com/v1`).
- Enter `api_key_ref` (e.g., `env:CUSTOM_API_KEY`).
- Enter a comma-separated `model_allowlist` (e.g., `local-gpt,local-vision`).

### Probe

- A **Probe connection** button appears when the main probe target is configured.
- Probe is non-destructive and does not log response bodies or resolved secrets.
- Probe success is `status: ok` and remains `not_live_acceptance` evidence.

### Save

1. Enable the provider and fill the fields.
2. Click **Save provider config**.
3. Restart the runtime to apply.

---

## 5. Model Catalog

Path: `/config/catalog`

### Main model selection

- The catalog shows built-in models with `Vision: supported` or `Vision: not supported` badges.
- Select a provider (or use the only one) and the desired model.
- Click **Save catalog selection**.

### Vision capability

The `supports_vision` badge is used by Phase 77 routing. If the main model does not support vision, configure a dedicated vision model on `/config/vision`.

---

## 6. Vision Config

Path: `/config/vision`

### Routing mode

- **Auto** — use the multimodal main model when it supports vision; otherwise route images through the vision model.
- **Always preprocess** — always route images through the vision model before main.
- **Main only** — never call a vision model; fail-closed on images the main model cannot read.

### Vision provider and model

- Optional. Required only when routing mode needs a dedicated vision step.
- Select from providers registered in Provider Config. Model list is filtered by provider kind.
- Custom providers are not supported for vision routing in the MVP.

### Probe

- **Probe vision connection** appears when a vision provider/model is configured.
- Like the main probe, it does not log response bodies or resolved secrets.

### Save

1. Choose the routing mode.
2. Select a vision provider and model when needed.
3. Click **Save vision config**.
4. Restart the runtime to apply.

---

## 7. Saving and smoke-checking

After saving any config page:

1. Verify the success flash message.
2. Restart the runtime or the relevant host process.
3. Run a health check:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://$ADMIN_CONSOLE_API_URL/health
```

4. Run a non-destructive probe from the Provider or Vision Config page.
5. For QQ/WeCom channels, use `scripts/smoke_test.py --dry-run` for a dry-run smoke check.

All probe and smoke evidence is `not_live_acceptance`. It does not close Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance.

---

## 8. Gate honesty note

The console does not complete live acceptance.

**Carried human gates:**

- Phase 5 WeCom UAT
- Phase 8 lawyer trial
- QQ live acceptance

Saving config, running a probe, or passing a dry-run smoke test does not replace these gates. Automated gate results do not replace live acceptance. Do not edit Hermes `~/.hermes` profiles or gateway configuration for InkStatute providers; use this console and InkStatute env/ref keys.

---

## 9. Common issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 503 from UI | `admin_web_ui_enabled` is OFF | Enable the flag and restart |
| 403 on POST | Missing or invalid CSRF token | Refresh the page and resubmit |
| 403 on GET | Role denied | Use `admin` or `operator` role |
| Provider probe fails | `api_key_ref` not set or `api_base_url` unreachable | Check the ref and network |
| Channel not receiving live traffic | `qqbot_channel_enabled` or `wecom_channel_enabled` OFF, or `host_enabled` OFF | Check both knobs and restart hosts |

---

## 10. Reference

- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — gate-honesty notices and dashboard index cards
- `services/admin-web-ui/src/admin_web_ui/server.py` — `/config/*` request dispatch and CSRF validation
- `services/admin-web-ui/src/admin_web_ui/csrf.py` — `issue_csrf_token` / `validate_csrf_token` (HMAC-SHA256, identity-bound, route-bound)
- `services/admin-web-ui/README.md` — SSR, CSRF, and gate-honesty notes
- `runbook/SMOKE_TEST_RUNBOOK.md` — QQ dry-run and live smoke procedures
