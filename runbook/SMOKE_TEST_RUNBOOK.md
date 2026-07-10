# QQBot Smoke Test Runbook

Operator guide for the InkStatute one-click QQBot smoke toolkit (`scripts/smoke_test.py`).

**Scope:** leaf helpers (signature → text/keyboard send → INTERACTION normalize) **plus** host Protocol path (verify_and_ack → ingress/session → deliver) via the same helpers as `services/qqbot-service` webhook composition.

**CI / phase gate:** dry-run only. Live OpenAPI is a **HUMAN GATE** (Phase 72) and is **not** required for CI or phase verification. Do not commit secrets, tokens, raw payloads, or attachment URLs. Dry-run and live script evidence always stamps `not_live_acceptance=true` — CI / autonomous phase complete must **not auto-claim** live acceptance.

---

## Host enablement (LIVE-02)

Before expecting the **deployed host** (`services/qqbot-service`) to accept live QQ traffic, operators must enable the channel via config — this is separate from the smoke CLI value-env injection.

| Knob / key | Role |
|------------|------|
| `INKSTATUTE_QQBOT_CHANNEL_ENABLED` | Host config enable flag (`QQBotHostConfig.enabled`) |
| `INKSTATUTE_QQBOT_APP_ID_REF` | AppId **reference** only (`secret://qqbot/…` or `env:VAR`) |
| `INKSTATUTE_QQBOT_APP_SECRET_REF` | Client-secret **reference** only |
| `INKSTATUTE_QQBOT_TOKEN_SECRET_REF` | Token **reference** only |
| `INKSTATUTE_QQBOT_BOT_SECRET_REF` | BotSecret **reference** only |

**Pitfall:** never plant raw secrets in `*_REF` keys. Refs must be `secret://qqbot/…` or `env:VAR_NAME` shapes. Full `secret://` → value-env map and resolution rules live in [`services/qqbot-service/README.md`](../services/qqbot-service/README.md) — do not duplicate secret values here.

### Dual-knob mapping

Host factory (`qqbot_service.wiring.build_qqbot_wired_runtime`) maps:

```text
QQBotChannelConfig.enabled =
  RuntimeFeatureFlags.qqbot_channel_enabled
  AND QQBotHostConfig.enabled   # from INKSTATUTE_QQBOT_CHANNEL_ENABLED
```

Either knob OFF → channel fails closed / live injection is stripped (`token_manager` / `transport` not injected). Both default OFF. See README “Runtime wiring (Phase 69)” for live-injection details.

### Smoke `--live` value env vs host `*_REF`

| Concern | Smoke CLI `--live` | Host process config |
|---------|--------------------|---------------------|
| Enablement | N/A (CLI mode flag) | `INKSTATUTE_QQBOT_CHANNEL_ENABLED` + platform `qqbot_channel_enabled` (dual-knob) |
| Credentials | Value env: `INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_CLIENT_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`, `INKSTATUTE_QQBOT_USER_OPENID`, `INKSTATUTE_QQBOT_REPLY_MSG_ID` | `INKSTATUTE_QQBOT_*_REF` only (resolved at process edge) |
| Network | Leaf OpenAPI via Urllib after fail-closed env check | Protocol path via webhook composition when dual-knob ON |

Smoke `--live` does **not** flip host dual-knob flags. Enabling the host for production traffic and running controlled smoke are related but distinct operator steps.

---

## Credential / env-var setup (smoke CLI)

Live mode reads **value** environment variables (not production `*_REF` / `secret://` config keys).

| Env var | Dry-run | Live | Purpose |
|---------|---------|------|---------|
| `INKSTATUTE_QQBOT_APP_ID` | unused (fixture) | required | Real AppId value |
| `INKSTATUTE_QQBOT_CLIENT_SECRET` | unused (fixture) | required | Token client secret |
| `INKSTATUTE_QQBOT_BOT_SECRET` | DEMO constant in script | required | Ed25519 BotSecret |
| `INKSTATUTE_QQBOT_USER_OPENID` | fixture openid | required | C2C target openid |
| `INKSTATUTE_QQBOT_REPLY_MSG_ID` | fixture msg_id | required | Passive-reply `msg_id` |

Export values from a private secret store into the shell for the live session only. Never paste secrets into this runbook, git commits, or evidence archives.

### Passive-reply `msg_id` window (live)

For live text / keyboard sends, `INKSTATUTE_QQBOT_REPLY_MSG_ID` must come from a **recent user message** still inside QQ’s passive-reply window. Inventing or reusing a stale `msg_id` will fail the send steps. Dry-run uses a fixture id and does not need a live window.

---

## Dry-run vs live

| Mode | Who runs it | Network | Acceptance |
|------|-------------|---------|------------|
| `--dry-run` | CI / phase verify / autonomous agents | Fake transports only | Always `not_live_acceptance=true` |
| `--live` | Operator **HUMAN GATE** only | Real OpenAPI after fail-closed env | Script still stamps `not_live_acceptance=true`; human may relabel a sanitized archive |

CI and phase verification use **dry-run only**. Autonomous phase complete must **not auto-claim** live acceptance and must not require a live evidence archive.

---

## Dry-run command (CI / default)

From the repo root (no live credentials required):

```bash
python3 scripts/smoke_test.py --dry-run
```

Optional sanitized evidence file:

```bash
python3 scripts/smoke_test.py --dry-run --evidence-out /tmp/qqbot-smoke-dry-run.json
```

Optional callback fixture override (defaults to `packages/channels/qqbot/fixtures/qqbot_interaction_create.json`):

```bash
python3 scripts/smoke_test.py --dry-run --callback-json packages/channels/qqbot/fixtures/qqbot_interaction_create.json
```

