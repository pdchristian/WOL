import UIKit
import WatchConnectivity

@main
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // BGTask-Handler MUSS hier registriert werden (vor dem ersten Schedule).
        ScheduleScheduler.register()
        // Datenverzeichnis + Repo init (Keychain-Migration läuft beim ersten Laden).
        _ = AppContainer.shared
        // Apple-Watch-Brücke (nur auf dem iPhone verfügbar).
        if WCSession.isSupported() {
            WatchBridgeService.shared.activate()
        }
        return true
    }

    // ── Szenen-Konfiguration ────────────────────────────────────────────────

    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let config = UISceneConfiguration(name: "Default", sessionRole: connectingSceneSession.role)
        config.delegateClass = SceneDelegate.self
        return config
    }

    func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {}

    // Kurzes Zurück in den Hintergrund: nächsten Hintergrund-Refresh einplanen.
    func applicationDidEnterBackground(_ application: UIApplication) {
        ScheduleScheduler.schedule()
    }
}
