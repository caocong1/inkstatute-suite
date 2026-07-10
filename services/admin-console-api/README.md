# Admin Console API

Admin Console API for InkStatute V2 operator views and operator config. Authenticates via a static token from env (`ADMIN_API_TOKEN`) or, when `rbac_enabled` is on, via RBAC bearer tokens. Exposes sessions, tasks, feedback, gates, and health views with filtering and pagination. Reuses `ContractLogReadModel` and cursor pagination from `services/conversation-read-view/`.

## Feature flags

| Flag | Role |
|------|------|
| `admin_api_enabled` | Outer gate — when `False`, all admin requests are refused (`admin_api_disabled`) |
| `operator_config_enabled` | Mutate gate for `PUT /config/*` — when `False`, PUT returns `403 operator_config_disabled` with no store file side effects; GET `/config/{section}` still returns defaults/file |
| `rbac_enabled` | When `True`, RBAC tokens + `PERMISSIONS_MATRIX` enforce role access |

Defaults: all flags `False`.

## Config surface (`/config/*`)

Section-scoped GET/PUT for ADMIN and OPERATOR only (LAWYER/VIEWER → `403 forbidden`):

- `GET /config/{channels,providers,catalog,vision}` — refs-only section JSON
- `PUT /config/{channels,providers,catalog,vision}` — replace one section via `OperatorConfigStore`

Bare `/config` and unknown sections return `404`. Secrets are stored and returned as `*_ref` values only — raw `api_key` / `sk-…` payloads are rejected (`400 invalid_config`) and never echoed. Admin handlers never resolve `secret://` / `env:` refs.

### Channels dual-knob (`/config/channels`)

Successful GET/PUT responses include an additive `effective` block alongside `data`:

| Field | Meaning |
|-------|---------|
| `effective.{qqbot,wecom}.platform_flag` | Runtime flag (`qqbot_channel_enabled` / `wecom_channel_enabled`) |
| `effective.{qqbot,wecom}.host_enabled` | Store `channels.*.enabled` (host knob) |
| `effective.{qqbot,wecom}.effective_enabled` | `platform_flag AND host_enabled` |
| `effective.{qqbot,wecom}.refs_configured` | Presence-only map of `*_ref` fields → bool |

`data.*.enabled` remains the host knob only — never overwritten with the AND result. PUT accepts host `enabled` + `*_ref` fields only; platform flags are not writable via this API.

Channels success metadata includes `apply_semantics: "restart_required"` (restart-to-apply MVP — no hot-reload claim).

Handlers live in `config_api.py`; persist only through `OperatorConfigStore.save`. Inject a temp-path store in tests — never write the default `.inkstatute/operator-config.json` in CI.

## Operational views (read-only)

`/sessions`, `/tasks`, `/feedback`, `/health`, and `/gates` remain read-only:

- GET responses include `metadata.read_only: true`
- `PUT` on these prefixes returns `405 method_not_allowed` after auth
- `views.py` has no create/update/delete/write helpers

`handle_admin_put` exists solely for `/config/*`.

Health/status views use a field allowlist that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values.

Gate status views run `run_v2_gates.py --json-summary` via subprocess — no gate internals are imported.

## Dependencies / PYTHONPATH

This package has empty runtime deps beyond the monorepo packages it imports. For local unittest:

```bash
PYTHONPATH=services/admin-console-api/src:packages/operator-config/src:packages/platform-runtime/src:packages/rbac/src:packages/platform-contract/src:services/conversation-read-view/src:services/feedback-service/src \
  python -m unittest discover -s services/admin-console-api/tests -q
```

Include `packages/operator-config/src` whenever exercising `/config` handlers.
