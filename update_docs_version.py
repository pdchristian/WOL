"""Synchronize the version string across ALL build variants and docs.

Single source of truth: ``wol_app/__init__.py`` (``__version__``).
This script propagates that version to every hardcoded reference so the
Windows, Ubuntu, Android and iOS variants can never drift apart again:

  Build files (functional — the shipped binaries use these):
    - setup.iss                          ``#define AppVersion "X.Y.Z"``
    - android_html/app/build.gradle.kts  ``versionName = "X.Y.Z"``
    - ios/project.yml                    ``"MARKETING_VERSION": "X.Y.Z"``
    - ios/WebApp/app.js                  ``let APP_VERSION = "X.Y.Z"``
    - android_html/.../assets/app/app.js ``let APP_VERSION = "X.Y.Z"``
    - ios/WebApp/bridge.js               ``versionName: "X.Y.Z-demo"``
    - android_html/.../bridge.js         ``versionName: "X.Y.Z-demo"``
    - ios/WolManager/WebView/Bridge.swift fallbacks ``?? "X.Y.Z"``

  Documentation / build helpers (cosmetic, kept in step as well):
    - README.md, Bedienungsanleitung.md, KNOWLEDGE.md, SECURITY.md,
      build.ps1, Wake-on-LAN Manager.spec, docs/android/html-app.md

The Xcode project (``ios/WolManager.xcodeproj/project.pbxproj``) is generated
from ``ios/project.yml`` — run ``xcodegen generate`` inside ``ios/`` (or use
``update_version.py``, which does it automatically).

Run directly (e.g. from build.ps1, build_html.ps1 or CI) — no arguments needed.
Use ``update_version.py X.Y.Z`` to bump the version everywhere at once.
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
    # ---- Documentation / build helpers: cosmetic ----
    "README.md": [
        (r"\*\*Version (\d+\.\d+\.\d+)([^\n]*)\*\*", r"**Version {version}\2**"),
    ],
    "Bedienungsanleitung.md": [
        (r"\*Version (\d+\.\d+\.\d+)([^\n]*)\*", r"*Version {version}\2*"),
    ],
    "KNOWLEDGE.md": [
        # Keep the column padding: only the version digits are replaced.
        (r"(\| \*\*version\*\*\s+\| )\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "SECURITY.md": [
        (r"- \*\*Version:\*\* (\d+\.\d+\.\d+)", r"- **Version:** {version}"),
    ],
    "build.ps1": [
        (r"(Version: )\d+\.\d+\.\d+", r"\g<1>{version}"),
        (r"(Manager v)\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "Wake-on-LAN Manager.spec": [
        (r"(Version )\d+\.\d+\.\d+", r"\g<1>{version}"),
    ],
    "docs/android/html-app.md": [
        (r"(`versionName )\d+\.\d+\.\d+(`)", r"\g<1>{version}\g<2>"),
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


def read_version() -> str:
    """Extract ``__version__ = "X.Y.Z"`` from the source file."""
    text = VERSION_SOURCE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']', text)
    if not match:
        raise SystemExit(f"ERROR: Could not find __version__ in {VERSION_SOURCE}")
    return match.group(1)


def update_file(path: Path, version: str) -> bool:
    """Apply version substitutions to *path*. Returns True if anything changed."""
    text = path.read_text(encoding="utf-8")
    changed = False
    # DOC_PATTERNS keys use '/' — Path.relative_to yields '\' on Windows, so
    # without this normalization every sub-directory file silently matched no
    # pattern and was reported as "already up to date" (2.3.5 drift).
    key = str(path.relative_to(ROOT)).replace("\\", "/")
    for pattern, replacement in DOC_PATTERNS.get(key, []):
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
    print(f"Source version: {version}")

    updated = []
    for filename in DOC_PATTERNS:
        path = ROOT / filename
        if not path.exists():
            print(f"  SKIP  {filename} (not found)")
            continue
        if update_file(path, version):
            updated.append(filename)
            print(f"  UPDATE {filename}")
        else:
            print(f"  OK    {filename} (already up to date)")

    if updated:
        print(f"\nUpdated {len(updated)} file(s) to version {version}.")
    else:
        print("\nAll docs already at version", version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
