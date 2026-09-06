#!/usr/bin/env bash
# Build a Debian package (.deb) for the Wake-on-LAN Manager (Ubuntu/GNOME port).
#
# Produces  dist/wake-on-lan-manager_<version>-1_all.deb  which installs:
#   * the GUI app            -> GNOME app grid entry "Wake-on-LAN Manager"
#   * the WOL Host Service   -> systemd unit (enabled by default) + CLI
#
# Uses only dpkg-deb (no debhelper / fakeroot / root required):
#   ./packaging/build_deb.sh
#   sudo apt install ./dist/wake-on-lan-manager_*_all.deb
#
# Environment overrides:
#   DEB_REVISION=<n>   package revision (default 1)
#   DEB_OUT=<dir>      output directory (default: <repo>/dist)
set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$PACKAGING_DIR/.." && pwd)"

PKG_NAME="wake-on-lan-manager"
SERVICE_NAME="wol-host-service"
APP_DIR="usr/share/$PKG_NAME"          # package-internal path (no leading /)
REVISION="${DEB_REVISION:-1}"
OUT_DIR="${DEB_OUT:-$PROJECT_DIR/dist}"

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' "$PROJECT_DIR/wol_app/__init__.py")"
if [ -z "$VERSION" ]; then
    echo "ERROR: could not read __version__ from wol_app/__init__.py" >&2
    exit 1
fi
FULL_VERSION="${VERSION}-${REVISION}"
STAGE="$OUT_DIR/stage/${PKG_NAME}_${FULL_VERSION}_all"

echo "== $PKG_NAME $FULL_VERSION =="
echo "-> staging $STAGE"
rm -rf "$STAGE"
mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/lib/systemd/system" \
    "$STAGE/usr/share/applications" \
    "$STAGE/$APP_DIR"

# --- 1. Application files ---------------------------------------------------
# The app resolves bundled resources relative to the wol_app package and its
# parent directory (wol_app.utils.get_resource_path), so keeping the repo
# layout under /usr/share/<pkg>/ works without any code change.
cp "$PROJECT_DIR/run.py" "$STAGE/$APP_DIR/run.py"
# Stage the Linux host service (systemd/PAM) under its canonical name.
cp "$PROJECT_DIR/wol_host_service_linux.py" "$STAGE/$APP_DIR/wol_host_service.py"
cp "$PROJECT_DIR/icon_modern.png" "$STAGE/$APP_DIR/icon_modern.png"
[ -f "$PROJECT_DIR/icon.png" ] && cp "$PROJECT_DIR/icon.png" "$STAGE/$APP_DIR/icon.png"
for doc in README.md SECURITY.md; do
    [ -f "$PROJECT_DIR/$doc" ] && cp "$PROJECT_DIR/$doc" "$STAGE/$APP_DIR/$doc"
done

# wol_app package incl. locales, stripped of __pycache__ / *.pyc.
# The classic single-window UI (and its dialogs) are NOT part of the Ubuntu
# port: they are excluded so the package ships the Modern UI only. settings_dialog.py
# stays because settings_view imports its pure validators (Linux-safe).
( cd "$PROJECT_DIR" && tar \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='wol_app/main_window.py' \
    --exclude='wol_app/device_dialog.py' \
    --exclude='wol_app/log_dialog.py' \
    --exclude='wol_app/network_scan_dialog.py' \
    --exclude='wol_app/schedule_dialog.py' \
    --exclude='wol_app/update_dialog.py' \
    --exclude='wol_app/graphify-out' \
    -cf - wol_app ) \
    | ( cd "$STAGE/$APP_DIR" && tar -xf - )

# --- 2. Icons (hicolor standard sizes) -------------------------------------
# GNOME follows the hicolor theme; the source icon is 616x616, so the standard
# sizes are rendered with Qt (no ImageMagick dependency). Falls back to a
# single copy when PyQt6 is not importable at build time.
render_icons() {
    local py="$1" dest_root="$2"
    "$py" - "$dest_root" "$PROJECT_DIR/icon_modern.png" "$PKG_NAME.png" <<'PY'
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

stage, source, icon_name = sys.argv[1], sys.argv[2], sys.argv[3]
for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
    img = QImage(source).scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    out_dir = os.path.join(stage, "usr/share/icons/hicolor",
                           f"{size}x{size}", "apps")
    os.makedirs(out_dir, exist_ok=True)
    if not img.save(os.path.join(out_dir, icon_name)):
        raise SystemExit(f"failed to write {size}x{size} icon")
PY
}

