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

# --- Tool availability checks ---
if ! command -v zip >/dev/null 2>&1; then
  echo "ERROR: zip not found — install zip (apt-get install zip / brew install zip)" >&2
  exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "ERROR: sha256sum not found — install coreutils" >&2
  exit 1
fi

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
git -C "$WORKDIR/dsh" checkout "$COMMIT"

# --- Install dependencies (run inside a subshell so CWD is restored) ---
echo "Installing dependencies..."
(
  cd "$WORKDIR/dsh"
  if pnpm install --frozen-lockfile; then
    echo "Install succeeded with --frozen-lockfile"
  else
    echo "WARN: lockfile drift, retrying without --frozen-lockfile" >&2
    pnpm install
  fi
)

# --- Build ---
echo "Building DSH..."
(
  cd "$WORKDIR/dsh"
  pnpm run build
)

# --- Assemble engine directory via pnpm deploy + missing dep resolution ---
# pnpm deploy creates a minimal tree with only the deployed package's deps.
# --legacy is needed because pnpm v10+ requires inject-workspace-packages=true
# for the default deploy path.
DEPLOY_DIR="$WORKDIR/$ENGINE_DIR_NAME"
echo "Deploying engine package to: $DEPLOY_DIR"
(
  cd "$WORKDIR/dsh"
  if ! pnpm deploy --filter @deepseek-ai/dsh-acp-demo --legacy "$DEPLOY_DIR"; then
    echo "ERROR: pnpm deploy failed" >&2
    exit 1
  fi
)

if [ ! -f "$DEPLOY_DIR/lib/bin.js" ]; then
  echo "ERROR: deployed engine missing lib/bin.js" >&2
  exit 1
fi

cp "$CORDIS_FILE" "$DEPLOY_DIR/acp.cordis.yml"

# --- Copy missing workspace packages and their external deps ---
# pnpm deploy --legacy does not hoist transitive peerDependencies or
# dynamically-loaded plugins. Copy missing workspace packages (lib + package.json)
# and hoist their external npm deps into the deploy tree's root node_modules.
echo "Copying missing workspace packages and resolving external deps..."
WS_PKG_COUNT=0
DEPLOY_PNPM_STORE="$DEPLOY_DIR/node_modules/.pnpm"
DSH_PNPM_STORE="$WORKDIR/dsh/node_modules/.pnpm"

# Copy a pnpm store entry from DSH to deploy, including transitive deps.
# Recursively follows symlinks inside the store entry's node_modules.
copy_store_entry() {
  local store_name="$1"
  local dest_store="$DEPLOY_PNPM_STORE/$store_name"
  if [ -d "$dest_store" ]; then return 0; fi
  local src_store="$DSH_PNPM_STORE/$store_name"
  if [ ! -d "$src_store" ]; then return 0; fi
  mkdir -p "$DEPLOY_PNPM_STORE"
  cp -a "$src_store" "$dest_store"
  # Find symlinks inside the copied store entry that point to other store entries
  # and recursively copy those store entries
  find "$dest_store" -type l 2>/dev/null | while IFS= read -r link; do
    target=$(readlink "$link")
    # pnpm store symlinks look like ../../<store-name>/node_modules/<pkg>
    case "$target" in
      ../../../*) ;;
      *) continue ;;
    esac
    # Extract the store name from the relative path
    rel="${target#../../../}"
    ref_store="${rel%%/node_modules/*}"
    if [ -n "$ref_store" ] && [ "$ref_store" != "$store_name" ]; then
      copy_store_entry "$ref_store"
    fi
  done
}

# Hoist an external dep into the deploy root node_modules.
# Creates the pnpm store entry and symlink.
hoist_external_dep() {
  local dep_name="$1"
  # Skip if already resolvable in deploy root
  if [ -e "$DEPLOY_DIR/node_modules/$dep_name" ] || [ -L "$DEPLOY_DIR/node_modules/$dep_name" ]; then return 0; fi
  local dep_base=$(basename "$dep_name")
  # pnpm store entries are named <basename>@<version>
  local store_entry
  store_entry=$(find "$DSH_PNPM_STORE" -maxdepth 1 -name "${dep_base}@*" -type d 2>/dev/null | head -1)
  if [ -z "$store_entry" ]; then return 0; fi
  local store_name=$(basename "$store_entry")
  # Copy store entry (recursively) into deploy pnpm store
  copy_store_entry "$store_name"
  # Create symlink in deploy root node_modules
  local dep_scope="${dep_name%%/*}"
  local dep_pkg="${dep_name#*/}"
  if [ "$dep_scope" = "$dep_name" ]; then
    # unscoped package
    ln -sf ".pnpm/$store_name/node_modules/$dep_base" "$DEPLOY_DIR/node_modules/$dep_name"
  else
    mkdir -p "$DEPLOY_DIR/node_modules/$dep_scope"
    ln -sf "../../.pnpm/$store_name/node_modules/$dep_pkg" "$DEPLOY_DIR/node_modules/$dep_name"
  fi
}

