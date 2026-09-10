"""Bump the application version EVERYWHERE — the one command to release a version.

The single source of truth is ``wol_app/__init__.py`` (``__version__``).
This tool sets the new version there and propagates it to every build file
and document (Android ``build.gradle.kts``, iOS ``project.yml``, ``setup.iss``,
WebApp fallbacks, docs, …) via ``update_docs_version.py``, then regenerates
the Xcode project with ``xcodegen generate`` when it is available.

Usage:
    python update_version.py 2.3.5          # bump everywhere
    python update_version.py --check        # verify sync without changing files

``--check`` exits with code 1 and lists every file whose version differs
from the source of truth (also used by tests/test_version_sync.py).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import update_docs_version as sync

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def set_source_version(version: str) -> bool:
    """Write ``__version__ = "X.Y.Z"`` into wol_app/__init__.py."""
    text = sync.VERSION_SOURCE.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'(__version__\s*=\s*["\'])\d+\.\d+\.\d+(["\'])',
        rf"\g<1>{version}\g<2>",
        text,
    )
    if count != 1:
        raise SystemExit(f"ERROR: Could not rewrite __version__ in {sync.VERSION_SOURCE}")
    if new_text != text:
        sync.VERSION_SOURCE.write_text(new_text, encoding="utf-8")
        return True
    return False


def check() -> list[str]:
    """Return a list of human-readable drift messages (empty == everything in sync)."""
    version = sync.read_version()
    drift: list[str] = []
    for filename, patterns in sync.DOC_PATTERNS.items():
        path = sync.ROOT / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, _replacement in patterns:
            for match in re.finditer(pattern, text):
                found = VERSION_RE.search(match.group(0))
                if found and found.group(0) != version:
                    drift.append(
                        f"{filename}: found {found.group(0)}, "
                        f"expected {version} (pattern {pattern!r})"
                    )
    return drift


def regenerate_xcodeproj() -> None:
    """Regenerate ios/WolManager.xcodeproj from ios/project.yml if xcodegen exists."""
    if shutil.which("xcodegen") is None:
        print("NOTE: xcodegen not found — run 'xcodegen generate' in ios/ manually.")
        return
    result = subprocess.run(
        ["xcodegen", "generate"], cwd=sync.ROOT / "ios", capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"WARNING: xcodegen failed:\n{result.stderr}")
    else:
        print("Xcode project regenerated (ios/WolManager.xcodeproj).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", nargs="?", help="New version, e.g. 2.3.5")
    parser.add_argument("--check", action="store_true",
                        help="Only verify that all files share the source version.")
    args = parser.parse_args(argv)

    if args.check:
        version = sync.read_version()
        drift = check()
        if drift:
            print(f"VERSION DRIFT vs. {sync.VERSION_SOURCE.relative_to(sync.ROOT)} "
                  f"({version}):")
            for line in drift:
                print(f"  MISMATCH {line}")
            print("\nFix with: python update_docs_version.py")
            return 1
        print(f"All files in sync at version {version}.")
        return 0

    if not args.version:
        parser.error("version required (or use --check)")
    assert args.version is not None
    if not VERSION_RE.fullmatch(args.version):
        parser.error(f"invalid version {args.version!r}, expected X.Y.Z")

    if set_source_version(args.version):
        print(f'Set __version__ = "{args.version}" in {sync.VERSION_SOURCE.name}')
    else:
        print(f'__version__ already "{args.version}"')

    sync.main()
    regenerate_xcodeproj()
    print(f"\nDone. Version {args.version} applied to all variants "
          f"(Windows, Ubuntu, Android, iOS).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
