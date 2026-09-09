import XCTest
@testable import WolManager

/* Ipv4Resolver: IPv4-Forcierung für Host-Namen — analog Ipv4ResolverTest.kt. */
final class Ipv4ResolverTests: XCTestCase {

    func testIpv4LiteralPassesThrough() {
        XCTAssertEqual(Ipv4Resolver.resolveAll("192.168.2.150"), ["192.168.2.150"])
        XCTAssertEqual(Ipv4Resolver.resolveAll("  10.0.0.1  "), ["10.0.0.1"])
    }

    func testIsIpv4LiteralAcceptsDottedQuadOnly() {
        XCTAssertTrue(Ipv4Resolver.isIpv4Literal("0.0.0.0"))
        XCTAssertTrue(Ipv4Resolver.isIpv4Literal("255.255.255.255"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("256.1.1.1"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("1.2.3"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("1.2.3.4.5"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("blade-18"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("::1"))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal(""))
        XCTAssertFalse(Ipv4Resolver.isIpv4Literal("1.2.3."))
    }

    func testEmptyValueResolvesToEmpty() {
        XCTAssertEqual(Ipv4Resolver.resolveAll(""), [])
        XCTAssertEqual(Ipv4Resolver.resolveAll("   "), [])
    }

    func testUnresolvableHostYieldsEmpty() {
        XCTAssertEqual(Ipv4Resolver.resolveAll("this-host-does-not-exist.invalid"), [])
    }

    func testLocalhostResolvesToIpv4() {
        let ips = Ipv4Resolver.resolveAll("localhost")
        XCTAssertTrue(ips.contains { $0.hasPrefix("127.") }, "expected IPv4 loopback, got \(ips)")
    }
}
