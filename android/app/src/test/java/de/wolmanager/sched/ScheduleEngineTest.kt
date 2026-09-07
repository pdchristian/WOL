package de.wolmanager.sched

import de.wolmanager.data.ScheduleDef
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar
import java.util.GregorianCalendar
import java.util.TimeZone

class ScheduleEngineTest {

    private fun cal(y: Int, mo: Int, d: Int, h: Int, min: Int): Calendar {
        val c = GregorianCalendar(y, mo - 1, d, h, min, 0)
        c.set(Calendar.MILLISECOND, 0)
        c.timeZone = TimeZone.getDefault()
        return c
    }

    @Test
    fun dayKey_matchesWeekday() {
        // 2024-01-01 = Montag
        assertEquals("Mon", ScheduleEngine.dayKey(cal(2024, 1, 1, 0, 0)))
        // 2024-01-07 = Sonntag
        assertEquals("Sun", ScheduleEngine.dayKey(cal(2024, 1, 7, 0, 0)))
        // 2024-01-03 = Mittwoch
        assertEquals("Wed", ScheduleEngine.dayKey(cal(2024, 1, 3, 0, 0)))
    }

    @Test
    fun matchesMinute() {
        val s = ScheduleDef(hour = 7, minute = 30, days = listOf("Mon"), enabled = true)
        assertTrue(ScheduleEngine.matchesMinute(s, cal(2024, 1, 1, 7, 30)))
        assertFalse(ScheduleEngine.matchesMinute(s, cal(2024, 1, 1, 7, 31)))
        assertFalse(ScheduleEngine.matchesMinute(s, cal(2024, 1, 2, 7, 30))) // Di
        assertFalse(ScheduleEngine.matchesMinute(s.copy(enabled = false), cal(2024, 1, 1, 7, 30)))
    }

    @Test
    fun dueForCatchUp_withinWindow() {
        val s = ScheduleDef(hour = 7, minute = 0, days = listOf("Mon"), enabled = true, lastRun = 0L)
        val now = cal(2024, 1, 1, 7, 10) // 10 min nach Plan
        val window = 20 * 60_000L
        val fireMs = cal(2024, 1, 1, 7, 0).timeInMillis
        assertTrue(ScheduleEngine.dueForCatchUp(s.copy(lastRun = 0L), now, window, 0L))
        // Bereits nach Plan ausgeführt → nicht fällig
        assertFalse(ScheduleEngine.dueForCatchUp(s, now, window, fireMs))
        // Außerhalb des Fensters (30 min) → nicht fällig
        assertFalse(ScheduleEngine.dueForCatchUp(s.copy(lastRun = 0L), cal(2024, 1, 1, 7, 30), window, 0L))
    }

    @Test
    fun parseTime() {
        assertEquals(7 to 30, ScheduleEngine.parseTime("07:30"))
        assertEquals(0 to 5, ScheduleEngine.parseTime("0:05"))
        assertEquals(23 to 59, ScheduleEngine.parseTime("23:59"))
        assertNull(ScheduleEngine.parseTime("24:00"))
        assertNull(ScheduleEngine.parseTime("7:5"))
        assertNull(ScheduleEngine.parseTime("abc"))
    }

    @Test
    fun formatTime() {
        assertEquals("07:05", ScheduleEngine.formatTime(7, 5))
        assertEquals("00:00", ScheduleEngine.formatTime(0, 0))
        assertEquals("23:59", ScheduleEngine.formatTime(23, 59))
    }
}
