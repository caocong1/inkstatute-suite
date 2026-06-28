# ADR-0003: Hermes Invocation Boundary

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

Hermes lawfirm is the first production backend for InkStatute, but Hermes gateway
must not be the ordinary-user channel boundary. The proven path is the existing
lawfirm one-shot invocation. Hermes also exposes API-style run surfaces in some
versions, but lawfirm parity through those APIs is not yet proven.

## Decision

Hermes integration stays behind `BackendAdapter`. The default Hermes lane remains
one-shot until proven otherwise.

Capability probing must be non-mutating. It may inspect health, version,
capabilities, and model metadata, but it must not create runs, alter sessions,
or send user-visible messages.

The `/v1/runs` lane remains behind a parity gate and feature flag. It can become
eligible only after fixtures prove equivalence with one-shot for lawfirm routing,
skills, gates, MCP/tool use, artifacts, feedback target behavior, output
boundary behavior, and failure handling.

Hermes adapter implementations must not perform channel I/O to ordinary WeCom
users. All user-visible delivery returns through InkStatute channel and runtime
boundaries.

## Consequences

This preserves the working lawyer backend while preventing unproven Hermes API
paths from silently becoming production defaults. It also keeps future backends
from inheriting Hermes-specific channel assumptions.

The cost is extra parity evidence before the more stateful `/v1/runs` API can be
promoted.

## Verification Notes

Phase 11 must add capability probe tests, one-shot adapter conformance tests, and
fixture-based `/v1/runs` parity reporting. Until that evidence passes and a human
live gate approves promotion, one-shot remains the default.

