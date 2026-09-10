package de.wolmanager.html.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Prüft die URI-Konstruktion für die Windows App (Legacy rdp://-Schema) und die
 * Value-Kodierung — ohne Android-API, daher als JVM-Test lauffähig.
 */
class RemoteDesktopTest {

    @Test
    fun hostPrefersIpOverName() {
        assertEquals("192.168.1.10", RemoteDesktop.hostOf("192.168.1.10", "Fractal"))
        assertEquals("192.168.1.10", RemoteDesktop.hostOf("  192.168.1.10  ", "Fractal"))
    }

    @Test
    fun hostFallsBackToName() {
        assertEquals("Fractal", RemoteDesktop.hostOf("", "Fractal"))
        assertEquals("Fractal", RemoteDesktop.hostOf("   ", "Fractal"))
        assertEquals("", RemoteDesktop.hostOf("", ""))
    }

    @Test
    fun candidatesRdpFirstWithUsername() {
        val c = RemoteDesktop.candidates("192.168.2.10", "christian", "full")
        assertEquals(2, c.size)
        assertEquals("rdp://full%20address=s:192.168.2.10&username=s:christian", c[0])
        assertEquals("ms-rd://add/host/192.168.2.10?username=christian", c[1])
    }

    @Test
    fun candidatesWithoutUsername() {
        val c = RemoteDesktop.candidates("nas01.lan", "", "win")
        assertEquals("rdp://full%20address=s:nas01.lan", c[0])
        assertEquals("ms-rd://add/host/nas01.lan", c[1])
    }

    @Test
    fun candidatesEmptyWhenNoHost() {
        assertTrue(RemoteDesktop.candidates("", "", "full").isEmpty())
    }

    @Test
    fun encodeValueKeepsHostSafeChars() {
        assertEquals("nas-01.lan", RemoteDesktop.encodeValue("nas-01.lan"))
        assertEquals("user@corp", RemoteDesktop.encodeValue("user@corp"))
    }

    @Test
    fun encodeValuePercentEncodesSeparators() {
        // & = # ? sind Query-Trenner → müssen kodiert werden, sonst bricht die URI.
        assertEquals("a%26b", RemoteDesktop.encodeValue("a&b"))
        assertEquals("a%3Db", RemoteDesktop.encodeValue("a=b"))
        assertEquals("a%23b", RemoteDesktop.encodeValue("a#b"))
        assertEquals("a%3Fb", RemoteDesktop.encodeValue("a?b"))
        assertEquals("a%25b", RemoteDesktop.encodeValue("a%b"))
        assertEquals("a%20b", RemoteDesktop.encodeValue("a b"))
    }

    @Test
    fun encodeValueUtf8ForNonAscii() {
        // ä = U+00E4 → UTF-8 0xC3 0xA4
        assertEquals("%C3%A4", RemoteDesktop.encodeValue("ä"))
    }

    @Test
    fun usernameWithDomainIsEncoded() {
        // DOMAIN\user → Backslash muss kodiert werden.
        val c = RemoteDesktop.candidates("10.0.0.5", "CORP\\admin", "full")
        assertEquals("rdp://full%20address=s:10.0.0.5&username=s:CORP%5Cadmin", c[0])
    }

    @Test
    fun rdpContentFullscreenWithUser() {
        val s = RemoteDesktop.buildRdpContent("192.168.2.10", "ch", "", "full")
        assertTrue(s.contains("full address:s:192.168.2.10"))
        assertTrue(s.contains("username:s:ch"))
        assertTrue(s.contains("screen mode id:i:1"))
        assertTrue(s.contains("authentication level:i:0"))
        assertTrue(s.contains("use redirection server name:i:1"))
        assertTrue(!s.contains("password:"))
        assertTrue(s.endsWith("\r\n"))
    }

    @Test
    fun rdpContentEmbedsPasswordAsUtf16LeBase64() {
        val s = RemoteDesktop.buildRdpContent("host", "user", "pw", "win")
        val expected = java.util.Base64.getEncoder()
            .encodeToString("pw".toByteArray(Charsets.UTF_16LE))
        assertTrue(s.contains("password:54:$expected"))
        assertTrue(s.contains("prompt credential:i:0"))
        assertTrue(s.contains("screen mode id:i:2"))
    }

    @Test
    fun sanitizedFilenameStripsUnsafeChars() {
        assertEquals("Fractal", RemoteDesktop.sanitizedFilename("Fractal"))
        assertEquals("A4 H20", RemoteDesktop.sanitizedFilename("  A4/H20  "))
        assertEquals("Remote-PC", RemoteDesktop.sanitizedFilename("///"))
        assertEquals(60, RemoteDesktop.sanitizedFilename("x".repeat(200)).length)
    }
}
