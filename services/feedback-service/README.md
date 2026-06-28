# Feedback Service

This package contains FeedbackEvent normalization, classification, dedupe, and derived pending queue helpers for InkStatute V2 validation.

It converts sanitized `feedback.jsonl` and `pending_previews.jsonl` records into platform `FeedbackEvent` dictionaries for fixture replay. Phase 6 also accepts InkStatute WeCom callback-normalized `FeedbackEvent` dictionaries and contract-log `FeedbackEvent` dictionaries as primary inputs.

The pending review output is a derived pending queue. It is rebuildable from feedback events and does not introduce a durable queue service, worker daemon, runtime database, or new feedback channel.

Phase 6 owns APIs, queues, broad classification, dedupe service behavior, and pending review exports.

Classification is deterministic and rule-based over event fields such as `event_type`, `action`, labels, message hints, route-mismatch flags, and skill-candidate metadata. Route-mismatch and skill-candidate feedback remain human-reviewed, carry `no_auto_modify` metadata where available, and this package does not automatically modify legal skills or call skill optimization runners.
