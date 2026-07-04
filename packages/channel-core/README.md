# Channel Core

Channel-generic logic shared across InkStatute channel adapters. Extracted from wecom-service in Phase 43. Contains idempotency key helpers, delivery completion guard, active task router, output policy, and owned notices. Channel adapters (WeCom, QQBot, Web/SSE) import from this package instead of duplicating logic.

WeCom-specific wrappers remain in wecom-service as thin re-export shims for backward compatibility.
