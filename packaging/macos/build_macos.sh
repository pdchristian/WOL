#!/usr/bin/env bash
# ============================================================================
# Wake-on-LAN Manager - macOS Build Script (Apple Silicon)
# ============================================================================
# Baut die App als unsigned .app-Bundle + .dmg (entspricht build.ps1 für
# Windows / packaging/build_deb.sh für Ubuntu).
#
#   ./packaging/macos/build_macos.sh            # App (mit Host-Service-Payload) + DMG
#
# Ergebnis:
#   dist/Wake-on-LAN Manager.app            (enthält Contents/Resources/WOL Host Service)
#   dist/Wake-on-LAN-Manager_<version>_arm64.dmg
#   dist/WOL Host Service/                   (onedir, zusätzlich zur Einbettung)
#
# Hinweis: Unsigned -> Verteiler müssen Rechtsklick > Oeffnen (Gatekeeper)
# oder `xattr -dr com.apple.quarantine` verwenden.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

APP_NAME="Wake-on-LAN Manager"
APP_SPEC="Wake-on-LAN Manager-macos.spec"
SERVICE_SPEC="wol_host_service_macos.spec"
SERVICE_NAME="WOL Host Service"
DIST_DIR="dist"

# --- Interpreter: immer das Projekt-venv (.venv auf macOS) -----------------
PY="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "FEHLER: venv nicht gefunden: $PY" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt" >&2
    exit 1
fi
echo "  Interpreter: $PY"
"$PY" --version

VERSION="$("$PY" -c 'import sys; sys.path.insert(0, "'"$PROJECT_DIR"'"); import wol_app; print(wol_app.__version__)')"
echo "  Version: $VERSION"

# --- Step 0: Versions-Sync ---------------------------------------------------
echo "[0/5] Synchronisiere Version in docs..."
"$PY" update_docs_version.py

# --- Step 1: Aufraeumen ------------------------------------------------------
echo "[1/5] Bereite Build vor..."
rm -rf "$DIST_DIR/$APP_NAME.app" "$DIST_DIR/${APP_NAME}_${VERSION}_arm64.dmg"
rm -rf "$DIST_DIR/$SERVICE_NAME"
rm -rf "build/$APP_NAME" "build/$SERVICE_NAME"

# --- Step 2: .icns erzeugen (falls aelter als die Quell-PNG) ----------------
if [ ! -f icon_macos.icns ] || [ icon_modern.png -nt icon_macos.icns ]; then
    echo "[2/5] Erzeuge App-Icon (icon_macos.icns)..."
    ICONSET="Wake-on-LAN Manager.iconset"
    rm -rf "$ICONSET"; mkdir -p "$ICONSET"
    for s in 16 32 128 256 512; do
        sips -z $s $s   icon_modern.png --out "$ICONSET/icon_${s}x${s}.png"     >/dev/null
        sips -z $((s*2)) $((s*2)) icon_modern.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o icon_macos.icns
    rm -rf "$ICONSET"
else
    echo "[2/5] App-Icon aktuell."
fi

# --- Step 3: Host Service bauen (Payload der App) ----------------------------
# Der Service wird VOR der App gebaut: die Spec bettet dist/$SERVICE_NAME als
# Contents/Resources/$SERVICE_NAME in das .app-Bundle ein, damit die App ihn
# beim ersten Start ohne Download installieren kann.
echo "[3/5] Baue $SERVICE_NAME (onedir, Payload fuer die App)..."
"$PY" -m PyInstaller "$SERVICE_SPEC" --distpath "$DIST_DIR" --noconfirm --clean
if [ ! -x "$DIST_DIR/$SERVICE_NAME/$SERVICE_NAME" ]; then
    echo "FEHLER: Host-Service-Bundle nicht gefunden." >&2
    exit 1
fi
# Versions-Stempel: die App vergleicht ihn mit der installierten Version
# (Update-Erkennung) und schreibt ihn beim Installieren als Marker.
echo "$VERSION" > "$DIST_DIR/$SERVICE_NAME/service_version.txt"
codesign --force --sign - "$DIST_DIR/$SERVICE_NAME/$SERVICE_NAME" 2>/dev/null || true

# --- Step 4: App-Bundle bauen ------------------------------------------------
echo "[4/5] Baue $APP_NAME.app (PyInstaller, arm64)..."
"$PY" -m PyInstaller "$APP_SPEC" --distpath "$DIST_DIR" --noconfirm --clean
if [ ! -d "$DIST_DIR/$APP_NAME.app" ]; then
    echo "FEHLER: .app-Bundle nicht gefunden." >&2
    exit 1
fi
if [ ! -x "$DIST_DIR/$APP_NAME.app/Contents/Resources/$SERVICE_NAME/$SERVICE_NAME" ]; then
    echo "FEHLER: Host-Service-Payload fehlt im .app-Bundle (Spec datas?)." >&2
    exit 1
fi
# Ad-hoc-Signatur: ohne jede Signatur verweigert macOS arm64-Binaeres den
# Start - auch fuer den eingebetteten Service (codesign --deep).
codesign --force --deep --sign - "$DIST_DIR/$APP_NAME.app" 2>/dev/null || \
    echo "  WARNUNG: Ad-hoc-codesign fehlgeschlagen (App laeuft ggf. nur lokal)."

# --- Step 5: DMG ---------------------------------------------------------------
echo "[5/5] Erzeuge DMG..."
DMG="$DIST_DIR/${APP_NAME}_${VERSION}_arm64.dmg"
STAGING="$DIST_DIR/dmg_staging"
rm -rf "$STAGING" "$DMG"; mkdir -p "$STAGING"
cp -R "$DIST_DIR/$APP_NAME.app" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGING"

echo ""
echo "==========================================="
echo "  Build fertig:"
echo "  $DMG ($(du -h "$DMG" | cut -f1))"
echo "  Host Service eingebettet: Contents/Resources/$SERVICE_NAME"
echo "==========================================="
