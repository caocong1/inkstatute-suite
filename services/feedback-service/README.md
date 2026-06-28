# Feedback Service

This package currently contains the Phase 5 minimal validation normalizer for sanitized WeCom feedback evidence.

It converts sanitized `feedback.jsonl` and `pending_previews.jsonl` records into platform `FeedbackEvent` dictionaries for fixture replay. It does not own the live WeCom callback channel, Hermes template card shim, runtime storage, HTTP APIs, persistent queues, worker daemons, or pending review exports.

Phase 6 owns APIs, queues, broad classification, dedupe service behavior, and pending review exports. This Phase 5 package does not automatically modify legal skills and must not call skill optimization runners.
