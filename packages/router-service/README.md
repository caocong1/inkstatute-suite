# inkstatute-router-service

Standalone router library that produces normalized `RouteDecision` records.

## Overview

This package provides:

- **`RouterPort`** — Protocol defining the router interface with a single
  `decide(context) -> RouteDecision` method. Implementations must be stateless
  and side-effect free. Callers fall back to inline inference when the router
  is unavailable (None default preserves existing behavior).
- **`RouterStrategy`** — StrEnum with `RULE = "rule"` and `SKILL = "skill"`.
  These are router-internal strategies that map onto the frozen `RouteMode`
  outcome values (`matched`, `simple_qa`, `skipped`, `zero_match`). They are
  NOT new `RouteMode` enum values.
- **`RouterService`** — Concrete `RouterPort` implementation supporting both
  RULE (keyword/regex intent classification) and SKILL (skill registry lookup)
  strategies.
- **`classify_intent`** — Keyword/regex intent classifier used by the RULE
  strategy.

## Design

- The router is a library package (NOT an HTTP service). It is importable
  in-process by `hermes-contract-layer`.
- Dependency graph: `hermes-contract-layer -> router-service -> {platform-contract, skill-registry}`.
  No circular imports.
- The `skill_registry` parameter defaults to `None`, preserving inline
  inference behavior when no router is injected.
- All `RouteDecision` records produced use frozen `RouteMode` values only.
  The strategy is recorded in `metadata["router_strategy"]`, not in `mode`.
