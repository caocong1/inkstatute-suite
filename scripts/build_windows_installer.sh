#!/usr/bin/env bash
# build_windows_installer.sh — Build the InkStatute Windows installer (PKG-01).
#
# Bundles: Flutter release build + DSH engine zip + portable Python + lxml +
# track-changes script + initial content pack + presets.
# Produces: dist/InkStatute-Setup-<version>.exe
#
# Usage: ./scripts/build_windows_installer.sh [--version <version>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/flutter_app"
ENGINES_DIR="$ROOT_DIR/engines"
PRESETS_DIR="$ROOT_DIR/presets"
ASSETS_SCRIPTS_DIR="$APP_DIR/assets/scripts"

VERSION="${1:-0.1.0}"
DIST_DIR="$ROOT_DIR/dist"
STAGING_DIR="$DIST_DIR/staging"

echo "=== InkStatute Windows Installer Build ==="
echo "Version: $VERSION"
echo "Root: $ROOT_DIR"
echo ""

# Step 1: Flutter build windows --release
echo "[1/6] Building Flutter Windows release..."
cd "$APP_DIR"
flutter build windows --release
echo "Flutter build complete."
echo ""

# Step 2: Create staging directory
echo "[2/6] Creating staging directory..."
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
mkdir -p "$STAGING_DIR/app"
mkdir -p "$STAGING_DIR/engine"
mkdir -p "$STAGING_DIR/python"
mkdir -p "$STAGING_DIR/scripts"
mkdir -p "$STAGING_DIR/presets"
mkdir -p "$STAGING_DIR/content"
echo "Staging directory created."
echo ""

# Step 3: Copy Flutter build output
echo "[3/6] Copying Flutter build output..."
FLUTTER_BUILD_DIR="$APP_DIR/build/windows/x64/runner/Release"
if [ -d "$FLUTTER_BUILD_DIR" ]; then
  cp -r "$FLUTTER_BUILD_DIR"/* "$STAGING_DIR/app/"
  echo "Flutter build copied."
else
  echo "WARNING: Flutter build directory not found at $FLUTTER_BUILD_DIR"
fi
echo ""

# Step 4: Copy engine
echo "[4/6] Copying DSH engine..."
if [ -d "$ENGINES_DIR" ]; then
  for engine_zip in "$ENGINES_DIR"/engine-*.zip; do
    if [ -f "$engine_zip" ]; then
      cp "$engine_zip" "$STAGING_DIR/engine/"
      echo "Engine zip copied: $(basename "$engine_zip")"
    fi
  done
  if [ -f "$ENGINES_DIR/engine-manifest.json" ]; then
    cp "$ENGINES_DIR/engine-manifest.json" "$STAGING_DIR/engine/"
    echo "Engine manifest copied."
  fi
else
  echo "WARNING: engines/ directory not found"
fi
echo ""

# Step 5: Copy portable Python and scripts
echo "[5/6] Copying Python and scripts..."
if [ -f "$ASSETS_SCRIPTS_DIR/contract_review_trackchanges_v4.py" ]; then
  cp "$ASSETS_SCRIPTS_DIR/contract_review_trackchanges_v4.py" "$STAGING_DIR/scripts/"
  echo "Track-changes script copied."
fi
echo "NOTE: Portable Python must be downloaded and placed in staging/python/"
echo "      See .planning/phases/118-word-track-changes-export/118-RESEARCH.md"
echo ""

# Step 6: Copy presets and content pack
echo "[6/6] Copying presets and content pack..."
if [ -d "$PRESETS_DIR" ]; then
  cp -r "$PRESETS_DIR"/* "$STAGING_DIR/presets/"
  echo "Presets copied."
fi
echo ""

# Step 7: Run Inno Setup (if available)
echo "=== Running Inno Setup ==="
ISS_FILE="$SCRIPT_DIR/inkstatute_installer.iss"
if [ -f "$ISS_FILE" ]; then
  if command -v iscc >/dev/null 2>&1; then
    iscc "/Q" "/DAPP_VERSION=$VERSION" "$ISS_FILE"
    echo "Installer built: dist/InkStatute-Setup-$VERSION.exe"
  else
    echo "NOTE: Inno Setup (iscc) not found. Staging directory created at:"
    echo "      $STAGING_DIR"
    echo "      Run Inno Setup manually with: iscc $ISS_FILE"
  fi
else
  echo "NOTE: Inno Setup script not found at $ISS_FILE"
  echo "      Staging directory created at: $STAGING_DIR"
fi

echo ""
echo "=== Build complete ==="
echo "Staging: $STAGING_DIR"
echo "Output:  $DIST_DIR/InkStatute-Setup-$VERSION.exe (if Inno Setup ran)"
