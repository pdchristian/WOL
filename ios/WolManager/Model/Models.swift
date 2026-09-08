import Foundation

/*
 * Datenmodelle — kompatibel zum Windows-Format (devices.json / schedules.json /
 * logs.json / settings.json). devices.json ist ein JSON-ARRAY von Device
 * (Desktop-Kompatibilität). Persistierung in snake_case, im Code camelCase.
 */

enum ConnState: String {
    case unknown = "unknown"
    case online = "online"
    case offline = "offline"
    case waking = "waking"
}

struct BatchDef: Codable, Equatable {
    var id: String = ""
    var name: String = ""
    var script: String = ""
    var timeout: Int = 120

    init(id: String = "", name: String = "", script: String = "", timeout: Int = 120) {
        self.id = id; self.name = name; self.script = script; self.timeout = timeout
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        script = try c.decodeIfPresent(String.self, forKey: .script) ?? ""
        timeout = try c.decodeIfPresent(Int.self, forKey: .timeout) ?? 120
    }
}

/// Persistiertes Geräteformat. `password` wird vor dem Schreiben geleert und
/// separat im SecureStore (Keychain) abgelegt. `shutdownMethod` wird nur der
/// Windows-Roundtrip-Kompatibilität willen mitgeführt und nie ausgewertet.
struct Device: Codable, Equatable {
    var id: String = ""
    var name: String = ""
    var mac: String = ""
    var ip: String = ""
    var username: String = ""
    var password: String = ""
    var enabled: Bool = true
    var batches: [BatchDef] = []
    var allowBatch: Bool = false
    var shutdownMethod: String = "host_service"
    var watchProcesses: [String] = []

    enum CodingKeys: String, CodingKey {
        case id, name, mac, ip, username, password, enabled, batches
        case allowBatch = "allow_batch"
        case shutdownMethod = "shutdown_method"
        case watchProcesses = "watch_processes"
    }

    init(id: String = "", name: String = "", mac: String = "", ip: String = "",
         username: String = "", password: String = "", enabled: Bool = true,
         batches: [BatchDef] = [], allowBatch: Bool = false,
         shutdownMethod: String = "host_service", watchProcesses: [String] = []) {
        self.id = id; self.name = name; self.mac = mac; self.ip = ip
        self.username = username; self.password = password; self.enabled = enabled
        self.batches = batches; self.allowBatch = allowBatch
        self.shutdownMethod = shutdownMethod; self.watchProcesses = watchProcesses
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        mac = try c.decodeIfPresent(String.self, forKey: .mac) ?? ""
        ip = try c.decodeIfPresent(String.self, forKey: .ip) ?? ""
        username = try c.decodeIfPresent(String.self, forKey: .username) ?? ""
        password = try c.decodeIfPresent(String.self, forKey: .password) ?? ""
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        batches = try c.decodeIfPresent([BatchDef].self, forKey: .batches) ?? []
        allowBatch = try c.decodeIfPresent(Bool.self, forKey: .allowBatch) ?? false
        shutdownMethod = try c.decodeIfPresent(String.self, forKey: .shutdownMethod) ?? "host_service"
        watchProcesses = try c.decodeIfPresent([String].self, forKey: .watchProcesses) ?? []
    }
}

struct ScheduleDef: Codable, Equatable {
    var id: String = ""
    var deviceId: String = ""
    var hour: Int = 0
    var minute: Int = 0
    var days: [String] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    var enabled: Bool = true
    var action: String = "wake"
    var lastRun: Int64 = 0

    var isWake: Bool { action.lowercased() != "shutdown" }

    enum CodingKeys: String, CodingKey {
        case id, hour, minute, days, enabled, action
        case deviceId = "device_id"
        case lastRun = "last_run"
    }

    init(id: String = "", deviceId: String = "", hour: Int = 0, minute: Int = 0,
         days: [String] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
         enabled: Bool = true, action: String = "wake", lastRun: Int64 = 0) {
        self.id = id; self.deviceId = deviceId; self.hour = hour; self.minute = minute
        self.days = days; self.enabled = enabled; self.action = action; self.lastRun = lastRun
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        deviceId = try c.decodeIfPresent(String.self, forKey: .deviceId) ?? ""
        hour = try c.decodeIfPresent(Int.self, forKey: .hour) ?? 0
        minute = try c.decodeIfPresent(Int.self, forKey: .minute) ?? 0
        days = try c.decodeIfPresent([String].self, forKey: .days) ?? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        action = try c.decodeIfPresent(String.self, forKey: .action) ?? "wake"
        lastRun = try c.decodeIfPresent(Int64.self, forKey: .lastRun) ?? 0
    }
}

struct LogEntry: Codable, Equatable {
    var ts: Int64 = 0
    var device: String = ""
    var level: String = "info"
    var msg: String = ""

    init(ts: Int64 = 0, device: String = "", level: String = "info", msg: String = "") {
        self.ts = ts; self.device = device; self.level = level; self.msg = msg
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ts = try c.decodeIfPresent(Int64.self, forKey: .ts) ?? 0
        device = try c.decodeIfPresent(String.self, forKey: .device) ?? ""
        level = try c.decodeIfPresent(String.self, forKey: .level) ?? "info"
        msg = try c.decodeIfPresent(String.self, forKey: .msg) ?? ""
    }
}

