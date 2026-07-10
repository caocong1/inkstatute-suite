# InkStatute QQBot Service

InkStatute-owned QQBot webhook host package. This host will own the HTTP edge,
secret resolution at process edge, and wiring of channel/session/feedback
composition in later phases (69–70).

Ownership boundary:

- `inkstatute_channels_qqbot` owns Protocol IO (verify/normalize/deliver).
- This host package owns deployable composition and process-edge concerns.
- ADAPTER-04: no `wecom_service` imports on the QQBot host path.
- Live-IO feature flags default OFF.
- Secrets are stored as references only; raw values are never committed.

Phase 68 delivers the empty-deps skeleton and safety baseline only — no webhook
composition yet.
