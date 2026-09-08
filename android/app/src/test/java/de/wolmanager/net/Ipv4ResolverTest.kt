package de.wolmanager.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * IPv4-Resolver — Regression: Geräte mit Host-Namen (z. B. `blade-18.fritz.box`)
 * müssen zu IPv4 aufgelöst werden, damit sie den nur auf IPv4 lauschenden
 * Host-Service erreichen (Windows-Fix `resolve_ipv4_all` wird gespiegelt).
 */
class Ipv4ResolverTest {

    @Test
    fun ipv4Literal_passesThrough() {
        assertEquals(listOf("192.168.2.150"), Ipv4Resolver.resolveAll("192.168.2.150"))
        assertEquals(listOf("0.0.0.0"), Ipv4Resolver.resolveAll("0.0.0.0"))
        assertEquals(listOf("255.255.255.255"), Ipv4Resolver.resolveAll("255.255.255.255"))
    }

    @Test
    fun ipv4Literal_isDetected() {
        assertTrue(Ipv4Resolver.isIpv4Literal("192.168.2.150"))
        assertTrue(Ipv4Resolver.isIpv4Literal("10.0.0.1"))
        assertTrue(Ipv4Resolver.isIpv4Literal("255.255.255.255"))
    }

    @Test
    fun nonIpv4_isNotLiteral() {
        assertFalse(Ipv4Resolver.isIpv4Literal("blade-18"))
        assertFalse(Ipv4Resolver.isIpv4Literal("blade-18.fritz.box"))
        assertFalse(Ipv4Resolver.isIpv4Literal("256.1.1.1"))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3"))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3.4.5"))
        assertFalse(Ipv4Resolver.isIpv4Literal(""))
        assertFalse(Ipv4Resolver.isIpv4Literal("1.2.3."))
        assertFalse(Ipv4Resolver.isIpv4Literal("::1"))
    }

    @Test
    fun emptyValue_resolvesToEmpty() {
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll(""))
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll("   "))
    }

    @Test
    fun unresolvableName_resolvesToEmpty() {
        // ".invalid" ist per RFC 2606 nie auflösbar.
        assertEquals(emptyList<String>(), Ipv4Resolver.resolveAll("host-does-not-exist.invalid"))
    }

    @Test
    fun loopbackName_resolvesToIpv4() {
        // "localhost" muss (auf jedem System) mindestens eine IPv4-Adresse liefern.
        val ips = Ipv4Resolver.resolveAll("localhost")
        assertTrue("localhost sollte zu IPv4 aufgelöst werden, war: $ips", ips.isNotEmpty())
        assertTrue(ips.all { Ipv4Resolver.isIpv4Literal(it) })
    }
}
