#!/usr/bin/env bash
# test_build_dsh_release.sh — smoke test for the DSH engine release pipeline.
#
# Validates:
#   1. engines/dsh-pin.txt exists and has required fields (dsh_commit, node_version)
#   2. engines/acp.cordis.yml exists and has approval.policy: ask
#   3. scripts/build_dsh_release.sh --dry-run exits 0 (validates pin + repo + planned steps)
#   4. No secrets in engines/ config files
#
# Does NOT do a real build — that is Phase 118 (真机回归).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PASS=0
FAIL=0

assert() {
  local description="$1"
  local result="$2"
  if [ "$result" -eq 0 ]; then
    echo "  PASS: $description"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $description"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== test_build_dsh_release.sh ==="

# --- Test 1: dsh-pin.txt exists and has required fields ---
echo "Checking engines/dsh-pin.txt..."
if [ -f "$REPO_ROOT/engines/dsh-pin.txt" ]; then
  assert "dsh-pin.txt exists" 0
else
  assert "dsh-pin.txt exists" 1
  echo "  ABORT: cannot run further pin tests without the file"
  exit 1
fi

# Check dsh_commit field
if grep -q '^dsh_commit=' "$REPO_ROOT/engines/dsh-pin.txt"; then
  assert "dsh-pin.txt has dsh_commit field" 0
else
  assert "dsh-pin.txt has dsh_commit field" 1
fi

# Check node_version field
if grep -q '^node_version=' "$REPO_ROOT/engines/dsh-pin.txt"; then
  assert "dsh-pin.txt has node_version field" 0
else
  assert "dsh-pin.txt has node_version field" 1
fi

# Check dsh_commit value is non-empty and looks like a git SHA
COMMIT_VALUE=$(grep '^dsh_commit=' "$REPO_ROOT/engines/dsh-pin.txt" | cut -d'=' -f2- | tr -d '[:space:]')
if [ -n "$COMMIT_VALUE" ] && [ ${#COMMIT_VALUE} -ge 7 ]; then
  assert "dsh_commit value is a valid-looking SHA ($COMMIT_VALUE)" 0
else
  assert "dsh_commit value is a valid-looking SHA" 1
fi

# --- Test 2: acp.cordis.yml exists and has approval.policy: ask ---
echo "Checking engines/acp.cordis.yml..."
if [ -f "$REPO_ROOT/engines/acp.cordis.yml" ]; then
  assert "acp.cordis.yml exists" 0
else
  assert "acp.cordis.yml exists" 1
  echo "  ABORT: cannot run further cordis tests without the file"
  exit 1
fi

if grep -q 'policy: ask' "$REPO_ROOT/engines/acp.cordis.yml"; then
  assert "acp.cordis.yml has approval.policy: ask" 0
else
  assert "acp.cordis.yml has approval.policy: ask" 1
fi

if grep -q 'workspace-write' "$REPO_ROOT/engines/acp.cordis.yml"; then
  assert "acp.cordis.yml has sandbox-policy.mode: workspace-write" 0
else
  assert "acp.cordis.yml has sandbox-policy.mode: workspace-write" 1
fi

# --- Test 3: build_dsh_release.sh --dry-run exits 0 ---
echo "Checking build_dsh_release.sh --dry-run..."
if [ -x "$REPO_ROOT/scripts/build_dsh_release.sh" ]; then
  assert "build_dsh_release.sh is executable" 0
else
  assert "build_dsh_release.sh is executable" 1
fi

if "$REPO_ROOT/scripts/build_dsh_release.sh" --dry-run >/dev/null 2>&1; then
  assert "build_dsh_release.sh --dry-run exits 0" 0
else
  assert "build_dsh_release.sh --dry-run exits 0" 1
fi

# --- Test 4: No secrets in engines/ config files ---
echo "Checking for secrets in engines/..."
if grep -rq 'DEEPSEEK_API_KEY\|sk-[a-zA-Z0-9]\|secret_key\|password' "$REPO_ROOT/engines/" 2>/dev/null; then
  assert "no secrets in engines/ config" 1
  echo "  WARNING: potential secrets found:"
  grep -rn 'DEEPSEEK_API_KEY\|sk-[a-zA-Z0-9]\|secret_key\|password' "$REPO_ROOT/engines/" || true
else
  assert "no secrets in engines/ config" 0
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
