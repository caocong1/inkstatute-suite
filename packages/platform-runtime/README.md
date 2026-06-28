# InkStatute Platform Runtime

Signature-only runtime contracts for the InkStatute agent platform.

Phase 09 intentionally keeps this package non-runtime:

- Protocol method signatures for `ChannelAdapter`, `BackendAdapter`,
  `SolutionLoader`, and `RunRuntime`.
- Frozen dataclasses and aliases needed to express those signatures.
- No orchestration, HTTP, storage, WeCom, Hermes, backend, channel, or solution
  materialization behavior.

Runtime behavior is deferred to Phase 10 and later plans.

