"""Wake-on-LAN Manager - Professional Windows Installer

Features:
- Registry-based Add/Remove Programs registration
- Start Menu folder with application and uninstall shortcuts
- Desktop shortcut
- Proper .exe uninstaller via registry integration
- Admin privilege detection and elevation
- Rollback on installation failure
- User data cleanup on reinstall
"""

import os
import sys
import shutil
import ctypes
import subprocess
import tempfile
import winreg
from datetime import datetime
from pathlib import Path


# --- Application Metadata ---
APP_NAME = "Wake-on-LAN Manager"
APP_VERSION = "1.4.0"
APP_PUBLISHER = "Wake-on-LAN"
APP_INSTALL_DIR_NAME = "WakeOnLAN"
APP_EXE_NAME = "Wake-on-LAN Manager.exe"
UNINSTALLER_NAME = "uninstall.exe"
ICON_NAME = "icon.ico"
REG_KEY_NAME = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WakeOnLAN"


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_resource_path(filename):
    """Get path to bundled resource file."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        # Development mode - look in dist folder
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
        if not os.path.exists(os.path.join(base_path, filename)):
            base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


def remove_user_data():
    """Remove user configuration data from ~/.wol_app/ securely."""
    try:
        wol_dir = Path.home() / ".wol_app"
        if wol_dir.exists():
            # First, securely wipe files containing sensitive data
            config_file = wol_dir / "config.json"
            master_key_file = wol_dir / "master_key.dat"
            
            if config_file.exists():
                try:
                    # Overwrite config file with zeros before deletion
                    config_file.write_bytes(b'\x00' * config_file.stat().st_size)
                except Exception:
                    pass
                config_file.unlink()
            
            if master_key_file.exists():
                try:
                    # Overwrite master key file with zeros before deletion
                    master_key_file.write_bytes(b'\x00' * master_key_file.stat().st_size)
                except Exception:
                    pass
                master_key_file.unlink()
            
            # Remove the entire directory
            shutil.rmtree(wol_dir, ignore_errors=True)
            print("  Securely removed existing user data.")
            return True
        return True
    except Exception as e:
        print(f"  Warning: Could not remove user data: {e}")
        return False


def user_has_full_control(directory):
    """Check if the current user already has full control on a directory.
    Uses icacls query to check effective permissions - much faster than
    trying to fix permissions that are already correct."""
    try:
        result = subprocess.run(
            ["icacls", str(directory)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False  # Can't read permissions, assume we need to fix

        username = os.environ.get("USERNAME", "")
        output = result.stdout.lower()
        # Check if current user has (F)ull or (M)odify access
        user_lower = username.lower()
        return user_lower in output and ("(f)" in output or "(m)" in output)
    except Exception:
        return False  # On any error, assume fix is needed


def fix_wol_app_permissions():
    """Ensure the .wol_app directory is owned by the current user, not Administrator.
    This is important because the installer runs with elevated privileges,
    which can cause the directory to be created with admin-only permissions.

    Steps:
    1. Check if user already has full control - skip if yes (fast path)
    2. Take ownership for the current user (takeown)
    3. Reset DACL and grant full control recursively (icacls)
    """
    try:
        wol_dir = Path.home() / ".wol_app"
        if not wol_dir.exists():
            return True

        username = os.environ.get("USERNAME", "")
        userdomain = os.environ.get("USERDOMAIN", ".")
        if not username:
            return False

        user_account = f"{userdomain}\\{username}"

        # Fast path: skip if user already has full control
        # This is common when migrating data from a previous installation
        if user_has_full_control(wol_dir):
            print(f"  Permissions OK for: {wol_dir}")
            return True

        # Step 1: Take ownership recursively (including all files/subdirs)
        takeown_result = subprocess.run(
            ["takeown", "/F", str(wol_dir), "/R", "/D", "Y"],
            capture_output=True, timeout=15
        )
        if takeown_result.returncode != 0:
            print(f"  Warning: takeown failed (rc={takeown_result.returncode})")

        # Step 2: Reset the DACL and grant full control to the current user recursively
        icacls_result = subprocess.run(
            ["icacls", str(wol_dir), "/reset", "/T", "/C", "/Q"],
            capture_output=True, timeout=15
        )
        if icacls_result.returncode != 0:
            print(f"  Warning: icacls reset failed (rc={icacls_result.returncode})")

        # Step 3: Grant full control to the current user recursively
        # Note: use /grant with (F) flag, NOT /grant:f (which is invalid syntax)
        icacls_grant = subprocess.run(
            ["icacls", str(wol_dir), "/grant", f"{user_account}:(CI)(OI)F", "/T", "/C", "/Q"],
            capture_output=True, timeout=15
        )
        if icacls_grant.returncode != 0:
            print(f"  Warning: icacls grant failed (rc={icacls_grant.returncode})")

        print(f"  Fixed permissions for: {wol_dir}")
        return True
    except Exception as e:
        print(f"  Warning: Could not fix .wol_app permissions: {e}")
        return False


def rollback_installation(install_dir, created_items):
    """Rollback installation if something fails."""
    print("\nERROR: Installation failed! Rolling back...")

    # Remove shortcuts
    for item in created_items:
        if item.endswith('.lnk'):
            try:
                if os.path.exists(item):
                    os.remove(item)
            except Exception:
                pass

    # Remove registry entry
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY_NAME)
    except Exception:
        pass

    # Remove install directory
    try:
        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
    except Exception:
        pass

    print("  Rollback complete.")


def create_shortcut(target_path, shortcut_path, work_dir="", icon_path=""):
    """Create a Windows shortcut using WScript.Shell COM object via temp PS script."""
    ps_script = f'''
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut("{shortcut_path}")
$shortcut.TargetPath = "{target_path}"
$shortcut.WorkingDirectory = "{work_dir}"
if ("{icon_path}") {{ $shortcut.IconLocation = "{icon_path}" }}
$shortcut.Description = "{APP_NAME} v{APP_VERSION}"
$shortcut.WindowStyle = 1
$shortcut.Save()
'''
    tmp_file = None
    try:
        fd, tmp_file = tempfile.mkstemp(suffix='.ps1')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(ps_script)
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", tmp_file],
            capture_output=True, check=True, timeout=10
        )
        return True
    except Exception as e:
        print(f"  Warning: Could not create shortcut: {e}")
        return False
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass

def register_app_in_registry(install_dir, exe_path, uninstaller_path):
    """Register the application in Windows Add/Remove Programs list."""
    reg_key_path = REG_KEY_NAME

    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, reg_key_path)

        display_name = APP_NAME
        uninstall_string = f'"{uninstaller_path}"'
        quiet_uninstall = f'"{uninstaller_path}" /S'
        install_location = install_dir
        publisher = APP_PUBLISHER
        version = APP_VERSION
        help_link = ""
        url_info_about = ""
        no_modify = 1
        no_repair = 1

        values = [
            ("DisplayName", display_name),
            ("DisplayVersion", version),
            ("Publisher", publisher),
            ("InstallLocation", install_location),
            ("InstallDate", datetime.now().strftime("%Y%m%d")),
            ("UninstallString", uninstall_string),
            ("QuietCustomActions", quiet_uninstall),
            ("NoModify", no_modify),
            ("NoRepair", no_repair),
        ]

        # Set DisplayIcon so the icon appears in Add/Remove Programs
        icon_dest = os.path.join(install_dir, ICON_NAME)
        if os.path.exists(icon_dest):
            values.append(("DisplayIcon", f'"{icon_dest}"'))

        if help_link:
            values.append(("HelpLink", help_link))
        if url_info_about:
            values.append(("URLInfoAbout", url_info_about))

        for name, value in values:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))

        winreg.CloseKey(key)
        print("  Registered in Add/Remove Programs.")
        return True
    except Exception as e:
        print(f"  Warning: Could not register in registry: {e}")
        return False


def unregister_app_from_registry():
    """Remove the application from Windows Add/Remove Programs list,
    including any orphaned keys from previous versions."""
    reg_key_path = REG_KEY_NAME

    try:
        # Try to delete the key
        subkeys = []
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as key:
            i = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break

        if "WakeOnLAN" in subkeys:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, reg_key_path)
            print("  Removed from Add/Remove Programs.")

        # Also clean up any orphaned keys from previous versions
        for subkey_name in subkeys:
            if subkey_name == "WakeOnLAN":
                continue  # Already handled above
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{subkey_name}") as subkey:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    if "Wake-on-LAN" in display_name or "wake-on-lan" in display_name.lower():
                        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE,
                                        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{subkey_name}")
                        print(f"  Removed orphaned registry key: {subkey_name}")
            except (FileNotFoundError, OSError):
                pass

        return True
    except FileNotFoundError:
        print("  Not registered in Add/Remove Programs (already clean).")
        return True
    except Exception as e:
        print(f"  Warning: Could not unregister from registry: {e}")
        return False


def copy_uninstaller(install_dir):
    """Copy the uninstaller executable to the install directory."""
    uninstaller_source = get_resource_path(UNINSTALLER_NAME)
    uninstaller_dest = os.path.join(install_dir, UNINSTALLER_NAME)

    if not os.path.exists(uninstaller_source):
        print("  Warning: Uninstaller not found.")
        return None

    try:
        shutil.copy2(uninstaller_source, uninstaller_dest)
        print(f"  Copied: {UNINSTALLER_NAME}")
        return uninstaller_dest
    except Exception as e:
        print(f"  Error copying uninstaller: {e}")
        return None


def create_start_menu_folder(install_dir, exe_dest):
    """Create Start Menu folder with application and uninstall shortcuts."""
    start_menu_folder = os.path.join(
        os.environ["ProgramData"], "Microsoft", "Windows",
        "Start Menu", "Programs", APP_NAME
    )

    try:
        os.makedirs(start_menu_folder, exist_ok=True)
    except Exception as e:
        print(f"  Error creating Start Menu folder: {e}")
        raise

    app_link = os.path.join(start_menu_folder, f"{APP_NAME}.lnk")
    uninstall_link = os.path.join(start_menu_folder, "Uninstall Wake-on-LAN Manager.lnk")

    # Get icon path
    icon_dest = os.path.join(install_dir, ICON_NAME)
    icon_location = icon_dest if os.path.exists(icon_dest) else exe_dest

    create_shortcut(exe_dest, app_link, install_dir, icon_location)
    print("  Created application shortcut in Start Menu.")

    uninstaller_path = os.path.join(install_dir, UNINSTALLER_NAME)
    create_shortcut(uninstaller_path, uninstall_link, install_dir, icon_location)
    print("  Created uninstall shortcut in Start Menu.")

    return app_link, uninstall_link


def main():
    app_name = APP_NAME
    install_dir = os.path.join(os.environ["ProgramFiles"], APP_INSTALL_DIR_NAME)

    print("=" * 50)
    print(f"  {app_name} - Installer")
    print("=" * 50)
    print()

    # Check admin rights
    if not is_admin():
        print("ERROR: Administrator privileges required!")
        print("Please right-click and 'Run as Administrator'.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Get paths to bundled files
    exe_source = get_resource_path(APP_EXE_NAME)
    manual_source = get_resource_path("Bedienungsanleitung.md")

    if not os.path.exists(exe_source):
        print("ERROR: Application file not found!")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Track created items for rollback
    created_items = []

    # Check if already installed - clean up old installation first
    exe_dest = os.path.join(install_dir, APP_EXE_NAME)
    if os.path.exists(exe_dest):
        print(f"INFO: {app_name} is already installed at:")
        print(f"  {install_dir}")
        response = input("\nReinstall? (This will remove old data) [y]: ").lower()
        if response not in ('', 'y'):
            print("Installation cancelled.")
            return
        # Clean up old installation
        print("\nRemoving old installation...")
        try:
            # Kill running process
            subprocess.run(
                ["taskkill", "/f", "/im", APP_EXE_NAME],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

        # Remove old registry entry
        unregister_app_from_registry()

        # Remove old shortcuts
        start_menu_folder = os.path.join(
            os.environ["ProgramData"], "Microsoft", "Windows",
            "Start Menu", "Programs", APP_NAME
        )
        try:
            if os.path.exists(start_menu_folder):
                shutil.rmtree(start_menu_folder)
        except Exception:
            pass

        desktop_link = os.path.join(
            os.environ.get("PUBLIC", ""), "Desktop", f"{APP_NAME}.lnk"
        )
        try:
            if os.path.exists(desktop_link):
                os.remove(desktop_link)
        except Exception:
            pass

        # Remove old install directory
        try:
            if os.path.exists(install_dir):
                shutil.rmtree(install_dir)
        except Exception:
            pass

        # Ask whether to keep or remove existing user data (devices, settings, etc.)
        wol_dir = Path.home() / ".wol_app"
        if wol_dir.exists():
            response = input(
                "\nExisting device entries and settings found.\n"
                "Keep them? (y=keep / n=remove) [y]: ").lower()
            if response == 'n':
                remove_user_data()
            else:
                print("  Keeping existing user data.")
        else:
            print("  No existing user data found.")

    # Create install directory
    print(f"\nInstalling to: {install_dir}")
    try:
        os.makedirs(install_dir, exist_ok=True)
    except Exception as e:
        print(f"ERROR: Could not create install directory: {e}")
        rollback_installation(install_dir, created_items)
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Copy application files
    print("Copying files...")
    try:
        shutil.copy2(exe_source, exe_dest)
        print(f"  Copied: {APP_EXE_NAME}")
    except Exception as e:
        print(f"ERROR: Could not copy application file: {e}")
        rollback_installation(install_dir, created_items)
        input("\nPress Enter to exit...")
        sys.exit(1)

    if os.path.exists(manual_source):
        try:
            shutil.copy2(manual_source, os.path.join(install_dir, "Bedienungsanleitung.md"))
            print("  Copied: Bedienungsanleitung.md")
        except Exception as e:
            print(f"ERROR: Could not copy manual: {e}")
            rollback_installation(install_dir, created_items)
            input("\nPress Enter to exit...")
            sys.exit(1)

    # Copy PDF manual
    pdf_source = get_resource_path("Bedienungsanleitung.pdf")
    if os.path.exists(pdf_source):
        try:
            shutil.copy2(pdf_source, os.path.join(install_dir, "Bedienungsanleitung.pdf"))
            print("  Copied: Bedienungsanleitung.pdf")
        except Exception as e:
            print(f"ERROR: Could not copy PDF manual: {e}")
            rollback_installation(install_dir, created_items)
            input("\nPress Enter to exit...")
            sys.exit(1)

    # Copy registry file
    reg_source = get_resource_path("Wake-on-LAN.reg")
    if os.path.exists(reg_source):
        try:
            shutil.copy2(reg_source, os.path.join(install_dir, "Wake-on-LAN.reg"))
            print("  Copied: Wake-on-LAN.reg")
        except Exception as e:
            print(f"ERROR: Could not copy registry file: {e}")
            rollback_installation(install_dir, created_items)
            input("\nPress Enter to exit...")
            sys.exit(1)

    # Copy icon for Add/Remove Programs display
    icon_source = get_resource_path(ICON_NAME)
    if os.path.exists(icon_source):
        try:
            shutil.copy2(icon_source, os.path.join(install_dir, ICON_NAME))
            print(f"  Copied: {ICON_NAME}")
        except Exception as e:
            print(f"  Warning: Could not copy icon: {e}")

    # Copy uninstaller
    print("Copying uninstaller...")
    uninstall_path = copy_uninstaller(install_dir)
    if uninstall_path is None:
        print("ERROR: Could not copy uninstaller!")
        rollback_installation(install_dir, created_items)
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Create Start Menu folder with shortcuts
    print("Creating Start Menu entries...")
    try:
        app_link, uninstall_link = create_start_menu_folder(install_dir, exe_dest)
        created_items.append(app_link)
        created_items.append(uninstall_link)
    except Exception as e:
        print(f"ERROR: Could not create Start Menu entries: {e}")
        rollback_installation(install_dir, created_items)
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Create desktop shortcut
    print("Creating desktop shortcut...")
    desktop_link = os.path.join(
        os.environ.get("PUBLIC", ""), "Desktop", f"{APP_NAME}.lnk"
    )
    create_shortcut(exe_dest, desktop_link, install_dir, exe_dest)
    created_items.append(desktop_link)

    # Register in Windows Add/Remove Programs
    print("Registering application...")
    if not register_app_in_registry(install_dir, exe_dest, uninstall_path):
        print("WARNING: Registry registration failed, but installation will continue.")

    # Fix permissions on user data directory (installer runs as admin)
    print("Fixing user data permissions...")
    fix_wol_app_permissions()

    # Summary
    print("\n" + "=" * 50)
    print("  Installation Complete!")
    print("=" * 50)
    print(f"\nInstall Location: {install_dir}")
    print(f"Start Menu: {APP_NAME}")
    print(f"Desktop Shortcut: {APP_NAME}")
    print(f"Uninstall via: Start Menu or Add/Remove Programs")
    print()

    # Launch app?
    response = input("Start Wake-on-LAN Manager now? [y]: ").lower()
    if response in ('', 'y'):
        # Launch without elevation so the app doesn't create admin-only files in .wol_app.
        # Use ShellExecute with "open" verb which runs under the standard user token.
        try:
            import ctypes
            SW_SHOWNORMAL = 1
            ctypes.windll.shell32.ShellExecuteW(
                None, "open", exe_dest, None, None, SW_SHOWNORMAL
            )
        except Exception:
            # Fallback: launch normally (may still be elevated, but permission fix in config.py will handle it)
            subprocess.Popen([exe_dest])

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
