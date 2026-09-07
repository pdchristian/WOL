package de.wolmanager.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.util.UUID

/**
 * JSON-Repository (devices/schedules/logs/settings) unter [baseDir].
 * devices.json bleibt ein JSON-ARRAY (Desktop-Kompatibilität). Passwörter werden
 * vor dem Schreiben geleert und an [secure] delegiert.
 */
class Repo(
    private val baseDir: File,
    private val secure: SecureStore?,
) {
    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    data class Snapshot(
        val devices: List<Device> = emptyList(),
        val schedules: List<ScheduleDef> = emptyList(),
        val logs: List<LogEntry> = emptyList(),
        val settings: AppSettings = AppSettings(),
    )

    private val _snapshot = MutableStateFlow(load())
    val snapshot: StateFlow<Snapshot> = _snapshot.asStateFlow()

    private val devicesFile get() = File(baseDir, "devices.json")
    private val schedulesFile get() = File(baseDir, "schedules.json")
    private val logsFile get() = File(baseDir, "logs.json")
    private val settingsFile get() = File(baseDir, "settings.json")

    // ── Init ────────────────────────────────────────────────────────────────

    private fun load(): Snapshot {
        baseDir.mkdirs()
        val devices = (read(devicesFile) { json.decodeFromString<List<Device>>(it) } ?: emptyList())
            .map { migratePasswords(it) }
        val schedules = read(schedulesFile) { json.decodeFromString<List<ScheduleDef>>(it) } ?: emptyList()
        val logs = read(logsFile) { json.decodeFromString<List<LogEntry>>(it) } ?: emptyList()
        val settings = read(settingsFile) { json.decodeFromString<AppSettings>(it) } ?: AppSettings()
        return Snapshot(devices, schedules, logs, settings)
    }

    /** Einmalige Migration: Klartext-Passwort aus devices.json in den SecureStore ziehen. */
    private fun migratePasswords(d: Device): Device {
        if (d.password.isNotEmpty() && secure != null) {
            val existing = secure.getPassword(d.id)
            if (existing.isEmpty()) secure.setPassword(d.id, d.password)
            return d.copy(password = "")
        }
        return d
    }

    private inline fun <T> read(file: File, block: (String) -> T): T? = try {
        if (file.exists()) block(file.readText()) else null
    } catch (_: Exception) {
        null
    }

    private inline fun <reified T : Any> write(file: File, value: T, serializer: (T) -> String) {
        try {
            baseDir.mkdirs()
            val tmp = File(file.parentFile, file.name + ".tmp")
            tmp.writeText(serializer(value))
            // renameTo überschreibt auf Windows nicht → Ziel zuerst entfernen.
            if (!tmp.renameTo(file)) {
                runCatching { file.delete() }
                tmp.renameTo(file)
            }
        } catch (_: Exception) {
        }
    }

    // ── Geräte ──────────────────────────────────────────────────────────────

    private fun persistDevices(devices: List<Device>) {
        write(devicesFile, devices) { json.encodeToString(it) }
    }

    fun saveDevice(device: Device) {
        val pw = device.password
        val id = device.id.ifEmpty { UUID.randomUUID().toString() }
        val stored = device.copy(id = id, password = "")
        secure?.setPassword(id, pw)
        val cur = _snapshot.value.devices.toMutableList()
        val idx = cur.indexOfFirst { it.id == id }
        if (idx >= 0) cur[idx] = stored else cur.add(stored)
        persistDevices(cur)
        _snapshot.value = _snapshot.value.copy(devices = cur)
    }

    fun deleteDevice(id: String) {
        val cur = _snapshot.value.devices.filter { it.id != id }
        secure?.removePassword(id)
        persistDevices(cur)
        // Zugehörige Zeitpläne mit entfernen
        val sched = _snapshot.value.schedules.filter { it.deviceId != id }
        write(schedulesFile, sched) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(devices = cur, schedules = sched)
    }

    fun getPassword(id: String): String = secure?.getPassword(id) ?: ""

    fun deviceName(id: String): String? =
        _snapshot.value.devices.firstOrNull { it.id == id }?.name

    // ── Zeitpläne ───────────────────────────────────────────────────────────

    fun saveSchedule(schedule: ScheduleDef) {
        val id = schedule.id.ifEmpty { UUID.randomUUID().toString() }
        val stored = schedule.copy(id = id)
        val cur = _snapshot.value.schedules.toMutableList()
        val idx = cur.indexOfFirst { it.id == id }
        if (idx >= 0) cur[idx] = stored else cur.add(stored)
        write(schedulesFile, cur) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(schedules = cur)
    }

    fun deleteSchedule(id: String) {
        val cur = _snapshot.value.schedules.filter { it.id != id }
        write(schedulesFile, cur) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(schedules = cur)
    }

    fun updateScheduleLastRun(id: String, ts: Long) {
        val cur = _snapshot.value.schedules.map {
            if (it.id == id) it.copy(lastRun = ts) else it
        }
        write(schedulesFile, cur) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(schedules = cur)
    }

    // ── Protokoll ───────────────────────────────────────────────────────────

    fun log(device: String, level: String, msg: String) {
        val entry = LogEntry(System.currentTimeMillis(), device, level, msg)
        val max = _snapshot.value.settings.maxLogs.coerceAtLeast(10)
        val cur = (listOf(entry) + _snapshot.value.logs).take(max)
        write(logsFile, cur) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(logs = cur)
    }

    fun clearLogs() {
        write(logsFile, emptyList<LogEntry>()) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(logs = emptyList())
    }

    // ── Einstellungen ───────────────────────────────────────────────────────

    fun saveSettings(settings: AppSettings) {
        write(settingsFile, settings) { json.encodeToString(it) }
        _snapshot.value = _snapshot.value.copy(settings = settings)
    }

    fun resetSettings() = saveSettings(AppSettings())
}
