# ADR-0001: Agent Platform Layering

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

Milestone v1.1 refactors InkStatute toward a reusable agent platform while the
existing lawyer bot keeps running. The platform must not make Hermes, WeCom, or
the lawyer solution the core boundary. It needs stable seams that allow channels,
agent backends, solutions, and runtime hosts to evolve independently.

## Decision

Define the platform around four neutral contracts:

- `ChannelAdapter` for channel receive, acknowledgement, normalization,
  delivery, and health.
- `BackendAdapter` for agent backend bootstrap, run submission, run state,
  streaming events, cancellation, approvals, and artifacts.
- `SolutionLoader` for neutral solution validation, loading, and backend-specific
  materialization.
- `RunRuntime` for the embeddable run lifecycle surface.

Concrete implementations such as WeCom, Hermes, and the lawyer solution plug
into those contracts. Channel adapters must not call backend adapters directly.
The runtime depends on injected ports so it can be hosted by a server, sidecar,
test harness, or future embedded host.

## Consequences

This layering keeps Hermes lawfirm as the first backend and solution without
making Hermes core a platform dependency. It also keeps WeCom as the first
channel without making channel protocol details part of platform core.

Future backends, channels, and solutions can be added by implementing the
relevant contract instead of changing platform runtime code.

## Verification Notes

Phase 09 creates signature-only Protocol stubs and boundary documentation.
Later phases must add tests proving channel adapters do not import backends,
runtime can construct without channels, and concrete adapters remain behind
feature flags until parity is proven.

