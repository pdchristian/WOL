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

    func testAdapterAddressMapsToSubnetNetworkAddress() {
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "192.168.2.130", prefix: 24), "192.168.2.0")
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "192.168.2.74", prefix: 24), "192.168.2.0")
    }

    func testNonDefaultPrefixIsHonoured() {
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "10.20.30.77", prefix: 22), "10.20.28.0")
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "10.0.5.9", prefix: 16), "10.0.0.0")
    }

    func testIfaceExposesItsSubnetNetwork() {
        let iface = NetworkScanner.Iface(name: "en0", ip: "192.168.2.130", prefix: 24, dns: "")
        XCTAssertEqual(iface.network, "192.168.2.0")
    }

    func testInvalidAddressOrPrefixFallsBackSafely() {
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "not-an-ip", prefix: 24), "not-an-ip")
        // unbrauchbarer Präfix -> /24 wird angenommen
        XCTAssertEqual(NetworkScanner.networkAddress(ip: "192.168.2.130", prefix: 99), "192.168.2.0")
    }
}
