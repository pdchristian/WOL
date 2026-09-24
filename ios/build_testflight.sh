#!/bin/zsh
# Buildet ein App-Store-Archive der iOS-App (inkl. eingebetteter Watch-App)
# und lädt es nach TestFlight hoch.
#
# Voraussetzung:
#   - Kostenpflichtiges Apple-Developer-Konto in Xcode → Settings → Accounts
#   - TEAM_ID als Umgebungsvariable oder unten gesetzt (z. B. EW9H238RWQ)
#
# Verwendung:
#   TEAM_ID=XXXXXXXXXX ./build_testflight.sh            # Archive + Export
#   TEAM_ID=XXXXXXXXXX ./build_testflight.sh --upload   # zusätzlich Upload zu App Store Connect
#
# Nach erfolgreichem Upload: Build erscheint in App Store Connect → TestFlight
# (Verarbeitung dauert 1–15 min), dann interne Tester einladen.
#
# ACHTUNG: Jeder Upload braucht eine eindeutige Build-Nummer
# (CURRENT_PROJECT_VERSION in project.yml) — vor erneutem Upload hochzählen,
# z. B. 1 → 2 (MARKETING_VERSION = 2.3.6 bleibt gleich, nur Build-Nummer hoch).

set -e
cd "$(dirname "$0")"

TEAM_ID="${TEAM_ID:?Bitte TEAM_ID=<DeinTeamID> setzen (kostenpflichtiges Developer-Konto)}"
UPLOAD="${1:-}"

# 0. Projekt aus project.yml neu erzeugen (kanonische Quelle)
xcodegen generate

# 1. Versions-/Build-Nummer aus project.yml lesen
VERSION=$(grep 'MARKETING_VERSION' project.yml | head -1 | sed 's/.*"\(.*\)".*/\1/')
BUILD=$(grep 'CURRENT_PROJECT_VERSION' project.yml | head -1 | sed 's/.*"\(.*\)".*/\1/')
echo "Version $VERSION (Build $BUILD), Team $TEAM_ID"

# 2. Archive (Release, echtes Gerät — Watch-App wird über die Dependency eingebettet)
xcodebuild -scheme WolManager \
  -destination 'generic/platform=iOS' \
  -configuration Release \
  -archivePath build/WolManager.xcarchive \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  CODE_SIGN_STYLE=Automatic \
  -allowProvisioningUpdates \
  clean archive

echo "Archive: $(pwd)/build/WolManager.xcarchive"

# 3. ExportOptions erzeugen (Team-ID einsetzen; bei --upload direkt nach ASC)
OPTIONS=build/ExportOptions.plist
sed "s/TEAM_ID_HIER_EINTRAGEN/$TEAM_ID/" ExportOptions.plist > "$OPTIONS"
if [[ "$UPLOAD" == "--upload" ]]; then
  # destination=upload lädt den Build direkt zu App Store Connect → TestFlight
  /usr/libexec/PlistBuddy -c "Set :destination upload" "$OPTIONS"
fi

# 4. Export/Upload für App Store Connect (validiert Signing + Profile)
xcodebuild -exportArchive \
  -archivePath build/WolManager.xcarchive \
  -exportOptionsPlist "$OPTIONS" \
  -exportPath build/export \
  -allowProvisioningUpdates

if [[ "$UPLOAD" == "--upload" ]]; then
  echo "Hochgeladen. In App Store Connect → TestFlight prüfen (Verarbeitung 1–15 min)."
else
  echo "Export: $(pwd)/build/export/WolManager.ipa"
  echo "Upload entweder mit: TEAM_ID=... ./build_testflight.sh --upload"
  echo "oder manuell: Xcode → Window → Organizer → Distribute App."
fi
