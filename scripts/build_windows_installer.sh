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

# Step 5: Download and set up portable Python and scripts
echo "[5/6] Setting up portable Python..."
if [ -f "$ASSETS_SCRIPTS_DIR/contract_review_trackchanges_v4.py" ]; then
  cp "$ASSETS_SCRIPTS_DIR/contract_review_trackchanges_v4.py" "$STAGING_DIR/scripts/"
  echo "Track-changes script copied."
fi

# Allow skipping Python download (e.g., when already present or offline build)
SKIP_PYTHON="${SKIP_PYTHON:-false}"
PYTHON_ZIP_CACHE="${PYTHON_ZIP_CACHE:-}"
PYTHON_VERSION="3.12.7"
PYTHON_ARCH="amd64"
PYTHON_EMBED_ZIP="python-${PYTHON_VERSION}-embed-${PYTHON_ARCH}.zip"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_EMBED_ZIP}"
PYTHON_STAGING_DIR="$STAGING_DIR/python"

if [ "$SKIP_PYTHON" = "true" ] && [ -f "$PYTHON_STAGING_DIR/python.exe" ]; then
  echo "SKIP_PYTHON=true and python.exe exists — skipping download."
elif [ -f "$PYTHON_STAGING_DIR/python.exe" ]; then
  echo "Portable Python already present at staging/python/ — skipping download."
else
  echo "Downloading portable Python ${PYTHON_VERSION}..."

  PYTHON_TMP_ZIP="$DIST_DIR/${PYTHON_EMBED_ZIP}"

  if [ -n "$PYTHON_ZIP_CACHE" ] && [ -f "$PYTHON_ZIP_CACHE" ]; then
    echo "Using cached portable Python: $PYTHON_ZIP_CACHE"
    cp "$PYTHON_ZIP_CACHE" "$PYTHON_TMP_ZIP"
  elif command -v curl >/dev/null 2>&1; then
    curl -fSL -o "$PYTHON_TMP_ZIP" "$PYTHON_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$PYTHON_TMP_ZIP" "$PYTHON_URL"
  else
    echo "ERROR: neither curl nor wget found — cannot download portable Python" >&2
    exit 1
  fi

  echo "Extracting portable Python..."
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$PYTHON_TMP_ZIP" -d "$PYTHON_STAGING_DIR"
  elif command -v 7z >/dev/null 2>&1; then
    7z x -y -o"$PYTHON_STAGING_DIR" "$PYTHON_TMP_ZIP"
  else
    echo "ERROR: neither unzip nor 7z found — cannot extract portable Python" >&2
    exit 1
  fi

  # Install pip into the embeddable Python (needed for python-docx + lxml)
  echo "Installing pip into portable Python..."
  # The embeddable distribution has python312._pth; uncomment the import site line
  # so pip can work, then download get-pip.py and run it.
  PTH_FILE=$(find "$PYTHON_STAGING_DIR" -name "python*._pth" -type f | head -1)
  if [ -n "$PTH_FILE" ]; then
    sed -i 's/^#import site/import site/' "$PTH_FILE"
  fi

  GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"
  GET_PIP_TMP="$DIST_DIR/get-pip.py"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$GET_PIP_TMP" "$GET_PIP_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$GET_PIP_TMP" "$GET_PIP_URL"
  fi

  if [ -f "$GET_PIP_TMP" ]; then
    (cd "$PYTHON_STAGING_DIR" && ./python.exe "$GET_PIP_TMP" --quiet 2>&1 || true)
    # Install python-docx and lxml (the track-changes script dependencies)
    "$PYTHON_STAGING_DIR/python.exe" -m pip install --quiet --no-warn-script-location python-docx lxml 2>&1 || {
      echo "WARN: pip install of python-docx/lxml failed — Word export may not work" >&2
    }
  else
    echo "WARN: could not download get-pip.py — Word export may not work" >&2
  fi

  # Verify the portable Python works
  echo "Verifying portable Python..."
  if ! "$PYTHON_STAGING_DIR/python.exe" -c "import docx; import lxml; print('ok')" 2>/dev/null; then
    echo "WARN: portable Python verification failed — python-docx/lxml may not be installed" >&2
  else
    echo "Portable Python verified: python-docx and lxml available."
  fi

  # Clean up temp files
  rm -f "$PYTHON_TMP_ZIP" "$GET_PIP_TMP"
fi
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
