import UIKit

/*
 * Remotedesktop via Microsoft Remote Desktop / Windows App.
 * iOS kann keinen eigenen RDP-Client bereitstellen → wir übergeben die Verbindung
 * an die installierte App. Die Windows App legt beim Aufruf ein Profil an, das auf
 * dem Gerät bestehen bleibt (gewollt – im Gegensatz zur Windows-Desktop-Version der
 * App wird hier nichts wieder gelöscht).
 *
 * ── Was die Windows App (mobil) laut Microsoft-Doku kann und was nicht ──
 * Legacy-Schema `rdp://<attribut>=<typ>:<wert>&…` (gilt für macOS/iOS/Android):
 *   • `full address=s:<host>` und `username=s:<user>` werden übernommen.
 *   • Es gibt KEIN Passwort-Attribut und KEIN Friendly-/Anzeigename-Attribut.
 * `ms-rd://` ist offiziell NUR für den Windows Desktop Client (MSRDC) → auf iOS
 *   meist ohne Handler, bleibt aber als letzter Kandidat erhalten.
 *
 * ⇒ Passwort: einziger dokumentierter Weg = Zwischenablage (UI zeigt Hinweis-Toast).
 * ⇒ Anzeigename = Gerätename: nur über eine übergebene `.rdp`-Datei erreichbar
 *   (die Windows App benennt das neue Profil nach dem Dateinamen). Da iOS eine
 *   Datei nicht programmatisch in einer fremden App öffnen kann, führt die Bridge
 *   dazu das Freigabe-Sheet auf. Diese Datei enthält bewusst KEIN Passwort (mobile
 *   Clients lesen `password:` ohnehin nicht, und Klartext im Teilungspfad wäre ein
 *   unnötiges Risiko).
 *
 * ── Wichtiger Parsing-Fix ──
 * Seit iOS 17 gilt in `URL(string:)` striktes RFC-3986-Parsing: ein rohes `=`/`:`
 * im Autoritäts-Teil (z. B. `full%20address=s:host`) macht die URL `nil` → der
 * Kandidat wurde bislang still übersprungen („nicht installiert", obwohl die
 * Windows App vorhanden war). Deshalb werden die Attribut-Trenner jetzt selbst
 * prozentkodiert (`%3D`/`%3A`/`%26`); die Windows App dekodiert sie vor dem
 * Auswerten der Attribute (genau so wie sie bereits `full%20address` dekodiert).
 */
enum RemoteDesktop {
    static let errNotInstalled = "remote.notinstalled"
    static let errNoHost = "remote.nohost"

    struct Result {
        let host: String
        let username: String
        let passwordCopied: Bool
        let hasPassword: Bool
        /// true, wenn kein URI-Handler griff und stattdessen eine `.rdp`-Datei
        /// erzeugt wurde (Bridge zeigt dann das Freigabe-Sheet).
        let viaFile: Bool
        let fileUrl: URL?
        let fileName: String
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

    /// URI-Kandidaten in Reihenfolge: legacy `rdp://` (dokumentiert für iOS, mit
    /// `full address` + `username`), dann `ms-rd://add/host/` (MSRDC-Form).
    /// Alle Attribut-Trenner werden prozentkodiert, damit `URL(string:)` (iOS 17+
    /// strikt nach RFC 3986) die URI überhaupt akzeptiert.
    static func candidates(host: String, username: String, mode: String = "full") -> [String] {
        let h = encodeValue(host.trimmingCharacters(in: .whitespacesAndNewlines))
        guard !h.isEmpty else { return [] }
        let u = encodeValue(username.trimmingCharacters(in: .whitespacesAndNewlines))
        // Legacy: `full address=s:<host>` → `full%20address%3Ds%3A<host>`; der Wert
        // behält sein eigenes (bereits kodiertes) Escaping.
        var legacy = "rdp://full%20address%3Ds%3A" + h
        if !u.isEmpty { legacy += "%26username%3Ds%3A" + u }
        var query: [String] = ["use.maximizewindow=\(mode == "full" ? "true" : "false")"]
        if !u.isEmpty { query.insert("username=\(u)", at: 0) }
        let msrd = "ms-rd://add/host/\(h)?" + query.joined(separator: "&")
        return [legacy, msrd]
    }

