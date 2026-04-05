#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Nabaztag.app"
DMG_NAME="nabaztag-macos-client.dmg"
DOWNLOADS_DIR="$SCRIPT_DIR/../../apps/portal/portal_app/static/downloads"
BUILD_VENV="$SCRIPT_DIR/.build-venv"
APP_PATH="$SCRIPT_DIR/dist/$APP_NAME"
DMG_PATH="$DOWNLOADS_DIR/$DMG_NAME"
APPLE_DEVELOPER_IDENTITY="${APPLE_DEVELOPER_IDENTITY:-}"
APPLE_NOTARY_PROFILE="${APPLE_NOTARY_PROFILE:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

cd "$SCRIPT_DIR"

rm -rf build dist
python3 -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel py2app
python3 setup.py py2app

if [[ -n "$APPLE_DEVELOPER_IDENTITY" ]]; then
  echo "Signature de l'application avec Developer ID…"
  codesign \
    --force \
    --deep \
    --timestamp \
    --options runtime \
    --sign "$APPLE_DEVELOPER_IDENTITY" \
    "$APP_PATH"
else
  echo "Aucune identité Developer ID fournie. DMG non signé."
fi

mkdir -p "$DOWNLOADS_DIR"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "Nabaztag" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

if [[ -n "$APPLE_DEVELOPER_IDENTITY" ]]; then
  echo "Signature du DMG…"
  codesign \
    --force \
    --timestamp \
    --sign "$APPLE_DEVELOPER_IDENTITY" \
    "$DMG_PATH"
fi

if [[ -n "$APPLE_NOTARY_PROFILE" ]]; then
  echo "Notarization du DMG avec le profil notarytool '$APPLE_NOTARY_PROFILE'…"
  xcrun notarytool submit "$DMG_PATH" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG_PATH"
elif [[ -n "$APPLE_ID" && -n "$APPLE_TEAM_ID" && -n "$APPLE_APP_PASSWORD" ]]; then
  echo "Notarization du DMG avec Apple ID…"
  xcrun notarytool submit \
    "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait
  xcrun stapler staple "$DMG_PATH"
else
  echo "Aucune configuration de notarization fournie. DMG non notarized."
fi

echo "DMG généré : $DMG_PATH"
