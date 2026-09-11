"""Wake-on-LAN Manager Application Package.

Versionsnummer: SINGLE SOURCE OF TRUTH für alle Varianten
(Windows, Ubuntu, Android, iOS). Diese Zahl ändern und danach
``python update_version.py 2.3.5`` ausführen — es verteilt die Version auf
alle Build-Dateien (build.gradle.kts, project.yml, setup.iss, Docs, …)
und regeneriert das Xcode-Projekt. ``tests/test_version_sync.py``
stellt sicher, dass nichts mehr driftet.
"""

__version__ = "2.3.5"
