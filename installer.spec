# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Wake-on-LAN Manager installer helper.

This is NOT the user-facing installer anymore. The user-facing installer is
built by Inno Setup (see setup.iss). This small helper EXE only carries the
Python install logic (host-service SCM registration, .wol_app permission
fixes, user-data handling, reinstall cleanup) and is invoked by the Inno
Setup installer as a custom action via Exec.

File copying, shortcuts, registry (Add/Remove Programs) and the GUI are all
handled by Inno Setup, so this helper bundles only the Python code + wol_app.
"""

block_cipher = None

a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['winreg', 'wol_app', 'wol_app.utils'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_bin=True,
    name='installer',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
