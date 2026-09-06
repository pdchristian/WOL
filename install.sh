#!/usr/bin/env bash
# Wake-on-LAN Manager (Ubuntu/GNOME) - installation script.
#
# Installs system dependencies, creates a virtualenv and a GNOME desktop
# entry. Run from the project root:  ./install.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
DESKTOP_FILE="$HOME/.local/share/applications/wake-on-lan-manager.desktop"
ICON_DIR="$HOME/.local/share/icons"

echo "== Wake-on-LAN Manager - Ubuntu installation =="

# 1. System dependencies -----------------------------------------------------
echo "-> Installing system packages (sudo required)"
sudo apt update
sudo apt install -y \
    python3 python3-venv python3-pip \
    python3-pyqt6 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    freerdp2-x11 \
    iputils-ping \
    iproute2 \
    avahi-daemon \
    libpam0g \
    libpam0g-dev

# 2. Python virtualenv --------------------------------------------------------
echo "-> Creating virtualenv at $VENV_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# 3. Desktop entry ------------------------------------------------------------
echo "-> Installing GNOME desktop entry"
mkdir -p "$(dirname "$DESKTOP_FILE")" "$ICON_DIR"
install -m 0644 "$PROJECT_DIR/icon_modern.png" "$ICON_DIR/wake-on-lan-manager.png" 2>/dev/null \
    || cp "$PROJECT_DIR/icon_modern.png" "$ICON_DIR/wake-on-lan-manager.png"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Wake-on-LAN Manager
Comment=Wake, scan and manage devices on your local network
Exec=$VENV_DIR/bin/python3 $PROJECT_DIR/run.py
Path=$PROJECT_DIR
Icon=$ICON_DIR/wake-on-lan-manager.png
Terminal=false
Categories=Utility;Network;
StartupWMClass=wake-on-lan-manager
EOF
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "-> Optional: WOL Host Service (remote shutdown / dashboard metrics)"
read -r -p "   Install the 'WOL Host Service' (systemd, TCP 8765)? [Y/n] " INSTALL_HOST
case "${INSTALL_HOST:-Y}" in
    [Yy]*)
        sudo "$VENV_DIR/bin/python3" "$PROJECT_DIR/wol_host_service_linux.py" --install \
            || echo "WARNING: Host service installation failed - you can retry with:
   sudo $VENV_DIR/bin/python3 $PROJECT_DIR/wol_host_service_linux.py --install"
        ;;
    *)
        echo "   Skipped. Install later with:"
        echo "   sudo $VENV_DIR/bin/python3 $PROJECT_DIR/wol_host_service_linux.py --install"
        ;;
esac

echo ""
echo "== Done =="
echo "Start from the GNOME app grid ('Wake-on-LAN Manager') or with:"
echo "  $VENV_DIR/bin/python3 $PROJECT_DIR/run.py"
echo ""
echo "Remote shutdown and dashboard metrics use the WOL Host Service"
echo "(wol_host_service_linux.py, TCP port 8765) on the target machine."
