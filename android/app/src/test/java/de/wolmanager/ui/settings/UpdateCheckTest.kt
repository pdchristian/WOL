package de.wolmanager.ui.settings

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateCheckTest {

    @Test
    fun newerVersions() {
        assertTrue(isNewer("2.4.0", "2.3.0"))
        assertTrue(isNewer("2.3.1", "2.3.0"))
        assertTrue(isNewer("3.0.0", "2.9.9"))
        assertTrue(isNewer("2.3.0.1", "2.3.0"))
    }

    @Test
    fun sameOrOlder() {
        assertFalse(isNewer("2.3.0", "2.3.0"))
        assertFalse(isNewer("2.2.9", "2.3.0"))
        assertFalse(isNewer("1.9.9", "2.0.0"))
        assertFalse(isNewer("2.3", "2.3.0"))
    }

    @Test
    fun nonNumericParts() {
        assertTrue(isNewer("v2.4.0", "2.3.0") || !isNewer("v2.4.0", "2.3.0")) // stürzt nicht ab
        assertTrue(isNewer("2.4", "2.3.1"))
    }
}
