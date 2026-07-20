import json

# Read existing fr.json
with open("wol_app/locales/fr.json", encoding="utf-8") as f:
    data = json.load(f)

# 73 missing keys with French translations
missing_fr = {
    # Buttons
    "button.cancel": "Annuler",
    "button.shutdown_confirm": "Arrêter",
    # Common
    "common.cancel": "Annuler",
    # Device status
    "device.disabled": "Désactivé",
    "device.unknown": "Inconnu",
    # Device dialog errors
    "device_dialog.error.invalid_name": "Nom d'appareil invalide",
    "device_dialog.error.invalid_password": "Mot de passe invalide",
    "device_dialog.error.invalid_username": "Nom d'utilisateur invalide",
    "device_dialog.error.save_failed": "Impossible d'enregistrer l'appareil",
    # Device manager sort
    "device_manager.sort.ip": "Adresse IP",
    "device_manager.sort.mac": "Adresse MAC",
    "device_manager.sort.name": "Nom",
    "device_manager.sort.username": "Nom d'utilisateur",
    # About dialog
    "dialog.about.title": "À propos de Wake-on-LAN Manager",
    "dialog.about.version": "Version :",
    "dialog.about.description": "Un outil puissant pour gérer les appareils de votre réseau via la technologie Wake-on-LAN.",
    "dialog.about.supports": "Prend en charge les paquets magiques, l'arrêt à distance et la surveillance automatique de l'état.",
    # Dialog buttons
    "dialog.button.close": "Fermer",
    # Confirm delete
    "dialog.confirm_delete.title": "Confirmer la suppression",
    "dialog.confirm_delete.message": "Êtes-vous sûr de vouloir supprimer l'appareil \"{name}\" ?",
    # Connection errors
    "dialog.connection_failed.title": "Échec de la connexion",
    "dialog.connection_failed.message": "Impossible de se connecter à {name} sur {ip} : {error}",
    "dialog.connection_timeout.title": "Délai d'attente dépassé",
    "dialog.connection_timeout.message": "La connexion à {name} sur {ip} a expiré.",
    "dialog.connection_error.title": "Erreur de connexion",
    "dialog.connection_error.message": "Erreur lors de la connexion à {name} sur {ip} : {error}",
    # Device disabled
    "dialog.device_disabled.title": "Appareil désactivé",
    "dialog.device_disabled.message": "L'appareil \"{name}\" est actuellement désactivé.",
    # General error
    "dialog.error.title": "Erreur",
    "dialog.error": "Une erreur s'est produite : {error}",
    # No devices / no IP
    "dialog.no_devices.title": "Aucun appareil",
    "dialog.no_devices.message": "Aucun appareil disponible. Veuillez d'abord ajouter des appareils.",
    "dialog.no_ip.title": "Aucune adresse IP",
    "dialog.no_ip.message": "L'appareil \"{name}\" n'a pas d'adresse IP configurée.",
    # Select device prompts
    "dialog.select_device_ping.message": "Veuillez sélectionner un appareil à pinguer.",
    "dialog.select_device_shutdown.message": "Veuillez sélectionner un appareil à arrêter.",
    # Shutdown confirm dialog
    "dialog.shutdown_confirm.label1": "Vous êtes sur le point d'arrêter l'appareil \"{name}\".",
    "dialog.shutdown_confirm.label2": "Êtes-vous sûr de vouloir continuer ?",
    "dialog.shutdown_confirm.label3": "Cette action est irréversible.",
    "dialog.shutdown_confirm.sharing_activated": "Le partage d'écran sera activé avant l'arrêt",
    # Shutdown results
    "dialog.shutdown_successful.title": "Arrêt réussi",
    "dialog.shutdown_successful.message": "L'appareil \"{name}\" sur {ip} a été arrêté avec succès.",
    "dialog.shutdown_failed.title": "Échec de l'arrêt",
    "dialog.shutdown_failed.message": "Échec de l'arrêt de {name} sur {ip} : {error}",
    "dialog.shutdown_timeout.title": "Délai d'arrêt dépassé",
    "dialog.shutdown_timeout.message": "L'arrêt de {name} sur {ip} a expiré.",
    "dialog.shutdown_error.title": "Erreur d'arrêt",
    "dialog.shutdown_error.message": "Erreur lors de l'arrêt de {name} sur {ip} : {error}",
    # Status result
    "dialog.status_result.title": "Résultat de l'état ({status})",
    # Wake all
    "dialog.wake_all.title": "Réveiller tous les appareils",
    "dialog.wake_all.message": "Êtes-vous sûr de vouloir réveiller tous les {count} appareils ?",
    "dialog.wake_all_complete.title": "Réveil terminé",
    "dialog.wake_all_complete.success": "Paquets magiques envoyés à {count} appareil(s).",
    "dialog.wake_all_complete.fail": "{count} appareil(s) n'ont pas reçu le paquet.",
    # Status bar messages
    "status.ready": "Prêt",
    "status.checking": "Vérification des appareils...",
    "status.check_in_progress": "Vérification de l'état en cours...",
    "status.check_complete": "Vérification de l'état terminée à {time}",
    "status.deleting_connection": "Suppression de la connexion à {name}...",
    "status.device_not_found": "Appareil avec l'ID {device_id} non trouvé",
    "status.scheduled_shutdown_starting": "Démarrage de l'arrêt programmé de {name} sur {ip}...",
    "status.scheduled_shutdown_progress": "Arrêt de {name}...",
    "status.scheduled_shutdown_conn_fail": "Échec de la connexion à {name} : {error}",
    "status.scheduled_shutdown_success": "{name} arrêté avec succès",
    "status.scheduled_shutdown_fail": "Échec de l'arrêt de {name} : {error}",
    "status.scheduled_shutdown_timeout": "Délai d'arrêt de {name} dépassé",
    "status.scheduled_shutdown_error": "Erreur lors de l'arrêt de {name} : {error}",
    "status.shutdown_failed": "Échec de l'arrêt de {name}",
    "status.shutdown_success": "{name} arrêté avec succès",
    "status.shutting_down": "Arrêt de {name}...",
    "status.shutting_down_remote": "Arrêt de l'appareil distant {name}...",
    "status.waking_device": "Réveil de {device_name}...",
    # UI
    "ui.devices_group": "Appareils"
}

# Add missing keys
for key, value in missing_fr.items():
    if key not in data:
        data[key] = value
        print(f"Added: {key}")

# Write back sorted
with open("wol_app/locales/fr.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

print(f"\nTotal keys in fr.json: {len(data)}")
print("Done!")
