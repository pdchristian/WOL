package de.wolmanager.net

import java.net.Inet4Address
import java.net.InetAddress

/**
 * Resolves a device address (IPv4 literal or host name) to IPv4 addresses.
 *
 * Mirrors `wol_app/utils.resolve_ipv4_all` of the Windows app. Two reasons this
 * is required for host names such as `blade-18.fritz.box`:
 *
 *  1. The WOL Host Service listens on IPv4 only (`0.0.0.0:8765`). A plain
 *     `InetSocketAddress(name, port)` resolves the name to a SINGLE address —
 *     and Android/Java prefer the AAAA record when the DNS server (e.g. a
 *     Fritz!Box) also publishes IPv6. The connect then targets `[ipv6]:8765`,
 *     nothing listens there, and an online device is reported offline.
 *  2. A name can carry several A records (a stale DHCP lease next to the
 *     current one) and the resolver order is not deterministic, so every
 *     candidate has to be probed rather than trusting the first.
 *
 * IPv4 literals pass through unchanged; unresolvable values yield an empty list.
 */
object Ipv4Resolver {

    /** Every IPv4 address [value] resolves to (deduplicated). IPv4 literals pass through. */
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

    /** True for a dotted-quad IPv4 literal (0-255 per octet, no leading junk). */
    fun isIpv4Literal(value: String): Boolean {
        val parts = value.trim().split(".")
        if (parts.size != 4) return false
        return parts.all { p ->
            p.isNotEmpty() && p.length <= 3 && p.all { it.isDigit() } &&
                (p.toIntOrNull() ?: -1) in 0..255
        }
    }
}