struct AppSettings: Codable, Equatable {
    var broadcastIp: String = "255.255.255.255"
    var broadcastPort: Int = 9
    var language: String = ""          // "" = Systemsprache
    var displayMode: String = "auto"
    var autoUpdate: Bool = true
    var interval: String = "168"       // Prüfintervall in Stunden
    var maxLogs: Int = 100
    var defaultShutdownMethod: String = "host_service"

    enum CodingKeys: String, CodingKey {
        case broadcastIp = "broadcast_ip"
        case broadcastPort = "broadcast_port"
        case language
        case displayMode = "display_mode"
        case autoUpdate = "auto_update"
        case interval
        case maxLogs = "max_logs"
        case defaultShutdownMethod = "default_shutdown_method"
    }

    init(broadcastIp: String = "255.255.255.255", broadcastPort: Int = 9, language: String = "",
         displayMode: String = "auto", autoUpdate: Bool = true, interval: String = "168",
         maxLogs: Int = 100, defaultShutdownMethod: String = "host_service") {
        self.broadcastIp = broadcastIp; self.broadcastPort = broadcastPort; self.language = language
        self.displayMode = displayMode; self.autoUpdate = autoUpdate; self.interval = interval
        self.maxLogs = maxLogs; self.defaultShutdownMethod = defaultShutdownMethod
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        broadcastIp = try c.decodeIfPresent(String.self, forKey: .broadcastIp) ?? "255.255.255.255"
        broadcastPort = try c.decodeIfPresent(Int.self, forKey: .broadcastPort) ?? 9
        language = try c.decodeIfPresent(String.self, forKey: .language) ?? ""
        displayMode = try c.decodeIfPresent(String.self, forKey: .displayMode) ?? "auto"
        autoUpdate = try c.decodeIfPresent(Bool.self, forKey: .autoUpdate) ?? true
        interval = try c.decodeIfPresent(String.self, forKey: .interval) ?? "168"
        maxLogs = try c.decodeIfPresent(Int.self, forKey: .maxLogs) ?? 100
        defaultShutdownMethod = try c.decodeIfPresent(String.self, forKey: .defaultShutdownMethod) ?? "host_service"
    }
}

/// Vom Netzwerk-Scanner gefundener Host (MAC bleibt auf iOS leer).
struct DiscoveredHost: Equatable {
    var hostname: String
    var ipv4: String
    var mac: String = ""
    var openPorts: [Int] = []
    var known: Bool = false
}

// ── Host-Service: metrics / run_batch (Wire-Format v4, snake_case) ──────────

struct MetricsSnapshot: Codable, Equatable {
    var protocolVersion: Int = 0
    var hostname: String = ""
    var cpu: Double?
    var cpuCount: Int?
    var ramUsed: Double?
    var ramTotal: Double?
    var uptime: Double?
    var gpu: Double?
    var vramUsed: Double?
    var vramTotal: Double?
    var gpuName: String?
    var processes: [String: WatchInfo] = [:]

    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol"
        case hostname, cpu
        case cpuCount = "cpu_count"
        case ramUsed = "ram_used"
        case ramTotal = "ram_total"
        case uptime, gpu
        case vramUsed = "vram_used"
        case vramTotal = "vram_total"
        case gpuName = "gpu_name"
        case processes
    }
}

/// Ein Eintrag aus metrics.processes.
struct WatchInfo: Codable, Equatable {
    var running: Bool = false
    var count: Int?
    var pid: Int?
    var cpu: Double?
    var ram: Double?
    var uptime: Double?
    var model: String?
    var apiPort: Int?
    var apiPortOpen: Bool?
    var models: [String] = []

    enum CodingKeys: String, CodingKey {
        case running, count, pid, cpu, ram, uptime, model
        case apiPort = "api_port"
        case apiPortOpen = "api_port_open"
        case models
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        running = try c.decodeIfPresent(Bool.self, forKey: .running) ?? false
        count = try c.decodeIfPresent(Int.self, forKey: .count)
        pid = try c.decodeIfPresent(Int.self, forKey: .pid)
        cpu = try c.decodeIfPresent(Double.self, forKey: .cpu)
        ram = try c.decodeIfPresent(Double.self, forKey: .ram)
        uptime = try c.decodeIfPresent(Double.self, forKey: .uptime)
        model = try c.decodeIfPresent(String.self, forKey: .model)
        apiPort = try c.decodeIfPresent(Int.self, forKey: .apiPort)
        apiPortOpen = try c.decodeIfPresent(Bool.self, forKey: .apiPortOpen)
        models = try c.decodeIfPresent([String].self, forKey: .models) ?? []
    }
}

/// Antwort des Host-Service-Befehls "run_batch".
struct BatchResult: Codable, Equatable {
    var exitCode: Int = -1
    var stdout: String = ""
    var stderr: String = ""
    var durationMs: Int64 = 0
    var truncated: Bool = false

    enum CodingKeys: String, CodingKey {
        case exitCode = "exit_code"
        case stdout, stderr
        case durationMs = "duration_ms"
        case truncated
    }
}
