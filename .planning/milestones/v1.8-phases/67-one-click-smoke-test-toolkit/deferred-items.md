# Phase 67 Deferred Items

## Resolved during 67-03

- **qqbot-channel gate PYTHONPATH omitted `services/feedback-service/src`:** Four Phase 66 e2e tests import `feedback_service.queue`. Fixed by extending the existing `qqbot-channel` gate path list (no new gate name — OQ-2). Full discover now green (321 tests).