    /// Wert-Escaping für URI-Attribute: wie Android (RFC 3986, ohne Sub-delims).
    /// `:` ist hier NICHT erlaubt, obwohl Hostnamen es enthalten dürfen (`host:3389`):
    /// Die Legacy-URI liegt ohne `?` im Autoritäts-Teil, und iOS 17+ verwirft bei
    /// rohen Doppelpunkten die gesamte URL. Prozentkodiert dekodiert die Windows App
    /// den Wert korrekt zurück.
    static func encodeValue(_ value: String) -> String {
        let allowed = CharacterSet(charactersIn:
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~@/")
        return value.addingPercentEncoding(withAllowedCharacters: allowed) ?? value
    }

    /// Inhalt einer `.rdp`-Datei (KEY:TYP:WERT, CRLF) – Format wie die Desktop-App
    /// (`wol_app/utils.py`), aber ohne Passwort: mobile Clients lesen `password:`
    /// nicht, und der Anzeigename kommt aus dem Dateinamen.
    static func buildContent(host: String, username: String, mode: String) -> String {
        var lines = [
            "full address:s:\(host.trimmingCharacters(in: .whitespacesAndNewlines))",
            // Selbstsignierte Zertifikate (typisch für xrdp/Linux) ohne Rückfrage akzeptieren.
            "authentication level:i:0",
            // Adresse nach Redirection-Hop als Serveridentität behalten (xrdp).
            "use redirection server name:i:1",
        ]
        let u = username.trimmingCharacters(in: .whitespacesAndNewlines)
        if !u.isEmpty { lines.append("username:s:\(u)") }
        lines.append("screen mode id:i:\(mode == "full" ? 1 : 2)")
        return lines.joined(separator: "\r\n") + "\r\n"
    }

    /// Dateiname (ohne Endung) aus dem Gerätenamen: dateisystemsicher; die Windows
    /// App verwendet ihn als Anzeigename des neuen Profils.
    static func sanitizedFilename(_ name: String) -> String {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let allowed = CharacterSet(charactersIn:
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 -._")
        var out = String(trimmed.unicodeScalars.filter { allowed.contains($0) })
            .trimmingCharacters(in: .whitespaces)
        if out.isEmpty { out = "Remote-PC" }
        if out.count > 60 { out = String(out.prefix(60)).trimmingCharacters(in: .whitespaces) }
        return out
    }

    /// `.rdp`-Datei in den Cache schreiben (bleibt, bis iOS den Räumungsdienst aufruft).
    static func writeRdpFile(name: String, host: String, username: String, mode: String) throws -> URL {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("rdp", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent("\(name).rdp")
        let data = buildContent(host: host, username: username, mode: mode).data(using: .utf8) ?? Data()
        try data.write(to: url, options: .atomic)
        return url
    }

    /// Öffnet die Windows App für das Gerät; Passwort → Zwischenablage.
    /// Wichtig: die Zwischenablage wird VOR dem Öffnen gefüllt – ab iOS 16
    /// ist der Pasteboard-Zugriff aus dem Hintergrund eingeschränkt, und die
    /// App wechselt mit `open(url)` sofort in den Hintergrund. Vorher wird
    /// per `canOpenURL` geprüft, damit bei fehlender App nichts in die
    /// Zwischenablage gelangt.
    ///
    /// Greift kein URI-Handler, wird eine `.rdp`-Datei erzeugt und mit
    /// `viaFile` zurückgegeben; die Bridge übergibt sie dann per Freigabe-Sheet
    /// an die Windows App (Profilname = Gerätename). Nur wenn auch das nicht
    /// möglich ist (Dateiwrite schlug fehl), meldet die Bridge
    /// "remote.notinstalled"; fehlender Host → "remote.nohost".
    @discardableResult
    static func open(device: Device, password: String, mode: String) async throws -> Result {
        let host = hostOf(ip: device.ip, name: device.name)
        guard !host.isEmpty else { throw RemoteError.noHost }
        let uri = candidates(host: host, username: device.username, mode: mode)
        let fileName = sanitizedFilename(device.name)
        let launched = await MainActor.run { () -> Bool in
            for u in uri {
                guard let url = URL(string: u), UIApplication.shared.canOpenURL(url) else { continue }
                if !password.isEmpty { UIPasteboard.general.string = password }
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
                return true
            }
            return false
        }
        if !launched {
            // Kein URI-Handler → `.rdp`-Datei für die Datei-Übergabe vorhalten.
            let url = try? writeRdpFile(name: fileName, host: host,
                                        username: device.username, mode: mode)
            if url == nil { throw RemoteError.notInstalled }
            return Result(host: host, username: device.username,
                          passwordCopied: false, hasPassword: !password.isEmpty,
                          viaFile: true, fileUrl: url, fileName: fileName)
        }
        return Result(host: host, username: device.username,
                      passwordCopied: !password.isEmpty, hasPassword: !password.isEmpty,
                      viaFile: false, fileUrl: nil, fileName: fileName)
    }
}
