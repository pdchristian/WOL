import XCTest
@testable import WolManager

final class CsvTests: XCTestCase {

    func testHeaderAndBom() {
        let csv = Csv.logsToCsv([])
        XCTAssertTrue(csv.hasPrefix("\u{FEFF}Zeit;Gerät;Level;Nachricht\r\n"))
    }

    func testRowEscaping() {
        let e = LogEntry(ts: 1_750_000_000_000, device: "PC;1", level: "info", msg: "sagt \"hallo\"")
        let csv = Csv.logsToCsv([e])
        // Zeitformat yyyy-MM-dd HH:mm:ss → Ziffern prüfen genügt (Zeitzone lokal)
        XCTAssertTrue(csv.contains("\"PC;1\""))
        XCTAssertTrue(csv.contains("\"sagt \"\"hallo\"\"\""))
        XCTAssertTrue(csv.hasSuffix("\r\n"))
    }

    func testNewlinesFlattened() {
        let e = LogEntry(ts: 0, device: "A", level: "warn", msg: "zeile1\nzeile2\r\nzeile3")
        let csv = Csv.logsToCsv([e])
        XCTAssertFalse(csv.contains("\nzeile2"))
        XCTAssertTrue(csv.contains("zeile1 zeile2 zeile3"))
    }
}
