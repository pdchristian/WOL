import Foundation
import WatchConnectivity

/*
 * WCSession-Client (Watch-Seite). Sende Befehle an das iPhone
 * (WatchBridgeService/WatchCommandDispatcher) und empfange Antworten.
 * Fällt zurück auf den letzten applicationContext-Snapshot, wenn das iPhone
 * nicht erreichbar ist (Handy zu Hause, Watch allein im WLAN/LTE).
 */
final class WatchService: NSObject, WCSessionDelegate, @unchecked Sendable {
    // Thread-Zugriff auf pending/lock wird über NSLock serialisiert; reachable
    // ist ein indikativer Status ohne sicherheitskritische Entscheidungen.

    static let shared = WatchService()

    /// true, wenn die letzte Anfrage das iPhone erreicht hat (oder erreichte).
    private(set) var reachable = false

    private var pending: [String: (Result<[String: Any], Error>) -> Void] = [:]
    private let lock = NSLock()

    static let contextDidChange = Notification.Name("de.wolmanager.watch.context")

    /// Zuletzt empfangener applicationContext. Bewusst das Delegate-Payload und
    /// nicht WCSession.default.applicationContext: die Property liefert (auch
    /// im Simulator) teils leere Daten, obwohl didReceiveApplicationContext
    /// den Payload bekommt. Zugriff serialisiert über `lock`.
    private var _lastContext: [String: Any] = [:]

    var lastContext: [String: Any] {
        lock.lock(); defer { lock.unlock() }
        return _lastContext
    }

