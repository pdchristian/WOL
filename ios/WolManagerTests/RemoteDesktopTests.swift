import XCTest
@testable import WolManager

/* Reine Logik von RemoteDesktop (URI-Builder) – ohne UIKit-Aufrufe testbar.
   Hinweis: nach Hinzufügen dieser Datei `xcodegen generate` ausführen,
   damit WolManager.xcodeproj sie enthält. */
final class RemoteDesktopTests: XCTestCase {

    func testHostOfPrefersIp() {
        XCTAssertEqual(RemoteDesktop.hostOf(ip: "192.168.2.10", name: "Fractal"), "192.168.2.10")
    }

    func testHostOfFallsBackToName() {
        XCTAssertEqual(RemoteDesktop.hostOf(ip: "  ", name: "Fractal"), "Fractal")
        XCTAssertEqual(RemoteDesktop.hostOf(ip: "", name: ""), "")
    }

    func testCandidatesWithUser() {
        let c = RemoteDesktop.candidates(host: "192.168.2.10", username: "christian", mode: "full")
        XCTAssertEqual(c.count, 2)
        // Attribut-Trenner sind prozentkodiert (= → %3D, : → %3A, & → %26), damit
        // URL(string:) (iOS 17+ strikt) die Legacy-URI akzeptiert.
        XCTAssertEqual(c[0], "rdp://full%20address%3Ds%3A192.168.2.10%26username%3Ds%3Achristian")
        XCTAssertEqual(c[1], "ms-rd://add/host/192.168.2.10?username=christian&use.maximizewindow=true")
    }

    func testCandidatesWithoutUserWindowMode() {
        let c = RemoteDesktop.candidates(host: "buero-pc", username: "   ", mode: "win")
        XCTAssertEqual(c[0], "rdp://full%20address%3Ds%3Abuero-pc")
        XCTAssertEqual(c[1], "ms-rd://add/host/buero-pc?use.maximizewindow=false")
    }

    func testCandidatesEmptyHost() {
        XCTAssertTrue(RemoteDesktop.candidates(host: "  ", username: "u").isEmpty)
    }

    func testEncodeValue() {
        // Doppelpunkt wird kodiert (sonst verwirft iOS 17 die URL als Port-Trenner).
        XCTAssertEqual(RemoteDesktop.encodeValue("pc.lan:3389"), "pc.lan%3A3389")
        XCTAssertEqual(RemoteDesktop.encodeValue("user name"), "user%20name")
        XCTAssertEqual(RemoteDesktop.encodeValue("paß"), "pa%C3%9F")
    }

    func testCandidateUrlsAreParsable() {
        for uri in RemoteDesktop.candidates(host: "fractal.local", username: "ch r", mode: "full") {
            XCTAssertNotNil(URL(string: uri), "URL nicht parsebar: \(uri)")
        }
    }

    func testCandidateUrlsAreParsableWithPortAndDomain() {
        // Host:Port und DOMAIN\\user – frühere Kandidaten waren hier nil.
        for uri in RemoteDesktop.candidates(host: "fractal.local:3389", username: "CORP\\admin", mode: "full") {
            XCTAssertNotNil(URL(string: uri), "URL nicht parsebar: \(uri)")
        }
    }

    func testBuildContentFullscreen() {
        let s = RemoteDesktop.buildContent(host: "192.168.2.10", username: "ch", mode: "full")
        XCTAssertTrue(s.contains("full address:s:192.168.2.10"))
        XCTAssertTrue(s.contains("username:s:ch"))
        XCTAssertTrue(s.contains("screen mode id:i:1"))
        XCTAssertTrue(s.contains("authentication level:i:0"))
        XCTAssertFalse(s.contains("password"), "Kein Passwort in der Datei")
        XCTAssertTrue(s.hasSuffix("\r\n"))
    }

    func testBuildContentWithoutUserWindow() {
        let s = RemoteDesktop.buildContent(host: "nas01", username: "  ", mode: "win")
        XCTAssertFalse(s.contains("username:"))
        XCTAssertTrue(s.contains("screen mode id:i:2"))
    }

    func testSanitizedFilename() {
        XCTAssertEqual(RemoteDesktop.sanitizedFilename("Fractal"), "Fractal")
        XCTAssertEqual(RemoteDesktop.sanitizedFilename("  A4/H20  "), "A4H20")
        XCTAssertEqual(RemoteDesktop.sanitizedFilename("PC: #1"), "PC 1")
        XCTAssertEqual(RemoteDesktop.sanitizedFilename("///"), "Remote-PC")
        XCTAssertEqual(RemoteDesktop.sanitizedFilename("").count, "Remote-PC".count)
        XCTAssertTrue(RemoteDesktop.sanitizedFilename(String(repeating: "x", count: 200)).count <= 60)
    }
}
