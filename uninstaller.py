"""Wake-on-LAN Manager - Uninstaller

Removes all traces of the application:
- Installation files
- Registry entries (Add/Remove Programs)
- Start Menu shortcuts
- Desktop shortcut
- User configuration data (~/.wol_app/)
"""

import os
import sys
import shutil
import ctypes
import subprocess
import winreg
from pathlib import Path

# --- Application Metadata ---
APP_NAME = "Wake-on-LAN Manager"
APP_VERSION = "1.3.0"
APP_INSTALL_DIR_NAME = "WakeOnLAN"
APP_EXE_NAME = "Wake-on-LAN Manager.exe"
REG_KEY_NAME = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WakeOnLAN"


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_user_profile_dir():
    """Get the actual user profile directory, even when running elevated as admin."""
    # Path.home() respects the original user context on Windows
    try:
        home = str(Path.home())
        if os.path.isdir(home):
            return home
    except Exception:
        pass

    # Fallback: USERPROFILE env var
    profile = os.environ.get("USERPROFILE", "")
    if profile and os.path.isdir(profile):
        return profile

    # Last resort
    return str(Path.home())


def get_install_dir():
    """Get the installation directory from registry or default path."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY_NAME) as key:
            install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
            if install_location and os.path.exists(install_location):
                return install_location
    except (FileNotFoundError, OSError):
        pass

    # Fallback to default path
    return os.path.join(
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        APP_INSTALL_DIR_NAME
    )


def kill_app_process():
    """Force-kill the application if it is running."""
    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", APP_EXE_NAME],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("  Stopped running application.")
        else:
            combined = (result.stderr or "") + (result.stdout or "")
            if "not found" in combined.lower() or "nicht gefunden" in combined.lower():
                print("  Application is not running.")
            else:
                print("  Warning: Could not stop application.")
        return True
    except subprocess.TimeoutExpired:
        print("  Warning: Could not stop application in time.")
        return False
    except FileNotFoundError:
        print("  Application is not running.")
        return True
    except Exception as e:
        print(f"  Warning: Error stopping application: {e}")
        return False


def delete_registry_key():
    """Remove the registry key (Add/Remove Programs entry)."""
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY_NAME)
        print("  Removed registry key.")
        return True
    except FileNotFoundError:
        print("  Registry key not found (already clean).")
        return True
    except Exception as e:
        print(f"  Warning: Could not remove registry key: {e}")
        return False


def delete_shortcut(shortcut_path):
    """Delete a shortcut file."""
    try:
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print(f"  Removed: {shortcut_path}")
        return True
    except Exception as e:
        print(f"  Warning: Could not remove shortcut: {e}")
        return False


def delete_directory(dir_path):
    """Delete a directory and all its contents."""
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
            if os.path.exists(dir_path):
                print(f"  Warning: Some files could not be removed from {dir_path}")
                return False
            print(f"  Removed: {dir_path}")
        return True
    except Exception as e:
        print(f"  Warning: Could not remove directory: {e}")
        return False


def secure_wipe_file(file_path):
    """Overwrite a file with zeros before deletion."""
    try:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            with open(file_path, "wb") as f:
                f.write(b"\x00" * size)
            os.remove(file_path)
    except Exception:
        pass


def cleanup_user_data(user_profile_dir):
    """Remove user-specific data: .wol_app folder and desktop shortcut."""
    wol_dir = os.path.join(user_profile_dir, ".wol_app")

    # Securely wipe sensitive files before deletion
    secure_wipe_file(os.path.join(wol_dir, "config.json"))
    secure_wipe_file(os.path.join(wol_dir, "master_key.dat"))

    # Remove .wol_app directory
    delete_directory(wol_dir)

    # Remove user desktop shortcut
    user_desktop_link = os.path.join(user_profile_dir, "Desktop", f"{APP_NAME}.lnk")
    delete_shortcut(user_desktop_link)


def cleanup_public_shortcuts():
    """Remove public desktop shortcut."""
    public_desktop = os.environ.get("PUBLIC", "C:\\Users\\Public")
    public_link = os.path.join(public_desktop, "Desktop", f"{APP_NAME}.lnk")
    delete_shortcut(public_link)


def cleanup_start_menu():
    """Remove Start Menu folder and all shortcuts inside."""
    # All Users Start Menu
    start_menu_folder = os.path.join(
        os.environ.get("ProgramData", ""),
        "Microsoft", "Windows",
        "Start Menu", "Programs", APP_NAME
    )
    delete_directory(start_menu_folder)

    # User-specific Start Menu
    user_profile = get_user_profile_dir()
    user_start_menu = os.path.join(
        user_profile, "AppData", "Roaming",
        "Microsoft", "Windows",
        "Start Menu", "Programs", APP_NAME
    )
    delete_directory(user_start_menu)


def cleanup_install_directory(install_dir):
    """Remove the installation directory."""
    if not os.path.exists(install_dir):
        print("  Install directory not found (already clean).")
        return True

    # Try direct removal first
    try:
        shutil.rmtree(install_dir, ignore_errors=True)
        if not os.path.exists(install_dir):
            print(f"  Removed: {install_dir}")
            return True
    except Exception:
        pass

    # If still exists, schedule delayed removal via PowerShell
    ps_command = (
        f"Start-Sleep -Seconds 2; "
        f"Remove-Item -LiteralPath '{install_dir}' -Recurse -Force -ErrorAction SilentlyContinue"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_command],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        )
        print(f"  Scheduled for removal: {install_dir}")
        return True
    except Exception as e:
        print(f"  Warning: Could not schedule cleanup: {e}")
        return False


def main():
    silent = "/S" in sys.argv or "/s" in sys.argv

    if not silent:
        print("=" * 50)
        print(f"  {APP_NAME} - Uninstaller")
        print("=" * 50)
        print()

    # Check admin rights
    if not is_admin():
        print("ERROR: Administrator privileges required!")
        print("Please right-click and Run as Administrator.")
        if not silent:
            input("\nPress Enter to exit...")
        sys.exit(1)

    install_dir = get_install_dir()
    user_profile_dir = get_user_profile_dir()

    # Confirm uninstallation (unless /S flag for silent mode)
    if not silent:
        print(f"This will remove {APP_NAME} and ALL associated data:")
        print(f"  - Installation files ({install_dir})")
        print(f"  - User configuration (~/.wol_app/)")
        print(f"  - Start Menu and Desktop shortcuts")
        print(f"  - Registry entries")
        print()
        response = input("Are you sure you want to continue? (y/n): ").lower()
        if response != "y":
            print("Uninstallation cancelled.")
            sys.exit(0)

        print("\nRemoving application...")

    # Step 1: Stop running application
    kill_app_process()

    # Step 2: Remove registry entry
    delete_registry_key()

    # Step 3: Remove Start Menu shortcuts
    cleanup_start_menu()

    # Step 4: Remove desktop shortcuts (public + user)
    cleanup_public_shortcuts()

    # Step 5: Remove user data (.wol_app)
    cleanup_user_data(user_profile_dir)

    # Step 6: Remove installation directory
    cleanup_install_directory(install_dir)

    if not silent:
        print("\n" + "=" * 50)
        print("  Uninstallation complete.")
        print("=" * 50)
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()