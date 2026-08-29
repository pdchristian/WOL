; ============================================================================
; Wake-on-LAN Manager - Inno Setup script
;
; This is the user-facing GUI installer. It replaces the old terminal-based
; PyInstaller installer (installer.py with console=True).
;
; Division of labor (wrapper approach):
;   - Inno Setup handles: GUI/wizard, file copying, Start Menu + Desktop
;     shortcuts, registry (Add/Remove Programs), launching the app, and
;     removing everything it installed on uninstall.
;   - The Python helpers (installer.exe / uninstall.exe) are invoked as
;     custom actions via Exec for what Inno cannot do well:
;       * WOL Host Service SCM registration/removal + firewall rule
;       * .wol_app permission fixes (takeown/icacls)
;       * user-data handling (secure wipe vs. keep)
;       * reinstall cleanup (old install, taskkill, orphaned registry keys)
;
; Build: iscc /DAppVersion=<version> setup.iss   (see build.ps1)
; ============================================================================

#ifndef AppVersion
  #define AppVersion "1.10.3"
#endif

[Setup]
; A stable AppId is required so Inno recognizes previous installs (reinstall).
AppId={{A7F3C21D-9B6E-4A7F-8C2D-1E5F6A7B8C9D}
AppName=Wake-on-LAN Manager
AppVersion={#AppVersion}
AppVerName=Wake-on-LAN Manager {#AppVersion}
AppPublisher=Wake-on-LAN
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName=Wake-on-LAN Manager
DefaultDirName={autopf}\WakeOnLAN
DefaultGroupName=Wake-on-LAN Manager
UninstallDisplayName=Wake-on-LAN Manager
UninstallDisplayIcon={app}\icon.ico
; Install for all users with elevation (matches the old installer).
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=Wake-on-LAN Manager WinInstaller
; Same icon as uninstall.exe: plain app icon. The admin shield is added by
; Windows automatically because the manifest (patched by
; patch_setup_manifest.ps1) declares requireAdministrator.
SetupIconFile=icon.ico
SetupMutex=WakeOnLANManagerSetupMutex
WizardStyle=modern
; Start directly in the OS language (no language picker). If the OS language
; is not one of the bundled languages, the FIRST listed language (English)
; is used.
ShowLanguageDialog=no
Compression=lzma2/max
SolidCompression=yes
; Don't let Inno warn about the large host-service payload.
DisableWelcomePage=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
en.task_desktopicon=Create a &desktop icon
en.task_group_icons=Additional icons:
en.task_service_onedir=Install WOL Host Service as a &folder (recommended)
en.task_service_onefile=Install WOL Host Service as a s&ingle file
en.task_service_none=Do &not install WOL Host Service
en.task_group_service=WOL Host Service (lets other PCs shut down this one remotely):
en.task_ui_modern=&Modern app (dark control-center layout with sidebar)
en.task_ui_classic=&Classic app (traditional window layout)
en.task_group_ui=Application design (both have identical features):
en.msg_reinstall_found=An existing installation of Wake-on-LAN Manager was found.
en.msg_keep_data=Keep existing device entries and settings?
en.msg_remove_service=Remove the WOL Host Service (WOLHostService) and its firewall rule?
en.msg_remove_data=Remove device entries and settings (~/_wol_app)?
en.run_launch=Launch Wake-on-LAN Manager
de.task_desktopicon=&Desktop-Verknüpfung erstellen
de.task_group_icons=Zusätzliche Symbole:
de.task_service_onedir=WOL Host Service als &Ordner installieren (empfohlen)
de.task_service_onefile=WOL Host Service als &einzelne Datei installieren
de.task_service_none=WOL Host Service &nicht installieren
de.task_group_service=WOL Host Service (ermöglicht anderen PCs, diesen PC remote herunterzufahren):
de.task_ui_modern=&Moderne App (dunkles Control-Center-Layout mit Seitenleiste)
de.task_ui_classic=&Klassische App (traditionelles Fenster-Layout)
de.task_group_ui=App-Design (beide Varianten haben identische Funktionen):
de.msg_reinstall_found=Eine bestehende Installation von Wake-on-LAN Manager wurde gefunden.
de.msg_keep_data=Vorhandene Geräte und Einstellungen behalten?
de.msg_remove_service=WOL Host Service (WOLHostService) und seine Firewall-Regel entfernen?
de.msg_remove_data=Geräte und Einstellungen (~/_wol_app) entfernen?
de.run_launch=Wake-on-LAN Manager starten
fr.task_desktopicon=Créer un raccourci sur le &bureau
fr.task_group_icons=Icônes supplémentaires :
fr.task_service_onedir=Installer WOL Host Service sous forme de &dossier (recommandé)
fr.task_service_onefile=Installer WOL Host Service en &un seul fichier
fr.task_service_none=Ne &pas installer le WOL Host Service
fr.task_group_service=WOL Host Service (permet à d'autres PC d'éteindre celui-ci à distance) :
fr.task_ui_modern=Application &moderne (centre de contrôle sombre avec barre latérale)
fr.task_ui_classic=Application &classique (disposition fenêtre traditionnelle)
fr.task_group_ui=Design de l'application (fonctionnalités identiques) :
fr.msg_reinstall_found=Une installation existante de Wake-on-LAN Manager a été trouvée.
fr.msg_keep_data=Conserver les entrées d'appareils et les paramètres existants ?
fr.msg_remove_service=Supprimer le WOL Host Service (WOLHostService) et sa règle de pare-feu ?
fr.msg_remove_data=Supprimer les entrées d'appareils et les paramètres (~/_wol_app) ?
fr.run_launch=Lancer Wake-on-LAN Manager
es.task_desktopicon=Crear un acceso directo en el &escritorio
es.task_group_icons=Iconos adicionales:
es.task_service_onedir=Instalar WOL Host Service como &carpeta (recomendado)
es.task_service_onefile=Instalar WOL Host Service como &un solo archivo
es.task_service_none=&No instalar WOL Host Service
es.task_group_service=WOL Host Service (permite a otros PC apagar este PC a distancia):
es.task_ui_modern=Aplicación &moderna (centro de control oscuro con barra lateral)
es.task_ui_classic=Aplicación &clásica (diseño de ventana tradicional)
es.task_group_ui=Diseño de la aplicación (ambas con funciones idénticas):
es.msg_reinstall_found=Se encontró una instalación existente de Wake-on-LAN Manager.
es.msg_keep_data=¿Conservar las entradas de dispositivos y la configuración existentes?
es.msg_remove_service=¿Eliminar el WOL Host Service (WOLHostService) y su regla de firewall?
es.msg_remove_data=¿Eliminar las entradas de dispositivos y la configuración (~/_wol_app)?
es.run_launch=Iniciar Wake-on-LAN Manager

[Tasks]
Name: "desktopicon"; Description: "{cm:task_desktopicon}"; GroupDescription: "{cm:task_group_icons}"; Flags: unchecked
; The three host-service options are mutually exclusive (radio-button
; behaviour): all carry the `exclusive` flag within the same group, so
; checking one auto-unchecks the others. The user may also uncheck all of
; them to skip the host service entirely (the "none" option).
Name: "service_onedir"; Description: "{cm:task_service_onedir}"; GroupDescription: "{cm:task_group_service}"; Flags: exclusive
Name: "service_onefile"; Description: "{cm:task_service_onefile}"; GroupDescription: "{cm:task_group_service}"; Flags: unchecked exclusive
Name: "service_none"; Description: "{cm:task_service_none}"; GroupDescription: "{cm:task_group_service}"; Flags: unchecked exclusive
; UI layout choice (radio group). Recorded in the registry
; (HKLM\SOFTWARE\Wake-on-LAN Manager\UiMode) and read by the app on first
; start. The user can still switch the layout later in the settings dialog.
Name: "ui_modern"; Description: "{cm:task_ui_modern}"; GroupDescription: "{cm:task_group_ui}"; Flags: exclusive
Name: "ui_classic"; Description: "{cm:task_ui_classic}"; GroupDescription: "{cm:task_group_ui}"; Flags: unchecked exclusive

[Files]
; Main application
Source: "dist\Wake-on-LAN Manager.exe"; DestDir: "{app}"; Flags: ignoreversion
; Documentation + misc
Source: "Bedienungsanleitung.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "Bedienungsanleitung.pdf"; DestDir: "{app}"; Flags: ignoreversion
Source: "Wake-on-LAN.reg"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; Uninstaller helper (kept in the install dir so the uninstall custom
; actions can invoke it).
Source: "dist\uninstall.exe"; DestDir: "{app}"; Flags: ignoreversion
; Installer helper (embedded only, extracted to {tmp} at runtime; NOT copied
; into the install dir).
Source: "dist\installer.exe"; DestDir: "{tmp}"; Flags: dontcopy ignoreversion
; WOL Host Service - onedir variant (exe + _internal folder)
Source: "dist\WOL Host Service\*"; DestDir: "{app}\WOL Host Service"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: service_onedir
; WOL Host Service - onefile variant (single exe)
Source: "dist_onefile\WOL Host Service.exe"; DestDir: "{app}"; Flags: ignoreversion; Tasks: service_onefile

[Icons]
Name: "{group}\Wake-on-LAN Manager"; Filename: "{app}\Wake-on-LAN Manager.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall Wake-on-LAN Manager"; Filename: "{app}\uninstall.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\Wake-on-LAN Manager"; Filename: "{app}\Wake-on-LAN Manager.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; Launch the app after install, as the ORIGINAL (non-elevated) user, so it
; does not create admin-owned files in .wol_app.
Filename: "{app}\Wake-on-LAN Manager.exe"; WorkingDir: "{app}"; Description: "{cm:run_launch}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
var
  ResultCode: Integer;

procedure InitializeWizard;
begin
  // Extract the installer helper to {tmp} so it can be run as a custom action.
  ExtractTemporaryFile('installer.exe');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Reinstall: clean up a previous installation before copying new files.
  if FileExists(ExpandConstant('{app}\Wake-on-LAN Manager.exe')) then
  begin
    // Ja = keep existing data, Nein = remove existing data.
    if MsgBox(ExpandConstant('{cm:msg_reinstall_found}') + #13#13 + ExpandConstant('{cm:msg_keep_data}'), mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--preinstall-cleanup --install-dir "' + ExpandConstant('{app}') + '"',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    else
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--preinstall-cleanup --install-dir "' + ExpandConstant('{app}') + '" --remove-data',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // The installer runs elevated; fix ownership of the user data directory.
    Exec(ExpandConstant('{tmp}\installer.exe'),
         '--fix-permissions', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Register + start the selected WOL Host Service variant (+ firewall rule).
    if WizardIsTaskSelected('service_onedir') then
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--install-service onedir --install-dir "' + ExpandConstant('{app}') + '"',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if WizardIsTaskSelected('service_onefile') then
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--install-service onefile --install-dir "' + ExpandConstant('{app}') + '"',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Record the chosen UI layout so the app can pick the right main window
    // on first start (an explicit user choice in the settings overrides it).
    if WizardIsTaskSelected('ui_classic') then
      RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Wake-on-LAN Manager', 'UiMode', 'classic')
    else
      RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Wake-on-LAN Manager', 'UiMode', 'modern');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // usUninstall runs BEFORE Inno deletes the installed files, so the
  // uninstall.exe helper (which lives in {app}) is still available here.
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox(ExpandConstant('{cm:msg_remove_service}'), mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{app}\uninstall.exe'),
           '--remove-service', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    if MsgBox(ExpandConstant('{cm:msg_remove_data}'), mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{app}\uninstall.exe'),
           '--cleanup-user-data', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Remove orphaned Add/Remove Programs keys from previous versions.
    Exec(ExpandConstant('{app}\uninstall.exe'),
           '--cleanup-orphaned-registry', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