# Scan workspace packages from packages/*/*, vendor/*, and native/landlock-run/packages/*
scan_and_copy_pkg() {
  local pkg_dir="$1"
  [ -f "$pkg_dir/package.json" ] || return 0
  [ -d "$pkg_dir/lib" ] || return 0
  local pkg_name
  pkg_name=$(python3 -c "import json; print(json.load(open('$pkg_dir/package.json')).get('name',''))" 2>/dev/null || echo "")
  if [ -z "$pkg_name" ]; then return 0; fi
  local scope="${pkg_name%%/*}"
  local pkg_base="${pkg_name#*/}"
  local dest_dir="$DEPLOY_DIR/node_modules/$scope/$pkg_base"
  # Skip if already exists (pnpm-managed symlink or real dir with deps)
  if [ -e "$dest_dir/lib" ] || [ -L "$dest_dir" ]; then return 0; fi
  mkdir -p "$dest_dir"
  cp -r "$pkg_dir/lib" "$dest_dir/"
  cp "$pkg_dir/package.json" "$dest_dir/"
  # Hoist external deps into deploy root node_modules
  python3 -c "
import json
pkg = json.load(open('$pkg_dir/package.json'))
deps = {}
deps.update(pkg.get('dependencies', {}))
deps.update(pkg.get('peerDependencies', {}))
for name in deps:
    if not name.startswith('@deepseek-ai/'):
        print(name)
" 2>/dev/null | while IFS= read -r dep_name; do
    hoist_external_dep "$dep_name"
  done
  WS_PKG_COUNT=$((WS_PKG_COUNT + 1))
}

for pkg_dir in "$WORKDIR/dsh/packages"/*/*; do
  scan_and_copy_pkg "$pkg_dir"
done
for pkg_dir in "$WORKDIR/dsh/vendor"/*; do
  scan_and_copy_pkg "$pkg_dir"
done
for pkg_dir in "$WORKDIR/dsh/native/landlock-run/packages"/*; do
  scan_and_copy_pkg "$pkg_dir"
done
echo "Copied $WS_PKG_COUNT missing workspace packages"

# --- Fix broken symlinks in the pnpm store ---
# pnpm deploy may leave store entries with symlinks to other store entries
# that weren't included in the deploy. Scan all store entries for symlinks
# pointing to missing store entries and copy them from the DSH pnpm store.
echo "Fixing broken pnpm store symlinks..."
STORE_FIX_COUNT=0
find "$DEPLOY_PNPM_STORE" -type l 2>/dev/null | while IFS= read -r link; do
  # Skip if target exists
  if [ -e "$link" ]; then continue; fi
  target=$(readlink "$link")
  # pnpm store symlinks look like ../../<store-name>/node_modules/<pkg>
  case "$target" in
    ../../../*) ;;
    ../*)
      # relative to .pnpm root: ../<store-name>/node_modules/<pkg>
      rel="${target#../../../}"
      rel="${target#../}"
      ;;
    *) continue ;;
  esac
  rel="${target#../}"
  # Remove leading ../ until we get the store name
  while case "$rel" in ../*) true;; *) false;; esac; do
    rel="${rel#../}"
  done
  ref_store="${rel%%/node_modules/*}"
  if [ -n "$ref_store" ]; then
    copy_store_entry "$ref_store"
  fi
done
echo "Fixed broken pnpm store symlinks"

# --- Fix workspace-relative symlinks ---
# pnpm deploy --legacy leaves symlinks pointing to <workspace>/dsh/<path>
# (vendor/*, packages/*). These resolve during build because the DSH clone
# exists in the temp workdir, but break when the zip is extracted elsewhere.
# Find all symlinks whose target contains /dsh/ and replace with real copies.
echo "Fixing workspace-relative symlinks..."
FIXED_COUNT=0
while IFS= read -r ws_link; do
  target=$(readlink "$ws_link")
  # Extract the path after /dsh/ — this is relative to the DSH repo root
  dsh_subpath="${target##*/dsh/}"
  real_source="$WORKDIR/dsh/$dsh_subpath"
  if [ -e "$real_source" ]; then
    rm "$ws_link"
    cp -r "$real_source" "$ws_link"
    FIXED_COUNT=$((FIXED_COUNT + 1))
  else
    echo "WARN: cannot resolve workspace symlink: $ws_link -> $target" >&2
  fi
done < <(find "$DEPLOY_DIR" -type l -exec sh -c 'for f; do t=$(readlink "$f"); case "$t" in */dsh/*) echo "$f";; esac; done' _ {} + 2>/dev/null)
echo "Fixed $FIXED_COUNT workspace-relative symlinks"

# Remove any remaining broken symlinks (non-essential packages)
find "$DEPLOY_DIR" -xtype l -delete 2>/dev/null || true

# Verify no broken symlinks remain
BROKEN_REMAINING=$(find "$DEPLOY_DIR" -xtype l 2>/dev/null | wc -l)
if [ "$BROKEN_REMAINING" -gt 0 ]; then
  echo "ERROR: $BROKEN_REMAINING broken symlinks remain after fixup" >&2
  find "$DEPLOY_DIR" -xtype l 2>/dev/null | head -5 >&2
  exit 1
fi

# --- Zip with symlink preservation (-y) ---
ZIP_PATH="$OUTPUT_DIR/engine-$VERSION.zip"
echo "Zipping: $ZIP_PATH"
(
  cd "$WORKDIR"
  zip -ry "$ZIP_PATH" "$ENGINE_DIR_NAME"
)

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
