import Foundation

/*
 * Datenmodelle der Watch-App — Spiegel des iPhone-Vertrags
 * (WatchCommandDispatcher): Geräte ohne Passwörter, Metriken im flachen
 * UI-Format (Prozent/GB) aus MetricsUI.uiJson.
 */

/// Geräte-Kurzprofil (Snapshot-Befehl / applicationContext).
struct WatchDevice: Identifiable, Equatable, Hashable {
    var id: String
    var name: String
    var mac: String
    var ip: String
    var username: String
    var enabled: Bool
    var hasPassword: Bool
    var watch: [String]
    /// Live-Status aus statusAll (nil = unbekannt).
    var online: Bool?
    /// true, solange die App nach dem Wake auf das Hochfahren wartet.
    var waking: Bool

    init(id: String, name: String, mac: String = "", ip: String = "", username: String = "",
         enabled: Bool = true, hasPassword: Bool = false, watch: [String] = [],
         online: Bool? = nil, waking: Bool = false) {
        self.id = id; self.name = name; self.mac = mac; self.ip = ip
        self.username = username; self.enabled = enabled; self.hasPassword = hasPassword
        self.watch = watch; self.online = online; self.waking = waking
    }
}

extension WatchDevice: Decodable {
    enum CodingKeys: String, CodingKey {
        case id, name, mac, ip, username, enabled, hasPassword, watch
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        mac = try c.decodeIfPresent(String.self, forKey: .mac) ?? ""
        ip = try c.decodeIfPresent(String.self, forKey: .ip) ?? ""
        username = try c.decodeIfPresent(String.self, forKey: .username) ?? ""
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        hasPassword = try c.decodeIfPresent(Bool.self, forKey: .hasPassword) ?? false
        watch = try c.decodeIfPresent([String].self, forKey: .watch) ?? []
        online = nil
        waking = false
    }
}

/// Metriken im UI-Format (MetricsUI.uiJson): Prozent 0–100, GB, gerundet.
struct WatchMetrics: Decodable {
    var cpu: Double?
    var ram: Double?
    var gpu: Double?
    var vram: Double?
    var uptime: Double?
    var processes: [WatchProcess]

    enum CodingKeys: String, CodingKey {
        case cpu, ram, gpu, vram, uptime, processes
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        cpu = try c.decodeIfPresent(Double.self, forKey: .cpu)
        ram = try c.decodeIfPresent(Double.self, forKey: .ram)
        gpu = try c.decodeIfPresent(Double.self, forKey: .gpu)
        vram = try c.decodeIfPresent(Double.self, forKey: .vram)
        uptime = try c.decodeIfPresent(Double.self, forKey: .uptime)
        processes = try c.decodeIfPresent([WatchProcess].self, forKey: .processes) ?? []
    }
}

/// Beobachteter Prozess (Dienst-Chip im Dashboard).
struct WatchProcess: Decodable, Identifiable, Equatable {
    var key: String
    var running: Bool
    var model: String?

    var id: String { key }

    enum CodingKeys: String, CodingKey { case key, running, model }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        key = try c.decodeIfPresent(String.self, forKey: .key) ?? ""
        running = try c.decodeIfPresent(Bool.self, forKey: .running) ?? false
        model = try c.decodeIfPresent(String.self, forKey: .model)
    }
}

/// Anzeige-Formatierungen (Uptime).
enum Fmt {
    /// Sekunden → "3d 4h" / "2h 05min" / "12min"; nil bei fehlenden Daten.
    static func uptime(_ seconds: Double?) -> String? {
        guard let seconds, seconds >= 0 else { return nil }
        let t = Int(seconds)
        let d = t / 86_400
        let h = (t % 86_400) / 3_600
        let m = (t % 3_600) / 60
        if d > 0 { return "\(d)d \(h)h" }
        if h > 0 { return String(format: "%dh %02dmin", h, m) }
        return "\(m)min"
    }
}
