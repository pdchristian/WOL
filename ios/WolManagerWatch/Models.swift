import Foundation

/*
 * Datenmodelle der Watch-App — Spiegel des iPhone-Vertrags
 * (WatchCommandDispatcher): Geräte ohne Passwörter und ohne Batch-Skripte
 * (Batches nur als id/Name in iOS-Reihenfolge), Metriken im flachen UI-Format
 * (Prozent/GB) aus MetricsUI.uiJson.
 */

/// Batch-Kurzprofil (Snapshot-Befehl / applicationContext). Bewusst nur id und
/// Name: Das Skript verlässt das iPhone nicht, ausgeführt wird auf dem iPhone
/// (Host-Service). Die Array-Reihenfolge ist die in der iOS-App eingestellte.
struct WatchBatch: Identifiable, Equatable, Hashable {
    var id: String
    var name: String
}

extension WatchBatch: Decodable {
    enum CodingKeys: String, CodingKey { case id, name }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
    }
}

/// Übersetzungshilfe für Schlüssel aus `Resources/Localizable.xcstrings`
/// (Landessprache; unbekannte Schlüssel liefern den Schlüssel selbst).
/// Format-Schlüssel („batch.done" mit %1$@/%2$@) mit `String(format:)` füllen.
enum L10n {
    static func key(_ key: String) -> String {
        let value = String(localized: String.LocalizationValue(key))
        return value == key ? key : value
    }
}

/// Ergebnis einer von der Watch gestarteten Batch-Ausführung (Push vom iPhone).
struct WatchBatchResult {
    var deviceId: String
    var batchId: String
    var name: String
    var ok: Bool
    var exitCode: Int
    var durationMs: Int64
    var error: String?

    init(_ message: [String: Any]) {
        deviceId = (message["id"] as? String) ?? ""
        batchId = (message["batchId"] as? String) ?? ""
        name = (message["name"] as? String) ?? ""
        ok = (message["ok"] as? Bool) ?? false
        exitCode = (message["exitCode"] as? Int) ?? -1
        durationMs = (message["durationMs"] as? Int).map(Int64.init)
            ?? (message["durationMs"] as? Int64) ?? 0
        error = message["error"] as? String
    }

    /// "2.3 s" für die Toast-Zeile.
    var durationText: String {
        String(format: "%.1f s", Double(durationMs) / 1000.0)
    }
}

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
    /// Batches in der Reihenfolge der iOS-App (Drag & Drop dort, nicht auf der Watch).
    var batches: [WatchBatch]
    /// Freigabe der Batch-Ausführung am Gerät (`allow_batch`).
    var allowBatch: Bool
    /// Live-Status aus statusAll (nil = unbekannt).
    var online: Bool?
    /// true, solange die App nach dem Wake auf das Hochfahren wartet.
    var waking: Bool

    init(id: String, name: String, mac: String = "", ip: String = "", username: String = "",
         enabled: Bool = true, hasPassword: Bool = false, watch: [String] = [],
         batches: [WatchBatch] = [], allowBatch: Bool = false,
         online: Bool? = nil, waking: Bool = false) {
        self.id = id; self.name = name; self.mac = mac; self.ip = ip
        self.username = username; self.enabled = enabled; self.hasPassword = hasPassword
        self.watch = watch; self.batches = batches; self.allowBatch = allowBatch
        self.online = online; self.waking = waking
    }
}

extension WatchDevice: Decodable {
    enum CodingKeys: String, CodingKey {
        case id, name, mac, ip, username, enabled, hasPassword, watch, batches, allowBatch
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
        batches = try c.decodeIfPresent([WatchBatch].self, forKey: .batches) ?? []
        allowBatch = try c.decodeIfPresent(Bool.self, forKey: .allowBatch) ?? false
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
