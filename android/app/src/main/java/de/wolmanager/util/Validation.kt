package de.wolmanager.util

import java.util.regex.Pattern

/** Validierungsregeln — spiegeln settings_dialog/device_io der Windows-App. */
object Validation {

    private val MAC_RE = Pattern.compile("^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
    private val IPV4_RE =
        Pattern.compile("^((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\.){3}(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)$")
    private val HOSTNAME_RE =
        Pattern.compile("^[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?)*$")

    fun isValidMac(mac: String): Boolean = MAC_RE.matcher(mac.trim()).matches()

    fun isValidIpOrHostname(value: String): Boolean {
        val v = value.trim()
        if (v.isEmpty()) return true // IP ist optional
        return IPV4_RE.matcher(v).matches() || HOSTNAME_RE.matcher(v).matches()
    }

    fun isValidIpv4(value: String): Boolean = IPV4_RE.matcher(value.trim()).matches()

    fun isValidPort(port: Int): Boolean = port in 1..65535

    fun normalizeMac(mac: String): String = mac.trim().uppercase().replace("-", ":").replace(" ", ":")

    /** true, wenn die (bereits normalisierte) MAC bereits unter einer anderen Geräte-ID existiert. */
    fun macExists(mac: String, existing: Collection<String>, excludeId: String? = null): Boolean {
        val norm = normalizeMac(mac)
        return existing.any { normalizeMac(it) == norm }
    }
}
