package de.wolmanager.html.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateCheckTest {

    @Test
    fun normalizeTagVariants() {
        assertEquals("2.3.5", UpdateCheck.normalizeTag("v2.3.5"))
        // Real existierender GitHub-Tag mit Punkt nach dem v — führte sonst zu
        // ".2.3.5" → erstes Segment 0 → fälschlich "bereits aktuell".
        assertEquals("2.3.5", UpdateCheck.normalizeTag("v.2.3.5"))
        assertEquals("2.3.5", UpdateCheck.normalizeTag("V2.3.5"))
        assertEquals("2.3.5", UpdateCheck.normalizeTag("  v.2.3.5  "))
        assertEquals("2.3.5", UpdateCheck.normalizeTag("2.3.5"))
        assertEquals("", UpdateCheck.normalizeTag(""))
    }

    @Test
    fun dotTagIsDetectedAsUpdate() {
        assertTrue(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.3.0"))
        assertFalse(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.3.5"))
        assertFalse(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.4.0"))
    }

    @Test
    fun isNewerBasics() {
        assertTrue(UpdateCheck.isNewer("2.3.1", "2.3.0"))
        assertTrue(UpdateCheck.isNewer("2.4.0", "2.3.9"))
        assertTrue(UpdateCheck.isNewer("3.0.0", "2.99.99"))
        assertFalse(UpdateCheck.isNewer("2.3.0", "2.3.0"))
        assertFalse(UpdateCheck.isNewer("2.2.9", "2.3.0"))
    }
}
