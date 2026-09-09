import XCTest
@testable import WolManager

/// In-Memory-Fake für Tests (kein Keychain nötig).
final class MemorySecureStore: SecureStore {
    private var store: [String: String] = [:]
    override func getPassword(deviceId: String) -> String { store[deviceId] ?? "" }
    override func setPassword(deviceId: String, password: String) {
        if password.isEmpty { store.removeValue(forKey: deviceId) } else { store[deviceId] = password }
    }
    override func removePassword(deviceId: String) { store.removeValue(forKey: deviceId) }
}

final class RepoTests: XCTestCase {

    private var dir: URL!
    private var secure: MemorySecureStore!
    private var repo: Repo!

    override func setUpWithError() throws {
        dir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("repo-test-\(UUID().uuidString)")
        secure = MemorySecureStore()
        repo = Repo(baseDir: dir, secure: secure)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    // ── Geräte ──────────────────────────────────────────────────────────────

    func testSaveDeviceMovesPasswordToSecureStore() throws {
        let saved = repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF",
                                           ip: "192.168.1.10", username: "user", password: "geheim"))
        XCTAssertEqual(saved.password, "")
        XCTAssertEqual(repo.getPassword(id: "d1"), "geheim")

        // devices.json auf Platte enthält kein Klartext-Passwort
        let text = try String(contentsOf: dir.appendingPathComponent("devices.json"), encoding: .utf8)
        XCTAssertFalse(text.contains("geheim"))
        XCTAssertTrue(text.contains("\"mac\""))

        // Reload liest konsistent
        repo.reload()
        XCTAssertEqual(repo.snapshot.devices.count, 1)
        XCTAssertEqual(repo.device("d1")?.name, "PC")
        XCTAssertEqual(repo.getPassword(id: "d1"), "geheim")
    }

    func testSaveDeviceGeneratesId() {
        let saved = repo.saveDevice(Device(name: "Ohne ID", mac: "AA:BB:CC:DD:EE:FF"))
        XCTAssertFalse(saved.id.isEmpty)
        XCTAssertNotNil(repo.device(saved.id))
    }

    func testUpdateDeviceKeepsOtherFieldsOnList() {
        repo.saveDevice(Device(id: "d1", name: "Alt", mac: "AA:BB:CC:DD:EE:FF"))
        repo.saveDevice(Device(id: "d1", name: "Neu", mac: "11:22:33:44:55:66"))
        XCTAssertEqual(repo.snapshot.devices.count, 1)
        XCTAssertEqual(repo.device("d1")?.name, "Neu")
        XCTAssertEqual(repo.device("d1")?.mac, "11:22:33:44:55:66")
    }

    func testMigratePlaintextPasswordsOnLoad() throws {
        // devices.json mit Klartext-Passwort anlegen (Windows-Export-Szenario)
        let plain = """
        [{"id":"old1","name":"ALT","mac":"AA:BB:CC:DD:EE:FF","ip":"",\
        "username":"u","password":"klar123","enabled":true}]
        """
        try plain.write(to: dir.appendingPathComponent("devices.json"), atomically: true, encoding: .utf8)

        let r2 = Repo(baseDir: dir, secure: secure)
        XCTAssertEqual(r2.device("old1")?.password, "") // Arbeitsspeicher: geleert
        XCTAssertEqual(r2.getPassword(id: "old1"), "klar123") // Keychain: migriert
    }

    func testDeleteDeviceRemovesSchedulesAndPassword() {
        repo.saveDevice(Device(id: "d1", name: "PC", mac: "AA:BB:CC:DD:EE:FF", password: "pw"))
        repo.saveSchedule(ScheduleDef(id: "s1", deviceId: "d1", hour: 7, minute: 0))
        repo.saveSchedule(ScheduleDef(id: "s2", deviceId: "other", hour: 8, minute: 0))

        repo.deleteDevice(id: "d1")
        XCTAssertNil(repo.device("d1"))
        XCTAssertEqual(repo.snapshot.schedules.map(\.id), ["s2"])
        XCTAssertEqual(repo.getPassword(id: "d1"), "")
    }

    // ── Zeitpläne ───────────────────────────────────────────────────────────

    func testScheduleCrud() {
        let s = repo.saveSchedule(ScheduleDef(id: "", deviceId: "d1", hour: 6, minute: 15,
                                              days: ["Mon"], action: "shutdown"))
        XCTAssertFalse(s.id.isEmpty)
        repo.reload()
        XCTAssertEqual(repo.snapshot.schedules.count, 1)
        XCTAssertEqual(repo.snapshot.schedules[0].minute, 15)
        XCTAssertEqual(repo.snapshot.schedules[0].action, "shutdown")

        repo.updateScheduleLastRun(id: s.id, ts: 123_456)
        XCTAssertEqual(repo.snapshot.schedules[0].lastRun, 123_456)

        repo.deleteSchedule(id: s.id)
        XCTAssertTrue(repo.snapshot.schedules.isEmpty)
    }

    func testSchedulePersistedSnakeCase() throws {
        repo.saveSchedule(ScheduleDef(id: "s1", deviceId: "d1"))
        let text = try String(contentsOf: dir.appendingPathComponent("schedules.json"), encoding: .utf8)
        XCTAssertTrue(text.contains("\"device_id\""))
        XCTAssertTrue(text.contains("\"last_run\""))
    }

    // ── Protokoll ───────────────────────────────────────────────────────────

    func testLogPrependAndTrim() {
        var settings = AppSettings()
        settings.maxLogs = 12
        repo.saveSettings(settings)
        for i in 0..<25 { repo.log(device: "D", level: "info", msg: "M\(i)") }
        let logs = repo.snapshot.logs
        XCTAssertEqual(logs.count, 12)
        XCTAssertEqual(logs.first?.msg, "M24") // neueste zuerst
        XCTAssertEqual(logs.last?.msg, "M13")
    }

    func testLogTrimNeverBelowTen() {
        var settings = AppSettings()
        settings.maxLogs = 1
        repo.saveSettings(settings)
        for i in 0..<20 { repo.log(device: "D", level: "info", msg: "N\(i)") }
        XCTAssertEqual(repo.snapshot.logs.count, 10)
    }

    func testClearLogs() {
        repo.log(device: "D", level: "info", msg: "x")
        repo.clearLogs()
        XCTAssertTrue(repo.snapshot.logs.isEmpty)
    }

    // ── Einstellungen ───────────────────────────────────────────────────────

    func testSettingsRoundtripAndReset() {
        var s = AppSettings()
        s.broadcastIp = "192.168.9.255"
        s.broadcastPort = 7000
        s.maxLogs = 500
        repo.saveSettings(s)
        repo.reload()
        XCTAssertEqual(repo.snapshot.settings.broadcastIp, "192.168.9.255")
        XCTAssertEqual(repo.snapshot.settings.broadcastPort, 7000)
        XCTAssertEqual(repo.snapshot.settings.maxLogs, 500)

        repo.resetSettings()
        XCTAssertEqual(repo.snapshot.settings, AppSettings())
    }
}
