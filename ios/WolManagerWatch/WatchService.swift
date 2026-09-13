import Foundation
import WatchConnectivity

/*
 * WCSession-Client (Watch-Seite). Sende Befehle an das iPhone
 * (WatchBridgeService/WatchCommandDispatcher) und empfange Antworten.
 * Fällt zurück auf den letzten applicationContext-Snapshot, wenn das iPhone
 * nicht erreichbar ist (Handy zu Hause, Watch allein im WLAN/LTE).
 */
final class WatchService: NSObject, WCSessionDelegate {

    static let shared = WatchService()

    /// true, wenn die letzte Anfrage das iPhone erreicht hat (oder erreichte).
    private(set) var reachable = false

    private var pending: [String: (Result<[String: Any], Error>) -> Void] = [:]
    private let lock = NSLock()

    private override init() {
        super.init()
        if WCSession.isSupported() {
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
        guard session.activationState == .activated else { throw WatchError.notReachable }
        // phoneReachable kann dauern — trotzdem senden: oft antwortet das iPhone
        // über BLE/LAN auch ohne Anzeige. Timeout fängt echte Funkstille ab.
        let reply: [String: Any] = try await withCheckedThrowingContinuation { cont in
            let key = UUID().uuidString
            let work = {
                self.lock.lock()
                self.pending[key] = { result in
                    cont.resume(with: result)
                }
                self.lock.unlock()
                // Sicherheitsnetz: ohne Antwort (BLE-Hänger) nicht unbegrenzt warten.
                DispatchQueue.main.asyncAfter(deadline: .now() + timeout) { [weak self] in
                    self?.resolve(key, with: .failure(WatchError.notReachable))
                }
                session.sendMessage(command,
                                    replyHandler: { reply in
                                        self.resolve(key, with: .success(reply))
                                    },
                                    errorHandler: { error in
                                        self.resolve(key, with: .failure(error))
                                    })
            }
            if Thread.isMainThread { work() } else { DispatchQueue.main.async(execute: work) }
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
    func loadDevices() async throws -> [WatchDevice] {
        let snap = try await request(["command": "snapshot"])
        guard let rawDevices = snap["devices"] as? [[String: Any]] else { throw WatchError.badResponse }
        var devices = rawDevices.compactMap { Self.decodeDevice($0) }
        if let statusReply = try? await request(["command": "statusAll"]),
           let statuses = statusReply["statuses"] as? [[String: Any]] {
            let map = Dictionary(uniqueKeysWithValues: statuses.compactMap { s -> (String, Bool)? in
                guard let id = s["id"] as? String else { return nil }
                return (id, (s["online"] as? Bool) ?? false)
            })
            for i in devices.indices { devices[i].online = map[devices[i].id] }
        }
        return devices
    }

    func metrics(id: String) async throws -> WatchMetrics {
        let reply = try await request(["command": "metrics", "id": id])
        guard let raw = reply["metrics"] as? [String: Any],
              let data = try? JSONSerialization.data(withJSONObject: raw) else {
            throw WatchError.badResponse
        }
        return try JSONDecoder().decode(WatchMetrics.self, from: data)
    }

    /// Letzer iPhone-Snapshot (offline-Fallback für die Geräteliste).
    func cachedDevices() -> [WatchDevice] {
        guard let raw = WCSession.default.applicationContext["devices"] as? [[String: Any]] else { return [] }
        return raw.compactMap { Self.decodeDevice($0) }
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

    // MARK: - WCSessionDelegate

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState,
                 error: Error?) {}

    func sessionReachabilityDidChange(_ session: WCSession) {
        reachable = session.isReachable
    }

    /// iPhone → Watch: applicationContext hält die Geräteliste für den Offline-Fall.
    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {}

    func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {}
}
