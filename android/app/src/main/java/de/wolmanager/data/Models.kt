package de.wolmanager.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * Geräte-Datenmodell — kompatibel zum Desktop-Format (devices.json).
 * Feld-Names: name, mac, ip, username, password, enabled.
 */
data class Device(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val mac: String,
    val ip: String = "",
    val username: String = "",
    val password: String = "",
    val enabled: Boolean = true,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("id", id)
        put("name", name)
        put("mac", mac)
        put("ip", ip)
        put("username", username)
        put("password", password)
        put("enabled", enabled)
    }

    companion object {
        fun fromJson(o: JSONObject): Device = Device(
            id = o.optString("id", UUID.randomUUID().toString()),
            name = o.optString("name", "?"),
            mac = o.optString("mac", ""),
            ip = o.optString("ip", ""),
            username = o.optString("username", ""),
            password = o.optString("password", ""),
            enabled = o.optBoolean("enabled", true),
        )
    }
}

enum class ConnState { UNKNOWN, ONLINE, OFFLINE }

/** Einstellungen — Port/Broadcast wie im Desktop-Client. */
data class AppPrefs(
    val servicePort: Int = 8765,
    val broadcastIp: String = "255.255.255.255",
    val wolPort: Int = 9,
    val statusCheckEnabled: Boolean = true,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("servicePort", servicePort)
        put("broadcastIp", broadcastIp)
        put("wolPort", wolPort)
        put("statusCheckEnabled", statusCheckEnabled)
    }

    companion object {
        fun fromJson(o: JSONObject): AppPrefs = AppPrefs(
            servicePort = o.optInt("servicePort", 8765),
            broadcastIp = o.optString("broadcastIp", "255.255.255.255"),
            wolPort = o.optInt("wolPort", 9),
            statusCheckEnabled = o.optBoolean("statusCheckEnabled", true),
        )
    }
}

/**
 * Persistenz im Dateisystem — devices.json im Desktop-Format, damit eine
 * Geräte-datei zwischen PC und Handy ausgetauscht werden kann.
 */
class DeviceStore(private val dir: File) {
    private val devicesFile = File(dir, "devices.json")
    private val prefsFile = File(dir, "prefs.json")

    fun loadDevices(): MutableList<Device> {
        if (!devicesFile.exists()) return mutableListOf()
        return try {
            val arr = JSONArray(devicesFile.readText(Charsets.UTF_8))
            (0 until arr.length()).map { Device.fromJson(arr.getJSONObject(it)) }.toMutableList()
        } catch (_: Exception) {
            mutableListOf()
        }
    }

    fun saveDevices(devices: List<Device>) {
        val arr = JSONArray()
        devices.forEach { arr.put(it.toJson()) }
        devicesFile.writeText(arr.toString(2), Charsets.UTF_8)
    }

    fun loadPrefs(): AppPrefs = try {
        if (prefsFile.exists()) AppPrefs.fromJson(JSONObject(prefsFile.readText(Charsets.UTF_8)))
        else AppPrefs()
    } catch (_: Exception) {
        AppPrefs()
    }

    fun savePrefs(prefs: AppPrefs) {
        prefsFile.writeText(prefs.toJson().toString(2), Charsets.UTF_8)
    }
}
