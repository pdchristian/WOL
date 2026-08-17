# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for the WOL Host Service - ONEFILE variant (experimental).

Produces a single standalone .exe (no _internal folder, no COLLECT).
Built into a separate dist dir (dist_onefile) so the onedir variant
(wol_host_service.spec -> dist) stays untouched.

Usage:
    python -m PyInstaller wol_host_service_onefile.spec --distpath dist_onefile --noconfirm
"""

import os
import sys

# Same pywin32 bundling as the onedir spec.
def _pywin32_binaries():
    import site
    for sp in site.getsitepackages():
        win32_dir = os.path.join(sp, "win32")
        sys32_dir = os.path.join(sp, "pywin32_system32")
        bins = []
        if os.path.isdir(win32_dir):
            bins.append((win32_dir, "win32"))
        if os.path.isdir(sys32_dir):
            bins.append((sys32_dir, "pywin32_system32"))
        if bins:
            return bins
    return []


a = Analysis(
    ['wol_host_service.py'],
    pathex=[],
    binaries=_pywin32_binaries(),
    datas=[],
    hiddenimports=[
        'win32api',
        'win32con',
        'win32event',
        'win32service',
        'win32serviceutil',
        'servicemanager',
        'win32evtlogutil',
        'pywintypes',
        'pythoncom',
        'win32timezone',
        'win32wnet',
        'win32net',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    optimize=0,
)
pyz = PYZ(a.pure)

# ONEFILE: everything goes into the EXE, no COLLECT step.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WOL Host Service',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
