import XCTest
@testable import WolManager

final class ValidationTests: XCTestCase {

    func testValidMacs() {
        XCTAssertTrue(Validation.isValidMac("AA:BB:CC:DD:EE:FF"))
        XCTAssertTrue(Validation.isValidMac("aa-bb-cc-dd-ee-ff"))
        XCTAssertTrue(Validation.isValidMac(" 01:23:45:67:89:ab "))
        XCTAssertFalse(Validation.isValidMac("AA:BB:CC:DD:EE"))
        XCTAssertFalse(Validation.isValidMac("GG:BB:CC:DD:EE:FF"))
        XCTAssertFalse(Validation.isValidMac(""))
    }

    func testValidIpv4() {
        XCTAssertTrue(Validation.isValidIpv4("192.168.1.1"))
        XCTAssertTrue(Validation.isValidIpv4("255.255.255.255"))
        XCTAssertTrue(Validation.isValidIpv4("0.0.0.0"))
        XCTAssertFalse(Validation.isValidIpv4("256.1.1.1"))
        XCTAssertFalse(Validation.isValidIpv4("192.168.1"))
        XCTAssertFalse(Validation.isValidIpv4("192.168.1.1.1"))
    }

    func testIpOrHostname() {
        XCTAssertTrue(Validation.isValidIpOrHostname("")) // optional
        XCTAssertTrue(Validation.isValidIpOrHostname("192.168.1.10"))
        XCTAssertTrue(Validation.isValidIpOrHostname("buero-pc"))
        XCTAssertTrue(Validation.isValidIpOrHostname("pc.lan.local"))
        XCTAssertFalse(Validation.isValidIpOrHostname("-bad"))
        XCTAssertFalse(Validation.isValidIpOrHostname("bad-"))
    }

    func testPorts() {
        XCTAssertTrue(Validation.isValidPort(1))
        XCTAssertTrue(Validation.isValidPort(65535))
        XCTAssertFalse(Validation.isValidPort(0))
        XCTAssertFalse(Validation.isValidPort(65536))
    }

    func testNormalizeMac() {
        XCTAssertEqual(Validation.normalizeMac("aa-bb-cc-dd-ee-ff"), "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(Validation.normalizeMac(" aa bb cc dd ee ff "), "AA:BB:CC:DD:EE:FF")
    }
}
