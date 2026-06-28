# ADR-0007: Boundary Scan Allowlist

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

Neutral platform packages must not become secretly coupled to Hermes internals,
WeCom protocol internals, the lawfirm solution, runtime payloads, or secrets.
At the same time, legitimate neutral contracts need to name allowed examples and
enum values such as Hermes, WeCom, lawfirm, codex, and provider_model.

## Decision

Use an allowlist-aware boundary scan rather than a blanket word ban.

Allowed uses include:

- backend mode enum values and examples such as `hermes`, `codex`, and
  `provider_model`;
- channel examples such as `wecom` when used as a concrete channel name or
  allowlisted implementation;
- solution examples such as `lawfirm` when used as the first solution example or
  under concrete solution packages;
- ADR and architecture prose that explicitly describes boundaries.

Forbidden uses include:

- private Hermes runtime paths or imports in neutral packages;
- WeCom callback body fields, protocol payload internals, tokens, encoding AES
  keys, access tokens, media payloads, or runtime callback examples in neutral
  packages;
- lawfirm-only or legal-only top-level required schema fields;
- raw payloads, customer legal content, runtime databases, logs, or plaintext
  secret values;
- channel adapters importing backend adapters directly.

## Consequences

The scan can allow honest examples and enum values without hiding real boundary
violations. Concrete packages such as `channels/wecom`, `backends/hermes`, and
`solutions/lawfirm` can contain implementation-specific names under stricter
package-local rules.

The cost is maintaining path-aware and context-aware rules instead of a simpler
text denylist.

## Verification Notes

Phase 09 boundary tests must prove both sides: allowed enum/example contexts pass
and forbidden private/runtime/secret/legal-top-level coupling fails.
