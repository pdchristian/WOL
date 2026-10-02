"""Bump the application version EVERYWHERE — the one command to release a version.

The single source of truth is ``wol_app/__init__.py``, which carries two
release lines: ``__version__`` for the desktop variants (Windows, Ubuntu,
macOS) and ``MOBILE_VERSION`` for the Android/iOS WebView clients. They are
separate because a desktop-only feature must not bump the mobile release, and
vice versa. This tool sets one line and propagates it to its build file
and document (Android ``build.gradle.kts``, iOS ``project.yml``, ``setup.iss``,
WebApp fallbacks, docs, …) via ``update_docs_version.py``, then regenerates
the Xcode project with ``xcodegen generate`` when it is available.

Usage:
    python update_version.py 2.4.0              # bump the desktop line
    python update_version.py --mobile 2.3.8     # bump the Android/iOS line
    python update_version.py --check            # verify both lines

``--check`` exits with code 1 and lists every file whose version differs
from its line's source of truth (also used by tests/test_version_sync.py).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys

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


def set_mobile_version(version: str) -> bool:
    """Write ``MOBILE_VERSION = "X.Y.Z"`` into wol_app/__init__.py."""
    text = sync.VERSION_SOURCE.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'(MOBILE_VERSION\s*=\s*["\'])\d+\.\d+\.\d+(["\'])',
        rf"\g<1>{version}\g<2>",
        text,
    )
    if count != 1:
        raise SystemExit(
            f"ERROR: Could not rewrite MOBILE_VERSION in {sync.VERSION_SOURCE}")
    if new_text != text:
        sync.VERSION_SOURCE.write_text(new_text, encoding="utf-8")
        return True
    return False


def check() -> list[str]:
    """Return drift messages for both release lines (empty == everything in sync)."""
    drift: list[str] = []
    for patterns, version in ((sync.DOC_PATTERNS, sync.read_version()),
                              (sync.MOBILE_PATTERNS, sync.read_mobile_version())):
        for filename, file_patterns in patterns.items():
            path = sync.ROOT / filename
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern, _replacement in file_patterns:
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
    parser.add_argument("version", nargs="?",
                        help="New desktop version, e.g. 2.4.0")
    parser.add_argument("--mobile", metavar="X.Y.Z",
                        help="Bump the Android/iOS line (MOBILE_VERSION) instead.")
    parser.add_argument("--check", action="store_true",
                        help="Only verify that every file matches its line.")
    args = parser.parse_args(argv)

    if args.check:
        drift = check()
        if drift:
            print(f"VERSION DRIFT vs. {sync.VERSION_SOURCE.relative_to(sync.ROOT)} "
                  f"(desktop {sync.read_version()} / "
                  f"mobile {sync.read_mobile_version()}):")
            for line in drift:
                print(f"  MISMATCH {line}")
            print("\nFix with: python update_docs_version.py")
            return 1
        print(f"All files in sync — desktop {sync.read_version()}, "
              f"mobile {sync.read_mobile_version()}.")
        return 0

    if args.mobile and args.version:
        parser.error("--mobile takes the version as its value; "
                     "do not also pass a positional version")

    target = args.mobile if args.mobile else args.version
    if not target:
        parser.error("version required (or use --check)")
    assert target is not None
    if not VERSION_RE.fullmatch(target):
        parser.error(f"invalid version {target!r}, expected X.Y.Z")

    if args.mobile:
        if set_mobile_version(target):
            print(f'Set MOBILE_VERSION = "{target}" in {sync.VERSION_SOURCE.name}')
        else:
            print(f'MOBILE_VERSION already "{target}"')
    else:
        if set_source_version(target):
            print(f'Set __version__ = "{target}" in {sync.VERSION_SOURCE.name}')
        else:
            print(f'__version__ already "{target}"')

    sync.main()
    regenerate_xcodeproj()
    line = "Android/iOS" if args.mobile else "Windows, Ubuntu, macOS"
    print(f"\nDone. Version {target} applied to the {line} variant(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
