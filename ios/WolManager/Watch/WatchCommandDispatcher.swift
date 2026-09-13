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
    func statusAllJson() async -> [String: Any] {
        let devices = repo.snapshot.devices.filter { $0.enabled && !$0.ip.isEmpty }
        var online: [String: Bool] = [:]
        await withTaskGroup(of: (String, Bool).self) { group in
            for d in devices {
                group.addTask { (d.id, await self.actions.checkStatus(device: d)) }
            }
            for await (id, isOnline) in group { online[id] = isOnline }
        }
        noteOnline(online)
        let statuses = devices.map { d in
            ["id": d.id, "online": online[d.id] ?? false]
        }
        return ok(["statuses": statuses])
    }

    /// Metriken eines Geräts (UI-Format über MetricsUI — Prozent/GB, gerundet).
    private func metricsJson(_ id: String) async -> [String: Any] {
        do {
            let d = try device(id)
            let r = await actions.metrics(device: d)
            switch r {
            case let .success(m): return ok(["metrics": MetricsUI.uiJson(m)])
            case let .failure(e): return err(errorDescription(e))
            }
        } catch {
            return err(errorDescription(error))
        }
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
