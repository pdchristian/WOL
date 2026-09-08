import Foundation

/*
 * Reine Logik zur Zeitplan-Erkennung — identische Semantik wie die Windows-App
 * (days = englische Kürzel, Mo=0 wie datetime.weekday()).
 */
enum ScheduleEngine {

    static let dayKeys = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    static func dayKey(_ date: Date, calendar: Calendar = Calendar.current) -> String {
        // weekday(): So=1 … Sa=7 → Mon=0 … Sun=6
        let wd = calendar.component(.weekday, from: date)
        return dayKeys[(wd + 5) % 7]
    }

    /// Trifft der Zeitplan auf genau diese Minute zu?
    static func matchesMinute(_ schedule: ScheduleDef, _ date: Date,
                              calendar: Calendar = Calendar.current) -> Bool {
        guard schedule.enabled else { return false }
        let c = calendar.dateComponents([.hour, .minute], from: date)
        guard c.hour == schedule.hour, c.minute == schedule.minute else { return false }
        return schedule.days.contains(dayKey(date, calendar: calendar))
    }

    /// Nachhole-Kriterium für BGTask-Läufe:
    /// Der geplante Zeitpunkt liegt in [now - windowMs, now] und wurde seitdem nicht ausgeführt.
    static func dueForCatchUp(_ schedule: ScheduleDef, now: Date, windowMs: Int64, lastRunMs: Int64,
                              calendar: Calendar = Calendar.current) -> Bool {
        guard schedule.enabled else { return false }
        let nowMs = Int64(now.timeIntervalSince1970 * 1000)
        let steps = Int(windowMs / 60_000)
        for back in 0...steps {
            guard let probe = Calendar.current.date(byAdding: .minute, value: -back, to: now) else { continue }
            if matchesMinute(schedule, probe, calendar: calendar) {
                let fireMs = Int64(probe.timeIntervalSince1970 * 1000)
                return fireMs > lastRunMs && fireMs <= nowMs
            }
        }
        return false
    }

    /// "HH:MM" → (stunde, minute) oder nil.
    static func parseTime(_ text: String) -> (hour: Int, minute: Int)? {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard let m = trimmed.firstMatch(of: Regex("^(\\d{1,2}):(\\d{2})$")) else { return nil }
        guard let h = Int(m.1), let min = Int(m.2) else { return nil }
        guard (0...23).contains(h), (0...59).contains(min) else { return nil }
        return (h, min)
    }

    static func formatTime(hour: Int, minute: Int) -> String {
        String(format: "%02d:%02d", hour, minute)
    }

    static func nowCalendar() -> Calendar { Calendar.current }
}
