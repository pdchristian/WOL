# -*- mode: python ; coding: utf-8 -*-


# Wake-on-LAN Manager Version 2.3.6 - Service Watch Edition
# macOS application bundle (Apple Silicon / arm64), unsigned

import os
import re

block_cipher = None

# Version aus der einzigen Quelle (wol_app/__init__.py) - nie hart verdrahten.
def _app_version():
    with open(os.path.join(SPECPATH, 'wol_app', '__init__.py'), encoding='utf-8') as fh:
        m = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', fh.read())
    return m.group(1) if m else '0.0.0'

APP_VERSION = _app_version()

# Nur die für den Freeze benötigten PyQt6-Module einbinden (kleineres Bundle).
qt_binaries = []
qt_datas = []
try:
    from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
    from PyInstaller import isolated

    @isolated.decorate
    def _pyqt6_deploy_files():
        import os
        from PyQt6.QtCore import QLibraryInfo
        from PyQt6.QtNetwork import QSslSocket
        base = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        plugins = [
            ("platforms", "libqcocoa.dylib"),
            ("styles", "libqmacstyle.dylib"),
            ("imageformats", "libqjpeg.dylib"),
            ("imageformats", "libqgif.dylib"),
            ("imageformats", "libqico.dylib"),
            ("iconengines", "libqsvgicon.dylib"),
            ("printsupport", "libcocoaprintersupport.dylib"),
        ]
        datas = [(os.path.join(base, d, f), os.path.join("PyQt6", "plugins", d))
                 for d, f in plugins]
        if QSslSocket.supportsEncryption():
            res = QLibraryInfo.path(QLibraryInfo.LibraryPath.DataPath)
            datas.append((os.path.join(res, "resources", "openssl.cnf"),
                          os.path.join("PyQt6", "resources")))
        return datas, base
    qt_datas, _qt_plugins_base = _pyqt6_deploy_files()
except Exception:
    qt_datas = []

# Host-Service-Payload: build_macos.sh baut dist/WOL Host Service VOR der App;
# die App kann ihn beim ersten Start ohne Download installieren. Fehlt das
# Bundle (Entwickler-Checkouts), wird ohne Payload gebaut - die App erkennt das
# (service_payload_path() -> None) und zeigt die Installations-Abfrage nicht.
_svc_datas = []
_svc = os.path.join(SPECPATH, 'dist', 'WOL Host Service')
if os.path.isdir(_svc):
    _svc_datas.append((_svc, 'WOL Host Service'))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=[
        ('icon_macos.icns', '.'),
        ('icon_modern.png', '.'),
        ('wol_app/locales/*.json', 'wol_app/locales'),
    ] + qt_datas + _svc_datas,
    hiddenimports=[
        'PyQt6.QtNetwork',
        'PyQt6.QtSvg',
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
        'wol_app.device_io',
        'wol_app.host_service_client',
        'wol_app.remote_desktop',
        'wol_app.scan_worker',
        'wol_app.schedule_runner',
        'wol_app.shutdown_flow',
        'wol_app.single_instance',
        'wol_app.modern_main_window',
        'wol_app.modern_theme',
        'wol_app.theme',
        'wol_app.views',
        'wol_app.views.devices_view',
        'wol_app.views.device_edit_dialog',
        'wol_app.views.logs_view',
        'wol_app.views.manage_view',
        'wol_app.views.schedule_edit_dialog',
        'wol_app.views.schedule_view',
        'wol_app.views.settings_view',
        'wol_app.views.shutdown_confirm_dialog',
        'wol_app.views.update_view',
        'wol_app.widgets',
        'wol_app.widgets.toggle_switch',
        # The installer reuses the service modules' path constants (LABEL,
        # INSTALL_DIR, ...); both import pamela/psutil only lazily.
        'wol_host_service_linux',
        'wol_host_service_macos',
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
    name='Wake-on-LAN Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name='Wake-on-LAN Manager',
)

app = BUNDLE(
    coll,
    name='Wake-on-LAN Manager.app',
    icon='icon_macos.icns',
    bundle_identifier='de.wolmanager',
    info_plist={
        'CFBundleName': 'Wake-on-LAN Manager',
        'CFBundleDisplayName': 'Wake-on-LAN Manager',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'LSMinimumSystemVersion': '11.0',
        'NSHumanReadableCopyright': 'Wake-on-LAN Manager',
        # Netzwerkzugriff erlauben (WOL-Broadcasts, Scans, Host-Service).
        'NSLocalNetworkUsageDescription': 'Wake-on-LAN Manager sendet Wake-on-LAN-Pakete und durchsucht das lokale Netzwerk nach Geräten.',
    },
)
