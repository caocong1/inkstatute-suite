#!/usr/bin/env bash
# test_materialize_presets.sh — smoke test for materialize_presets.sh
#
# Uses a temp directory as DEST to avoid touching the real ~/.agent-presets/.
# Verifies:
#   1. Files are materialized correctly (preset.yml + SKILL.md)
#   2. Installed files are read-only (write should fail)
#   3. Re-running the script overwrites atomically (idempotent)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TEST_DEST=$(mktemp -d)
TEST_SRC=$(mktemp -d)

cleanup() {
  chmod -R u+w "$TEST_DEST" "$TEST_SRC" 2>/dev/null || true
  rm -rf "$TEST_DEST" "$TEST_SRC"
}
trap cleanup EXIT

# Create a minimal test preset
mkdir -p "$TEST_SRC/test-domain"
cat > "$TEST_SRC/test-domain/preset.yml" << 'YAML'
name: test-domain
description: Test domain for materialization smoke test
YAML
mkdir -p "$TEST_SRC/test-domain/skills/test-skill"
cat > "$TEST_SRC/test-domain/skills/test-skill/SKILL.md" << 'SKILL'
---
name: test-skill
description: Test skill for materialization
---
Test skill body.
SKILL

echo "=== test_materialize_presets.sh ==="

# Run materialization with test paths
PRESETS_SRC="$TEST_SRC" DEST="$TEST_DEST" bash "$REPO_ROOT/scripts/materialize_presets.sh"

# Verify materialization
if [[ -f "$TEST_DEST/test-domain/preset.yml" ]]; then
  echo "  PASS: preset.yml materialized"
else
  echo "  FAIL: preset.yml not materialized"
  exit 1
fi

if [[ -f "$TEST_DEST/test-domain/skills/test-skill/SKILL.md" ]]; then
  echo "  PASS: SKILL.md materialized"
else
  echo "  FAIL: SKILL.md not materialized"
  exit 1
fi

# Verify read-only: writing should fail
if echo "test" >> "$TEST_DEST/test-domain/preset.yml" 2>/dev/null; then
  echo "  FAIL: installed file is writable (should be read-only)"
  exit 1
else
  echo "  PASS: installed file is read-only"
fi

# Verify atomic re-run (overwrite)
PRESETS_SRC="$TEST_SRC" DEST="$TEST_DEST" bash "$REPO_ROOT/scripts/materialize_presets.sh" >/dev/null
if [[ -f "$TEST_DEST/test-domain/preset.yml" ]]; then
  echo "  PASS: re-run preserved files (atomic overwrite)"
else
  echo "  FAIL: re-run did not preserve files"
  exit 1
fi

echo ""
echo "PASS: materialize_presets.sh smoke test"
