"""Wake-on-LAN Manager - Uninstaller

Removes all traces of the application:
- Installation files
- Registry entries (Add/Remove Programs)
- Start Menu shortcuts
- Desktop shortcut
- User configuration data (~/.wol_app/config.json)
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
APP_VERSION = "1.2.1"
APP_INSTALL_DIR_NAME = "WakeOnLAN"
APP_EXE_NAME = "Wake-on-LAN Manager.exe"
REG_KEY_NAME = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WakeOnLAN"


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def delete_registry_key(key_path):
    """Remove a registry key (Add/Remove Programs entry)."""
    try:
        parent_key, key_name = key_path.rsplit("\\", 1)
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, parent_key, 0,
                            winreg.KEY_WRITE) as key:
            if key_name in [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]:
                winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                print("  Removed from Add/Remove Programs.")
                return True
        print("  Registry key not found (already clean).")
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
        return True
    except Exception as e:
        print(f"  Warning: Could not remove shortcut: {e}")
        return False


def delete_directory(dir_path):
    """Delete a directory and all its contents."""
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"  Removed: {dir_path}")
            return True
        return True
    except Exception as e:
        print(f"  Warning: Could not remove directory: {e}")
        return False


def kill_app_process():
    """Force-kill the application if it's running."""
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", APP_EXE_NAME],
            capture_output=True, timeout=10
        )
        print("  Stopped running application.")
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


def remove_user_data():
    """Remove user configuration data from ~/.wol_app/."""
    try:
        wol_dir = Path.home() / ".wol_app"
        if wol_dir.exists():
            shutil.rmtree(wol_dir)
            print(f"  Removed user data: {wol_dir}")
            return True
        print("  No user data found (already clean).")
        return True
    except Exception as e:
        print(f"  Warning: Could not remove user data: {e}")
        return False


def disable_pin_verbs_for_exe():
    """Remove the 'Pin to Start' and 'Pin to Taskbar' shell verbs for .exe files."""
    base_key_path = r"SOFTWARE\Classes\exefile\shell"

    for verb_name in ["pintohome", "pinTostartScreen"]:
        verb_path = os.path.join(base_key_path, verb_name)
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, verb_path)
            print(f"  Removed '{verb_name}' context menu verb.")
        except FileNotFoundError:
            pass  # Already clean
        except Exception as e:
            print(f"  Warning: Could not remove '{verb_name}': {e}")


def get_install_dir():
    """Get the installation directory from registry or default path."""
    # Try to read from registry first
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY_NAME) as key:
            install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
            if install_location:
                return install_location
    except (FileNotFoundError, OSError):
        pass

    # Fallback to default
    return os.path.join(
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        APP_INSTALL_DIR_NAME
    )


def main():
    print("=" * 50)
    print(f"  {APP_NAME} - Uninstaller")
    print("=" * 50)
    print()

    # Check admin rights
    if not is_admin():
        print("ERROR: Administrator privileges required!")
        print("Please right-click and 'Run as Administrator'.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    install_dir = get_install_dir()

    # Confirm uninstallation (unless /S flag for silent mode)
    if "/S" not in sys.argv and "/s" not in sys.argv:
        print(f"This will remove {APP_NAME} and ALL associated data:")
        print(f"  - Installation files ({install_dir})")
        print(f"  - User configuration (~/.wol_app/)")
        print(f"  - Start Menu and Desktop shortcuts")
        print(f"  - Registry entries")
        print()
        response = input("Are you sure you want to continue? (y/n): ").lower()
        if response != 'y':
            print("Uninstallation cancelled.")
            return

    # Step 1: Kill running process
    print("\nStopping application...")
    kill_app_process()

    # Step 2: Remove shortcuts
    print("\nRemoving shortcuts...")
    start_menu_folder = os.path.join(
        os.environ["ProgramData"], "Microsoft", "Windows",
        "Start Menu", "Programs", APP_NAME
    )
    desktop_link = os.path.join(
        os.environ.get("PUBLIC", ""), "Desktop", f"{APP_NAME}.lnk"
    )
    delete_shortcut(desktop_link)
    delete_directory(start_menu_folder)

    # Step 3: Remove registry entry
    print("\nRemoving registry entries...")
    delete_registry_key(REG_KEY_NAME)

    # Step 3b: Remove context menu verbs for .exe files
    print("Removing context menu options...")
    disable_pin_verbs_for_exe()

    # Step 4: Remove user data (config, logs, etc.)
    print("\nRemoving user configuration data...")
    remove_user_data()

    # Step 5: Remove installation directory
    print("\nRemoving installation files...")
    import time
    time.sleep(1)  # Ensure file handles are released
    delete_directory(install_dir)

    # Summary
    print("\n" + "=" * 50)
    print("  Uninstallation Complete!")
    print("=" * 50)
    print(f"\nAll traces of {APP_NAME} have been removed.")
    print()

    if "/S" not in sys.argv and "/s" not in sys.argv:
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
