import UIKit

/*
 * Remotedesktop via Microsoft Remote Desktop / Windows App (ms-rd://).
 * iOS kann keinen eigenen RDP-Client bereitstellen → URL-Schema der
 * installierten App. Scheitern (nicht installiert) → Fehler "remote.notinstalled",
 * den die Web-UI als Toast anzeigt.
 *
 * Schema (Microsoft Remote Desktop / Windows App):
 *   ms-rd://add/host/<host>?use.maximizewindow=true|false
 */
enum RemoteDesktop {

    /// Öffnet eine RDP-Sitzung auf dem Gerät. Vollbild oder Fenster.
    @discardableResult
    static func open(device: Device, mode: String, from viewController: UIViewController) -> Bool {
        let host = device.ip.isEmpty ? device.name : device.ip
        guard !host.isEmpty else { return false }

        let maximize = mode == "full" ? "true" : "false"
        let encoded = host.addingPercentEncoding(withAllowedCharacters: .urlHostAllowed) ?? host
        guard let url = URL(string: "ms-rd://add/host/\(encoded)?use.maximizewindow=\(maximize)"),
              UIApplication.shared.canOpenURL(url) else {
            return false
        }
        UIApplication.shared.open(url, options: [:], completionHandler: nil)
        return true
    }
}
