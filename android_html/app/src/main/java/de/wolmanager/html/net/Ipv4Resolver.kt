package de.wolmanager.html.net

import java.net.Inet4Address
import java.net.InetAddress

/**
 * Host name → IPv4 resolution for the IPv4-only Host Service.
 *
 * Rationale: the WOL Host Service listens on 0.0.0.0:8765 (IPv4 only). A
 * plain `Socket().connect(hostname)` lets the OS resolver pick any record,
 * and on dual-stack networks it may prefer AAAA → connection refused →
 * device falsely shown offline. Likewise a name may have several A records
 * (stale DHCP lease + current address) in non-deterministic order, so every
 * IPv4 candidate must be tried. Mirrors wol_app/utils.resolve_ipv4_all.
 */
object Ipv4Resolver {

    /** All IPv4 addresses [value] resolves to (literal IPv4 → itself). */
    fun resolveAll(value: String): List<String> {
        val v = value.trim()
        if (v.isEmpty()) return emptyList()
        if (isIpv4Literal(v)) return listOf(v)
        return try {
            InetAddress.getAllByName(v)
                .filterIsInstance<Inet4Address>()
                .mapNotNull { it.hostAddress }
                .distinct()
        } catch (_: Exception) {
            emptyList()
        }
    }

    /** True for dotted-quad IPv4 literals (0.0.0.0 … 255.255.255.255). */
    fun isIpv4Literal(value: String): Boolean {
        val parts = value.trim().split(".")
        if (parts.size != 4) return false
        return parts.all { p ->
            p.isNotEmpty() && p.length <= 3 && p.all { it.isDigit() } &&
                (p.toIntOrNull() ?: -1) in 0..255
        }
    }
}
