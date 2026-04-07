#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Nabaztag.app"
DMG_NAME="nabaztag-macos-client.dmg"
DOWNLOADS_DIR="$SCRIPT_DIR/../../apps/portal/portal_app/static/downloads"
BUILD_VENV="$SCRIPT_DIR/.build-venv"
APP_PATH="$SCRIPT_DIR/dist/$APP_NAME"
DMG_PATH="$DOWNLOADS_DIR/$DMG_NAME"
PYPROJECT_PATH="$SCRIPT_DIR/pyproject.toml"
PYPROJECT_BACKUP="$SCRIPT_DIR/pyproject.toml.py2app-backup"
APPLE_DEVELOPER_IDENTITY="${APPLE_DEVELOPER_IDENTITY:-}"
APPLE_NOTARY_PROFILE="${APPLE_NOTARY_PROFILE:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

sign_path() {
  local target="$1"
  codesign \
    --force \
    --timestamp \
    --options runtime \
    --sign "$APPLE_DEVELOPER_IDENTITY" \
    "$target"
}

prune_qt_bundle() {
  local pyside_dir="$APP_PATH/Contents/Resources/lib/python3.10/PySide6"
  local qt_dir="$pyside_dir/Qt"
  local lib_dir="$qt_dir/lib"
  local plugins_dir="$qt_dir/plugins"

  [[ -d "$pyside_dir" ]] || return 0

  rm -rf \
    "$pyside_dir/Assistant.app" \
    "$pyside_dir/Designer.app" \
    "$pyside_dir/Linguist.app" \
    "$pyside_dir/include" \
    "$pyside_dir/doc" \
    "$pyside_dir/examples" \
    "$pyside_dir/glue" \
    "$pyside_dir/scripts" \
    "$pyside_dir/support" \
    "$pyside_dir/typesystems" \
    "$pyside_dir/Qt/qml" \
    "$pyside_dir/Qt/translations" \
    "$pyside_dir/Qt/metatypes" \
    "$pyside_dir/Qt/libexec"

  find "$pyside_dir" -maxdepth 1 -type f -name '*.abi3.so' \
    ! -name 'QtCore.abi3.so' \
    ! -name 'QtGui.abi3.so' \
    ! -name 'QtWidgets.abi3.so' \
    -delete

  find "$pyside_dir" -maxdepth 1 -type f \
    ! -name '__init__.py' \
    ! -name '_config.py' \
    ! -name 'QtCore.abi3.so' \
    ! -name 'QtGui.abi3.so' \
    ! -name 'QtWidgets.abi3.so' \
    ! -name 'libpyside6.abi3.6.11.dylib' \
    -delete

  if [[ -d "$lib_dir" ]]; then
    find "$lib_dir" -mindepth 1 -maxdepth 1 \
      ! -name 'QtCore.framework' \
      ! -name 'QtGui.framework' \
      ! -name 'QtWidgets.framework' \
      -exec rm -rf {} +
  fi

  if [[ -d "$plugins_dir" ]]; then
    find "$plugins_dir" -mindepth 1 -maxdepth 1 \
      ! -name 'platforms' \
      ! -name 'styles' \
      ! -name 'imageformats' \
      -exec rm -rf {} +
  fi
}

sign_embedded_code() {
  local content_root="$APP_PATH/Contents"
  local item

  while IFS= read -r -d '' item; do
    sign_path "$item"
  done < <(find "$content_root" -type f \( -name '*.dylib' -o -name '*.so' \) -print0 | sort -z)

  while IFS= read -r -d '' item; do
    sign_path "$item"
  done < <(find "$content_root" -type f -perm -111 -print0 | sort -z)

  while IFS= read -r -d '' item; do
    sign_path "$item"
  done < <(find "$content_root" -type d \( -name '*.framework' -o -name '*.app' \) -print0 | sort -z)
}

cd "$SCRIPT_DIR"

rm -rf build dist
python3 -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel py2app
python3 -m pip install PySide6 pyobjc-framework-CoreLocation
if [[ -f "$PYPROJECT_PATH" ]]; then
  mv "$PYPROJECT_PATH" "$PYPROJECT_BACKUP"
fi
trap 'if [[ -f "$PYPROJECT_BACKUP" ]]; then mv "$PYPROJECT_BACKUP" "$PYPROJECT_PATH"; fi' EXIT
python3 setup.py py2app
prune_qt_bundle

if [[ -n "$APPLE_DEVELOPER_IDENTITY" ]]; then
  echo "Signature de l'application avec Developer ID…"
  sign_embedded_code
  sign_path "$APP_PATH"
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
