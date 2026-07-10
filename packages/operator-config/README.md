# inkstatute-operator-config

InkStatute-owned, refs-only operator config authority (schemas, validators, store).

## Boundaries

- **InkStatute store is source of truth** — never treat Hermes `~/.hermes` / profile
  filesystem paths as config authority.
- **Secrets are refs only** — credential fields are `*_ref` shapes (`env:NAME`, bare
  `ENV_NAME`, or `secret://…`). Raw secret values must never appear in documents or
  error messages. Values resolve at the process edge in hosts, not in this package.
- **Default OFF** — mutate paths are gated by `operator_config_enabled` (default
  `False` on `RuntimeFeatureFlags`). `OperatorConfigStore.save` calls
  `require_operator_config_writable` before any disk write; when the flag is off,
  save raises `OperatorConfigDisabledError` and creates/updates no store file.
- **Path** — set `INKSTATUTE_OPERATOR_CONFIG_PATH` to the JSON store file, or omit
  it to use `.inkstatute/operator-config.json` under the process cwd. Runtime store
  files are gitignored (see repo `.gitignore`: `.inkstatute/operator-config.json`
  and `operator-config.json`).
- **No admin HTTP in this package** — Phase 74 owns `/config/*` on admin-console-api.
- **Empty deps** — stdlib only in this package; `platform_runtime` is provided via
  PYTHONPATH for the feature-flag gate (no qqbot-service or Hermes dependency).

## Document shape

Root `OperatorConfigDocument` (`schema_version: int = 1`) nests:

| Section | Type | Notes |
|---------|------|-------|
| `channels` | `ChannelsDoc` | Nested `qqbot` + `wecom` channel docs (`enabled=False`, `*_ref` only) |
| `providers` | `tuple[ProviderDoc, ...]` | Provider docs with `api_key_ref` (never raw `api_key`) |
| `catalog` | `CatalogSelectionDoc` | Selection stub: `provider_id` + `model_id` only |
| `vision` | `VisionPolicyDoc` | Policy stub: routing mode + model ids (no runtime flag here) |

## Public surface

```python
from platform_runtime.feature_flags import RuntimeFeatureFlags
from inkstatute_operator_config import (
    OperatorConfigDocument,
    OperatorConfigStore,
    OperatorConfigDisabledError,
    require_operator_config_writable,
    validate_document,
    default_operator_config_path,
)

flags = RuntimeFeatureFlags(operator_config_enabled=True)
store = OperatorConfigStore()  # or OperatorConfigStore(path)
store.save(OperatorConfigDocument(), feature_flags=flags)
doc = store.load()
```

`save` order: (1) flag gate, (2) `validate_document`, (3) sibling `.tmp` + `os.replace`.

## Tests

```bash
PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src \
  python -m unittest discover -s packages/operator-config/tests -q
```
