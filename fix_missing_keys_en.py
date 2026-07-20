import json

# Read existing en.json
with open("wol_app/locales/en.json", encoding="utf-8") as f:
    data = json.load(f)

# 73 missing keys with English translations
missing_en = {
    # Buttons
    "button.cancel": "Cancel",
    "button.shutdown_confirm": "Shutdown",
    # Common
    "common.cancel": "Cancel",
    # Device status
    "device.disabled": "Disabled",
    "device.unknown": "Unknown",
    # Device dialog errors
    "device_dialog.error.invalid_name": "Invalid device name",
    "device_dialog.error.invalid_password": "Invalid password",
    "device_dialog.error.invalid_username": "Invalid username",
    "device_dialog.error.save_failed": "Failed to save device",
    # Device manager sort
    "device_manager.sort.ip": "IP Address",
    "device_manager.sort.mac": "MAC Address",
    "device_manager.sort.name": "Name",
    "device_manager.sort.username": "Username",
    # About dialog
    "dialog.about.title": "About Wake-on-LAN Manager",
    "dialog.about.version": "Version:",
    "dialog.about.description": "A powerful tool for managing devices on your network via Wake-on-LAN technology.",
    "dialog.about.supports": "Supports magic packets, remote shutdown, and automatic status monitoring.",
    # Dialog buttons
    "dialog.button.close": "Close",
    # Confirm delete
    "dialog.confirm_delete.title": "Confirm Deletion",
    "dialog.confirm_delete.message": "Are you sure you want to delete the device \"{name}\"?",
    # Connection errors
    "dialog.connection_failed.title": "Connection Failed",
    "dialog.connection_failed.message": "Failed to connect to {name} at {ip}: {error}",
    "dialog.connection_timeout.title": "Connection Timeout",
    "dialog.connection_timeout.message": "Connection to {name} at {ip} timed out",
    "dialog.connection_error.title": "Connection Error",
    "dialog.connection_error.message": "Error connecting to {name} at {ip}: {error}",
    # Device disabled
    "dialog.device_disabled.title": "Device Disabled",
    "dialog.device_disabled.message": "The device \"{name}\" is currently disabled.",
    # General error
    "dialog.error.title": "Error",
    "dialog.error": "An error occurred: {error}",
    # No devices / no IP
    "dialog.no_devices.title": "No Devices",
    "dialog.no_devices.message": "No devices available. Please add devices first.",
    "dialog.no_ip.title": "No IP Address",
    "dialog.no_ip.message": "The device \"{name}\" has no IP address configured.",
    # Select device prompts
    "dialog.select_device_ping.message": "Please select a device to ping.",
    "dialog.select_device_shutdown.message": "Please select a device to shut down.",
    # Shutdown confirm dialog
    "dialog.shutdown_confirm.title": "Shutdown {name}",
    "dialog.shutdown_confirm.label1": "You are about to shut down the device \"{name}\".",
    "dialog.shutdown_confirm.label2": "Are you sure you want to continue?",
    "dialog.shutdown_confirm.label3": "This action cannot be undone.",
    "dialog.shutdown_confirm.sharing_activated": "Screen sharing will be activated before shutdown",
    # Shutdown results
    "dialog.shutdown_successful.title": "Shutdown Successful",
    "dialog.shutdown_successful.message": "The device \"{name}\" at {ip} has been successfully shut down.",
    "dialog.shutdown_failed.title": "Shutdown Failed",
    "dialog.shutdown_failed.message": "Failed to shut down {name} at {ip}: {error}",
    "dialog.shutdown_timeout.title": "Shutdown Timeout",
    "dialog.shutdown_timeout.message": "Shutdown of {name} at {ip} timed out.",
    "dialog.shutdown_error.title": "Shutdown Error",
    "dialog.shutdown_error.message": "Error shutting down {name} at {ip}: {error}",
    # Status result
    "dialog.status_result.title": "Status Result ({status})",
    # Wake all
    "dialog.wake_all.title": "Wake All Devices",
    "dialog.wake_all.message": "Are you sure you want to wake all {count} devices?",
    "dialog.wake_all_complete.title": "Wake All Complete",
    "dialog.wake_all_complete.success": "Successfully sent magic packets to {count} device(s).",
    "dialog.wake_all_complete.fail": "{count} device(s) failed to receive the packet.",
    # Status bar messages
    "status.ready": "Ready",
    "status.checking": "Checking devices...",
    "status.check_in_progress": "Status check in progress...",
    "status.check_complete": "Status check complete at {time}",
    "status.deleting_connection": "Deleting connection to {name}...",
    "status.device_not_found": "Device with ID {device_id} not found",
    "status.scheduled_shutdown_starting": "Starting scheduled shutdown of {name} at {ip}...",
    "status.scheduled_shutdown_progress": "Shutting down {name}...",
    "status.scheduled_shutdown_conn_fail": "Failed to connect to {name}: {error}",
    "status.scheduled_shutdown_success": "Successfully shut down {name}",
    "status.scheduled_shutdown_fail": "Shutdown of {name} failed: {error}",
    "status.scheduled_shutdown_timeout": "Shutdown of {name} timed out",
    "status.scheduled_shutdown_error": "Error during shutdown of {name}: {error}",
    "status.shutdown_failed": "Shutdown of {name} failed",
    "status.shutdown_success": "Successfully shut down {name}",
    "status.shutting_down": "Shutting down {name}...",
    "status.shutting_down_remote": "Shutting down remote device {name}...",
    "status.waking_device": "Waking up {device_name}...",
    # UI
    "ui.devices_group": "Devices"
}

# Add missing keys
for key, value in missing_en.items():
    if key not in data:
        data[key] = value
        print(f"Added: {key} -> {value}")
    else:
        print(f"Skip (exists): {key}")

# Write back sorted
with open("wol_app/locales/en.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

print(f"\nTotal keys in en.json: {len(data)}")
print("Done!")
