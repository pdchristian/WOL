import XCTest
@testable import WolManager

/*
 * NetworkScanner.isScannable: Bereichsfilter der Scan-Liste — analog NetworkScannerTest.kt
 * und Desktop is_real_interface (169.* APIPA / 172.* Virtualisierung komplett aus).
 */
final class NetworkScannerTests: XCTestCase {

    func testPrivateLansAreScannable() {
        XCTAssertTrue(NetworkScanner.isScannable("192.168.2.5"))
        XCTAssertTrue(NetworkScanner.isScannable("10.0.0.1"))
        XCTAssertTrue(NetworkScanner.isScannable("192.168.100.1"))
    }

    func testApipaRange169IsHidden() {
        XCTAssertFalse(NetworkScanner.isScannable("169.254.1.2"))
        XCTAssertFalse(NetworkScanner.isScannable("169.1.2.3"))
    }

    func testVirtualAdapterRange172IsHiddenEntirely() {
        XCTAssertFalse(NetworkScanner.isScannable("172.16.0.1"))
        XCTAssertFalse(NetworkScanner.isScannable("172.67.8.9"))
        XCTAssertFalse(NetworkScanner.isScannable("172.31.255.254"))
    }

    func testBlankOrNilIpIsNotScannable() {
        XCTAssertFalse(NetworkScanner.isScannable(""))
        XCTAssertFalse(NetworkScanner.isScannable(nil))
    }
}
