import Foundation
import WatchConnectivity

/*
 * WCSession-Brücke (iPhone-Seite) für die Apple Watch App.
 *  - aktiviert die Session, sobald ein gepaarter Watch vorhanden ist
 *  - routed sendMessage-Nachrichten an WatchCommandDispatcher
 *  - hält applicationContext mit einem Geräte-Snapshot (ohne Passwörter)
 *    frisch, damit die Watch auch ohne erreichbares iPhone zeigt, was sie weiß
 * Activation erfolgt zentral über AppDelegate (WCSession.isSupported()).
 */
final class WatchBridgeService: NSObject, WCSessionDelegate {

    static let shared = WatchBridgeService()

    private let dispatcher = WatchCommandDispatcher()
    private var activated = false

    // MARK: - Aktivierung

    /// Nur aufrufen, wenn WCSession.isSupported() (also auf dem iPhone).
    func activate() {
        guard WCSession.isSupported(), !activated else { return }
        activated = true
        let session = WCSession.default
        session.delegate = self
        session.activate()

        // Geräteänderungen (auch vom WebView-Bridge) → Snapshot zur Watch.
        container().repo.onChange = { [weak self] _ in
            self?.syncApplicationContext()
        }
    }

    private func container() -> AppContainer { .shared }

    /// Watch → iPhone: gemeldete Status übernehmen, damit der Snapshot (und
    /// damit der Offline-Fallback der Watch) den letzten Stand enthält.
    func noteOnline(_ statuses: [String: Bool]) {
        dispatcher.noteOnline(statuses)
    }

    // MARK: - applicationContext

    /// Geräte-Snapshot (ohne Passwörter) + letzter bekannter Online-Status +
    /// Listensortierung als Hintergrunddaten für die Watch, damit sie auch ohne
    /// erreichbares iPhone aktuelle Karten in der richtigen Reihenfolge zeigt.
    /// Wird auch vom SceneDelegate beim Wechsel in den Vordergrund aufgerufen,
    /// damit die Watch nach Repo-reload() (fremde Schreibzugriffe) den
    /// aktuellen Bestand aller konfigurierten Geräte erhält.
    func syncApplicationContext() {
        guard activated, WCSession.default.activationState == .activated else { return }
        let devices = container().repo.snapshot.devices.map { d in
            [
                "id": d.id, "name": d.name, "mac": d.mac, "ip": d.ip,
                "username": d.username, "enabled": d.enabled,
                "hasPassword": !container().repo.getPassword(id: d.id).isEmpty,
                "watch": d.watchProcesses,
            ] as [String: Any]
        }
        let payload: [String: Any] = [
            "devices": devices,
            "statuses": dispatcher.lastOnline,
            "sort": container().repo.snapshot.settings.deviceSort,
            "syncedAt": Date().timeIntervalSince1970,
        ]
        do {
            try WCSession.default.updateApplicationContext(payload)
        } catch {
            NSLog("WatchBridgeService: updateApplicationContext fehlgeschlagen: \(error)")
        }
    }

    // MARK: - WCSessionDelegate

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState,
                 error: Error?) {
        if activationState == .activated {
            // Nach Reconnect: aktuellen Stand nachliefern.
            syncApplicationContext()
        }
    }

    /// Watch → iPhone: Befehle ausführen und Antwort zurückschicken.
    func session(_ session: WCSession, didReceiveMessage message: [String: Any],
                 replyHandler: @escaping ([String: Any]) -> Void) {
        dispatcher.handle(message) { [weak self] reply in
            replyHandler(reply)
            // Nach Statusfragen: letzten Stand sofort als Snapshot nachliefern.
            if (message["command"] as? String) == "statusAll" {
                self?.syncApplicationContext()
            }
        }
    }

    /// Watch → iPhone: fire-and-forget (z. B. Status-Refresh nach Wake).
    func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        // Keine Antworten ohne replyHandler nötig — Bewusstsein hält die API-Fläche klein.
    }

    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {}

    func sessionDidBecomeInactive(_ session: WCSession) {}

    func sessionDidDeactivate(_ session: WCSession) {
        // Pairing-Wechsel: Session sofort wieder aktivieren.
        WCSession.default.activate()
    }
}
