#!/usr/bin/env bash
# build_dsh_release.sh — DSH engine release pipeline.
#
# Pipeline: read pin → clone/checkout DSH → pnpm install → pnpm build
#           → assemble engine dir → zip → generate engine-manifest.json
#
# Usage:
#   scripts/build_dsh_release.sh <version>           # full build
#   scripts/build_dsh_release.sh --dry-run           # validate pin + repo, print planned steps
#
# Environment:
#   DSH_REPO  — path to the DSH git repo (default: /home/sorawatcher/deepseek-harness)
#
# The script does NOT auto-upgrade — it builds only from the pinned commit in
# engines/dsh-pin.txt. Upgrading requires editing the pin file → rebuild →
# real-machine regression → app version release.
#
# The script does NOT modify the DSH repo (read-only source).
# The script does NOT bake any API keys or secrets into the engine zip.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIN_FILE="$REPO_ROOT/engines/dsh-pin.txt"
CORDIS_FILE="$REPO_ROOT/engines/acp.cordis.yml"
DSH_REPO="${DSH_REPO:-/home/sorawatcher/deepseek-harness}"
DRY_RUN=false
VERSION=""

# --- Parse arguments ---
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 <version> [--dry-run]"
      echo "  <version>   Engine version label (e.g. 0.1.0-47f943859b)"
      echo "  --dry-run   Validate pin + repo, print planned steps without building"
      exit 0
      ;;
    *)
      if [ -z "$VERSION" ]; then
        VERSION="$1"
        shift
      else
        echo "ERROR: unexpected argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

# --- Read pin file ---
if [ ! -f "$PIN_FILE" ]; then
  echo "ERROR: pin file not found: $PIN_FILE" >&2
  exit 1
fi

COMMIT=$(grep '^dsh_commit=' "$PIN_FILE" | cut -d'=' -f2- | tr -d '[:space:]')
NODE_VERSION_REQ=$(grep '^node_version=' "$PIN_FILE" | cut -d'=' -f2- | tr -d '[:space:]')

if [ -z "$COMMIT" ]; then
  echo "ERROR: dsh_commit not found in $PIN_FILE" >&2
  exit 1
fi

if [ -z "$NODE_VERSION_REQ" ]; then
  echo "ERROR: node_version not found in $PIN_FILE" >&2
  exit 1
fi

echo "Pin: dsh_commit=$COMMIT"
echo "Pin: node_version=$NODE_VERSION_REQ"

# --- Validate DSH repo exists ---
if [ ! -d "$DSH_REPO" ]; then
  echo "ERROR: DSH repo not found: $DSH_REPO" >&2
  exit 1
fi

if [ ! -d "$DSH_REPO/.git" ]; then
  echo "ERROR: not a git repository: $DSH_REPO" >&2
  exit 1
fi

# --- Validate cordis.yml exists ---
if [ ! -f "$CORDIS_FILE" ]; then
  echo "ERROR: acp.cordis.yml not found: $CORDIS_FILE" >&2
  exit 1
fi

# --- Validate the pinned commit exists in the DSH repo ---
if ! (cd "$DSH_REPO" && git cat-file -e "$COMMIT" 2>/dev/null); then
  echo "ERROR: commit $COMMIT not found in $DSH_REPO" >&2
  exit 1
fi

echo "DSH repo: $DSH_REPO (commit $COMMIT verified)"

# --- Dry-run mode: print planned steps and exit ---
if [ "$DRY_RUN" = true ]; then
  echo ""
  echo "=== DRY RUN — planned steps ==="
  echo "1. Clone $DSH_REPO to temp workdir"
  echo "2. Checkout commit $COMMIT"
  echo "3. pnpm install --frozen-lockfile (fallback: pnpm install)"
  echo "4. pnpm run build"
  echo "5. Assemble engine-$VERSION/ directory:"
  echo "   - lib/bin.js + lib/index.js + lib/invariant.js"
  echo "   - node_modules/@deepseek-ai/ (workspace deps)"
  echo "   - node_modules/@agentclientprotocol/ (ACP SDK)"
  echo "   - acp.cordis.yml (product composition)"
  echo "6. Zip as engine-$VERSION.zip"
  echo "7. Generate engine-manifest.json:"
  echo "   - engine_version: $VERSION"
  echo "   - dsh_commit: $COMMIT"
  echo "   - node_version: \$(node --version)"
  echo "   - sha256: \$(sha256sum engine-$VERSION.zip)"
  echo "   - built_at: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "DRY RUN: all validations passed. No build performed."
  exit 0
