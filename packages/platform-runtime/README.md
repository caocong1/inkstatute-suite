# InkStatute Platform Runtime

Embeddable runtime contracts and fake-backed runtime support for the InkStatute
agent platform.

Phase 09 introduced the signature layer:

- Protocol method signatures for `ChannelAdapter`, `BackendAdapter`,
  `SolutionLoader`, and `RunRuntime`.
- Frozen dataclasses and aliases needed to express those signatures.

Phase 10 adds library-only runtime behavior:

- `DefaultRunRuntime` implements create, poll, stream, cancel, and approve
  through injected adapters and support ports.
- `FakeBackendAdapter` and fake channel/runtime helpers provide deterministic
  tests and fixture evidence without network I/O.
- `RuntimeFeatureFlags` keeps run, streaming, approval, channel delivery, and
  contract-log lanes default-off until a host explicitly enables them.
- Runtime construction supports `channels=()` and exposes no server object.
- Stream output is checked by the assistant output boundary before ordinary
  user visibility.
- Contract-log evidence uses `raw_payload_ref`, IDs, and hashes instead of raw
  payload storage.

The Phase 10 fixture is fake-only embedded runtime evidence and is **not live acceptance**.
It proves zero-channel/no-server construction, default-off gates,
append-only sanitized event ordering, and output-boundary filtering against
fakes only. Production runtime activation remains a later host decision.
