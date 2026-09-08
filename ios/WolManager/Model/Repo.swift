import Foundation

/*
 * JSON-Repository (devices/schedules/logs/settings) unter [baseDir].
 * devices.json bleibt ein JSON-ARRAY (Desktop-Kompatibilität). Passwörter werden
 * vor dem Schreiben geleert und an SecureStore (Keychain) delegiert.
 * Analog zu Repo.kt — atomares Schreiben über .tmp + Rename.
 */
final class Repo {

    struct Snapshot {
        var devices: [Device] = []
        var schedules: [ScheduleDef] = []
        var logs: [LogEntry] = []
        var settings = AppSettings()
    }

    /// Wird nach jeder Änderung mit dem neuen Snapshot aufgerufen (Main-Queue).
    var onChange: ((Snapshot) -> Void)?

    private let baseDir: URL
    private let secure: SecureStore
    private let lock = NSLock()
    private var state: Snapshot

    private let enc: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }()
    private let dec = JSONDecoder()

    init(baseDir: URL, secure: SecureStore) {
        self.baseDir = baseDir
        self.secure = secure
        self.state = Snapshot()
        reload()
    }

    private var devicesFile: URL { baseDir.appendingPathComponent("devices.json") }
    private var schedulesFile: URL { baseDir.appendingPathComponent("schedules.json") }
    private var logsFile: URL { baseDir.appendingPathComponent("logs.json") }
    private var settingsFile: URL { baseDir.appendingPathComponent("settings.json") }

    // ── Init ────────────────────────────────────────────────────────────────

    func reload() {
        try? FileManager.default.createDirectory(at: baseDir, withIntermediateDirectories: true)
        var snap = Snapshot()
        snap.devices = (readList(devicesFile, Device.self) ?? []).map { migratePasswords($0) }
        snap.schedules = readList(schedulesFile, ScheduleDef.self) ?? []
        snap.logs = readList(logsFile, LogEntry.self) ?? []
        snap.settings = readOne(settingsFile, AppSettings.self) ?? AppSettings()
        lock.lock()
        state = snap
        lock.unlock()
    }

    /// Einmalige Migration: Klartext-Passwort aus devices.json in den Keychain ziehen.
    private func migratePasswords(_ d: Device) -> Device {
        if !d.password.isEmpty {
            if secure.getPassword(deviceId: d.id).isEmpty {
                secure.setPassword(deviceId: d.id, password: d.password)
            }
            var copy = d
            copy.password = ""
            return copy
        }
        return d
    }

    private func readList<T: Decodable>(_ file: URL, _ type: T.Type) -> [T]? {
        guard let text = try? String(contentsOf: file, encoding: .utf8) else { return nil }
        return try? dec.decode([T].self, from: Data(text.utf8))
    }

    private func readOne<T: Decodable>(_ file: URL, _ type: T.Type) -> T? {
        guard let text = try? String(contentsOf: file, encoding: .utf8) else { return nil }
        return try? dec.decode(T.self, from: Data(text.utf8))
    }

    private func write<T: Encodable>(_ file: URL, _ value: T) {
        do {
            try FileManager.default.createDirectory(at: baseDir, withIntermediateDirectories: true)
            let data = try enc.encode(value)
            let tmp = baseDir.appendingPathComponent(file.lastPathComponent + ".tmp")
            try data.write(to: tmp, options: .atomic)
            // replaceItem überschreibt atomar; Ziel zuerst entfernen, falls nicht vorhanden.
            if FileManager.default.fileExists(atPath: file.path) {
                _ = try? FileManager.default.replaceItemAt(file, withItemAt: tmp)
            } else {
                try FileManager.default.moveItem(at: tmp, to: file)
            }
        } catch {
            NSLog("Repo.write failed for \(file.lastPathComponent): \(error)")
        }
    }

    // ── Zugriff ─────────────────────────────────────────────────────────────

    var snapshot: Snapshot {
        lock.lock(); defer { lock.unlock() }
        return state
    }

    private func notify() {
        let snap = snapshot
        DispatchQueue.main.async { [onChange] in onChange?(snap) }
    }

    // ── Geräte ──────────────────────────────────────────────────────────────

    @discardableResult
    func saveDevice(_ device: Device) -> Device {
        let pw = device.password
        let id = device.id.isEmpty ? UUID().uuidString : device.id
        var stored = device
        stored.id = id
        stored.password = ""
        secure.setPassword(deviceId: id, password: pw)
        lock.lock()
        var cur = state.devices
        if let idx = cur.firstIndex(where: { $0.id == id }) { cur[idx] = stored } else { cur.append(stored) }
        state.devices = cur
        lock.unlock()
        write(devicesFile, cur)
        notify()
        return stored
    }

    func deleteDevice(id: String) {
        secure.removePassword(deviceId: id)
        lock.lock()
        let cur = state.devices.filter { $0.id != id }
        let sched = state.schedules.filter { $0.deviceId != id }
        state.devices = cur
        state.schedules = sched
        lock.unlock()
        write(devicesFile, cur)
        write(schedulesFile, sched)
        notify()
    }

    func getPassword(id: String) -> String { secure.getPassword(deviceId: id) }

    func deviceName(id: String) -> String? {
        snapshot.devices.first(where: { $0.id == id })?.name
    }

    func device(_ id: String) -> Device? {
        snapshot.devices.first(where: { $0.id == id })
    }

    // ── Zeitpläne ───────────────────────────────────────────────────────────

    @discardableResult
    func saveSchedule(_ schedule: ScheduleDef) -> ScheduleDef {
        let id = schedule.id.isEmpty ? UUID().uuidString : schedule.id
        var stored = schedule
        stored.id = id
        lock.lock()
        var cur = state.schedules
        if let idx = cur.firstIndex(where: { $0.id == id }) { cur[idx] = stored } else { cur.append(stored) }
        state.schedules = cur
        lock.unlock()
        write(schedulesFile, cur)
        notify()
        return stored
    }

    func deleteSchedule(id: String) {
        lock.lock()
        let cur = state.schedules.filter { $0.id != id }
        state.schedules = cur
        lock.unlock()
        write(schedulesFile, cur)
        notify()
    }

    func updateScheduleLastRun(id: String, ts: Int64) {
        lock.lock()
        let cur = state.schedules.map { $0.id == id ? ScheduleDef(id: $0.id, deviceId: $0.deviceId,
            hour: $0.hour, minute: $0.minute, days: $0.days, enabled: $0.enabled,
            action: $0.action, lastRun: ts) : $0 }
        state.schedules = cur
        lock.unlock()
        write(schedulesFile, cur)
        notify()
    }

    // ── Protokoll ───────────────────────────────────────────────────────────

    func log(device: String, level: String, msg: String) {
        let entry = LogEntry(ts: Int64(Date().timeIntervalSince1970 * 1000), device: device, level: level, msg: msg)
        lock.lock()
        let max = max(state.settings.maxLogs, 10)
        let cur = ([entry] + state.logs).prefix(max)
        state.logs = Array(cur)
        lock.unlock()
        write(logsFile, state.logs)
        notify()
    }

    func clearLogs() {
        lock.lock()
        state.logs = []
        lock.unlock()
        write(logsFile, [LogEntry]())
        notify()
    }

    // ── Einstellungen ───────────────────────────────────────────────────────

    func saveSettings(_ settings: AppSettings) {
        lock.lock()
        state.settings = settings
        lock.unlock()
        write(settingsFile, settings)
        notify()
    }

    func resetSettings() { saveSettings(AppSettings()) }
}
