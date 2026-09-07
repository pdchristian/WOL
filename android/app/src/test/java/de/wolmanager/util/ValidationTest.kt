package de.wolmanager.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ValidationTest {

    @Test
    fun isValidMac() {
        assertTrue(Validation.isValidMac("AA:BB:CC:DD:EE:FF"))
        assertTrue(Validation.isValidMac("aa-bb-cc-dd-ee-ff"))
        assertFalse(Validation.isValidMac("AA:BB:CC:DD:EE"))
        assertFalse(Validation.isValidMac("AG:BB:CC:DD:EE:FF"))
        assertFalse(Validation.isValidMac(""))
    }

    @Test
    fun isValidIpv4() {
        assertTrue(Validation.isValidIpv4("192.168.1.1"))
        assertTrue(Validation.isValidIpv4("255.255.255.255"))
        assertTrue(Validation.isValidIpv4("0.0.0.0"))
        assertFalse(Validation.isValidIpv4("256.1.1.1"))
        assertFalse(Validation.isValidIpv4("192.168.1"))
        assertFalse(Validation.isValidIpv4("192.168.1.1.1"))
        assertFalse(Validation.isValidIpv4("host-name"))
    }

    @Test
    fun isValidIpOrHostname() {
        assertTrue(Validation.isValidIpOrHostname("")) // optional
        assertTrue(Validation.isValidIpOrHostname("10.0.0.5"))
        assertTrue(Validation.isValidIpOrHostname("mein-pc"))
        assertTrue(Validation.isValidIpOrHostname("pc.local"))
        assertFalse(Validation.isValidIpOrHostname("-bad"))
        assertFalse(Validation.isValidIpOrHostname("bad name"))
    }

    @Test
    fun isValidPort() {
        assertTrue(Validation.isValidPort(1))
        assertTrue(Validation.isValidPort(65535))
        assertFalse(Validation.isValidPort(0))
        assertFalse(Validation.isValidPort(65536))
        assertFalse(Validation.isValidPort(-1))
    }

    @Test
    fun normalizeMac() {
        assertEquals("AA:BB:CC:DD:EE:FF", Validation.normalizeMac("aa-bb-cc-dd-ee-ff"))
        assertEquals("AA:BB:CC:DD:EE:FF", Validation.normalizeMac(" aa bb cc dd ee ff "))
    }

    @Test
    fun macExists() {
        val existing = listOf("AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66")
        assertTrue(Validation.macExists("aa-bb-cc-dd-ee-ff", existing))
        assertFalse(Validation.macExists("99:99:99:99:99:99", existing))
    }
}
