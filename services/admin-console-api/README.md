# Admin Console API

Read-only Admin Console API for InkStatute V2 operator views. Authenticates via a static token from env (`ADMIN_API_TOKEN`). Exposes sessions, tasks, feedback, gates, and health views with filtering and pagination. Reuses `ContractLogReadModel` and cursor pagination from `services/conversation-read-view/`. Strictly read-only — no mutations.

The `admin_api_enabled` feature flag defaults to `False`. When disabled, all requests are refused.

Health/status views use a field allowlist that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values.

Gate status views run `run_v2_gates.py --json-summary` via subprocess — no gate internals are imported.
