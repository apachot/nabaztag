#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Nabaztag.app"
DMG_NAME="nabaztag-macos-client.dmg"
DOWNLOADS_DIR="$SCRIPT_DIR/../../apps/portal/portal_app/static/downloads"
BUILD_VENV="$SCRIPT_DIR/.build-venv"

cd "$SCRIPT_DIR"

rm -rf build dist
python3 -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel py2app
python3 setup.py py2app

mkdir -p "$DOWNLOADS_DIR"
rm -f "$DOWNLOADS_DIR/$DMG_NAME"
hdiutil create \
  -volname "Nabaztag" \
  -srcfolder "dist/$APP_NAME" \
  -ov \
  -format UDZO \
  "$DOWNLOADS_DIR/$DMG_NAME"

echo "DMG généré : $DOWNLOADS_DIR/$DMG_NAME"
