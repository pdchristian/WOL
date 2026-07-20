import json

# Read existing de.json
with open("wol_app/locales/de.json", encoding="utf-8") as f:
    data = json.load(f)

# 73 missing keys with German translations
missing_de = {
    # Buttons
    "button.cancel": "Abbrechen",
    "button.shutdown_confirm": "Herunterfahren",
    # Common
    "common.cancel": "Abbrechen",
    # Device status
    "device.disabled": "Deaktiviert",
    "device.unknown": "Unbekannt",
    # Device dialog errors
    "device_dialog.error.invalid_name": "Ungültiger Gerätename",
    "device_dialog.error.invalid_password": "Ungültiges Passwort",
    "device_dialog.error.invalid_username": "Ungültiger Benutzername",
    "device_dialog.error.save_failed": "Gerät konnte nicht gespeichert werden",
    # Device manager sort
    "device_manager.sort.ip": "IP-Adresse",
    "device_manager.sort.mac": "MAC-Adresse",
    "device_manager.sort.name": "Name",
    "device_manager.sort.username": "Benutzername",
    # About dialog
    "dialog.about.title": "Über Wake-on-LAN Manager",
    "dialog.about.version": "Version:",
    "dialog.about.description": "Ein leistungsstärkes Tool zur Verwaltung von Geräten in Ihrem Netzwerk via Wake-on-LAN-Technologie.",
    "dialog.about.supports": "Unterstützt Magic Packets, Remote-Herunterfahren und automatische Statusüberwachung.",
    # Dialog buttons
    "dialog.button.close": "Schließen",
    # Confirm delete
    "dialog.confirm_delete.title": "Löschung bestätigen",
    "dialog.confirm_delete.message": "Möchten Sie das Gerät \"{name}\" wirklich löschen?",
    # Connection errors
    "dialog.connection_failed.title": "Verbindung fehlgeschlagen",
    "dialog.connection_failed.message": "Verbindung zu {name} unter {ip} fehlgeschlagen: {error}",
    "dialog.connection_timeout.title": "Verbindungszeitüberschreitung",
    "dialog.connection_timeout.message": "Verbindung zu {name} unter {ip}.timed out",
    "dialog.connection_error.title": "Verbindungsfehler",
    "dialog.connection_error.message": "Fehler bei der Verbindung zu {name} unter {ip}: {error}",
    # Device disabled
    "dialog.device_disabled.title": "Gerät deaktiviert",
    "dialog.device_disabled.message": "Das Gerät \"{name}\" ist derzeit deaktiviert.",
    # General error
    "dialog.error.title": "Fehler",
    "dialog.error": "Ein Fehler ist aufgetreten: {error}",
    # No devices / no IP
    "dialog.no_devices.title": "Keine Geräte",
    "dialog.no_devices.message": "Keine Geräte verfügbar. Bitte fügen Sie zuerst Geräte hinzu.",
    "dialog.no_ip.title": "Keine IP-Adresse",
    "dialog.no_ip.message": "Das Gerät \"{name}\" hat keine IP-Adresse konfiguriert.",
    # Select device prompts
    "dialog.select_device_ping.message": "Bitte wählen Sie ein Gerät zum Ping aus.",
    "dialog.select_device_shutdown.message": "Bitte wählen Sie ein Gerät zum Herunterfahren aus.",
    # Shutdown confirm dialog
    "dialog.shutdown_confirm.label1": "Sie sind dabei, das Gerät \"{name}\" herunterzufahren.",
    "dialog.shutdown_confirm.label2": "Sind Sie sicher, dass Sie fortfahren möchten?",
    "dialog.shutdown_confirm.label3": "Diese Aktion kann nicht rückgängig gemacht werden.",
    "dialog.shutdown_confirm.sharing_activated": "Bildschirmspiegeln wird vor dem Herunterfahren aktiviert",
    # Shutdown results
    "dialog.shutdown_successful.title": "Herunterfahren erfolgreich",
    "dialog.shutdown_successful.message": "Das Gerät \"{name}\" unter {ip} wurde erfolgreich heruntergefahren.",
    "dialog.shutdown_failed.title": "Herunterfahren fehlgeschlagen",
    "dialog.shutdown_failed.message": "Herunterfahren von {name} unter {ip} fehlgeschlagen: {error}",
    "dialog.shutdown_timeout.title": "Herunterfahren Zeitüberschreitung",
    "dialog.shutdown_timeout.message": "Herunterfahren von {name} unter {ip} timed out.",
    "dialog.shutdown_error.title": "Herunterfahren Fehler",
    "dialog.shutdown_error.message": "Fehler beim Herunterfahren von {name} unter {ip}: {error}",
    # Status result
    "dialog.status_result.title": "Status-Ergebnis ({status})",
    # Wake all
    "dialog.wake_all.title": "Alle Geräte aktivieren",
    "dialog.wake_all.message": "Möchten Sie wirklich alle {count} Geräte aktivieren?",
    "dialog.wake_all_complete.title": "Alle Geräte aktiviert",
    "dialog.wake_all_complete.success": "Magic Packets erfolgreich an {count} Gerät(e) gesendet.",
    "dialog.wake_all_complete.fail": "{count} Gerät(e) haben das Paket nicht erhalten.",
    # Status bar messages
    "status.ready": "Bereit",
    "status.checking": "Geräte werden überprüft...",
    "status.check_in_progress": "Statusüberprüfung läuft...",
    "status.check_complete": "Statusüberprüfung um {time} abgeschlossen",
    "status.deleting_connection": "Verbindung zu {name} wird gelöscht...",
    "status.device_not_found": "Gerät mit ID {device_id} nicht gefunden",
    "status.scheduled_shutdown_starting": "Geplantes Herunterfahren von {name} unter {ip} wird gestartet...",
    "status.scheduled_shutdown_progress": "{name} wird heruntergefahren...",
    "status.scheduled_shutdown_conn_fail": "Verbindung zu {name} fehlgeschlagen: {error}",
    "status.scheduled_shutdown_success": "{name} wurde erfolgreich heruntergefahren",
    "status.scheduled_shutdown_fail": "Herunterfahren von {name} fehlgeschlagen: {error}",
    "status.scheduled_shutdown_timeout": "Herunterfahren von {name} timed out",
    "status.scheduled_shutdown_error": "Fehler beim Herunterfahren von {name}: {error}",
    "status.shutdown_failed": "Herunterfahren von {name} fehlgeschlagen",
    "status.shutdown_success": "{name} wurde erfolgreich heruntergefahren",
    "status.shutting_down": "{name} wird heruntergefahren...",
    "status.shutting_down_remote": "Remote-Gerät {name} wird heruntergefahren...",
    "status.waking_device": "{device_name} wird geweckt...",
    # UI
    "ui.devices_group": "Geräte"
}

# Add missing keys
for key, value in missing_de.items():
    if key not in data:
        data[key] = value
        print(f"Added: {key}")

# Write back sorted
with open("wol_app/locales/de.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

print(f"\nTotal keys in de.json: {len(data)}")
print("Done!")
