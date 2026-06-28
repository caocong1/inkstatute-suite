# ADR-0005: Python Core And TypeScript Client Split

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

The platform needs a runtime, adapters, schemas, contract tests, client SDKs, and
future embeddable UI surfaces. The first backend and solution are Python/Hermes
shaped, while clients are web and webview shaped.

## Decision

Use JSON Schema as the cross-language contract source. Keep the platform core in
Python 3.11+ async and ship TypeScript at the client edge.

Python owns `RunRuntime`, channel adapters, backend adapters, solution loading,
the platform API host, and contract validation helpers. TypeScript owns the
generated client SDK and embeddable chat component. Rust, Go, and local native
runtime shells are deferred until an active phase requires them.

## Consequences

This lets Phase 09-13 build quickly with the strongest current ecosystem fit:
Python for agent/MCP/backend integration and TypeScript for clients. JSON Schema
prevents Python-only contracts from leaking into client code.

The consequence is that generated bindings and schema compatibility checks must
remain first-class, because no single language owns the full product surface.

## Verification Notes

Python packages should remain dependency-light and testable with stdlib where
possible. TypeScript SDK generation belongs to later phases and must be
deterministic from the schema/OpenAPI surface.

