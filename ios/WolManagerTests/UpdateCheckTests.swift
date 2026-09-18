import XCTest
@testable import WolManager

final class UpdateCheckTests: XCTestCase {

    func testIsNewer() {
        XCTAssertTrue(UpdateCheck.isNewer("2.3.1", "2.3.0"))
        XCTAssertTrue(UpdateCheck.isNewer("2.4.0", "2.3.9"))
        XCTAssertTrue(UpdateCheck.isNewer("3.0.0", "2.99.99"))
        XCTAssertTrue(UpdateCheck.isNewer("2.3.0.1", "2.3.0"))
    }

    func testNotNewer() {
        XCTAssertFalse(UpdateCheck.isNewer("2.3.0", "2.3.0"))
        XCTAssertFalse(UpdateCheck.isNewer("2.3", "2.3.0"))     // fehlende Teile = 0
        XCTAssertFalse(UpdateCheck.isNewer("2.2.9", "2.3.0"))
        XCTAssertFalse(UpdateCheck.isNewer("1.9.0", "2.0.0"))
    }

    func testNonNumericPartsCountAsZero() {
        XCTAssertFalse(UpdateCheck.isNewer("2.3.beta", "2.3.0")) // "beta" → 0
        XCTAssertTrue(UpdateCheck.isNewer("2.4.beta", "2.3.9"))
    }

    func testNormalizeTag() {
        XCTAssertEqual(UpdateCheck.normalizeTag("v2.3.5"), "2.3.5")
        // Real existierender GitHub-Tag mit Punkt nach dem v.
        XCTAssertEqual(UpdateCheck.normalizeTag("v.2.3.5"), "2.3.5")
        XCTAssertEqual(UpdateCheck.normalizeTag("V2.3.5"), "2.3.5")
        XCTAssertEqual(UpdateCheck.normalizeTag("  v.2.3.5  "), "2.3.5")
        XCTAssertEqual(UpdateCheck.normalizeTag("2.3.5"), "2.3.5")
        XCTAssertEqual(UpdateCheck.normalizeTag(""), "")
    }

    func testDotTagIsDetectedAsUpdate() {
        XCTAssertTrue(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.3.0"))
        XCTAssertFalse(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.3.5"))
        XCTAssertFalse(UpdateCheck.isNewer(UpdateCheck.normalizeTag("v.2.3.5"), "2.4.0"))
    }
}
