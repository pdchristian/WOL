package de.wolmanager.html.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ipv4Resolver: IPv4-Forcierung für Host-Namen (Multi-Kandidat, wie Windows-Side). */
class Ipv4ResolverTest {

    @Test
    fun `ipv4 literal passes through unchanged`() {
        assertEquals(listOf("192.168.2.150"), Ipv4Resolver.resolveAll("192.168.2.150"))
        assertEquals(listOf("10.0.0.1"), Ipv4Resolver.resolveAll("  10.0.0.1  "))
    }

    @Test
    fun `isIpv4Literal accepts dotted quad only`() {
        assertTrue(Ipv4Resolver.isIpv4Literal("0.0.0.0"))
        assertTrue(Ipv4Resolver.isIpv4Literal("255.255.255.255"))
        assertFalse(Ipv4Resolver.isIpv4Literal("256.1.1.1"))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3"))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3.4.5"))
        assertFalse(Ipv4Resolver.isIpv4Literal("blade-18"))
        assertFalse(Ipv4Resolver.isIpv4Literal("::1"))
        assertFalse(Ipv4Resolver.isIpv4Literal(""))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3."))
    }

    @Test
    fun `empty value resolves to empty list`() {
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll(""))
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll("   "))
    }

    @Test
    fun `unresolvable host yields empty list`() {
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll("this-host-does-not-exist.invalid"))
    }

    @Test
    fun `localhost resolves to an IPv4 address`() {
        val ips = Ipv4Resolver.resolveAll("localhost")
        assertTrue("expected an IPv4 loopback, got $ips", ips.any { it.startsWith("127.") })
    }
}
