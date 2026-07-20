import json

# Read existing es.json
with open("wol_app/locales/es.json", encoding="utf-8") as f:
    data = json.load(f)

# 73 missing keys with Spanish translations
missing_es = {
    # Buttons
    "button.cancel": "Cancelar",
    "button.shutdown_confirm": "Apagar",
    # Common
    "common.cancel": "Cancelar",
    # Device status
    "device.disabled": "Desactivado",
    "device.unknown": "Desconocido",
    # Device dialog errors
    "device_dialog.error.invalid_name": "Nombre de dispositivo inválido",
    "device_dialog.error.invalid_password": "Contraseña inválida",
    "device_dialog.error.invalid_username": "Nombre de usuario inválido",
    "device_dialog.error.save_failed": "No se pudo guardar el dispositivo",
    # Device manager sort
    "device_manager.sort.ip": "Dirección IP",
    "device_manager.sort.mac": "Dirección MAC",
    "device_manager.sort.name": "Nombre",
    "device_manager.sort.username": "Nombre de usuario",
    # About dialog
    "dialog.about.title": "Acerca de Wake-on-LAN Manager",
    "dialog.about.version": "Versión:",
    "dialog.about.description": "Una herramienta poderosa para gestionar dispositivos en su red mediante tecnología Wake-on-LAN.",
    "dialog.about.supports": "Admite paquetes mágicos, apagado remoto y monitorización automática del estado.",
    # Dialog buttons
    "dialog.button.close": "Cerrar",
    # Confirm delete
    "dialog.confirm_delete.title": "Confirmar eliminación",
    "dialog.confirm_delete.message": "¿Está seguro de que desea eliminar el dispositivo \"{name}\"?",
    # Connection errors
    "dialog.connection_failed.title": "Error de conexión",
    "dialog.connection_failed.message": "No se pudo conectar a {name} en {ip}: {error}",
    "dialog.connection_timeout.title": "Tiempo de conexión agotado",
    "dialog.connection_timeout.message": "La conexión a {name} en {ip} ha expirado.",
    "dialog.connection_error.title": "Error de conexión",
    "dialog.connection_error.message": "Error al conectar con {name} en {ip}: {error}",
    # Device disabled
    "dialog.device_disabled.title": "Dispositivo desactivado",
    "dialog.device_disabled.message": "El dispositivo \"{name}\" está actualmente desactivado.",
    # General error
    "dialog.error.title": "Error",
    "dialog.error": "Ha ocurrido un error: {error}",
    # No devices / no IP
    "dialog.no_devices.title": "Sin dispositivos",
    "dialog.no_devices.message": "No hay dispositivos disponibles. Agregue dispositivos primero.",
    "dialog.no_ip.title": "Sin dirección IP",
    "dialog.no_ip.message": "El dispositivo \"{name}\" no tiene una dirección IP configurada.",
    # Select device prompts
    "dialog.select_device_ping.message": "Seleccione un dispositivo para hacer ping.",
    "dialog.select_device_shutdown.message": "Seleccione un dispositivo para apagar.",
    # Shutdown confirm dialog
    "dialog.shutdown_confirm.label1": "Está a punto de apagar el dispositivo \"{name}\".",
    "dialog.shutdown_confirm.label2": "¿Está seguro de que desea continuar?",
    "dialog.shutdown_confirm.label3": "Esta acción no se puede deshacer.",
    "dialog.shutdown_confirm.sharing_activated": "El compartir pantalla se activará antes del apagado",
    # Shutdown results
    "dialog.shutdown_successful.title": "Apagado exitoso",
    "dialog.shutdown_successful.message": "El dispositivo \"{name}\" en {ip} se ha apagado correctamente.",
    "dialog.shutdown_failed.title": "Error al apagar",
    "dialog.shutdown_failed.message": "No se pudo apagar {name} en {ip}: {error}",
    "dialog.shutdown_timeout.title": "Tiempo de apagado agotado",
    "dialog.shutdown_timeout.message": "El apagado de {name} en {ip} ha expirado.",
    "dialog.shutdown_error.title": "Error de apagado",
    "dialog.shutdown_error.message": "Error al apagar {name} en {ip}: {error}",
    # Status result
    "dialog.status_result.title": "Resultado del estado ({status})",
    # Wake all
    "dialog.wake_all.title": "Activar todos los dispositivos",
    "dialog.wake_all.message": "¿Está seguro de que desea activar los {count} dispositivos?",
    "dialog.wake_all_complete.title": "Activación completada",
    "dialog.wake_all_complete.success": "Paquetes mágicos enviados a {count} dispositivo(s).",
    "dialog.wake_all_complete.fail": "{count} dispositivo(s) no recibieron el paquete.",
    # Status bar messages
    "status.ready": "Listo",
    "status.checking": "Comprobando dispositivos...",
    "status.check_in_progress": "Comprobación de estado en curso...",
    "status.check_complete": "Comprobación de estado completada a las {time}",
    "status.deleting_connection": "Eliminando conexión con {name}...",
    "status.device_not_found": "Dispositivo con ID {device_id} no encontrado",
    "status.scheduled_shutdown_starting": "Iniciando apagado programado de {name} en {ip}...",
    "status.scheduled_shutdown_progress": "Apagando {name}...",
    "status.scheduled_shutdown_conn_fail": "No se pudo conectar a {name}: {error}",
    "status.scheduled_shutdown_success": "{name} apagado correctamente",
    "status.scheduled_shutdown_fail": "Error al apagar {name}: {error}",
    "status.scheduled_shutdown_timeout": "Tiempo de apagado de {name} agotado",
    "status.scheduled_shutdown_error": "Error al apagar {name}: {error}",
    "status.shutdown_failed": "Error al apagar {name}",
    "status.shutdown_success": "{name} apagado correctamente",
    "status.shutting_down": "Apagando {name}...",
    "status.shutting_down_remote": "Apagando dispositivo remoto {name}...",
    "status.waking_device": "Activando {device_name}...",
    # UI
    "ui.devices_group": "Dispositivos"
}

# Add missing keys
for key, value in missing_es.items():
    if key not in data:
        data[key] = value
        print(f"Added: {key}")

# Write back sorted
with open("wol_app/locales/es.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
    f.write("\n")

print(f"\nTotal keys in es.json: {len(data)}")
print("Done!")