fi

# --- Real build mode ---
if [ -z "$VERSION" ]; then
  echo "ERROR: version argument required for real build" >&2
  echo "Usage: $0 <version> [--dry-run]" >&2
  exit 1
fi

echo "Building DSH engine $VERSION from commit $COMMIT"

# --- Workspace setup ---
WORKDIR=$(mktemp -d)
ENGINE_DIR_NAME="engine-$VERSION"
OUTPUT_DIR="$REPO_ROOT/engines/releases"
mkdir -p "$OUTPUT_DIR"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

# --- Clone and checkout ---
echo "Cloning DSH repo to $WORKDIR/dsh..."
git clone "$DSH_REPO" "$WORKDIR/dsh"
cd "$WORKDIR/dsh"
git checkout "$COMMIT"

# --- Install dependencies ---
echo "Installing dependencies..."
if pnpm install --frozen-lockfile; then
  echo "Install succeeded with --frozen-lockfile"
else
  echo "WARN: lockfile drift, retrying without --frozen-lockfile" >&2
  pnpm install
fi

# --- Build ---
echo "Building DSH..."
pnpm run build

# --- Assemble engine directory ---
ENGINE_DIR="$WORKDIR/$ENGINE_DIR_NAME"
echo "Assembling engine directory: $ENGINE_DIR"
mkdir -p "$ENGINE_DIR/lib"
mkdir -p "$ENGINE_DIR/node_modules"

# Copy built bin and lib outputs
cp -r "$WORKDIR/dsh/packages/examples/acp-demo/lib/"* "$ENGINE_DIR/lib/"

# Copy workspace dependency node_modules
if [ -d "$WORKDIR/dsh/node_modules/@deepseek-ai" ]; then
  cp -r "$WORKDIR/dsh/node_modules/@deepseek-ai" "$ENGINE_DIR/node_modules/"
else
  echo "ERROR: node_modules/@deepseek-ai not found after build" >&2
  exit 1
fi

if [ -d "$WORKDIR/dsh/node_modules/@agentclientprotocol" ]; then
  cp -r "$WORKDIR/dsh/node_modules/@agentclientprotocol" "$ENGINE_DIR/node_modules/"
else
  echo "WARN: node_modules/@agentclientprotocol not found" >&2
fi

# Copy product composition config
cp "$CORDIS_FILE" "$ENGINE_DIR/acp.cordis.yml"

# --- Zip ---
ZIP_PATH="$OUTPUT_DIR/engine-$VERSION.zip"
echo "Zipping: $ZIP_PATH"
cd "$WORKDIR"
zip -r "$ZIP_PATH" "$ENGINE_DIR_NAME"

# --- Generate manifest ---
SHA256=$(sha256sum "$ZIP_PATH" | cut -d' ' -f1)
NODE_VERSION=$(node --version)
BUILT_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

MANIFEST_PATH="$OUTPUT_DIR/engine-manifest.json"
cat > "$MANIFEST_PATH" << EOF
{
  "engine_version": "$VERSION",
  "dsh_commit": "$COMMIT",
  "node_version": "$NODE_VERSION",
  "sha256": "$SHA256",
  "built_at": "$BUILT_AT"
}
EOF

echo ""
echo "=== Build complete ==="
echo "  Engine zip:      $ZIP_PATH"
echo "  Manifest:        $MANIFEST_PATH"
echo "  SHA-256:         $SHA256"
echo "  DSH commit:      $COMMIT"
echo "  Node version:    $NODE_VERSION"
echo "  Built at:        $BUILT_AT"
