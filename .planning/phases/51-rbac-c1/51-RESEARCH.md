# Phase 51: RBAC (C1) - Research

**Researched:** 2026-07-06
**Domain:** Role-based access control, permissions matrix, token-based auth, default-deny CI enforcement
**Confidence:** HIGH

## Summary

Phase 51 introduces a new `packages/rbac/` package implementing 4 roles (admin, operator, lawyer, viewer) with a declarative permissions matrix mapping admin API endpoints → required role, an `RbacGuard.check(role, endpoint)` middleware, default-deny enforcement via a CI scan that fails on unannotated endpoints, and short-lived HMAC-signed tokens carrying role+tenant claims. The `rbac_enabled` feature flag already exists in `RuntimeFeatureFlags` (added in Phase 45, defaults to `False`) — this phase productizes the RBAC lane behind it while preserving the v1.6 `check_auth_header` static-token fallback when the flag is off.

The admin-console-api (`services/admin-console-api/src/admin_console_api/`) currently gates requests in `handle_admin_get` via a 4-step pipeline: (1) `admin_api_enabled` feature flag, (2) `resolve_admin_token` env lookup, (3) `check_auth_header` Bearer validation with `hmac.compare_digest`, (4) route dispatch to read-only view handlers (`/sessions`, `/tasks`, `/feedback`, `/health`, `/gates`). All handlers are read-only GETs — no POST/PUT/DELETE. The RBAC integration inserts a role check between the existing auth step and route dispatch, but ONLY when `rbac_enabled=True`. When `False`, the existing static-token path runs unchanged (zero regression).

