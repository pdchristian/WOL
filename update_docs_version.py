"""Synchronize the version strings across ALL build variants and docs.

Single source of truth: ``wol_app/__init__.py`` — but in TWO lines, because
the desktop and the mobile clients do not always ship the same content:

  ``__version__``      desktop line  (Windows, Ubuntu, macOS)
  ``MOBILE_VERSION``   mobile line   (Android/iOS WebView clients)

``update_docs_version.py`` (no arguments) applies each line to its own files:

  Desktop build files (functional — the shipped binaries use these):
    - setup.iss                          ``#define AppVersion "X.Y.Z"``
    - build.ps1, Wake-on-LAN Manager*.spec

  Mobile build files (functional):
    - android_html/app/build.gradle.kts  ``versionName = "X.Y.Z"``
    - ios/project.yml                    ``"MARKETING_VERSION": "X.Y.Z"``
    - ios/WebApp/app.js                  ``let APP_VERSION = "X.Y.Z"``
    - android_html/.../assets/app/app.js ``let APP_VERSION = "X.Y.Z"``
    - ios/WebApp/bridge.js               ``versionName: "X.Y.Z-demo"``
    - android_html/.../bridge.js         ``versionName: "X.Y.Z-demo"``
    - ios/WolManager/WebView/Bridge.swift fallbacks ``?? "X.Y.Z"``
    - docs/android/html-app.md

  Documentation (desktop line — the docs headline the desktop release):
    - README.md, Bedienungsanleitung.md, KNOWLEDGE.md, SECURITY.md,
      docs/ubuntu/*.md

The Xcode project (``ios/WolManager.xcodeproj/project.pbxproj``) is generated
from ``ios/project.yml`` — run ``xcodegen generate`` inside ``ios/`` (or use
``update_version.py``, which does it automatically).

Run directly (e.g. from build.ps1, build_html.ps1 or CI) — no arguments needed.
Use ``update_version.py X.Y.Z`` (desktop) or ``update_version.py --mobile
X.Y.Z`` (Android/iOS) to bump one line everywhere at once.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_SOURCE = ROOT / "wol_app" / "__init__.py"

# file (relative to repo root): list of (pattern, replacement).
# Replacement may use {version} plus regex backreferences (\g<1>, \g<2>, ...).
DOC_PATTERNS: dict[str, list[tuple[str, str]]] = {
    # ---- Build files: functional, the shipped binaries read these ----
    "setup.iss": [
        (r'(#define AppVersion ")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    # ---- Documentation: headline the desktop release ----
    "README.md": [
        (r"\*\*Version (\d+\.\d+\.\d+)([^\n]*)\*\*", r"**Version {version}\2**"),
    ],
    "Bedienungsanleitung.md": [
        # Only the footer line tracks the release. Anchored on purpose: an
        # unanchored pattern also rewrote historical statements such as
        # "Mit **Version 2.0.0** ist ein neues, modernes App-Design …".
        (r"(\*Version )\d+\.\d+\.\d+( \| Wake-on-LAN Manager\*)",
         r"\g<1>{version}\g<2>"),
    ],
    # NOTE: KNOWLEDGE.md and SECURITY.md each have a single consolidated entry
    # further below — a duplicate dict key here would silently override it.
    "build.ps1": [
        (r"(Version: )\d+\.\d+\.\d+", r"\g<1>{version}"),
        (r"(Manager v)\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "Wake-on-LAN Manager.spec": [
        (r"(Version )\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "Wake-on-LAN Manager-macos.spec": [
        (r"(Version )\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "docs/ubuntu/vm-test-guide.md": [
        (r"(wake-on-lan-manager_)\d+\.\d+\.\d+(-1_all\.deb)", r"\g<1>{version}\g<2>"),
        (r"(Tag `v)\d+\.\d+\.\d+(`)", r"\g<1>{version}\g<2>"),
    ],
    "docs/ubuntu/03-packaging-release.md": [
        (r"(Version aus `wol_app/__init__\.py` \(=)\d+\.\d+\.\d+(\))", r"\g<1>{version}\g<2>"),
        (r"(Version final )\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "docs/ubuntu/README.md": [
        (r"(Windows, v)\d+\.\d+\.\d+(, Source of Truth)", r"\g<1>{version}\g<2>"),
        (r"(Version: auf \*\*)\d+\.\d+\.\d+(\*\* angleichen)", r"\g<1>{version}\g<2>"),
    ],
    "SECURITY.md": [
        # Document header line tracks the current release.
        (r"- \*\*Version:\*\* (\d+\.\d+\.\d+)", r"- **Version:** {version}"),
        # Only the "AKTUELL" row of the version history tracks the release;
        # historical rows keep their version numbers.
        (r"(\| \*\*)\d+\.\d+\.\d+(?=\*\*[^\n]*AKTUELL)", r"\g<1>{version}"),
    ],
    "KNOWLEDGE.md": [
        # Keep the column padding: only the version digits are replaced.
        (r"(\| \*\*version\*\*\s+\| )\d+\.\d+\.\d+", r"\g<1>{version}"),
        # installer.py metadata table + registry sample (current version).
        (r"(\| Version\s+\| )\d+\.\d+\.\d+", r"\g<1>{version}"),
        (r'(DisplayVersion\s+=\s+")\d+\.\d+\.\d+(")', r"\g<1>{version}\g<2>"),
        # Version-history row marked as current ("Current version." keyword).
        (r"(\| )\d+\.\d+\.\d+(?=[^\n]*Current version)", r"\g<1>{version}"),
    ],
}

# Android/iOS WebView clients follow ``MOBILE_VERSION`` instead of
# ``__version__``: desktop-only features must not drag the mobile release
# number forward while its own code is unchanged.
MOBILE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "android_html/app/build.gradle.kts": [
        (r'(versionName\s*=\s*")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    "ios/project.yml": [
        (r'("MARKETING_VERSION":\s*")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    "ios/WebApp/app.js": [
        (r'(let APP_VERSION = ")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    "android_html/app/src/main/assets/app/app.js": [
        (r'(let APP_VERSION = ")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    "ios/WebApp/bridge.js": [
        (r'(versionName: ")\d+\.\d+\.\d+(-demo")', r'\g<1>{version}\g<2>'),
    ],
    "android_html/app/src/main/assets/app/bridge.js": [
        (r'(versionName: ")\d+\.\d+\.\d+(-demo")', r'\g<1>{version}\g<2>'),
    ],
    "ios/WolManager/WebView/Bridge.swift": [
        (r'(\?\? ")\d+\.\d+\.\d+(")', r'\g<1>{version}\g<2>'),
    ],
    "docs/android/html-app.md": [
        (r"(`versionName )\d+\.\d+\.\d+(`)", r"\g<1>{version}\g<2>"),
    ],
}


def read_version() -> str:
    """Extract ``__version__ = "X.Y.Z"`` from the source file."""
    text = VERSION_SOURCE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']', text)
    if not match:
        raise SystemExit(f"ERROR: Could not find __version__ in {VERSION_SOURCE}")
    return match.group(1)


def read_mobile_version() -> str:
    """Extract ``MOBILE_VERSION = "X.Y.Z"`` from the source file."""
    text = VERSION_SOURCE.read_text(encoding="utf-8")
    match = re.search(r'MOBILE_VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']', text)
    if not match:
        raise SystemExit(
            f"ERROR: Could not find MOBILE_VERSION in {VERSION_SOURCE}")
    return match.group(1)


def update_file(path: Path, version: str,
                patterns: dict[str, list[tuple[str, str]]] | None = None) -> bool:
    """Apply version substitutions to *path*. Returns True if anything changed.

    ``patterns`` selects the release line (``DOC_PATTERNS`` for the desktop,
    ``MOBILE_PATTERNS`` for the WebView clients); omitting it keeps the
    historical desktop-only behaviour.
    """
    text = path.read_text(encoding="utf-8")
    changed = False
    table = DOC_PATTERNS if patterns is None else patterns
    # Pattern keys use '/' — Path.relative_to yields '\' on Windows, so
    # without this normalization every sub-directory file silently matched no
    # pattern and was reported as "already up to date" (2.3.5 drift).
    key = str(path.relative_to(ROOT)).replace("\\", "/")
    for pattern, replacement in table.get(key, []):
        # Replace {version} with the actual version, then let re.sub resolve
        # the remaining backreferences (\1, \2, ...) via the string form.
        repl = replacement.format(version=version)
        new_text = re.sub(pattern, repl, text)
        if new_text != text:
            text = new_text
            changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    version = read_version()
    mobile_version = read_mobile_version()
    print(f"Desktop version: {version} | mobile version: {mobile_version}")

    updated = []
    for patterns, line_version, label in (
        (DOC_PATTERNS, version, "desktop"),
        (MOBILE_PATTERNS, mobile_version, "mobile"),
    ):
        for filename in patterns:
            path = ROOT / filename
            if not path.exists():
                print(f"  SKIP  {filename} (not found)")
                continue
            if update_file(path, line_version, patterns):
                updated.append(filename)
                print(f"  UPDATE {filename} -> {line_version} ({label})")
            else:
                print(f"  OK    {filename} ({label} {line_version})")

    if updated:
        print(f"\nUpdated {len(updated)} file(s).")
    else:
        print("\nAll build files and docs already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
