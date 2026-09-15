#!/usr/bin/env bash
# ============================================================================
# WOL Host Service - macOS Installation (LaunchDaemon)
# ============================================================================
# Installiert den "WOL Host Service" (TCP 8765) als LaunchDaemon, damit die
# Wake-on-LAN Manager App (Android/iOS/Desktop) diesen Mac fernsteuern kann
# (Status, Metriken, Herunterfahren, Neustart).
#
# Doppelklick im Finder ODER im Terminal:
#   sudo ./packaging/macos/install_host_service.command
#
# Quellen (in dieser Reihenfolge gesucht):
#   1. dist/WOL Host Service/            (onedir-Bundle, von build_macos.sh)
#   2. Neben diesem Skript: WOL Host Service/
#   3. Fallback: .venv/bin/python + wol_host_service_macos.py aus dem Repo
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="/usr/local/lib/wol-host-service"
BIN_NAME="WOL Host Service"
SERVICE_PY="$PROJECT_DIR/wol_host_service_macos.py"

echo "============================================"
echo "  WOL Host Service - macOS Installation"
echo "============================================"

# root-Privilegien fuer Installationsvorgang sicherstellen
if [ "$(id -u)" != "0" ]; then
    echo "-> sudo erforderlich (LaunchDaemon + Firewall)."
    exec sudo "$0" "$@"
fi

# --- Quelle ermitteln -------------------------------------------------------
SRC_BUNDLE=""
for cand in "$PROJECT_DIR/dist/$BIN_NAME" "$SCRIPT_DIR/$BIN_NAME"; do
    if [ -x "$cand/$BIN_NAME" ]; then SRC_BUNDLE="$cand"; break; fi
done

PY="$PROJECT_DIR/.venv/bin/python"

if [ -n "$SRC_BUNDLE" ]; then
    echo "-> Installiere Bundle: $SRC_BUNDLE"
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cp -R "$SRC_BUNDLE/." "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$BIN_NAME"
    TARGET=("$INSTALL_DIR/$BIN_NAME")
elif [ -x "$PY" ] && [ -f "$SERVICE_PY" ]; then
    echo "-> Kein Bundle gefunden - Installiere aus dem Repo (venv-python)."
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    # Kopie des Quellcodes, damit loeschen/umbenennen des Repos unproblematisch ist.
    cp "$SERVICE_PY" "$PROJECT_DIR/wol_host_service_linux.py" "$INSTALL_DIR/"
    TARGET=("$PY" "$INSTALL_DIR/wol_host_service_macos.py")
else
    echo "FEHLER: Weder gebautes Bundle (dist/'$BIN_NAME') noch" >&2
    echo "        $SERVICE_PY mit $PY gefunden." >&2
    echo "        Build: ./packaging/macos/build_macos.sh" >&2
    exit 1
fi

# --- LaunchDaemon registrieren (Service-Kopie aufrufen lassen) --------------
# --install schreibt die plist selbst (ProgramArguments zeigen auf die
# Installationskopie, nicht auf das Repo) und konfigurert die Firewall.
"${TARGET[@]}" --install

echo ""
echo "-> Status:"
"${TARGET[@]}" --status || true
echo ""
echo "Fertig. Der Dienst laeuft ab jetzt automatisch nach jedem Start."
echo ""
echo "  Deinstallieren:  sudo '${TARGET[0]}' --uninstall"
echo "  Batch (run_batch) aktivieren (opt-in):"
echo "                   sudo '${TARGET[0]}' --enable-batch"
echo ""
echo "In der Wake-on-LAN Manager App den Mac als Geraet mit Host-Service"
echo "(Port 8765) anlegen, um Status/Metriken/Fernabschaltung zu nutzen."
