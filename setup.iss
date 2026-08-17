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
  #define AppVersion "1.7.0"
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
SetupIconFile=icon.ico
SetupMutex=WakeOnLANManagerSetupMutex
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Don't let Inno warn about the large host-service payload.
DisableWelcomePage=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "service_onedir"; Description: "Install WOL Host Service as a &folder (recommended)"; GroupDescription: "WOL Host Service (lets other PCs shut down this one remotely):"
Name: "service_onefile"; Description: "Install WOL Host Service as a s&ingle file"; GroupDescription: "WOL Host Service (lets other PCs shut down this one remotely):"; Flags: unchecked

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
Filename: "{app}\Wake-on-LAN Manager.exe"; WorkingDir: "{app}"; Description: "Launch Wake-on-LAN Manager"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
var
  ResultCode: Integer;

procedure InitializeWizard;
begin
  // Extract the installer helper to {tmp} so it can be run as a custom action.
  ExtractTemporaryFile('installer.exe');
end;

function NextPage: Boolean;
begin
  Result := True;
  // At most one host-service variant may be selected.
  if WizardIsTaskSelected('service_onedir') and WizardIsTaskSelected('service_onefile') then
  begin
    MsgBox('Please select at most one WOL Host Service variant.', mbError, MB_OK);
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Reinstall: clean up a previous installation before copying new files.
  if FileExists(ExpandConstant('{app}\Wake-on-LAN Manager.exe')) then
  begin
    if MsgBox('An existing installation of Wake-on-LAN Manager was found.' #13#13 'Remove existing device entries and settings?', mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--preinstall-cleanup --install-dir "' + ExpandConstant('{app}') + '" --remove-data',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    else
      Exec(ExpandConstant('{tmp}\installer.exe'),
           '--preinstall-cleanup --install-dir "' + ExpandConstant('{app}') + '"',
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
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // usUninstall runs BEFORE Inno deletes the installed files, so the
  // uninstall.exe helper (which lives in {app}) is still available here.
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('Remove the WOL Host Service (WOLHostService) and its firewall rule?', mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{app}\uninstall.exe'),
           '--remove-service', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    if MsgBox('Remove device entries and settings (~/.wol_app)?', mbConfirmation, MB_YESNO) = idYes then
      Exec(ExpandConstant('{app}\uninstall.exe'),
           '--cleanup-user-data', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Remove orphaned Add/Remove Programs keys from previous versions.
    Exec(ExpandConstant('{app}\uninstall.exe'),
           '--cleanup-orphaned-registry', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
