# Conversation Read View

This package builds read-only operator views from InkStatute V2 contract logs.

The read model is derived and rebuildable. It does not create an authoritative session store, does not create a conversation database, and does not read Hermes `sessions.db` in the minimum path. Hermes session data may only appear later behind an explicitly Hermes-specific fallback adapter.

The package stores no raw legal payloads. Contract log readers must preserve references such as `raw_payload_ref` and reject callback bodies, customer documents, media bytes, secrets, tokens, runtime database paths, and exact raw payload fields.

Phase 6 starts with pure Python helpers so tests can call the read model directly. It does not start a server, does not own WeCom receive/send, and does not add persistent storage.

Supported lookups:

- `conversation_id` for conversation summaries and recent turn/result details.
- `task id` for task views. The read model prefers `metadata.task_id` and falls back to `turn_id`.
- `trace_id` for task lookup through execution trace metadata.

Pure GET handler examples:

```python
from conversation_read_view import build_read_model, handle_get, load_records_from_jsonl
from feedback_service.queue import build_pending_feedback_queue

read_model = build_read_model(load_records_from_jsonl("contract-log.jsonl"))
feedback_queue = build_pending_feedback_queue(feedback_events)

status, conversation = handle_get("/conversations/{conversation_id}", "", read_model)
status, task = handle_get("/tasks/{task_id_or_trace_id}", "", read_model)
status, pending = handle_get("/feedback?status=pending", "", read_model, feedback_queue)
```

The package does not require Hermes `sessions.db`; any future session fallback must be explicit, Hermes-specific, and marked as non-authoritative.
