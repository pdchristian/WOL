"""Wake-on-LAN Manager Application Package.

Versionsnummer: SINGLE SOURCE OF TRUTH für alle Varianten — in zwei Linien,
weil Desktop und Mobile unterschiedliche Inhalte haben:

``__version__``
    Desktop-Linie (Windows, Ubuntu, macOS). ``python update_version.py X.Y.Z``
    verteilt sie auf ``setup.iss``, die PyInstaller-Specs, ``build.ps1``, das
    Ubuntu-``.deb`` (liest ``__version__`` direkt) und das macOS-Bundle.

``MOBILE_VERSION``
    Mobile-Linie (Android/iOS-WebView-Clients). ``python update_version.py
    --mobile X.Y.Z`` verteilt sie auf ``build.gradle.kts``, ``project.yml``,
    die WebApp-Fallbacks und ``docs/android/html-app.md``.

Getrennte Zahlen sind Absicht: Funktionen, die nur der Desktop hat (z. B.
Plattform-Pill, RDP/Turbo-VNC-Routing, gruppierte Einstellungen), lassen die
Mobile-App unverändert — sie behält ihre vorherige Release-Nummer, bis sie
eigene Änderungen trägt. ``tests/test_version_sync.py`` stellt sicher, dass
jede Linie mit ihren Build-Dateien übereinstimmt.
"""

__version__ = "2.5.0"

# Android/iOS WebView clients — 2.4.0: settings grouped like the desktop.
MOBILE_VERSION = "2.4.0"
