package de.wolmanager.html.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * NetworkScanner.isScannable: Bereichsfilter für die Netzwerkliste (Parität zur
 * Desktop-App, wol_app/network_scanner.py is_real_interface).
 * networkAddress: Scan beginnt bei der Subnetzadresse, nicht bei der Adapteradresse.
 */
class NetworkScannerTest {

    @Test
    fun `private and common LAN ranges are scannable`() {
        assertTrue(NetworkScanner.isScannable("192.168.2.5"))
        assertTrue(NetworkScanner.isScannable("10.0.0.1"))
        assertTrue(NetworkScanner.isScannable("192.168.100.1"))
    }

    @Test
    fun `apipa range 169 is hidden`() {
        assertFalse(NetworkScanner.isScannable("169.254.1.2"))
        assertFalse(NetworkScanner.isScannable("169.1.2.3"))
    }

    @Test
    fun `virtual adapter range 172 is hidden entirely`() {
        assertFalse(NetworkScanner.isScannable("172.16.0.1"))
        assertFalse(NetworkScanner.isScannable("172.67.8.9"))
        assertFalse(NetworkScanner.isScannable("172.31.255.254"))
    }

    @Test
    fun `blank or null ip is not scannable`() {
        assertFalse(NetworkScanner.isScannable(""))
        assertFalse(NetworkScanner.isScannable(null))
    }

    @Test
    fun `adapter address maps to its subnet network address`() {
        assertEquals("192.168.2.0", NetworkScanner.networkAddress("192.168.2.130", 24))
        assertEquals("192.168.2.0", NetworkScanner.networkAddress("192.168.2.74", 24))
    }

    @Test
    fun `non default prefix is honoured`() {
        assertEquals("10.20.28.0", NetworkScanner.networkAddress("10.20.30.77", 22))
        assertEquals("10.0.0.0", NetworkScanner.networkAddress("10.0.5.9", 16))
    }

    @Test
    fun `iface exposes its subnet network`() {
        val iface = NetworkScanner.Iface("wlan0", "192.168.2.130", 24, "192.168.2.1")
        assertEquals("192.168.2.0", iface.network)
    }

    @Test
    fun `invalid address or prefix falls back safely`() {
        assertEquals("not-an-ip", NetworkScanner.networkAddress("not-an-ip", 24))
        // unbrauchbarer Präfix -> /24 wird angenommen
        assertEquals("192.168.2.0", NetworkScanner.networkAddress("192.168.2.130", 99))
    }
}
