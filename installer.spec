# -*- mode: python ; coding: utf-8 -*-
import os

"""
PyInstaller spec for Wake-on-LAN Manager Installer.
Bundles the app executable, manual, and uninstaller into a single installer .exe.
"""

block_cipher = None

# Determine base directory (spec file location)
SPEC_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()

a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(SPEC_DIR, 'dist', 'Wake-on-LAN Manager.exe'), '.'),
        (os.path.join(SPEC_DIR, 'dist', 'uninstall.exe'), '.'),
        ('Bedienungsanleitung.md', '.'),
        ('icon.ico', '.'),
    ],
    hiddenimports=['winreg'],
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
    name='Wake-on-LAN Manager Installer',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
