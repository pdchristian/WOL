import XCTest
@testable import WolManager

/*
 * WatchCommandDispatcher: Vertrag (ok/error), Passwort-Freiheit und Delegation.
 * Netzwerk wird über FakeWatchActions ausgeblendet; Repo läuft auf einem
 * temporären Verzeichnis mit MemorySecureStore (siehe RepoTests).
 */
final class FakeWatchActions: WatchActions {
    var wakeResult: Result<Void, Error> = .success(())
    var shutdownResult: Result<Void, Error> = .success(())
    var statusOnlineIds: Set<String> = []
    var metricsResult: Result<MetricsSnapshot, Error> = .success(MetricsSnapshot(protocolVersion: 5, hostname: "PC"))
    /// Geräte-IDs, deren Statuscheck (sekundenlang) blockiert — für Timeout-Tests.
    var statusBlockIds: Set<String> = []

    private(set) var wakeCalls: [Device] = []
    private(set) var shutdownCalls: [Device] = []
    private(set) var statusCalls: [Device] = []
    private(set) var metricsCalls: [Device] = []

    func wake(device: Device) async -> Result<Void, Error> {
        wakeCalls.append(device); return wakeResult
    }
    func shutdown(device: Device) async -> Result<Void, Error> {
        shutdownCalls.append(device); return shutdownResult
    }
    func checkStatus(device: Device) async -> Bool {
        statusCalls.append(device)
        if statusBlockIds.contains(device.id) {
            try? await Task.sleep(nanoseconds: 30_000_000_000)
            return false
        }
        return statusOnlineIds.contains(device.id)
    }
    func metrics(device: Device) async -> Result<MetricsSnapshot, Error> {
        metricsCalls.append(device); return metricsResult
    }
}

final class WatchCommandDispatcherTests: XCTestCase {

    private var dir: URL!
    private var repo: Repo!
    private var fake: FakeWatchActions!
    private var dispatcher: WatchCommandDispatcher!

