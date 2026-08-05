"""Synchronize the version string across documentation files.

Reads the single source of truth ``wol_app/__init__.py`` (``__version__``)
and updates every hardcoded version reference in the docs so they can never
drift out of sync again.

Supported files (path -> regex patterns with a single capture group):
  - README.md            ``**Version X.Y.Z - Edition**``
  - Bedienungsanleitung.md  ``*Version X.Y.Z | Wake-on-LAN Manager*``
  - KNOWLEDGE.md         ``| **version**         | X.Y.Z |``
  - SECURITY.md          ``- **Version:** X.Y.Z``

Run directly (e.g. from build.ps1 or CI) — no arguments needed.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_SOURCE = ROOT / "wol_app" / "__init__.py"

# file: list of (pattern, replacement) — each pattern has exactly one capture group
DOC_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "README.md": [
        (r"\*\*Version (\d+\.\d+\.\d+)([^\n]*)\*\*", r"**Version {version}\2**"),
    ],
    "Bedienungsanleitung.md": [
        (r"\*Version (\d+\.\d+\.\d+)([^\n]*)\*", r"*Version {version}\2*"),
    ],
    "KNOWLEDGE.md": [
        (r"\| \*\*version\*\*\s+\| (\d+\.\d+\.\d+) \|", r"| **version**         | {version} |"),
    ],
    "SECURITY.md": [
        (r"- \*\*Version:\*\* (\d+\.\d+\.\d+)", r"- **Version:** {version}"),
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
    for pattern, replacement in DOC_PATTERNS.get(path.name, []):
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
