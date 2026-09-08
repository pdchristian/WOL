import XCTest
@testable import WolManager

/* Magic-Packet-Aufbau — bekannter Vektor: 6×0xFF + 16×MAC (102 Byte). */
final class MagicPacketTests: XCTestCase {

    func testBuildKnownVector() throws {
        let pkt = try MagicPacket.build(mac: "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(pkt.count, 102)
        let bytes = [UInt8](pkt)
        for i in 0..<6 { XCTAssertEqual(bytes[i], 0xFF) }
        let mac: [UInt8] = [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
        for r in 0..<16 {
            XCTAssertEqual(Array(bytes[(6 + r * 6)..<(12 + r * 6)]), mac, "Wiederholung \(r)")
        }
    }

    func testBuildAcceptsDashAndLowercase() throws {
        let a = try MagicPacket.build(mac: "aa-bb-cc-dd-ee-ff")
        let b = try MagicPacket.build(mac: "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(a, b)
    }

    func testMacBytesVariants() {
        let expected: [UInt8] = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06]
        XCTAssertEqual(MagicPacket.macBytes("01:02:03:04:05:06"), expected)
        XCTAssertEqual(MagicPacket.macBytes("01-02-03-04-05-06"), expected)
        XCTAssertEqual(MagicPacket.macBytes(" 1:2:3:4:5:6 "), expected)
        XCTAssertNil(MagicPacket.macBytes("01:02:03"))
        XCTAssertNil(MagicPacket.macBytes("GG:02:03:04:05:06"))
    }

    func testBuildThrowsOnInvalidMac() {
        XCTAssertThrowsError(try MagicPacket.build(mac: "kein-mac"))
    }

    func testCanWake() {
        XCTAssertTrue(MagicPacket.canWake(Device(mac: "AA:BB:CC:DD:EE:FF")))
        XCTAssertFalse(MagicPacket.canWake(Device(mac: "")))
    }

    func testDirectedBroadcast() {
        XCTAssertEqual(MagicPacket.directedBroadcast(ip: "192.168.1.42", netmask: "255.255.255.0"),
                       "192.168.1.255")
        XCTAssertEqual(MagicPacket.directedBroadcast(ip: "10.0.5.9", netmask: "255.255.0.0"),
                       "10.0.255.255")
        XCTAssertNil(MagicPacket.directedBroadcast(ip: "kein-ip", netmask: "255.255.255.0"))
    }

    func testPrefixFromNetmask() {
        XCTAssertEqual(InterfaceHelper.prefix(fromNetmask: "255.255.255.0"), 24)
        XCTAssertEqual(InterfaceHelper.prefix(fromNetmask: "255.255.0.0"), 16)
        XCTAssertEqual(InterfaceHelper.prefix(fromNetmask: "255.255.255.128"), 25)
    }
}
