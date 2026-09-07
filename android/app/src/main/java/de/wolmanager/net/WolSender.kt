package de.wolmanager.net

import android.content.Context
import android.net.wifi.WifiManager
import de.wolmanager.data.Device
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Magic-Packet-Wiederaufwecken — Wire-Format identisch zum Desktop-Client
 * (wol_app/wol_engine.py): 6 × 0xFF gefolgt von 16 × MAC, UDP-Broadcast.
 */
object WolSender {

    fun buildMagicPacket(mac: String): ByteArray {
        val bytes = macBytes(mac) ?: throw IllegalArgumentException("Ungültige MAC: $mac")
        val packet = ByteArray(6 + 16 * 6)
        for (i in 0 until 6) packet[i] = 0xFF.toByte()
        for (i in 0 until 16) {
            System.arraycopy(bytes, 0, packet, 6 + i * 6, 6)
        }
        return packet
    }

    fun isValidMac(mac: String): Boolean = macBytes(mac) != null

    private fun macBytes(mac: String): ByteArray? {
        val parts = mac.trim().split(":", "-", " ").filter { it.isNotBlank() }
        if (parts.size != 6) return null
        val out = ByteArray(6)
        parts.forEachIndexed { i, p ->
            if (p.length != 2) return null
            val v = p.toIntOrNull(16) ?: return null
            out[i] = v.toByte()
        }
        return out
    }

    /**
     * Sendet das Magic Packet. Auf Android ist ein MulticastLock nötig,
     * damit UDP-Broadcasts vom WLAN-Adapter durchgelassen werden.
     */
    suspend fun send(context: Context, device: Device, broadcastIp: String, wolPort: Int): Result<String> =
        withContext(Dispatchers.IO) {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val lock = wifi?.createMulticastLock("wol")
            try {
                lock?.setReferenceCounted(false)
                lock?.acquire()
                val packet = buildMagicPacket(device.mac)
                DatagramSocket().use { sock ->
                    sock.broadcast = true
                    val addr = InetAddress.getByName(broadcastIp)
                    sock.send(DatagramPacket(packet, packet.size, addr, wolPort))
                }
                Result.success("Wake an ${device.mac} → $broadcastIp:$wolPort")
            } catch (e: Exception) {
                Result.failure(e)
            } finally {
                try { lock?.release() } catch (_: Exception) {}
            }
        }
}

/**
 * Host-Service-Client — Protokoll v4: eine JSON-Zeile (LF-terminiert) pro
 * Anfrage. "status" ist authentifizierungsfrei und liefert
 * {"status":"ok","message":"online"}.
 */
object HostClient {

    data class HostReply(val status: String, val message: String?, val raw: String)

    /** TCP-Verbindungsaufbau + status-Anfrage; wirft bei Verbindungsfehler. */
    suspend fun status(host: String, port: Int, timeoutMs: Int = 2000): HostReply =
        withContext(Dispatchers.IO) {
            Socket().use { sock ->
                sock.connect(InetSocketAddress(InetAddress.getByName(host), port), timeoutMs)
                sock.soTimeout = timeoutMs
                val req = """{"command":"status"}""" + "\n"
                sock.getOutputStream().write(req.toByteArray(Charsets.UTF_8))
                sock.getOutputStream().flush()
                val input = sock.getInputStream()
                val sb = StringBuilder()
                var ch: Int
                while (input.read().also { ch = it } != -1 && ch != '\n'.code) {
                    sb.append(ch.toChar())
                }
                val obj = org.json.JSONObject(sb.toString())
                HostReply(
                    status = obj.optString("status", ""),
                    message = obj.optString("message", "").ifEmpty { null },
                    raw = sb.toString(),
                )
            }
        }
}