    override func setUpWithError() throws {
        dir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("watch-test-\(UUID().uuidString)")
        repo = Repo(baseDir: dir, secure: MemorySecureStore())
        fake = FakeWatchActions()
        dispatcher = WatchCommandDispatcher(actions: fake, repo: repo)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    /// handle() synchron warten lassen (completion kommt auf der Main-Queue).
    private func send(_ message: [String: Any]) -> [String: Any] {
        let exp = expectation(description: "reply")
        var result: [String: Any] = [:]
        dispatcher.handle(message) { reply in
            result = reply
            exp.fulfill()
        }
        wait(for: [exp], timeout: 5.0)
        return result
    }

    // ── snapshot ────────────────────────────────────────────────────────────

    func testSnapshotOmitsPasswords() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF",
                               ip: "192.168.1.10", username: "u", password: "sekret",
                               watchProcesses: ["llama-server"]))
        let reply = send(["command": "snapshot"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        let devices = try XCTUnwrap(reply["devices"] as? [[String: Any]])
        XCTAssertEqual(devices.count, 1)
        let d = try XCTUnwrap(devices.first)
        XCTAssertEqual(d["id"] as? String, "d1")
        XCTAssertEqual(d["hasPassword"] as? Bool, true)
        XCTAssertEqual(d["watch"] as? [String], ["llama-server"])
        // Kein Passwort-Feld — und der Klartext taucht nirgends auf.
        XCTAssertNil(d["password"])
        let data = try JSONSerialization.data(withJSONObject: reply)
        let text = String(data: data, encoding: .utf8) ?? ""
        XCTAssertFalse(text.contains("sekret"))
    }

    func testUnknownCommand() {
        let reply = send(["command": "deleteAll"])
        XCTAssertEqual(reply["ok"] as? Bool, false)
        XCTAssertEqual(reply["error"] as? String, "unknown_command:deleteAll")
    }

    /// Alle in der iOS-App konfigurierten Geräte erreichen die Watch — auch
    /// deaktivierte und ohne IP (sie fehlen sonst still in der Liste).
    func testSnapshotIncludesAllConfiguredDevices() throws {
        repo.saveDevice(Device(id: "d1", name: "Aktiv", mac: "AA:BB:CC:DD:EE:01", ip: "192.168.1.10"))
        repo.saveDevice(Device(id: "d2", name: "Ohne IP", mac: "AA:BB:CC:DD:EE:02", ip: ""))
        repo.saveDevice(Device(id: "d3", name: "Deaktiviert", mac: "AA:BB:CC:DD:EE:03",
                               ip: "192.168.1.12", enabled: false))
        let reply = send(["command": "snapshot"])
        let devices = try XCTUnwrap(reply["devices"] as? [[String: Any]])
        XCTAssertEqual(Set(devices.compactMap { $0["id"] as? String }), ["d1", "d2", "d3"])
    }

    // ── wake / shutdown ─────────────────────────────────────────────────────

    func testWakeDelegatesToActions() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF"))
        let reply = send(["command": "wake", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        XCTAssertEqual(fake.wakeCalls.map(\.id), ["d1"])
    }

    func testWakeUnknownDevice() {
        let reply = send(["command": "wake", "id": "nope"])
        XCTAssertEqual(reply["ok"] as? Bool, false)
        XCTAssertEqual(reply["error"] as? String, "device_not_found")
        XCTAssertTrue(fake.wakeCalls.isEmpty)
    }

    func testWakeFailureReturnsError() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF"))
        fake.wakeResult = .failure(BridgeError("send failed"))
        let reply = send(["command": "wake", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, false)
        XCTAssertEqual(reply["error"] as? String, "send failed")
    }

    func testShutdownDelegatesToActions() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF", ip: "10.0.0.5"))
        let reply = send(["command": "shutdown", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        XCTAssertEqual(fake.shutdownCalls.map(\.id), ["d1"])
    }

    // ── statusAll ───────────────────────────────────────────────────────────

    func testStatusAllOnlyEnabledWithIp() throws {
        repo.saveDevice(Device(id: "on", name: "A", mac: "AA", ip: "10.0.0.1", enabled: true))
        repo.saveDevice(Device(id: "off", name: "B", mac: "BB", ip: "10.0.0.2", enabled: false))
        repo.saveDevice(Device(id: "nip", name: "C", mac: "CC", ip: "", enabled: true))
        fake.statusOnlineIds = ["on"]

        let reply = send(["command": "statusAll"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        let statuses = try XCTUnwrap(reply["statuses"] as? [[String: Any]])
        XCTAssertEqual(Set(statuses.map { $0["id"] as? String }), Set(["on"]))
        XCTAssertEqual(statuses.first?["online"] as? Bool, true)
    }

    /// Ein blockierender Host darf die Statusrunde nicht anhalten: die Antwort
    /// kommt nach dem Zeitfenster, der Blockierer fehlt (Watch behält seinen
    /// letzten Stand), die übrigen Geräte werden korrekt gemeldet.
    func testStatusAllSkipsBlockedDevice() throws {
        repo.saveDevice(Device(id: "fast", name: "Fast", mac: "AA", ip: "10.0.0.1", enabled: true))
        repo.saveDevice(Device(id: "slow", name: "Slow", mac: "BB", ip: "10.0.0.2", enabled: true))
        fake.statusOnlineIds = ["fast"]
        fake.statusBlockIds = ["slow"]
        dispatcher.statusCheckWindow = 0.5

        let start = Date()
        let reply = send(["command": "statusAll"])
        let elapsed = Date().timeIntervalSince(start)
        XCTAssertEqual(reply["ok"] as? Bool, true)
        XCTAssertLessThan(elapsed, 3, "Antwort muss nach dem Zeitfenster kommen")
        let statuses = try XCTUnwrap(reply["statuses"] as? [[String: Any]])
        XCTAssertEqual(statuses.count, 1)
        XCTAssertEqual(statuses.first?["id"] as? String, "fast")
        XCTAssertEqual(statuses.first?["online"] as? Bool, true)
    }

    // ── metrics ─────────────────────────────────────────────────────────────

    /// Status-Letzter-Stand-Merge: späteres "online" überschreibt frühere "false".
    func testNoteOnlineKeepsLatestStatus() {
        dispatcher.noteOnline(["d1": false])
        dispatcher.noteOnline(["d1": true, "d2": false])
        XCTAssertEqual(dispatcher.lastOnline["d1"], true)
        XCTAssertEqual(dispatcher.lastOnline["d2"], false)
    }

    func testMetricsReturnsUiFormat() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA", ip: "10.0.0.1",
                               watchProcesses: ["llama-server"]))
        let gb = 1024.0 * 1024.0 * 1024.0
        fake.metricsResult = .success(MetricsSnapshot(protocolVersion: 5, hostname: "PC",
                                                      cpu: 42, ramUsed: 8 * gb, ramTotal: 32 * gb))
        let reply = send(["command": "metrics", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        // Metriken reisen als JSON-String (WCSession-verträglich, siehe Dispatcher).
        let json = try XCTUnwrap(reply["metrics_json"] as? String)
        let m = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(json.utf8)) as? [String: Any])
        XCTAssertEqual(m["cpu"] as? Double, 42)
        XCTAssertEqual(m["ram"] as? Double, 25)
        XCTAssertEqual(m["ramUsedGB"] as? Double, 8)
        XCTAssertEqual(m["ramTotalGB"] as? Double, 32)
        XCTAssertEqual(fake.metricsCalls.map(\.id), ["d1"])
    }

    /// Regression: die Metrics-Antwort MUSS eine Property-List sein — WCSession
    /// kann Dictionaries mit NSNull nicht serialisieren ("property lists cannot
    /// contain objects of type 'CFNull'") und liefert dann nichts zurück
    /// (Watch: "Keine Antwort vom Host-Service"). uiJson enthält fast immer
    /// NSNull (fehlende GPU/VRAM/model/t/s) → JSON-String-Transport.
    func testMetricsReplyIsPropertyListSerializable() throws {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA", ip: "10.0.0.1",
                               watchProcesses: ["llama-swap.exe:8080"]))
        // Snapshot ohne GPU/VRAM/Modell → uiJson produziert NSNull-Einträge.
        let snap = MetricsSnapshot(protocolVersion: 5, hostname: "PC", cpu: 1)
        fake.metricsResult = .success(snap)
        let reply = send(["command": "metrics", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        XCTAssertNotNil(try? PropertyListSerialization.data(fromPropertyList: reply,
                                                            format: .binary, options: 0),
                        "WCSession-Antwort muss plist-fähig sein")
        // uiJson enthält tatsächlich NSNull (GPU/VRAM fehlen) …
        XCTAssertTrue(MetricsUI.uiJson(snap).values.contains { $0 is NSNull })
        // … und das alte Dictionary-Format wäre daran gescheitert.
        let legacy: [String: Any] = ["ok": true, "metrics": MetricsUI.uiJson(snap)]
        XCTAssertNil(try? PropertyListSerialization.data(fromPropertyList: legacy,
                                                         format: .binary, options: 0))
    }

    func testMetricsErrorPath() {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA", ip: "10.0.0.1"))
        fake.metricsResult = .failure(BridgeError("host_unreachable"))
        let reply = send(["command": "metrics", "id": "d1"])
        XCTAssertEqual(reply["ok"] as? Bool, false)
        XCTAssertEqual(reply["error"] as? String, "host_unreachable")
    }

    func testMetricsUnknownDevice() {
        let reply = send(["command": "metrics", "id": "nope"])
        XCTAssertEqual(reply["ok"] as? Bool, false)
        XCTAssertEqual(reply["error"] as? String, "device_not_found")
    }
}
