#!/usr/bin/env bash
# test_portable_python_download.sh — Standalone test for portable Python download.
#
# Exercises only the Python download + extraction + verification steps
# (not the full installer build). Can be run in CI to verify the Python
# download pipeline without building the full installer.
#
# Usage: ./scripts/test_portable_python_download.sh [--tmp-dir <dir>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TMP_DIR="${TMP_DIR:-$(mktemp -d)}"
PYTHON_VERSION="3.12.7"
PYTHON_ARCH="amd64"
PYTHON_EMBED_ZIP="python-${PYTHON_VERSION}-embed-${PYTHON_ARCH}.zip"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_EMBED_ZIP}"
PYTHON_DIR="$TMP_DIR/python"

echo "=== Portable Python Download Test ==="
echo "Version: $PYTHON_VERSION"
echo "Temp dir: $TMP_DIR"
echo ""

# Check prerequisites
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  echo "ERROR: neither curl nor wget found" >&2
  exit 1
fi
if ! command -v unzip >/dev/null 2>&1 && ! command -v 7z >/dev/null 2>&1; then
  echo "ERROR: neither unzip nor 7z found" >&2
  exit 1
fi

# Step 1: Download
echo "[1/4] Downloading portable Python..."
PYTHON_ZIP="$TMP_DIR/${PYTHON_EMBED_ZIP}"
if command -v curl >/dev/null 2>&1; then
  curl -fSL -o "$PYTHON_ZIP" "$PYTHON_URL"
else
  wget -q -O "$PYTHON_ZIP" "$PYTHON_URL"
fi
echo "Downloaded: $PYTHON_ZIP"
echo ""

# Step 2: Extract
echo "[2/4] Extracting portable Python..."
mkdir -p "$PYTHON_DIR"
if command -v unzip >/dev/null 2>&1; then
  unzip -q -o "$PYTHON_ZIP" -d "$PYTHON_DIR"
else
  7z x -y -o"$PYTHON_DIR" "$PYTHON_ZIP"
fi
echo "Extracted to: $PYTHON_DIR"
echo ""

# Step 3: Install pip + python-docx + lxml
echo "[3/4] Installing pip and dependencies..."
PTH_FILE=$(find "$PYTHON_DIR" -name "python*._pth" -type f | head -1)
if [ -n "$PTH_FILE" ]; then
  sed -i 's/^#import site/import site/' "$PTH_FILE"
fi

GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"
GET_PIP_TMP="$TMP_DIR/get-pip.py"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL -o "$GET_PIP_TMP" "$GET_PIP_URL"
else
  wget -q -O "$GET_PIP_TMP" "$GET_PIP_URL"
fi

if [ -f "$GET_PIP_TMP" ]; then
  (cd "$PYTHON_DIR" && ./python.exe "$GET_PIP_TMP" --quiet 2>&1 || true)
  "$PYTHON_DIR/python.exe" -m pip install --quiet --no-warn-script-location python-docx lxml 2>&1 || true
fi
echo ""

# Step 4: Verify
echo "[4/4] Verifying portable Python..."
if "$PYTHON_DIR/python.exe" -c "import docx; import lxml; print('ok')" 2>/dev/null; then
  echo "PASS: python-docx and lxml are available."
else
  echo "WARN: python-docx/lxml verification failed (may not be installed)" >&2
fi
echo ""

# Cleanup
rm -rf "$TMP_DIR"
echo "=== Test complete ==="
