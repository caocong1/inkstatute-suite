# QQBot Smoke Test Runbook

Operator guide for the InkStatute one-click QQBot smoke toolkit (`scripts/smoke_test.py`).

**Scope:** leaf helpers (signature → text/keyboard send → INTERACTION normalize) **plus** host Protocol path (verify_and_ack → ingress/session → deliver) via the same helpers as `services/qqbot-service` webhook composition.

**CI / phase gate:** dry-run only. Live OpenAPI is a **HUMAN GATE** (Phase 72) and is **not** required for CI or phase verification. Do not commit secrets, tokens, raw payloads, or attachment URLs. Dry-run evidence always stamps `not_live_acceptance=true` — never claim live acceptance from CI.

---

## Credential / env-var setup

Live mode reads **value** environment variables (not production `*_REF` / `secret://` config keys).

| Env var | Dry-run | Live | Purpose |
|---------|---------|------|---------|
| `INKSTATUTE_QQBOT_APP_ID` | unused (fixture) | required | Real AppId value |
| `INKSTATUTE_QQBOT_CLIENT_SECRET` | unused (fixture) | required | Token client secret |
| `INKSTATUTE_QQBOT_BOT_SECRET` | DEMO constant in script | required | Ed25519 BotSecret |
| `INKSTATUTE_QQBOT_USER_OPENID` | fixture openid | required | C2C target openid |
| `INKSTATUTE_QQBOT_REPLY_MSG_ID` | fixture msg_id | required | Passive-reply `msg_id` |

**Do not** set or document `INKSTATUTE_QQBOT_*_REF` for this CLI — those are host config references, not smoke value injection.

Export values from a private secret store into the shell for the live session only. Never paste secrets into this runbook, git commits, or evidence archives.

### Passive-reply `msg_id` window (live)

For live text / keyboard sends, `INKSTATUTE_QQBOT_REPLY_MSG_ID` must come from a **recent user message** still inside QQ’s passive-reply window. Inventing or reusing a stale `msg_id` will fail the send steps. Dry-run uses a fixture id and does not need a live window.

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

Incomplete env fails closed (exit non-zero) and prints **key names only** — never secret values.

### Optional live ACK PUT (`--callback-json`)

- Dry-run: always normalize-only from fixture / `--callback-json` (no PUT).
- Live: text + keyboard sends are the primary path. Live interaction **ACK PUT** runs only when `--live` **and** `--callback-json` supplies a real interaction id from a recent INTERACTION_CREATE payload. Otherwise treat ACK as an optional follow-up; do not invent interaction ids.

Example (operator-pasted sanitized envelope path — keep raw payloads off disk when possible):

```bash
python3 scripts/smoke_test.py --live --callback-json /tmp/interaction-envelope.json --evidence-out /tmp/qqbot-smoke-live.json
```

---

## Expected outputs

| Mode | Exit | Evidence stamps | Transports |
|------|------|-----------------|------------|
| `--dry-run` | `0` when all steps ok | `schema=inkstatute.qqbot.smoke_evidence.v1`, `mode=dry-run`, `not_live_acceptance=true` | Fake only |
| `--live` | `0` when all steps ok | `mode=live`; acceptance archival is a human decision | Real OpenAPI (Plan 03) |

Per-step `ok` flags under `steps` (dry-run): `signature`, `send_text` (`msg_type=0`), `send_keyboard` (`msg_type=2` + feedback actions), `callback` (`status=normalized`, `idempotency_key_present`), plus Protocol-path `adapter_ack`, `session_ingress`, `adapter_deliver`.
Live (`--live`) currently records leaf steps only; host Protocol live coverage is Phase 72.

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

Openids and similar ids appear only as `sha256` hex prefixes (`[:16]`). Dry-run never sets `not_live_acceptance` to `false`.

### Ban-list (must not appear in evidence)

- `Authorization`, `access_token`, BotSecret / token strings
- Raw message `content` / user payloads
- `http://` / `https://` URLs, `url` / `file_url` / `attachment_url` keys
- Transport call dumps or raw envelopes

The script never auto-writes under `.planning/`.

### Human archival path (live only)

After a successful live run, the operator may **manually copy** sanitized JSON to:

```text
.planning/phases/67-one-click-smoke-test-toolkit/evidence/YYYYMMDD-smoke-live.json
```

Example:

```bash
mkdir -p .planning/phases/67-one-click-smoke-test-toolkit/evidence
cp /tmp/qqbot-smoke-live.json \
  .planning/phases/67-one-click-smoke-test-toolkit/evidence/$(date +%Y%m%d)-smoke-live.json
```

Archive **sanitized** evidence only. Never commit secrets, raw callback payloads, or attachment URLs. CI does not require this archive.
