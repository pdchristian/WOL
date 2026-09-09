package de.wolmanager.html.net

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * NetworkScanner.isScannable: Bereichsfilter für die Netzwerkliste (Parität zur
 * Desktop-App, wol_app/network_scanner.py is_real_interface).
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
}
