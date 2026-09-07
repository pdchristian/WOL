package de.wolmanager.net

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Magic-Packet-Aufbau — bekannter Vektor: 6×0xFF + 16×MAC (102 Byte). */
class MagicPacketTest {

    @Test
    fun build_knownVector() {
        val pkt = MagicPacket.build("AA:BB:CC:DD:EE:FF")
        assertEquals(102, pkt.size)
        for (i in 0 until 6) assertEquals(0xFF.toByte(), pkt[i])
        val mac = byteArrayOf(0xAA.toByte(), 0xBB.toByte(), 0xCC.toByte(), 0xDD.toByte(), 0xEE.toByte(), 0xFF.toByte())
        for (r in 0 until 16) {
            val slice = pkt.copyOfRange(6 + r * 6, 12 + r * 6)
            assertArrayEquals("Wiederholung $r", mac, slice)
        }
    }

    @Test
    fun build_acceptsDashAndLowercase() {
        val a = MagicPacket.build("aa-bb-cc-dd-ee-ff")
        val b = MagicPacket.build("AA:BB:CC:DD:EE:FF")
        assertArrayEquals(a, b)
    }

    @Test
    fun macBytes_variants() {
        val expected = byteArrayOf(0x01, 0x02, 0x03, 0x04, 0x05, 0x06)
        assertArrayEquals(expected, MagicPacket.macBytes("01:02:03:04:05:06"))
        assertArrayEquals(expected, MagicPacket.macBytes("01-02-03-04-05-06"))
        assertArrayEquals(expected, MagicPacket.macBytes(" 1:2:3:4:5:6 "))
        assertNull(MagicPacket.macBytes("01:02:03"))
        assertNull(MagicPacket.macBytes("GG:02:03:04:05:06"))
    }

    @Test
    fun build_throwsOnInvalidMac() {
        try {
            MagicPacket.build("kein-mac")
            org.junit.Assert.fail("expected IllegalArgumentException")
        } catch (expected: IllegalArgumentException) {
        }
    }

    @Test
    fun canWake() {
        assertTrue(MagicPacket.canWake(de.wolmanager.data.Device(mac = "AA:BB:CC:DD:EE:FF")))
        assertFalse(MagicPacket.canWake(de.wolmanager.data.Device(mac = "")))
    }
}
