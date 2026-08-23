# -*- mode: python ; coding: utf-8 -*-


# Wake-on-LAN Manager Version 2.0.0 - Modern UI Edition
# Generated on 2026-08-22

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.'), ('wol_app/locales/*.json', 'wol_app/locales'), ('wol_app/assets/icons/*.svg', 'wol_app/assets/icons')],
    hiddenimports=[
        'wol_app',
        'wol_app.__init__',
        'wol_app.config',
        'wol_app.crypto',
        'wol_app.device_dialog',
        'wol_app.log_dialog',
        'wol_app.main_window',
        'wol_app.network_scan_dialog',
        'wol_app.network_scanner',
        'wol_app.schedule_dialog',
        'wol_app.settings_dialog',
        'wol_app.translations',
        'wol_app.update_dialog',
        'wol_app.updater',
        'wol_app.utils',
        'wol_app.wol_engine',
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
    a.binaries,
    a.datas,
    [],
    name='Wake-on-LAN Manager',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
