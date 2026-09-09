import UIKit

/*
 * Remotedesktop via Microsoft Remote Desktop / Windows App (2.3.3).
 * iOS kann keinen eigenen RDP-Client bereitstellen → URL-Schema der
 * installierten App. Die Windows App legt beim Aufruf ein Profil an
 * (Gerätesname als Host, Benutzer vorbefüllt); das Profil bleibt auf
 * dem Gerät bestehen (gewollt – unlike the Windows desktop version it
 * is NOT deleted afterwards).
 *
 * Da kein URI-Schema ein Passwort übertragen darf (Microsoft Doku:
 * Legacy rdp:// und ms-rd:// ohne Passwort-Attribut), wird das Passwort
 * in die Zwischenablage kopiert; die Web-UI zeigt dazu einen Hinweis-Toast.
 *
 * Kandidaten (Reihenfolge):
 *   rdp://full%20address=s:<host>&username=s:<user>   (Legacy, für iOS dokumentiert)
 *   ms-rd://add/host/<host>?username=<user>&use.maximizewindow=true|false
 * Scheitern → "remote.notinstalled"; fehlender Host → "remote.nohost".
 */
enum RemoteDesktop {
    static let errNotInstalled = "remote.notinstalled"
    static let errNoHost = "remote.nohost"

    struct Result {
        let host: String
        let username: String
        let passwordCopied: Bool
        let hasPassword: Bool
    }

    enum RemoteError: Error, Equatable {
        case noHost
        case notInstalled
    }

    /// Host für die RDP-Verbindung: IP/Hostname, sonst Gerätename.
    static func hostOf(ip: String, name: String) -> String {
        let t = ip.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? name.trimmingCharacters(in: .whitespacesAndNewlines) : t
    }

    /// URI-Kandidaten in Reihenfolge: legacy `rdp://` (dokumentiert für iOS,
    /// mit `full address` + `username`), dann `ms-rd://add/host/` (Windows App).
    static func candidates(host: String, username: String, mode: String = "full") -> [String] {
        let h = encodeValue(host.trimmingCharacters(in: .whitespacesAndNewlines))
        guard !h.isEmpty else { return [] }
        let u = encodeValue(username.trimmingCharacters(in: .whitespacesAndNewlines))
        var legacy = "rdp://full%20address=s:\(h)"
        if !u.isEmpty { legacy += "&username=s:\(u)" }
        var query: [String] = ["use.maximizewindow=\(mode == "full" ? "true" : "false")"]
        if !u.isEmpty { query.insert("username=\(u)", at: 0) }
        let msrd = "ms-rd://add/host/\(h)?" + query.joined(separator: "&")
        return [legacy, msrd]
    }

    /// Wert-Escaping für URI-Attribute: wie Android (RFC 3986, ohne Sub-delims).
    static func encodeValue(_ value: String) -> String {
        let allowed = CharacterSet(charactersIn:
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~:@/")
        return value.addingPercentEncoding(withAllowedCharacters: allowed) ?? value
    }

    /// Öffnet die Windows App für das Gerät; Passwort → Zwischenablage.
    /// Wichtig: die Zwischenablage wird VOR dem Öffnen gefüllt – ab iOS 16
    /// ist der Pasteboard-Zugriff aus dem Hintergrund eingeschränkt, und die
    /// App wechselt mit `open(url)` sofort in den Hintergrund. Vorher wird
    /// per `canOpenURL` geprüft, damit bei fehlender App nichts in die
    /// Zwischenablage gelangt.
    @discardableResult
    static func open(device: Device, password: String, mode: String) async throws -> Result {
        let host = hostOf(ip: device.ip, name: device.name)
        guard !host.isEmpty else { throw RemoteError.noHost }
        let uri = candidates(host: host, username: device.username, mode: mode)
        let launched = await MainActor.run { () -> Bool in
            for u in uri {
                guard let url = URL(string: u), UIApplication.shared.canOpenURL(url) else { continue }
                if !password.isEmpty { UIPasteboard.general.string = password }
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
                return true
            }
            return false
        }
        guard launched else { throw RemoteError.notInstalled }
        return Result(host: host, username: device.username,
                      passwordCopied: !password.isEmpty, hasPassword: !password.isEmpty)
    }
}
