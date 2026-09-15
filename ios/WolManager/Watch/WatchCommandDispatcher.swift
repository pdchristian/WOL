import Foundation

/*
 * Befehls-Ausführer für die Apple Watch (iPhone-Seite). Bewusst minimales
 * Untermenge der WebView-Bridge: snapshot, wake, shutdown, statusAll, metrics.
 * Passwörter verlassen niemals das iPhone — die Watch erhält nur boolesche
 * hasPassword-Markierungen und aggregierte Anzeigedaten.
 *
 * Vertrag (WCSession sendMessage, JSON-fähige Dictionaries):
 *   Anfrage:  { "command": "wake", "id": "<deviceId>", ... }
 *   Antwort:  { "ok": true,  ...daten }   |   { "ok": false, "error": "<code>" }
 * completion wird immer auf dem Main-Queue aufgerufen.
 */
final class WatchCommandDispatcher {

    /// Zeitfenster pro Geräte-Statuscheck in statusAll (DNS/mDNS + Connect + Read).
    /// Testbar herabsetzbar; 8 s deckt einen mDNS-Fehlschlag plus Connect ab.
    var statusCheckWindow: TimeInterval = 8

    private let actions: WatchActions
    private let repo: Repo

    /// Letzter bekannter Online-Status pro Gerät (aus statusAll / WebView-
    /// Refresh). Die Watch nutzt ihn als Fallback, wenn statusAll gerade nicht
    /// durchläuft, und für den applicationContext — sonst zeigt die Watch nach
    /// jedem Neustart pauschal "offline", obwohl das iPhone die Geräte kennt.
    /// Zugriff aus mehreren Queues (Delegate-Queue, WebView-Status-Task) → Lock.
    private let statusLock = NSLock()
    private var _lastOnline: [String: Bool] = [:]

    var lastOnline: [String: Bool] {
        statusLock.lock(); defer { statusLock.unlock() }
        return _lastOnline
    }

    init(actions: WatchActions = AppContainer.shared, repo: Repo = AppContainer.shared.repo) {
        self.actions = actions
        self.repo = repo
    }

    /// Von außen gemeldete Status (z. B. WebView-Statusrefresh) übernehmen.
    func noteOnline(_ statuses: [String: Bool]) {
        statusLock.lock(); defer { statusLock.unlock() }
        _lastOnline.merge(statuses) { _, new in new }
    }

    // ── Einstiegspunkt (WatchBridgeService) ─────────────────────────────────

    func handle(_ message: [String: Any], completion: @escaping ([String: Any]) -> Void) {
        let command = (message["command"] as? String) ?? ""
        Task { [weak self] in
            guard let self else { return }
            let result = await self.run(command, message)
            DispatchQueue.main.async { completion(result) }
        }
    }

    private func run(_ command: String, _ p: [String: Any]) async -> [String: Any] {
        switch command {
        case "snapshot":
            return ok(["devices": devicesJson()])
        case "wake":
            return await performAction(pStr(p, "id")) { [actions] d in await actions.wake(device: d) }
        case "shutdown":
            return await performAction(pStr(p, "id")) { [actions] d in await actions.shutdown(device: d) }
        case "statusAll":
            return await statusAllJson()
        case "metrics":
            return await metricsJson(pStr(p, "id"))
        default:
            return err("unknown_command:\(command)")
        }
    }

    // ── Einzelne Befehle ────────────────────────────────────────────────────

    /// Geräte-Snapshot für die Watch — ohne Passwörter (nur hasPassword), ohne
    /// Zeitpläne/Logs/Settings. Felder identisch zu Bridge.deviceToJson.
    func devicesJson() -> [[String: Any]] {
        repo.snapshot.devices.map { d in
            [
                "id": d.id, "name": d.name, "mac": d.mac, "ip": d.ip,
                "username": d.username, "enabled": d.enabled,
                "hasPassword": !repo.getPassword(id: d.id).isEmpty,
                "watch": d.watchProcesses,
            ]
        }
    }

    private func performAction(_ id: String,
                               _ call: @escaping (Device) async -> Result<Void, Error>) async -> [String: Any] {
        do {
            let d = try device(id)
            let r = await call(d)
            switch r {
            case .success: return ok([:])
            case let .failure(e): return err(errorDescription(e))
            }
        } catch {
            return err(errorDescription(error))
        }
    }

