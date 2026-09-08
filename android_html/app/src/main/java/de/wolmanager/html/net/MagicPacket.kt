package de.wolmanager.html.net

import android.content.Context
import android.net.wifi.WifiManager
import de.wolmanager.html.data.Device
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress

/**
 * Magic Packet — drahtidentisch zu wol_app/wol_engine.py:
 * 6× 0xFF gefolgt von 16× der MAC-Adresse. UDP-Broadcast auf Port 9 (konfigurierbar).
 */
object MagicPacket {

    /** Baut das 102-Byte-Paket. Erwartet eine normale MAC (Doppelpunkte/Bindestriche egal). */
    fun build(mac: String): ByteArray {
        val bytes = macBytes(mac) ?: throw IllegalArgumentException("invalid mac")
        val packet = ByteArray(6 + 16 * 6)
        for (i in 0 until 6) packet[i] = 0xFF.toByte()
        for (i in 0 until 16) {
            System.arraycopy(bytes, 0, packet, 6 + i * 6, 6)
        }
        return packet
    }

    fun macBytes(mac: String): ByteArray? {
        val norm = mac.trim().uppercase().replace("-", ":").replace(" ", ":")
        val parts = norm.split(":")
        if (parts.size != 6) return null
        return try {
            ByteArray(6) { parts[it].toInt(16).toByte() }
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Sendet das Magic Packet per UDP-Broadcast. MulticastLock wird für WLAN-Broadcast
     * benötigt (ohne Root zwingend).
     */
    suspend fun send(
        context: Context,
        device: Device,
        broadcastIp: String,
        port: Int,
    ): Result<Unit> = withContext(Dispatchers.IO) {
        val wifi = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = wifi?.createMulticastLock("wol_lock")
        try {
            lock?.acquire()
            val bytes = build(ValidationLocal.normalizeMac(device.mac))
            val addr = InetAddress.getByName(broadcastIp.ifEmpty { "255.255.255.255" })
            DatagramSocket().use { socket ->
                socket.broadcast = true
                val pkt = DatagramPacket(bytes, bytes.size, InetSocketAddress(addr, port))
                socket.send(pkt)
            }
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        } finally {
            runCatching { lock?.release() }
        }
    }

    /** Reicht die MAC für ein Wake aus? */
    fun canWake(device: Device): Boolean = macBytes(device.mac) != null

    private object ValidationLocal {
        fun normalizeMac(mac: String): String =
            mac.trim().uppercase().replace("-", ":").replace(" ", ":")
    }
}
