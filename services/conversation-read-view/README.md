# Conversation Read View

This package builds read-only operator views from InkStatute V2 contract logs.

The read model is derived and rebuildable. It does not create an authoritative session store, does not create a conversation database, and does not read Hermes `sessions.db` in the minimum path. Hermes session data may only appear later behind an explicitly Hermes-specific fallback adapter.

The package stores no raw legal payloads. Contract log readers must preserve references such as `raw_payload_ref` and reject callback bodies, customer documents, media bytes, secrets, tokens, runtime database paths, and exact raw payload fields.

Phase 6 starts with pure Python helpers so tests can call the read model directly without starting a server.

