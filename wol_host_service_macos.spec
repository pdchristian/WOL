# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for the WOL Host Service - macOS variant (onedir bundle).

Produces  dist/WOL Host Service/  ("WOL Host Service" binary + _internal/),
which packaging/macos/install_host_service.command copies as a whole to
/usr/local/lib/wol-host-service. The LaunchDaemon plist then points at
/usr/local/lib/wol-host-service/WOL Host Service --run.

Usage:
    .venv/bin/python -m PyInstaller wol_host_service_macos.spec --distpath dist --noconfirm
"""

a = Analysis(
    ['wol_host_service_macos.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # The macOS variant imports the shared Linux core as a plain module;
        # both files live in the project root, so PyInstaller bundles it.
        'wol_host_service_linux',
        'wol_host_service_macos',
        # Imported lazily inside functions -> invisible to static analysis:
        'pamela',   # PAM credential validation (service 'login')
        'psutil',   # dashboard metrics + watched processes
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='WOL Host Service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WOL Host Service',
)
