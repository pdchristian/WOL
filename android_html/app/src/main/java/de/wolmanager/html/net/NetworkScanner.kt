package de.wolmanager.html.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.NetworkCapabilities
import de.wolmanager.html.data.DiscoveredHost
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketException

/**
 * Netzwerk-Scan ohne Root: ICMP/ARP stehen Android nicht zur Verfügung, daher
 * TCP-Port-Sweep über alle aktiven /24-Netze. Ein Host gilt als gefunden, wenn einer
 * der SCAN_PORTS erreichbar antwortet. Hostname via Reverse-DNS, MAC nicht ermittelbar.
 */
class NetworkScanner(private val context: Context) {

    data class Iface(
        val name: String,
        val ip: String,
        val prefix: Int,
        val dns: String,
        var checked: Boolean = true,
    )

    sealed interface ScanEvent {
        data class Progress(val done: Int, val total: Int, val current: String) : ScanEvent
        data class Found(val host: DiscoveredHost) : ScanEvent
        data class Done(val count: Int) : ScanEvent
    }

    /** Liefert alle aktiven IPv4-/24-Netze (Loopback/APIPA ausgeschlossen). */
    fun activeInterfaces(): List<Iface> {
        val result = LinkedHashMap<String, Iface>()
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return emptyList()
        val nets = cm.allNetworks
        for (n in nets) {
            val caps = cm.getNetworkCapabilities(n) ?: continue
            if (!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) continue
            val link: LinkProperties = cm.getLinkProperties(n) ?: continue
            val dns = link.dnsServers.firstOrNull()?.hostAddress ?: ""
            for (addr in link.linkAddresses) {
                val inet = addr.address
                if (inet is Inet4Address && !inet.isLoopbackAddress) {
                    val ip = inet.hostAddress ?: continue
                    if (ip.startsWith("169.254.")) continue
                    val prefix = addr.prefixLength
                    result.putIfAbsent(ip, Iface(link.interfaceName ?: "?", ip, if (prefix in 8..30) prefix else 24, dns))
                }
            }
        }
        if (result.isEmpty()) {
            // Fallback: alle NICs direkt lesen
            try {
                for (ni in NetworkInterface.getNetworkInterfaces()) {
                    if (!ni.isUp || ni.isLoopback) continue
                    for (ia in ni.inetAddresses) {
                        if (ia is Inet4Address && !ia.isLoopbackAddress && !ia.hostAddress.startsWith("169.254.")) {
                            result.putIfAbsent(ia.hostAddress, Iface(ni.name, ia.hostAddress, 24, ""))
                        }
                    }
                }
            } catch (_: SocketException) {
            }
        }
        return result.values.toList()
    }

    /** Host-Adressen eines /24 (bzw. prefix-korrekt) Netzes, ohne Netzwerk-/Broadcast-Adresse. */
    private fun hostAddresses(base: String, prefix: Int): List<String> {
        val parts = base.split(".").map { it.toIntOrNull() ?: 0 }
        if (parts.size != 4) return emptyList()
        val network = (parts[0].toLong() shl 24) or (parts[1].toLong() shl 16) or
            (parts[2].toLong() shl 8) or parts[3].toLong()
        val mask = if (prefix >= 32) -1L else (-1L shl (32 - prefix)) and 0xFFFFFFFFL
        val netStart = network and mask
        val hostCount = (1L shl (32 - prefix)).toInt()
        if (hostCount > 1024) return emptyList() // sehr große Netze überspringen
        val list = ArrayList<String>()
        for (i in 1 until hostCount - 1) {
            val addr = netStart + i
            list.add(
                "${(addr shr 24) and 0xFF}.${(addr shr 16) and 0xFF}.${(addr shr 8) and 0xFF}.${addr and 0xFF}"
            )
        }
        return list
    }

    /** Führt den Sweep aus und emittiert Ereignisse. */
    fun scan(ifaces: List<Iface>): Flow<ScanEvent> = channelFlow {
        val targets = ifaces.filter { it.checked }.flatMap { hostAddresses(it.ip, it.prefix) }.distinct()
        val total = targets.size
        val done = java.util.concurrent.atomic.AtomicInteger(0)
        val found = java.util.concurrent.atomic.AtomicInteger(0)
        val sem = Semaphore(MAX_PARALLEL)
        targets.map { ip ->
            async(Dispatchers.IO) {
                sem.withPermit {
                    val open = SCAN_PORTS.filter { portOpen(ip, it) }
                    send(ScanEvent.Progress(done.incrementAndGet(), total, ip))
                    if (open.isNotEmpty()) {
                        found.incrementAndGet()
                        send(
                            ScanEvent.Found(
                                DiscoveredHost(
                                    hostname = reverseDns(ip),
                                    ipv4 = ip,
                                    mac = "",
                                    openPorts = open,
                                    known = open.contains(HostServiceClient.DEFAULT_PORT),
                                )
                            )
                        )
                    }
                }
            }
        }.awaitAll()
        send(ScanEvent.Done(found.get()))
    }.flowOn(Dispatchers.IO)

    private fun portOpen(ip: String, port: Int): Boolean = try {
        Socket().use { s ->
            s.connect(InetSocketAddress(ip, port), PORT_TIMEOUT_MS)
            true
        }
    } catch (_: Exception) {
        false
    }

    private fun reverseDns(ip: String): String = try {
        val addr = InetAddress.getByName(ip)
        val name = addr.canonicalHostName
        if (name == ip || name.isNullOrBlank()) "Unbekannt" else name.substringBefore(".")
    } catch (_: Exception) {
        "Unbekannt"
    }

    companion object {
        private val SCAN_PORTS = listOf(HostServiceClient.DEFAULT_PORT, 445, 135, 80, 443, 22)
        private const val PORT_TIMEOUT_MS = 300
        private const val MAX_PARALLEL = 64
    }
}