PY_BIN=""
for cand in "$PROJECT_DIR/venv/bin/python3" "$(command -v python3 || true)"; do
    [ -n "$cand" ] || continue
    if "$cand" -c 'import PyQt6.QtGui' >/dev/null 2>&1; then
        PY_BIN="$cand"
        break
    fi
done

if [ -n "$PY_BIN" ]; then
    echo "-> rendering hicolor icons with $PY_BIN"
    render_icons "$PY_BIN" "$STAGE"
else
    echo "-> PyQt6 unavailable at build time; installing a single 512x512 icon"
    DEST="$STAGE/usr/share/icons/hicolor/512x512/apps"
    mkdir -p "$DEST"
    cp "$PROJECT_DIR/icon_modern.png" "$DEST/$PKG_NAME.png"
fi

# --- 3. Launchers (system python3 + distro Qt bindings) ---------------------
cat > "$STAGE/usr/bin/$PKG_NAME" <<EOF
#!/bin/sh
# Wake-on-LAN Manager (installed system-wide, uses the distro python3).
exec python3 "/$APP_DIR/run.py" "\$@"
EOF

cat > "$STAGE/usr/bin/$SERVICE_NAME" <<EOF
#!/bin/sh
# WOL Host Service control CLI (uninstall/start/stop/status/run/enable-batch/
# disable-batch). The systemd unit invokes it with --run.
exec python3 "/$APP_DIR/wol_host_service.py" "\$@"
EOF

# --- 4. Desktop entry (GNOME app grid) --------------------------------------
cat > "$STAGE/usr/share/applications/$PKG_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Wake-on-LAN Manager
GenericName=Network utility
Comment=Wake, scan, monitor and shut down devices on the local network
Exec=$PKG_NAME
Terminal=false
Icon=$PKG_NAME
Categories=Network;
Keywords=wake;wol;magic packet;lan;shutdown;remote;
StartupWMClass=wake-on-lan-manager
EOF

# --- 5. systemd unit --------------------------------------------------------
sed "s|@APP_DIR@|/$APP_DIR|g" \
    "$PACKAGING_DIR/deb/$SERVICE_NAME.service" \
    > "$STAGE/usr/lib/systemd/system/$SERVICE_NAME.service"

# --- 6. Maintainer scripts --------------------------------------------------
cp "$PACKAGING_DIR/deb/DEBIAN/postinst" "$STAGE/DEBIAN/postinst"
cp "$PACKAGING_DIR/deb/DEBIAN/prerm"   "$STAGE/DEBIAN/prerm"
cp "$PACKAGING_DIR/deb/DEBIAN/postrm"  "$STAGE/DEBIAN/postrm"
chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

# --- 7. control -------------------------------------------------------------
INSTALLED_SIZE_KB="$(du -sk "$STAGE" | cut -f1)"
sed -e "s|@VERSION@|$FULL_VERSION|g" \
    -e "s|@PKG_NAME@|$PKG_NAME|g" \
    -e "s|@INSTALL_SIZE@|$INSTALLED_SIZE_KB|g" \
    "$PACKAGING_DIR/deb/DEBIAN/control.in" > "$STAGE/DEBIAN/control"

# --- 8. Permissions ---------------------------------------------------------
chmod 0755 "$STAGE/usr/bin/$PKG_NAME" "$STAGE/usr/bin/$SERVICE_NAME"
find "$STAGE" -type d -exec chmod 0755 {} +
find "$STAGE" -type f \( -name '*.png' -o -name '*.md' -o -name '*.desktop' \
    -o -name '*.service' -o -name '*.py' -o -name '*.json' \) -exec chmod 0644 {} +

# --- 9. Build ---------------------------------------------------------------
mkdir -p "$OUT_DIR"
DEB="$OUT_DIR/${PKG_NAME}_${FULL_VERSION}_all.deb"
rm -f "$DEB"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"

echo ""
echo "== Built: $DEB =="
dpkg-deb --info "$DEB" | sed -n '1,16p'
echo ""
echo "Install (resolves dependencies automatically):"
echo "  sudo apt install '$DEB'"
echo "Then: GNOME app grid -> 'Wake-on-LAN Manager',"
echo "      wol-host-service --status"
