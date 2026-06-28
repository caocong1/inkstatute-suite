# Conversation Read View

This package builds read-only operator views from InkStatute V2 contract logs.

The read model is derived and rebuildable. It does not create an authoritative session store, does not create a conversation database, and does not read Hermes `sessions.db` in the minimum path. Hermes session data may only appear later behind an explicitly Hermes-specific fallback adapter.

The package stores no raw legal payloads. Contract log readers must preserve references such as `raw_payload_ref` and reject callback bodies, customer documents, media bytes, secrets, tokens, runtime database paths, and exact raw payload fields.

Phase 6 starts with pure Python helpers so tests can call the read model directly without starting a server.

Supported lookups:

- `conversation_id` for conversation summaries and recent turn/result details.
- `task id` for task views. The read model prefers `metadata.task_id` and falls back to `turn_id`.
- `trace_id` for task lookup through execution trace metadata.

The package does not require Hermes `sessions.db`; any future session fallback must be explicit, Hermes-specific, and marked as non-authoritative.