    /// Host-Service-Status aller aktivierten Geräte mit IP (parallel). Jeder
    /// Check läuft durch (checkStatus checked nicht) — das Ergebnis wird als
    /// "letzter bekannter Stand" behalten und an den applicationContext der
    /// Watch weitergegeben, damit sie ohne erreichbares iPhone nicht pauschal
    /// alles auf "offline" setzt.
    ///
    /// Jeder Check hat ein hartes Zeitfenster (`statusCheckWindow`, DNS/mDNS +
    /// Connect + Read): ein einzelner langsamer Host darf statusAll nicht über
    /// das Watch-Timeout (20 s) halten, sonst friert der Online-Status komplett
    /// ein. Ein Zeitüberschreiter fehlt in der Antwort — die Watch behält dann
    /// den letzten bekannten Status des Geräts (statt es falsch als offline zu
    /// markieren).
    func statusAllJson() async -> [String: Any] {
        let devices = repo.snapshot.devices.filter { $0.enabled && !$0.ip.isEmpty }
        var online: [String: Bool] = [:]
        let window = statusCheckWindow
        await withTaskGroup(of: (String, Bool?).self) { group in
            for d in devices {
                group.addTask {
                    let r = await Self.bounded(window) { await self.actions.checkStatus(device: d) }
                    return (d.id, r)
                }
            }
            for await (id, result) in group {
                if let result { online[id] = result }
            }
        }
        noteOnline(online)
        let statuses = devices.compactMap { d -> [String: Any]? in
            guard let isOnline = online[d.id] else { return nil } // Timeout: letzter Stand behalten
            return ["id": d.id, "online": isOnline]
        }
        return ok(["statuses": statuses])
    }

    /// `work` mit Zeitfenster: liefert nil, wenn `work` länger als `seconds`
    /// braucht. `work` läuft dann als unstrukturierter Task weiter (Ergebnis
    /// wird verworfen) — nötig, weil blockierende Socket-/DNS-Aufrufe nicht
    /// abbrechbar sind und ein strukturierter Kind-Task die Antwort sonst
    /// trotzdem bis zur Fertigkeit blockieren würde.
    private static func bounded(_ seconds: TimeInterval,
                                work: @escaping @Sendable () async -> Bool) async -> Bool? {
        await withCheckedContinuation { (cont: CheckedContinuation<Bool?, Never>) in
            let once = ResumeOnce()
            Task.detached {
                let r = await work()
                if once.claim() { cont.resume(returning: r) }
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + seconds) {
                if once.claim() { cont.resume(returning: nil) }
            }
        }
    }

    /// Metriken eines Geräts (UI-Format über MetricsUI — Prozent/GB, gerundet).
    ///
    /// Die Metriken reisen als JSON-STRING (Feld "metrics_json"), nicht als
    /// Dictionary: WCSession-Antworten müssen Property-Listen sein, und
    /// MetricsUI.uiJson enthält NSNull für fehlende Werte (fehlende GPU/VRAM,
    /// Model, nicht gemessene t/s …). NSNull ist KEIN plist-Typ — die Antwort
    /// ließ sich nicht serialisieren und erreichte die Watch nie
    /// ("Keine Antwort vom Host-Service"), während das iPhone dieselben Daten
    /// als JSON an die WebView bekam und deshalb funktionierte.
    private func metricsJson(_ id: String) async -> [String: Any] {
        do {
            let d = try device(id)
            let r = await actions.metrics(device: d)
            switch r {
            case let .success(m):
                return ok(["metrics_json": Self.jsonString(MetricsUI.uiJson(m))])
            case let .failure(e): return err(errorDescription(e))
            }
        } catch {
            return err(errorDescription(error))
        }
    }

    /// Dictionary → JSON-Text (plist-sicherer Transport für verschachtelte Daten).
    static func jsonString(_ obj: [String: Any]) -> String {
        let data = (try? JSONSerialization.data(withJSONObject: obj)) ?? Data("{}".utf8)
        return String(data: data, encoding: .utf8) ?? "{}"
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    private func device(_ id: String) throws -> Device {
        guard let d = repo.device(id) else { throw BridgeError("device_not_found") }
        return d
    }

    private func pStr(_ p: [String: Any], _ key: String) -> String {
        (p[key] as? String) ?? ""
    }

    private func ok(_ data: [String: Any]) -> [String: Any] {
        var r = data
        r["ok"] = true
        return r
    }

    private func err(_ msg: String) -> [String: Any] {
        ["ok": false, "error": msg]
    }

    private func errorDescription(_ error: Error) -> String {
        (error as? BridgeError)?.msg ?? error.localizedDescription
    }
}

/// Fortschritts-Sperre: nur der erste `claim()`-Aufrufer darf eine
/// Continuation fortsetzen (work vs. Timeout laufen gegeneinander).
final class ResumeOnce: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false

    /// true, wenn sich der Aufrufer die Fortsetzung gesichert hat.
    func claim() -> Bool {
        lock.lock(); defer { lock.unlock() }
        if done { return false }
        done = true
        return true
    }
}