    private override init() {
        super.init()
        if WCSession.isSupported() {
            _lastContext = WCSession.default.applicationContext
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    // MARK: - Anfragen

    enum WatchError: LocalizedError {
        case notReachable
        case phoneError(String)
        case badResponse

        var errorDescription: String? {
            switch self {
            case .notReachable: return Self.localized("iphone_not_reachable")
            case let .phoneError(msg): return Self.localized(msg)
            case .badResponse: return Self.localized("bad_response")
            }
        }

        /// iPhone sendet Fehler-Codes (z. B. "device_not_found") — auf der Watch
        /// über Localizable.xcstrings in Landessprache übersetzen.
        static func localized(_ key: String) -> String {
            let value = String(localized: String.LocalizationValue(key))
            return value == key ? key : value
        }
    }

    /// Befehl an das iPhone; Fehler bei Timeout/Unreachability.
    func request(_ command: [String: Any], timeout: TimeInterval = 12) async throws -> [String: Any] {
        guard WCSession.isSupported() else { throw WatchError.notReachable }
        let session = WCSession.default
        // Direkt nach dem App-Start ist die Session oft noch nicht aktiviert —
        // kurz warten, sonst zeigt die Watch beim ersten Öffnen nur den (leeren)
        // Cache, obwohl alle Geräte auf dem iPhone vorhanden sind. Bis zu 5 s:
        // die iPhone-App wird durch die erste Zustellung ggf. erst kalt im
        // Hintergrund gestartet und aktiviert ihre Session danach.
        if session.activationState != .activated {
            _ = await waitForActivation(timeout: 5)
        }
        guard session.activationState == .activated else { throw WatchError.notReachable }
        // phoneReachable kann dauern — trotzdem senden: oft antwortet das iPhone
        // über BLE/LAN auch ohne Anzeige. Timeout fängt echte Funkstille ab.
        let reply: [String: Any] = try await withCheckedThrowingContinuation { (cont: CheckedContinuation<[String: Any], Error>) in
            // Kein Main-Thread-Hop: sendMessage ist thread-safe, resolve()
            // serialisiert intern über NSLock und MainQueue-Dispatch.
            let key = UUID().uuidString
            lock.lock()
            pending[key] = { result in
                cont.resume(with: result)
            }
            lock.unlock()
            // Sicherheitsnetz: ohne Antwort (BLE-Hänger) nicht unbegrenzt warten.
            DispatchQueue.main.asyncAfter(deadline: .now() + timeout) { [weak self] in
                self?.resolve(key, with: .failure(WatchError.notReachable))
            }
            session.sendMessage(command,
                                replyHandler: { [weak self] reply in
                                    self?.resolve(key, with: .success(reply))
                                },
                                errorHandler: { [weak self] error in
                                    self?.resolve(key, with: .failure(error))
                                })
        }
        reachable = true
        if let ok = reply["ok"] as? Bool, ok == false {
            throw WatchError.phoneError((reply["error"] as? String) ?? "error")
        }
        return reply
    }

    func wake(id: String) async throws { _ = try await request(["command": "wake", "id": id]) }
    func shutdown(id: String) async throws { _ = try await request(["command": "shutdown", "id": id]) }

    /// Alle Geräte + Online-Status (Snapshot + statusAll kombiniert).
    /// Wenn statusAll nicht durchkommt (iPhone inaktiv/Funkstille), greift der
    /// letzte bekannte Status aus dem applicationContext — sonst würden nach
    /// einem Timeout pauschal alle Geräte als offline erscheinen.
    func loadDevices() async throws -> [WatchDevice] {
        // Snapshot mit langem Timeout + Retry: liegt die iPhone-App im
        // Hintergrund oder ist beendet, startet iOS sie für diese Zustellung
        // automatisch (WCSession-Doku) — der Kaltstart kostet mehrere Sekunden.
        // Ohne das Geduld-Fenster würde die Watch unnötig auf den Cache fallen.
        let snap: [String: Any]
        do {
            snap = try await request(["command": "snapshot"], timeout: 25)
        } catch {
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            snap = try await request(["command": "snapshot"], timeout: 25)
        }
        guard let rawDevices = snap["devices"] as? [[String: Any]] else { throw WatchError.badResponse }
        var devices = rawDevices.compactMap { Self.decodeDevice($0) }
        let cached = cachedContext()
        if let statusReply = try? await request(["command": "statusAll"], timeout: 20),
           let statuses = statusReply["statuses"] as? [[String: Any]] {
            let map = Dictionary(uniqueKeysWithValues: statuses.compactMap { s -> (String, Bool)? in
                guard let id = s["id"] as? String else { return nil }
                return (id, (s["online"] as? Bool) ?? false)
            })
            for i in devices.indices { devices[i].online = map[devices[i].id] ?? cached.statuses[devices[i].id] }
        } else {
            for i in devices.indices where devices[i].online == nil {
                devices[i].online = cached.statuses[devices[i].id]
            }
        }
        return devices
    }

    func metrics(id: String) async throws -> WatchMetrics {
        // Langes Zeitfenster: liegt das iPhone im Hintergrund, startet iOS die
        // Gegenstellen-App für die Zustellung erst kalt (~5-10 s); zusätzlich
        // brauchen Host-Service-Abfragen mit Watch-Einträgen (Portsonde +
        // llama-server /v1/models + /metrics) mehrere Sekunden. Mit dem
        // 12-s-Default schlug genau diese Kombination regelmäßig fehl, während
        // die iPhone-App (ohne Kaltstart) dieselbe Abfrage problemlos
        // beantwortete.
        let reply = try await request(["command": "metrics", "id": id], timeout: 25)
        guard let raw = reply["metrics"] as? [String: Any],
              let data = try? JSONSerialization.data(withJSONObject: raw) else {
            throw WatchError.badResponse
        }
        return try JSONDecoder().decode(WatchMetrics.self, from: data)
    }

    /// Letzer iPhone-Snapshot (offline-Fallback für die Geräteliste).
    func cachedDevices() -> [WatchDevice] {
        cachedContext().devices
    }

    /// Inhalt des letzten applicationContext: Geräte, letzter bekannter Status
    /// und die in der iOS-App eingestellte Listensortierung.
    struct WatchContext {
        var devices: [WatchDevice] = []
        var statuses: [String: Bool] = [:]
        var sort: String = "name"
    }

    func cachedContext() -> WatchContext {
        let ctx = lastContext
        var out = WatchContext()
        if let raw = ctx["devices"] as? [[String: Any]] {
            out.devices = raw.compactMap { Self.decodeDevice($0) }
        }
        out.statuses = ctx["statuses"] as? [String: Bool] ?? [:]
        out.sort = (ctx["sort"] as? String) ?? "name"
        return out
    }

    private static func decodeDevice(_ raw: [String: Any]) -> WatchDevice? {
        guard let data = try? JSONSerialization.data(withJSONObject: raw) else { return nil }
        return try? JSONDecoder().decode(WatchDevice.self, from: data)
    }

    private func resolve(_ key: String, with result: Result<[String: Any], Error>) {
        lock.lock()
        let work = pending.removeValue(forKey: key)
        lock.unlock()
        if case .failure = result { reachable = false }
        DispatchQueue.main.async { work?(result) }
    }

    // MARK: - Session-Aktivierung

    /// Wartet (pollend, max. `timeout` s), bis die WCSession aktiviert ist.
    /// Polling statt Delegate-Continuation: mehrere wartende Anfragen bleiben
    /// unabhängig und auslaufende Waits laufen nie in eine Fortsetzung.
    private func waitForActivation(timeout: TimeInterval) async -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if WCSession.default.activationState == .activated { return true }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        return WCSession.default.activationState == .activated
    }

    // MARK: - WCSessionDelegate

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState,
                 error: Error?) {
        // Persistierter applicationContext wird erst mit der Aktivierung geladen —
        // ohne Delegate-Callback beim Kaltstart. Einmal nachaktivieren, damit
        // AppState Sortierung/Status aus dem Kontext übernimmt.
        guard activationState == .activated else { return }
        DispatchQueue.main.async {
            NotificationCenter.default.post(name: Self.contextDidChange, object: nil)
        }
    }

    func sessionReachabilityDidChange(_ session: WCSession) {
        reachable = session.isReachable
    }

    /// iPhone → Watch: applicationContext hält Geräte, letzten Status und die
    /// Listensortierung für den Offline-Fall. AppState aktualisiert live.
    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
        lock.lock()
        _lastContext = applicationContext
        lock.unlock()
        NotificationCenter.default.post(name: Self.contextDidChange, object: nil)
    }

    func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {}
}