**Primary recommendation:** Create `packages/rbac/` as a stdlib-only package (`dependencies = []`) with: (1) a `Role` enum + declarative `PERMISSIONS_MATRIX` mapping endpoint prefixes → allowed roles, (2) `RbacGuard` with a `check(role, endpoint)` method enforcing default-deny (endpoints absent from the matrix are denied), (3) an `RbacToken` signer/verifier using HMAC-SHA256 over a JSON claims payload (`role`, `tenant_id`, `iat`, `exp`) with short-lived TTL, (4) `resolve_identity()` extracting claims from a Bearer token, (5) a CI scan script (`scripts/scan_rbac_annotations.py`) that introspects the admin-console-api route table and fails when any endpoint lacks a role annotation. Wire `RbacGuard` into `handle_admin_get` behind the `rbac_enabled` flag, preserving the static-token fallback.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RBAC-01 | `packages/rbac/` implements 4 roles (admin, operator, lawyer, viewer) with a declarative permissions matrix mapping endpoint → required role; `RbacGuard.check(role, endpoint)` middleware wraps admin API handlers | §Architecture Patterns (permissions matrix), §Code Examples (RbacGuard default-deny) |
| RBAC-02 | RBAC enforces default-deny: a CI scan fails when any admin API endpoint lacks a role annotation; unannotated endpoints are treated as denied by default | §Architecture Patterns (default-deny CI scan), §Code Examples (scan script) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** RBAC tokens are signed with a host-injected secret; the secret itself is never committed. Token fixtures use throwaway test secrets. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.** `packages/rbac/` is a library package (no new service). `dependencies = []` invariant must be preserved — token signing uses stdlib `hmac`/`hashlib`/`json`/`time`/`secrets` only. [VERIFIED: AGENTS.md §Coding Rules]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]
- **Add tests before or with behavior changes.** RBAC matrix, guard, token signer, and CI scan all get unit tests. [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** Token claims are JSON with HMAC-SHA256 signature, verified with constant-time `hmac.compare_digest`. [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Role enum + permissions matrix | `packages/rbac/` (matrix.py) | — | RBAC owns the declarative role→endpoint mapping |
| RbacGuard.check(role, endpoint) | `packages/rbac/` (guard.py) | — | Guard owns default-deny enforcement logic |
| Token signing/verification (HMAC-SHA256) | `packages/rbac/` (token.py) | — | RBAC owns token lifecycle; stdlib-only |
| resolve_identity() claim extraction | `packages/rbac/` (identity.py) | — | RBAC owns identity resolution from Bearer token |
| CI scan for unannotated endpoints | `scripts/scan_rbac_annotations.py` | `packages/rbac/` (matrix introspection) | Script enforces default-deny at CI time |
| Feature flag gating | `packages/platform-runtime/` (feature_flags.py) | — | `rbac_enabled` already exists, defaults False |
| Admin API integration | `services/admin-console-api/` (api.py) | — | API wires RbacGuard behind the flag |

## Standard Stack

### Core

No new external packages. `packages/rbac/` uses only the Python standard library and existing project packages.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `hmac` | 3.11+ | Constant-time HMAC-SHA256 token signing/verification | Already used in `admin_console_api/auth.py` |
| Python stdlib `hashlib` | 3.11+ | SHA256 digest for HMAC | stdlib |
| Python stdlib `json` | 3.11+ | Token claims serialization | stdlib |
| Python stdlib `time` | 3.11+ | Token `iat`/`exp` timestamps (UTC seconds) | stdlib |
| Python stdlib `secrets` | 3.11+ | Test-secret generation helpers | stdlib |
| Python stdlib `base64` | 3.11+ | URL-safe token encoding | stdlib |
| `platform-runtime` | existing | `RuntimeFeatureFlags` (`rbac_enabled` flag) | Flag already present (Phase 45) |

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| PyJWT / jose library | Violates `dependencies = []` invariant; stdlib HMAC-SHA256 is sufficient for symmetric signed tokens |
| Asymmetric (RS256) signing | Adds complexity; RBAC tokens are issued by the same operator that verifies them (symmetric secret is appropriate) |
| Database-backed permissions | Introduces a runtime dependency; declarative matrix is reviewable in code and CI-scanned |
| Decorator-based endpoint annotation | Admin API uses a single `handle_admin_get` dispatcher with route matching; a declarative matrix keyed by endpoint prefix fits the existing architecture better than per-function decorators |

## Architecture Patterns

### 1. Declarative Permissions Matrix (endpoint prefix → allowed roles)

The admin-console-api routes are prefix-based (`/sessions`, `/sessions/{id}`, `/tasks`, `/tasks/{id}`, `/feedback`, `/health`, `/gates`). The permissions matrix maps each route prefix to the set of roles allowed to access it. `RbacGuard.check(role, endpoint)` resolves the endpoint to its matrix entry by longest-prefix match and returns `True` only if the caller's role is in the allowed set. Endpoints with no matrix entry are denied by default.

```python
PERMISSIONS_MATRIX: dict[str, frozenset[Role]] = {
    "/sessions": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
    "/tasks": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
    "/feedback": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/health": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/gates": frozenset({Role.ADMIN}),
}
```

### 2. Default-Deny RbacGuard

`RbacGuard.check(role, endpoint)` resolves the matrix entry by longest matching prefix. If no prefix matches, the endpoint is unannotated → denied. This makes the matrix the single source of truth: adding a new endpoint without a matrix entry is a CI failure (scan) AND a runtime denial (guard).

### 3. Short-Lived HMAC-SHA256 Tokens

Tokens are `base64url(payload_json) + "." + base64url(hmac_sha256(secret, payload_json))`. Payload contains `role`, `tenant_id`, `iat` (issued-at, UTC seconds), `exp` (expiry, UTC seconds). Verification recomputes the HMAC with `hmac.compare_digest` (constant-time), checks `exp > now`, and returns claims. TTL is configurable (default 900s / 15 min). No refresh tokens in this phase — operators mint new tokens via an out-of-band admin tool.

### 4. resolve_identity() with static-token fallback

`resolve_identity(auth_header, *, rbac_secret=None, static_token=None, rbac_enabled=False)`:
- When `rbac_enabled=True`: parse the Bearer token as an RBAC token, verify HMAC + expiry, return `Identity(role=..., tenant_id=...)`.
- When `rbac_enabled=False`: fall back to `check_auth_header(auth_header, static_token)` — if valid, return a default `Identity(role=Role.ADMIN, tenant_id="default")` (preserving v1.6 behavior where a valid static token grants full read access). The existing `handle_admin_get` static-token path is preserved verbatim when the flag is off.

### 5. CI Scan for Unannotated Endpoints

`scripts/scan_rbac_annotations.py` introspects the admin-console-api route table (the set of route prefixes dispatched in `handle_admin_get`) and the RBAC `PERMISSIONS_MATRIX`, then fails (exit 1) if any dispatched route prefix lacks a matrix entry. This enforces default-deny at CI time — a new endpoint added to the dispatcher without a matrix annotation breaks the build.

### 6. Feature Flag Gating (rbac_enabled defaults False)

`RuntimeFeatureFlags.rbac_enabled` already defaults to `False` (Phase 45). When `False`, `handle_admin_get` runs the existing 4-step static-token pipeline with zero changes. When `True`, after the static-token check passes, an additional RBAC step resolves the identity from the token and runs `RbacGuard.check(identity.role, route_path)`, returning 403 on denial.

## Code Examples

### RbacGuard (default-deny)

```python
class RbacGuard:
    def __init__(self, matrix: dict[str, frozenset[Role]] | None = None) -> None:
        self._matrix = matrix if matrix is not None else dict(PERMISSIONS_MATRIX)

    def check(self, role: Role, endpoint: str) -> bool:
        allowed = self._resolve(endpoint)
        if allowed is None:
            return False  # default-deny: unannotated endpoint
        return role in allowed

    def _resolve(self, endpoint: str) -> frozenset[Role] | None:
        # longest-prefix match
        best, best_len = None, -1
        for prefix, roles in self._matrix.items():
            if endpoint == prefix or endpoint.startswith(prefix + "/") or endpoint.startswith(prefix + "?"):
                if len(prefix) > best_len:
                    best, best_len = roles, len(prefix)
        return best
```

### Token signing (stdlib HMAC-SHA256)

```python
def issue_token(secret: str, *, role: Role, tenant_id: str, ttl_seconds: int = 900, now: int | None = None) -> str:
    iat = int(now if now is not None else time.time())
    exp = iat + ttl_seconds
    payload = {"role": role.value, "tenant_id": tenant_id, "iat": iat, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).rstrip(b"=").decode()
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{payload_b64}.{sig_b64}"
```

### CI scan script

```python
# scripts/scan_rbac_annotations.py
from rbac.matrix import PERMISSIONS_MATRIX
from admin_console_api.routes import ROUTE_PREFIXES  # extracted route table

def main() -> int:
    unannotated = [p for p in ROUTE_PREFIXES if p not in PERMISSIONS_MATRIX]
    if unannotated:
        print(f"FAIL: unannotated endpoints: {unannotated}")
        return 1
    print("OK: all endpoints annotated")
    return 0
```

## Common Pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| Modifying frozen contract surfaces (BackendAdapter, ChannelAdapter, RunEvent) | RBAC is a new package + admin-API-internal wiring; no frozen surface is touched. `test_contract_count_freeze` and `test_contract_freeze` must remain green. |
| Breaking the v1.6 static-token path when `rbac_enabled=False` | The RBAC step is gated behind `if feature_flags.rbac_enabled:`; the existing static-token checks run unconditionally first. Existing admin-console-api tests (which use `rbac_enabled=False` default) must pass unchanged. |
| Timing attacks on token comparison | Use `hmac.compare_digest` for signature verification (mirrors `check_auth_header`). |
| Token replay after expiry | Verify `exp > now` on every `resolve_identity` call; reject expired tokens. |
| CI scan false-positives from dynamic routes | Route table is a static `ROUTE_PREFIXES` tuple extracted from the dispatcher; the scan compares prefixes, not dynamic IDs. |
| Adding `dependencies` to `packages/rbac/pyproject.toml` | Enforce `dependencies = []` — stdlib only. A test asserts the invariant. |

## Open Questions

None — all decisions are at Claude's discretion per the skipped discuss phase, guided by ROADMAP success criteria and codebase conventions.

## Phasing

| Plan | Scope | Requirements |
|------|-------|--------------|
| 51-01 | Create `packages/rbac/` with 4 roles, permissions matrix, `RbacGuard.check(role, endpoint)` middleware | RBAC-01 |
| 51-02 | Token-based auth: short-lived HMAC tokens with role+tenant claims, `resolve_identity()`, `check_auth_header` fallback | RBAC-01 (token claims), RBAC-02 (identity) |
| 51-03 | CI scan for unannotated endpoints (default-deny enforcement) + admin-console-api integration behind `rbac_enabled` | RBAC-02, RBAC-01 (integration) |
