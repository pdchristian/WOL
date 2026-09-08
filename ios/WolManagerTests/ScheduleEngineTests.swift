import XCTest
@testable import WolManager

final class ScheduleEngineTests: XCTestCase {

    private var cal: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "UTC")!
        return c
    }()

    private func date(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int) -> Date {
        var c = DateComponents()
        c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi; c.second = 0
        return cal.date(from: c)!
    }

    func testDayKey() {
        // 2026-06-01 ist ein Montag
        XCTAssertEqual(ScheduleEngine.dayKey(date(2026, 6, 1, 0, 0), calendar: cal), "Mon")
        XCTAssertEqual(ScheduleEngine.dayKey(date(2026, 6, 7, 0, 0), calendar: cal), "Sun")
        XCTAssertEqual(ScheduleEngine.dayKey(date(2026, 6, 6, 0, 0), calendar: cal), "Sat")
    }

    func testMatchesMinute() {
        let sched = ScheduleDef(id: "s", deviceId: "d", hour: 7, minute: 30, days: ["Mon", "Wed"], enabled: true)
        XCTAssertTrue(ScheduleEngine.matchesMinute(sched, date(2026, 6, 1, 7, 30), calendar: cal))   // Mon
        XCTAssertFalse(ScheduleEngine.matchesMinute(sched, date(2026, 6, 1, 7, 31), calendar: cal))
        XCTAssertFalse(ScheduleEngine.matchesMinute(sched, date(2026, 6, 2, 7, 30), calendar: cal))  // Tue
        let off = ScheduleDef(id: "s", deviceId: "d", hour: 7, minute: 30, days: ["Mon"], enabled: false)
        XCTAssertFalse(ScheduleEngine.matchesMinute(off, date(2026, 6, 1, 7, 30), calendar: cal))
    }

    func testDueForCatchUp() {
        let sched = ScheduleDef(id: "s", deviceId: "d", hour: 7, minute: 0, days: ["Mon"], enabled: true)
        let now = date(2026, 6, 1, 7, 10) // Montag 07:10
        // zuletzt vor dem Plan → nachholen (Fenster 20 min)
        XCTAssertTrue(ScheduleEngine.dueForCatchUp(sched, now: now, windowMs: 20 * 60_000,
                                                   lastRunMs: 0, calendar: cal))
        // heute bereits ausgeführt → nicht nachholen
        let firedMs = Int64(date(2026, 6, 1, 7, 0).timeIntervalSince1970 * 1000)
        XCTAssertFalse(ScheduleEngine.dueForCatchUp(sched, now: now, windowMs: 20 * 60_000,
                                                    lastRunMs: firedMs, calendar: cal))
        // außerhalb des Fensters (13:10, Plan 07:00) → nichts
        XCTAssertFalse(ScheduleEngine.dueForCatchUp(sched, now: date(2026, 6, 1, 13, 10),
                                                    windowMs: 20 * 60_000, lastRunMs: 0, calendar: cal))
    }

    func testParseTime() {
        XCTAssertEqual(ScheduleEngine.parseTime("07:05")?.hour, 7)
        XCTAssertEqual(ScheduleEngine.parseTime("07:05")?.minute, 5)
        XCTAssertEqual(ScheduleEngine.parseTime("7:00")?.hour, 7)
        XCTAssertEqual(ScheduleEngine.parseTime("23:59")?.hour, 23)
        XCTAssertNil(ScheduleEngine.parseTime("24:00"))
        XCTAssertNil(ScheduleEngine.parseTime("12:60"))
        XCTAssertNil(ScheduleEngine.parseTime("morgens"))
        XCTAssertNil(ScheduleEngine.parseTime("12:5"))
    }

    func testFormatTime() {
        XCTAssertEqual(ScheduleEngine.formatTime(hour: 7, minute: 5), "07:05")
        XCTAssertEqual(ScheduleEngine.formatTime(hour: 0, minute: 0), "00:00")
        XCTAssertEqual(ScheduleEngine.formatTime(hour: 23, minute: 59), "23:59")
    }

    func testIsWake() {
        XCTAssertTrue(ScheduleDef(action: "wake").isWake)
        XCTAssertFalse(ScheduleDef(action: "shutdown").isWake)
        XCTAssertFalse(ScheduleDef(action: "SHUTDOWN").isWake)
    }
}
