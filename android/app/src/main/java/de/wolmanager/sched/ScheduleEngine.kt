package de.wolmanager.sched

import de.wolmanager.data.ScheduleDef
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

/**
 * Reine Logik zur Zeitplan-Erkennung — identische Semantik wie die Windows-App
 * (days = englische Kürzel, Mo=0 wie datetime.weekday()).
 */
object ScheduleEngine {

    val DAY_KEYS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    fun dayKey(cal: Calendar): String = DAY_KEYS[
        when (cal.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY -> 0
            Calendar.TUESDAY -> 1
            Calendar.WEDNESDAY -> 2
            Calendar.THURSDAY -> 3
            Calendar.FRIDAY -> 4
            Calendar.SATURDAY -> 5
            else -> 6
        }
    ]

    /** Trifft der Zeitplan auf genau diese Minute zu? */
    fun matchesMinute(schedule: ScheduleDef, cal: Calendar): Boolean {
        if (!schedule.enabled) return false
        if (cal.get(Calendar.HOUR_OF_DAY) != schedule.hour) return false
        if (cal.get(Calendar.MINUTE) != schedule.minute) return false
        return schedule.days.contains(dayKey(cal))
    }

    /**
     * Nachhole-Kriterium für WorkManager-Läufe (alle 15 min):
     * Der geplante Zeitpunkt liegt in [now - windowMs, now] und wurde seitdem nicht ausgeführt.
     */
    fun dueForCatchUp(schedule: ScheduleDef, now: Calendar, windowMs: Long, lastRunMs: Long): Boolean {
        if (!schedule.enabled) return false
        for (back in 0..(windowMs / 60_000L)) {
            val probe = (now.clone() as Calendar).apply { add(Calendar.MINUTE, -back.toInt()) }
            if (matchesMinute(schedule, probe)) {
                val fireMs = probe.timeInMillis
                return fireMs > lastRunMs && fireMs <= now.timeInMillis
            }
        }
        return false
    }

    /** "HH:MM" → Pair(stunde, minute) oder null. */
    fun parseTime(text: String): Pair<Int, Int>? {
        val m = Regex("^(\\d{1,2}):(\\d{2})$").find(text.trim()) ?: return null
        val h = m.groupValues[1].toIntOrNull() ?: return null
        val min = m.groupValues[2].toIntOrNull() ?: return null
        if (h !in 0..23 || min !in 0..59) return null
        return h to min
    }

    fun formatTime(hour: Int, minute: Int): String =
        String.format(Locale.US, "%02d:%02d", hour, minute)

    fun nowCalendar(): Calendar = Calendar.getInstance(TimeZone.getDefault())
}
