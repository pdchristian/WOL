import Foundation

/*
 * Zentrale Abhängigkeiten (manuelle Composition Root, kein DI-Framework) —
 * analog AppContainer in WolApplication.kt.
 */
final class AppContainer {

    static let shared = AppContainer()

    let secure = SecureStore()
    let repo: Repo
    let hostClient = HostServiceClient()
    let scanner = NetworkScanner()

    private var ticker: Timer?
    private var lastFiredMinute = ""

    private init() {
        let base = AppContainer.dataDir()
        repo = Repo(baseDir: base, secure: secure)
    }

    static func dataDir() -> URL {
        let fm = FileManager.default
        let support = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSTemporaryDirectory())
        let dir = support.appendingPathComponent("data", isDirectory: true)
        // App-Daten für Backup/TimeMachine sichtbar halten, nicht iCloud-synchron (Geräte-Listen lokal).
        var vals = URLResourceValues()
        vals.isExcludedFromBackup = false
        var mutableDir = dir
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        try? mutableDir.setResourceValues(vals)
        return dir
    }

    // ── In-App-Zeitplan-Ticker (5 s, exakter Minute-Treffer) ───────────────

    func startScheduleTicker() {
        guard ticker == nil else { return }
        let t = Timer(timeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.tickSchedules()
        }
        RunLoop.main.add(t, forMode: .common)
        ticker = t
    }

    func stopScheduleTicker() {
        ticker?.invalidate()
        ticker = nil
    }

    private func tickSchedules() {
        let now = Date()
        let nowMs = Int64(now.timeIntervalSince1970 * 1000)
        let minuteKey = String(nowMs / 60_000)
        guard minuteKey != lastFiredMinute else { return }
        let snap = repo.snapshot
        for sched in snap.schedules where sched.enabled {
            guard ScheduleEngine.matchesMinute(sched, now) else { continue }
            guard let device = snap.devices.first(where: { $0.id == sched.deviceId }) else { continue }
            repo.updateScheduleLastRun(id: sched.id, ts: nowMs)
            Task { await Self.runAction(container: self, device: device, sched: sched) }
        }
        lastFiredMinute = minuteKey
    }

    /// Zeitplan-Änderungen übernehmen: Hintergrund-Refresh neu planen.
    func syncSchedules() {
        ScheduleScheduler.schedule()
    }

    static func runAction(container: AppContainer, device: Device, sched: ScheduleDef) async {
        if sched.isWake { _ = await container.wake(device: device) }
        else { _ = await container.shutdown(device: device) }
    }

    // ── Aktionen ────────────────────────────────────────────────────────────

    /// Einmal Wake für ein Gerät; liefert Erfolg/Fehler.
    func wake(device: Device) async -> Result<Void, Error> {
        let s = repo.snapshot.settings
        let bIp = s.broadcastIp
        let bPort = s.broadcastPort
        let r: Result<Void, Error> = await Task.detached(priority: .userInitiated) {
            do {
                _ = try MagicPacket.send(device: device, broadcastIp: bIp, port: bPort)
                return .success(())
            } catch {
                return .failure(error)
            }
        }.value
        let errMsg: String?
        switch r {
        case .success: errMsg = nil
        case let .failure(e): errMsg = e.localizedDescription
        }
        repo.log(device: device.name, level: "info", msg: errMsg == nil
            ? "Wake: Magic Packet (Port \(bPort)) gesendet"
            : "Wake fehlgeschlagen: \(errMsg ?? "?")")
        return r
    }

    /// Herunterfahren über Host-Service (SMB ist unter iOS nicht möglich).
    func shutdown(device: Device) async -> Result<Void, Error> {
        let host = device.ip
        guard !host.isEmpty else {
            return .failure(BridgeError("no ip"))
        }
        let pass = repo.getPassword(id: device.id)
        let r = await hostClient.shutdown(host: host, username: device.username, password: pass)
        switch r {
        case .ok:
            repo.log(device: device.name, level: "info", msg: "Shutdown-Befehl akzeptiert")
            return .success(())
        case let .error(msg):
            repo.log(device: device.name, level: "error", msg: "Shutdown fehlgeschlagen: \(msg)")
            return .failure(BridgeError(msg))
        }
    }

    /// Status-Check: erreichbar über Host-Service?
    func checkStatus(device: Device) async -> Bool {
        let host = device.ip
        guard !host.isEmpty else { return false }
        let res = await hostClient.status(host: host)
        if case .ok = res { return true }
        return false
    }
}

struct BridgeError: Error, LocalizedError {
    let msg: String
    init(_ msg: String) { self.msg = msg }
    var errorDescription: String? { msg }
}
