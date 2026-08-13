#!/usr/bin/env bash
# materialize_presets.sh — Install presets/ to ~/.agent-presets/ (read-only, install-time only).
#
# Read-only discipline:
# - Installed files are marked read-only (chmod -R a-w).
# - All customization goes through the presets/ source in the repo,
#   never by editing installed files directly.
# - Upgrade = re-run this script (atomic overwrite via staging + rename).
# - Never edit installed files directly — change the source and re-materialize.
#
# Atomicity:
# - Each domain is staged in a temporary directory, marked read-only, then
#   atomically moved into place (rm -rf old + mv staging). This prevents
#   partial states during install/upgrade.
#
# Usage:
#   ./scripts/materialize_presets.sh                              # Install all presets
#   PRESETS_SRC=presets DEST=/tmp/test ./scripts/materialize_presets.sh  # Override paths
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PRESETS_SRC="${PRESETS_SRC:-presets}"
DEST="${DEST:-$HOME/.agent-presets}"

# Resolve PRESETS_SRC relative to repo root if it is not absolute.
case "$PRESETS_SRC" in
  /*) : ;;
  *) PRESETS_SRC="$REPO_ROOT/$PRESETS_SRC" ;;
esac

if [[ ! -d "$PRESETS_SRC" ]]; then
  echo "ERROR: Presets source directory '$PRESETS_SRC' not found" >&2
  exit 1
fi

mkdir -p "$DEST"

domain_count=0
for domain_dir in "$PRESETS_SRC"/*/; do
  [[ -d "$domain_dir" ]] || continue
  domain=$(basename "$domain_dir")
  target="$DEST/$domain"

  # Atomic copy: stage to temp, then rename.
  staging=$(mktemp -d)
  cp -r "$domain_dir." "$staging/"

  # Atomic replace: remove old target, move staging into place.
  # (mv needs write permission on the staging dir to update its ".." entry,
  # so we mark read-only AFTER the move, not before.)
  # Restore write permission on old target before removal (read-only dirs
  # block rm from deleting their contents).
  if [[ -d "$target" ]]; then
    chmod -R u+w "$target" 2>/dev/null || true
  fi
  rm -rf "$target"
  mv "$staging" "$target"

  # Mark read-only: installed files must not be edited directly.
  chmod -R a-w "$target"

  echo "Materialized: $domain → $target"
  domain_count=$((domain_count + 1))
done

if [[ "$domain_count" -eq 0 ]]; then
  echo "WARN: no domain directories found in '$PRESETS_SRC'" >&2
fi

echo "Preset materialization complete ($domain_count domain(s))."
