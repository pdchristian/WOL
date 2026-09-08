import UIKit

/*
 * Szene: ein Fenster, Vollbild, WebViewController als Root.
 * Safe Areas werden durchgelassen — die CSS-UI (env(safe-area-inset-*)) regelt die Abstände.
 */
class SceneDelegate: UIResponder, UIWindowSceneDelegate {

    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
               options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = (scene as? UIWindowScene) else { return }

        let window = UIWindow(windowScene: windowScene)
        window.rootViewController = WebViewController()
        window.overrideUserInterfaceStyle = .unspecified // System-Theme folgen (displayMode "auto")
        self.window = window
        window.makeKeyAndVisible()
    }

    func sceneDidDisconnect(_ scene: UIScene) {}

    func sceneDidBecomeActive(_ scene: UIScene) {
        AppContainer.shared.startScheduleTicker()
    }

    func sceneWillResignActive(_ scene: UIScene) {}

    func sceneWillEnterForeground(_ scene: UIScene) {
        AppContainer.shared.repo.reload()
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        AppContainer.shared.stopScheduleTicker()
        ScheduleScheduler.schedule()
    }
}
