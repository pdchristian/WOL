# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for the WOL Host Service.
Creates a standalone console .exe that can be registered as a Windows service.
"""

import os
import sys

# pywin32 ships as .pyd binaries + DLLs that PyInstaller's hiddenimports
# cannot always resolve. Bundle the whole win32 package and pywin32_system32
# explicitly so the service EXE is self-contained.
def _pywin32_binaries():
    # Use the interpreter that is actually running PyInstaller
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
        # psutil is imported lazily inside collect_metrics() (dashboard
        # metrics) and is therefore invisible to static analysis.
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    optimize=0,
)
pyz = PYZ(a.pure)

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
    # A console is REQUIRED: the EXE doubles as the CLI used for
    # --install/--uninstall/--start/--stop/--status. With console=False the
    # process has no stdout/stderr, so every print() is silently dropped and
    # those commands appear to "do nothing". When the SCM starts the service
    # (no args) stdout is redirected to the Windows Event Log, which is fine.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='WOL Host Service',
)
