# Plan 51-02 Summary: Token-Based Auth with Role+Tenant Claims and Static-Token Fallback

## Objective

Implement short-lived HMAC-SHA256 signed tokens carrying `role` and `tenant_id` claims, a `resolve_identity()` function that extracts claims from a Bearer token when `rbac_enabled=True` and falls back to the v1.6 `check_auth_header` static-token path when `rbac_enabled=False`. This satisfies RBAC-01 (token claims) and preserves the static-token fallback (success criteria 3 and 4).

## Tasks Completed

### Task 1: Implement RbacToken signer/verifier with HMAC-SHA256 and short-lived TTL

**Files created:**
- `packages/rbac/src/rbac/token.py` — `issue_token(secret, *, role, tenant_id, ttl_seconds=900, now=None) -> str` issues `base64url(payload_json).base64url(hmac_sha256(secret, payload_b64))` tokens. `verify_token(token, secret, now=None) -> RbacTokenClaims` verifies signature with `hmac.compare_digest` (constant-time) and rejects expired tokens (`exp <= now`). `RbacTokenClaims` frozen dataclass with `role`, `tenant_id`, `iat`, `exp`. `RbacTokenError` exception for invalid/tampered/expired tokens. `DEFAULT_TOKEN_TTL_SECONDS = 900` (15 minutes). Stdlib only: `base64`, `hashlib`, `hmac`, `json`, `time`.
- `packages/rbac/tests/test_token.py` — 12 tests: round-trip, expired token rejected, wrong secret rejected, tampered payload rejected, custom TTL, default TTL is 900, invalid format rejected, no dot rejected, claims fields, string role accepted, boundary expiry rejected (exp == now).

**Commit:** `9615749` — `feat(51-02): add RBAC token signing/verification and resolve_identity with static-token fallback`

### Task 2: Implement resolve_identity() with RBAC token and static-token fallback

**Files created:**
- `packages/rbac/src/rbac/identity.py` — `Identity` frozen dataclass with `role: Role` and `tenant_id: str`. `resolve_identity(auth_header, *, rbac_secret, static_token, rbac_enabled=False, now=None) -> Identity | None` extracts role+tenant claims from a Bearer token when `rbac_enabled=True` (returns `None` on invalid/expired/unknown-role tokens). When `rbac_enabled=False`, falls back to `check_auth_header` static-token validation (v1.6 behavior), returning a default `Identity(role=ADMIN, tenant_id="default")` on success. The `admin_console_api.auth` import is lazy (inside the function body) with a stdlib fallback (`_static_token_check`) so the rbac package remains testable standalone.
- `packages/rbac/tests/test_identity.py` — 14 tests: RBAC token resolves identity (admin + lawyer), expired token returns None, wrong secret returns None, unknown role string returns None, missing auth header returns None, rbac_secret=None returns None, non-Bearer header returns None, Identity is frozen; static-token fallback returns admin, invalid token returns None, missing header returns None, non-Bearer returns None, static_token=None returns None.

**Commit:** `9615749` — `feat(51-02): add RBAC token signing/verification and resolve_identity with static-token fallback`

## Deviations

- **[Post-OOM fix — non-blocking]** The `resolve_identity()` static-token fallback originally imported `from admin_console_api.auth import check_auth_header` directly inside the function body. This caused `ModuleNotFoundError` when running rbac tests standalone (without `admin_console_api` on PYTHONPATH). Fixed in Plan 03 commit (`ce4018e`) by adding a `try/except ImportError` fallback to a local `_static_token_check` function that replicates the same `hmac.compare_digest` Bearer-token comparison — preserving identical v1.6 semantics with no external dependency. The `test_package_invariants.py` test already accounted for the lazy import by only checking top-level (unindented) imports.

## Test Results

- **rbac package tests:** 54 tests pass (12 token + 14 identity + 4 roles + 7 matrix + 15 guard + 3 invariants) — after the identity.py fix in Plan 03
  - `PYTHONPATH="packages/rbac/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest discover -s packages/rbac/tests` — OK

## FROZEN Contract Surfaces Verified

- `dependencies = []` invariant preserved — stdlib only (`base64`, `hashlib`, `hmac`, `json`, `time`, `dataclasses`, `enum`)
- `admin_console_api.auth` import is lazy (inside function body) with stdlib fallback — package remains standalone-testable
- `py.typed` marker present

## Key Design Decisions

1. **Token format: `base64url(payload).base64url(signature)`** — simple, URL-safe, no external JWT library needed. Payload is JSON with `role`, `tenant_id`, `iat`, `exp` fields (sorted keys for deterministic signing).
2. **HMAC-SHA256 with `hmac.compare_digest`** — constant-time signature comparison prevents timing attacks, mirroring the existing `check_auth_header` pattern.
3. **`exp <= now` rejection (not `< now`)** — a token with `exp == now` is already expired; this is the boundary-expiry test case.
4. **`Identity` is frozen with `slots=True`** — immutable, memory-efficient, prevents accidental mutation of resolved identity.
5. **Static-token fallback returns `Identity(role=ADMIN, tenant_id="default")`** — preserves v1.6 behavior where a valid static token grants full admin access with no tenant scoping.
6. **Lazy import with stdlib fallback** — `resolve_identity()` tries `from admin_console_api.auth import check_auth_header` first (when the admin-console-api is on PYTHONPATH), falling back to `_static_token_check` (identical logic using `hmac.compare_digest`) when the import fails. This keeps the rbac package stdlib-only and testable in isolation.