Dry-run always uses Fake transports (no live QQ hosts / no Urllib). In addition to leaf helper steps, dry-run **must** exercise the host Protocol path:

1. `verify_and_ack` (signed C2C fixture → HTTP ACK)
2. post-ACK **ingress/session** via the same composition as `services/qqbot-service` webhook
3. **deliver** through Fake message transport behind the output boundary

Evidence steps therefore include `adapter_ack`, `session_ingress`, and `adapter_deliver` (all `ok`) alongside leaf steps. Leaf-only coverage is **not** host-complete. Callback leaf step **normalizes only** — it does **not** PUT an interaction ACK. Evidence remains `not_live_acceptance=true`.

Unittest coverage lives under the existing `qqbot-channel` discover gate (`packages/channels/qqbot/tests/test_smoke_toolkit.py`). There is **no** new `run_v2_gates.py` entry for this toolkit.

---

## Live command (HUMAN GATE)

Live is operator-only. It is **not** an autonomous deliverable and does **not** block phase complete.

1. Export the five value env vars above from a private store.
2. Obtain a fresh `INKSTATUTE_QQBOT_REPLY_MSG_ID` from a recent C2C user message (passive-reply window).
3. Run:

```bash
python3 scripts/smoke_test.py --live --evidence-out /tmp/qqbot-smoke-live.json
```

Incomplete env fails closed (exit non-zero) and prints **key names only** — never secret values. The script always stamps `not_live_acceptance=true` even on success.

### Interaction ACK safety / passive-reply windows

- **Dry-run:** always normalize-only from fixture / `--callback-json` (no ACK PUT).
- **Live ACK PUT:** runs only when `--live` **and** `--callback-json` supplies a **real** `interaction_id` from a recent INTERACTION_CREATE payload. Do not invent interaction ids.
- **Passive-reply:** live text/keyboard sends require a fresh `msg_id` still inside QQ’s passive-reply window (see credential section above).

Example (operator-pasted sanitized envelope path — keep raw payloads off disk when possible):

```bash
python3 scripts/smoke_test.py --live --callback-json /tmp/interaction-envelope.json --evidence-out /tmp/qqbot-smoke-live.json
```

---

## Expected outputs

| Mode | Exit | Evidence stamps | Transports |
|------|------|-----------------|------------|
| `--dry-run` | `0` when all steps ok | `schema=inkstatute.qqbot.smoke_evidence.v1`, `mode=dry-run`, `not_live_acceptance=true` | Fake only |
| `--live` | `0` when all steps ok | `mode=live`, `not_live_acceptance=true`; acceptance archival is a human decision | Real OpenAPI (leaf path) |

Per-step `ok` flags under `steps` (dry-run): `signature`, `send_text` (`msg_type=0`), `send_keyboard` (`msg_type=2` + feedback actions), `callback` (`status=normalized`, `idempotency_key_present`), plus Protocol-path `adapter_ack`, `session_ingress`, `adapter_deliver`.
Live (`--live`) currently records leaf steps only; host Protocol live coverage remains an operator concern beyond autonomous Phase 72 completion.

Stdout and `--evidence-out` emit **sanitized JSON only**.

---

## Evidence format and archival

### Schema (allowlisted)

```json
{
  "schema": "inkstatute.qqbot.smoke_evidence.v1",
  "mode": "dry-run",
  "not_live_acceptance": true,
  "steps": {
    "signature": { "ok": true, "vector": "qq_official_demo" },
    "send_text": { "ok": true, "msg_type": 0, "openid_hash": "…" },
    "send_keyboard": { "ok": true, "msg_type": 2, "actions": ["up", "down", "…"] },
    "callback": { "ok": true, "category": "interaction", "idempotency_key_present": true },
    "adapter_ack": { "ok": true, "http_status": 200, "op": 12, "accepted": true },
    "session_ingress": { "ok": true, "ingress_action": "accepted", "run_id_present": true, "branch": "message" },
    "adapter_deliver": { "ok": true, "deliver_accepted": true, "boundary_action": "allow" }
  }
}
```

Openids and similar ids appear only as `sha256` hex prefixes (`[:16]`). The script never sets `not_live_acceptance` to `false`.

### Ban-list (must not appear in evidence)

- `Authorization`, `access_token`, BotSecret / token strings
- Raw message `content` / user payloads
- `http://` / `https://` URLs, `url` / `file_url` / `attachment_url` keys
- Transport call dumps or raw envelopes

The script never auto-writes under `.planning/`.

### Human archival path (live only — Phase 72)

After a successful live run, the operator may **manually copy** sanitized JSON to:

```text
.planning/phases/72-controlled-live-integration/evidence/YYYYMMDD-smoke-live.json
```

Example:

```bash
mkdir -p .planning/phases/72-controlled-live-integration/evidence
cp /tmp/qqbot-smoke-live.json \
  .planning/phases/72-controlled-live-integration/evidence/$(date +%Y%m%d)-smoke-live.json
```

Archive **sanitized** evidence only. Never commit secrets, raw callback payloads, or attachment URLs. This archive is a **human copy only** and is **never required** for autonomous phase complete or CI.

---

## Carried human gates (not redefined by Phase 72)

Phase 72 documents controlled QQ live smoke as a **HUMAN GATE**. It does **not** close or redefine earlier gates:

| Gate | Status |
|------|--------|
| **Phase 5** live WeCom UAT | Remains a **carried human gate** — not v1.9 done |
| **Phase 8** lawyer trial acceptance | Remains a **carried human gate** — not v1.9 done |
| Phase 72 QQ `--live` acceptance | Separate HUMAN GATE; script stamps `not_live_acceptance=true` |

Do not mark Phase 5 or Phase 8 complete from QQ smoke evidence or from autonomous Phase 72 verification.
