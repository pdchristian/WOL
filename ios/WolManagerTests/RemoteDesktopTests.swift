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
        XCTAssertEqual(c[0], "rdp://full%20address=s:192.168.2.10&username=s:christian")
        XCTAssertEqual(c[1], "ms-rd://add/host/192.168.2.10?username=christian&use.maximizewindow=true")
    }

    func testCandidatesWithoutUserWindowMode() {
        let c = RemoteDesktop.candidates(host: "buero-pc", username: "   ", mode: "win")
        XCTAssertEqual(c[0], "rdp://full%20address=s:buero-pc")
        XCTAssertEqual(c[1], "ms-rd://add/host/buero-pc?use.maximizewindow=false")
    }

    func testCandidatesEmptyHost() {
        XCTAssertTrue(RemoteDesktop.candidates(host: "  ", username: "u").isEmpty)
    }

    func testEncodeValue() {
        XCTAssertEqual(RemoteDesktop.encodeValue("pc.lan:3389"), "pc.lan:3389")
        XCTAssertEqual(RemoteDesktop.encodeValue("user name"), "user%20name")
        XCTAssertEqual(RemoteDesktop.encodeValue("paß"), "pa%C3%9F")
    }

    func testCandidateUrlsAreParsable() {
        for uri in RemoteDesktop.candidates(host: "fractal.local", username: "ch r", mode: "full") {
            XCTAssertNotNil(URL(string: uri), "URL nicht parsebar: \(uri)")
        }
    }
}
