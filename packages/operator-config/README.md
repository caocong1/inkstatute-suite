# inkstatute-operator-config

InkStatute-owned, refs-only operator config authority (schemas, validators, store).

## Boundaries

- **InkStatute store is source of truth** — never treat Hermes `~/.hermes` / profile
  filesystem paths as config authority.
- **Secrets are refs only** — credential fields are `*_ref` shapes (`env:NAME`, bare
  `ENV_NAME`, or `secret://…`). Raw secret values must never appear in documents or
  error messages. Values resolve at the process edge in hosts, not in this package.
- **Default OFF** — mutate paths are gated by `operator_config_enabled` (default
  `False`). When the flag is off, writes refuse.
- **Path** — document store path via `INKSTATUTE_OPERATOR_CONFIG_PATH`.
- **No admin HTTP in this package** — Phase 74 owns `/config/*` on admin-console-api.
- **Empty deps** — stdlib only; no hard dependency on qqbot-service or Hermes.

## Document shape

Root `OperatorConfigDocument` (`schema_version: int = 1`) nests:

| Section | Type | Notes |
|---------|------|-------|
| `channels` | `ChannelsDoc` | Nested `qqbot` + `wecom` channel docs (`enabled=False`, `*_ref` only) |
| `providers` | `tuple[ProviderDoc, ...]` | Provider docs with `api_key_ref` (never raw `api_key`) |
| `catalog` | `CatalogSelectionDoc` | Selection stub: `provider_id` + `model_id` only |
| `vision` | `VisionPolicyDoc` | Policy stub: routing mode + model ids (no runtime flag here) |

## Public surface (Phase 73 Plan 01)

```python
from inkstatute_operator_config import (
    OperatorConfigDocument,
    ChannelsDoc,
    QQBotChannelDoc,
    WeComChannelDoc,
    ProviderDoc,
    CatalogSelectionDoc,
    VisionPolicyDoc,
    OperatorConfigError,
    OperatorConfigValidationError,
)
```

Secret-ref normalize lands in the next Plan 01 task; store/validate/flag gate land in
Plans 02–03.

## Tests

```bash
PYTHONPATH=packages/operator-config/src \
  python -m unittest discover -s packages/operator-config/tests -q
```
