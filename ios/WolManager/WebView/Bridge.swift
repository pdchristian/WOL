import Foundation
import WebKit

/* Was die Hülle (WebViewController) der Bridge bereitstellen muss: Document-Picker. */
protocol BridgeHost: AnyObject {
    func exportDocument(suggestedName: String, data: Data, completion: @escaping (Bool) -> Void)
    func openDocument(completion: @escaping (URL?) -> Void)
}

/*
 * JS ↔ native Brücke — 1:1-Port von Bridge.kt.
 * JS ruft `Android.call(callId, method, paramsJson)`; das Ergebnis kommt asynchron
 * über `window.__nativeResult(callId, {ok,data|error})` zurück. Länger laufende
 * Vorgänge senden zusätzlich Events über `window.__nativeEvent({...})`.
 *
 * Das JSON-Gegenstück nach JS ist bewusst camelCase/flach (UI-Vertrag), unabhängig
 * vom Windows-Schlangenformat, das der Repo persistiert.
 */
final class Bridge: NSObject, WKScriptMessageHandler {

    weak var webView: WKWebView?
    private weak var host: BridgeHost?
    private let container: AppContainer
    private var scanRunning = false

    /// HTML meldet offenes Sheet/Overlay → Zurück-Geste schließt erst dieses.
    private(set) var sheetOpen = false

    init(container: AppContainer, host: BridgeHost) {
        self.container = container
        self.host = host
    }

    // ── Injektion (WKUserScript @documentStart, VOR bridge.js) ─────────────

    static var userScript: WKUserScript {
        let source = """
        window.Android = {
            call: function (id, method, params) {
                window.webkit.messageHandlers.Android.postMessage({ id: id, method: method, params: params });
            },
            setSheetOpen: function (open) {
                window.webkit.messageHandlers.AndroidSetSheet.postMessage(open ? 1 : 0);
            }
        };
        """
        return WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
    }

    // ── Einstiegspunkt aus JS ───────────────────────────────────────────────

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        switch message.name {
        case "Android":
            guard let body = message.body as? [String: Any],
                  let idNum = body["id"] as? NSNumber,
                  let method = body["method"] as? String else { return }
            let callId = idNum.intValue
            let paramsJson = (body["params"] as? String) ?? ""
            let p = parseParams(paramsJson)
            Task { [weak self] in
                guard let self else { return }
                do {
                    let data = try await self.dispatch(method, p)
                    self.postResult(callId, ["ok": true, "data": data])
                } catch {
                    self.postResult(callId, ["ok": false, "error": (error as? BridgeError)?.msg
                        ?? error.localizedDescription])
                }
            }
        case "AndroidSetSheet":
            let open = (message.body as? Int).map { $0 != 0 } ?? ((message.body as? Bool) ?? false)
            sheetOpen = open
        default:
            break
        }
    }

    private func parseParams(_ s: String) -> [String: Any] {
        let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, let data = trimmed.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        return obj
    }

    // ── Dispatch (identische Methodentabelle wie Kotlin) ───────────────────

    private func dispatch(_ method: String, _ p: [String: Any]) async throws -> Any {
        switch method {
        case "snapshot": return try snapshotJson()
        case "info": return infoJson()
        case "saveDevice":
            container.repo.saveDevice(parseDevice(p))
            return devicesJson()
        case "deleteDevice":
            container.repo.deleteDevice(id: pStr(p, "id"))
            return devicesJson()
        case "getPassword":
            return container.repo.getPassword(id: pStr(p, "id"))
        case "saveSchedule":
            container.repo.saveSchedule(parseSchedule(p))
            container.syncSchedules()
            return schedulesJson()
        case "deleteSchedule":
            container.repo.deleteSchedule(id: pStr(p, "id"))
            container.syncSchedules()
            return schedulesJson()
        case "saveSettings":
            container.repo.saveSettings(parseSettings(p))
            return true
        case "resetSettings":
            container.repo.resetSettings()
            return true
        case "clearLogs":
            container.repo.clearLogs()
            return logsJson()
        case "log":
            container.repo.log(device: pStr(p, "device"), level: pStr(p, "level"), msg: pStr(p, "msg"))
            return true
        case "wake":
            let r = await container.wake(device: try device(pStr(p, "id")))
            return try rResult(r)
        case "shutdown":
            let r = await container.shutdown(device: try device(pStr(p, "id")))
            return try rResult(r)
        case "status":
            return await container.checkStatus(device: try device(pStr(p, "id")))
        case "ping":
            let d = try device(pStr(p, "id"))
            let diag = await container.hostClient.diagnose(host: d.ip.isEmpty ? d.mac : d.ip)
            var candidates: [[String: Any]] = []
            for c in diag.candidates {
                candidates.append(["address": c.address, "ok": c.ok,
                                   "rttMs": NSNumber(value: c.rttMs), "error": c.error])
            }
            let anyOk = diag.candidates.contains { $0.ok }
            return ["host": diag.host, "resolved": diag.resolved,
                    "resolveError": diag.resolveError, "ok": anyOk,
                    "candidates": candidates]
        case "metrics":
            return try await metricsJson(pStr(p, "id"))
        case "runBatch":
            return try await runBatchJson(pStr(p, "id"), pStr(p, "batchId"))
        case "scanIfaces":
            return ifacesJson()
        case "scanStart":
            startScan()
            return true
        case "scanStop":
            container.scanner.cancel()
            return true
        case "wakeAll":
            startWakeAll()
            return true
        case "refreshStatus":
            startRefreshStatus()
            return true
        case "exportDevices":
            exportDevices()
            return true
        case "exportCsv":
            exportCsv()
            return true
        case "importDevices":
            importDevices()
            return true
        case "updateCheck":
            return try await updateCheckJson()
        case "vibrate":
            let ms = (p["ms"] as? Int) ?? ((p["ms"] as? Double).map { Int($0) }) ?? 12
            Haptics.vibrate(ms: ms)
            return true
        case "remote":
            let d = try device(pStr(p, "id"))
            let mode = pStr(p, "mode")
            let ok = await MainActor.run { () -> Bool in
                guard let root = self.webView?.window?.rootViewController else { return false }
                return RemoteDesktop.open(device: d, mode: mode, from: Self.topViewController(root))
            }
            if ok { return true }
            throw BridgeError("remote.notinstalled")
        default:
            throw BridgeError("unknown_method:\(method)")
        }
    }

    private static func topViewController(_ vc: UIViewController) -> UIViewController {
        if let nav = vc as? UINavigationController, let top = nav.topViewController { return top }
        if let pres = vc.presentedViewController { return topViewController(pres) }
        return vc
    }

    // ── Snapshot ────────────────────────────────────────────────────────────

    private func snapshotJson() throws -> [String: Any] {
        let s = container.repo.snapshot
        return [
            "devices": devicesJson(),
            "schedules": schedulesJson(),
            "logs": logsJson(),
            "settings": settingsToJson(s.settings),
        ]
    }

    private func devicesJson() -> [[String: Any]] {
        container.repo.snapshot.devices.map { deviceToJson($0) }
    }

    private func schedulesJson() -> [[String: Any]] {
        container.repo.snapshot.schedules.map { scheduleToJson($0) }
    }

    private func logsJson() -> [[String: Any]] {
        container.repo.snapshot.logs.map { ["ts": $0.ts, "device": $0.device, "level": $0.level, "msg": $0.msg] }
    }

    private func deviceToJson(_ d: Device) -> [String: Any] {
        [
            "id": d.id, "name": d.name, "mac": d.mac, "ip": d.ip,
            "username": d.username, "enabled": d.enabled,
            "hasPassword": !container.repo.getPassword(id: d.id).isEmpty,
            "watch": d.watchProcesses,
            "allow_batch": d.allowBatch,
            "batches": d.batches.map { ["id": $0.id, "name": $0.name, "script": $0.script, "timeout": $0.timeout] },
        ]
    }

    private func scheduleToJson(_ s: ScheduleDef) -> [String: Any] {
        [
            "id": s.id, "deviceId": s.deviceId,
            "action": s.isWake ? "wake" : "shutdown",
            "time": ScheduleEngine.formatTime(hour: s.hour, minute: s.minute),
            "days": s.days,
            "enabled": s.enabled,
        ]
    }

    private func settingsToJson(_ s: AppSettings) -> [String: Any] {
        [
            "broadcastIp": s.broadcastIp, "broadcastPort": s.broadcastPort,
            "language": s.language, "displayMode": s.displayMode,
            "autoUpdate": s.autoUpdate, "interval": s.interval, "maxLogs": s.maxLogs,
        ]
    }

    private func infoJson() -> [String: Any] {
        [
            "versionName": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "2.3.0",
            "versionCode": Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1",
            "protocol": 4,
        ]
    }

    private func device(_ id: String) throws -> Device {
        guard let d = container.repo.device(id) else { throw BridgeError("device_not_found") }
        return d
    }

    // ── Parser (UI-Vertrag camelCase → Modell) ──────────────────────────────

    /*
     * Leeres Passwortfeld beim Bearbeiten = gespeichertes Passwort behalten.
     * Fehlende batches = bestehende behalten; Einträge ohne Script fallen weg;
     * leere Batch-ID → "b"+Millis; Timeout-Default 120; enabled-Default true.
     */
    private func parseDevice(_ p: [String: Any]) -> Device {
        let id = pStr(p, "id")
        let existing = container.repo.device(id)
        let pw = pStr(p, "password").isEmpty ? (existing.map { container.repo.getPassword(id: $0.id) } ?? "") : pStr(p, "password")

        var batches: [BatchDef]? = nil
        if let arr = p["batches"] as? [[String: Any]] {
            batches = arr.compactMap { o -> BatchDef? in
                let script = pStr(o, "script")
                guard !script.isEmpty else { return nil }
                let bid = pStr(o, "id").isEmpty ? "b\(Int64(Date().timeIntervalSince1970 * 1000))" : pStr(o, "id")
                return BatchDef(id: bid, name: pStr(o, "name"), script: script,
                                timeout: (o["timeout"] as? Int) ?? 120)
            }
        }
        let watch = (p["watch"] as? [String]) ?? existing?.watchProcesses ?? []

        return Device(
            id: id,
            name: pStr(p, "name"),
            mac: pStr(p, "mac"),
            ip: pStr(p, "ip"),
            username: pStr(p, "username"),
            password: pw,
            enabled: pBool(p, "enabled") ?? true,
            batches: batches ?? existing?.batches ?? [],
            allowBatch: pBool(p, "allow_batch") ?? existing?.allowBatch ?? false,
            shutdownMethod: "host_service",
            watchProcesses: watch
        )
    }

    private func parseSchedule(_ p: [String: Any]) -> ScheduleDef {
        let id = pStr(p, "id")
        let existing = container.repo.snapshot.schedules.first { $0.id == id }
        let hm = ScheduleEngine.parseTime(pStr(p, "time")) ?? (0, 0)
        let days = (p["days"] as? [String]) ?? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return ScheduleDef(
            id: id,
            deviceId: pStr(p, "deviceId"),
            hour: hm.hour, minute: hm.minute,
            days: days,
            enabled: pBool(p, "enabled") ?? true,
            action: pStr(p, "action").isEmpty ? "wake" : pStr(p, "action"),
            lastRun: existing?.lastRun ?? 0
        )
    }

    private func parseSettings(_ p: [String: Any]) -> AppSettings {
        let cur = container.repo.snapshot.settings
        return AppSettings(
            broadcastIp: pStr(p, "broadcastIp").isEmpty ? cur.broadcastIp : pStr(p, "broadcastIp"),
            broadcastPort: (p["broadcastPort"] as? Int) ?? cur.broadcastPort,
            language: pStr(p, "language"),
            displayMode: pStr(p, "displayMode").isEmpty ? cur.displayMode : pStr(p, "displayMode"),
            autoUpdate: pBool(p, "autoUpdate") ?? cur.autoUpdate,
            interval: pStr(p, "interval").isEmpty ? cur.interval : pStr(p, "interval"),
            maxLogs: (p["maxLogs"] as? Int) ?? cur.maxLogs
        )
    }

    // ── Metriken / Batch ────────────────────────────────────────────────────

    private func metricsJson(_ id: String) async throws -> [String: Any] {
        let d = try device(id)
        guard !d.ip.isEmpty else { throw BridgeError("no_ip") }
        let pass = container.repo.getPassword(id: d.id)
        let (res, snap) = await container.hostClient.metrics(host: d.ip, username: d.username,
                                                             password: pass, watch: d.watchProcesses)
        if case let .error(msg) = res { throw BridgeError(msg) }
        guard let m = snap else { throw BridgeError("bad_response") }
        return metricsToUIJson(m)
    }

    /// Wire-Format (Bytes) → UI-Format (Prozent/GB, gerundet) — analog Kotlin.
    private func metricsToUIJson(_ m: MetricsSnapshot) -> [String: Any] {
        let GBd = 1024.0 * 1024.0 * 1024.0
        let ramTotal = m.ramTotal ?? 0
        let ramPct = ramTotal > 0 ? (m.ramUsed ?? 0) / ramTotal * 100 : 0
        let vramTotal = m.vramTotal ?? 0
        let vramPct = vramTotal > 0 ? (m.vramUsed ?? 0) / vramTotal * 100 : 0
        func r1(_ v: Double) -> Double { (v * 10).rounded() / 10 }

        var out: [String: Any] = [
            "protocol": m.protocolVersion,
            "hostname": m.hostname,
            "cpu": m.cpu.map { ($0).rounded() },
            "cpuCount": m.cpuCount ?? NSNull(),
            "ram": ramPct.rounded(),
            "ramUsedGB": r1((m.ramUsed ?? 0) / GBd),
            "ramTotalGB": r1(ramTotal / GBd),
            "uptime": m.uptime.map { Int64($0) } ?? NSNull(),
            "gpu": m.gpu.map { ($0).rounded() },
            "vram": vramTotal > 0 ? vramPct.rounded() : NSNull(),
            "vramUsedGB": m.vramUsed.map { r1($0 / GBd) } as Any,
            "vramTotalGB": m.vramTotal.map { r1($0 / GBd) } as Any,
            "gpuName": m.gpuName as Any,
        ]
        out["processes"] = m.processes.map { (key, w) -> [String: Any] in
            [
                "key": key,
                "running": w.running,
                "pid": w.pid ?? NSNull(),
                "cpu": w.cpu.map { ($0).rounded() } as Any,
                "ram": w.ram.map { r1($0 / GBd) } as Any,
                "uptime": w.uptime.map { Int64($0) } as Any,
                "model": w.model as Any,
                "apiPort": w.apiPort ?? NSNull(),
                "apiPortOpen": w.apiPortOpen ?? NSNull(),
                "models": w.models,
            ]
        }
        return out
    }

    private func runBatchJson(_ id: String, _ batchId: String) async throws -> [String: Any] {
        let d = try device(id)
        guard !d.ip.isEmpty else { throw BridgeError("no_ip") }
        guard let batch = d.batches.first(where: { $0.id == batchId }) else {
            throw BridgeError("batch_not_found")
        }
        let pass = container.repo.getPassword(id: d.id)
        let (res, br) = await container.hostClient.runBatch(host: d.ip, script: batch.script,
                                                            username: d.username, password: pass,
                                                            timeoutSec: batch.timeout)
        if case let .error(msg) = res { throw BridgeError(msg) }
        guard let r = br else { throw BridgeError("bad_response") }
        return ["exitCode": r.exitCode, "stdout": r.stdout, "stderr": r.stderr,
                "durationMs": r.durationMs, "truncated": r.truncated]
    }

    // ── Scan / Wake-All / Status (Event-Streaming) ─────────────────────────

    private func startScan() {
        container.scanner.cancel()
        scanRunning = true
        let ifaces = container.scanner.activeInterfaces()
        container.scanner.scan(ifaces: ifaces, onEvent: { [weak self] ev in
            guard let self else { return }
            switch ev {
            case let .progress(done, total, current):
                self.emitEvent(["type": "scan-progress", "done": done, "total": total, "current": current])
            case let .found(host):
                self.emitEvent(["type": "scan-found", "ip": host.ipv4, "host": host.hostname,
                                "known": host.known, "mac": host.mac])
            case let .done(count):
                self.scanRunning = false
                self.emitEvent(["type": "scan-done", "count": count])
            }
        }, completion: {})
    }

    private func ifacesJson() -> [[String: Any]] {
        container.scanner.activeInterfaces().map {
            ["name": $0.name, "ip": $0.ip, "prefix": $0.prefix, "dns": $0.dns, "checked": $0.checked]
        }
    }

    private func startWakeAll() {
        Task { [weak self] in
            guard let self else { return }
            let devs = self.container.repo.snapshot.devices.filter { MagicPacket.canWake($0) }
            for d in devs {
                let r = await self.container.wake(device: d)
                var ev: [String: Any] = ["type": "wake-result", "id": d.id, "ok": r.isSuccess]
                if case let .failure(e) = r { ev["error"] = e.localizedDescription }
                self.emitEvent(ev)
            }
            self.emitEvent(["type": "wake-all-done", "count": devs.count])
        }
    }

    private func startRefreshStatus() {
        Task { [weak self] in
            guard let self else { return }
            let devs = self.container.repo.snapshot.devices
            for d in devs {
                let online = await self.container.checkStatus(device: d)
                self.emitEvent(["type": "status", "id": d.id, "online": online])
            }
            self.emitEvent(["type": "status-done"])
        }
    }

    // ── Import / Export (Document-Picker) ───────────────────────────────────

    private func exportDevices() {
        let devs = container.repo.snapshot.devices
        let arr: [[String: Any]] = devs.map { d in
            var o: [String: Any] = [
                "name": d.name, "mac": d.mac, "ip": d.ip,
                "username": d.username,
                "password": container.repo.getPassword(id: d.id), // Klartext → Windows-Import
                "enabled": d.enabled,
            ]
            if !d.batches.isEmpty {
                o["batches"] = d.batches.map { ["id": $0.id, "name": $0.name, "script": $0.script, "timeout": $0.timeout] }
                o["allow_batch"] = d.allowBatch
            }
            // Überwachte Prozesse (Dashboard) — Windows-Format (watch_processes).
            if !d.watchProcesses.isEmpty {
                o["watch_processes"] = d.watchProcesses
            }
            return o
        }
        let data = (try? JSONSerialization.data(withJSONObject: arr, options: [.prettyPrinted, .sortedKeys])) ?? Data()
        host?.exportDocument(suggestedName: "devices.json", data: data) { [weak self] ok in
            guard ok else { return }
            self?.emitEvent(["type": "exported", "name": "devices.json", "count": devs.count])
        }
    }

    private func exportCsv() {
        let logs = container.repo.snapshot.logs
        let csv = Csv.logsToCsv(logs)
        let data = csv.data(using: .utf8) ?? Data()
        host?.exportDocument(suggestedName: "wol_logs.csv", data: data) { [weak self] ok in
            guard ok else { return }
            self?.emitEvent(["type": "exported", "name": "wol_logs.csv", "count": logs.count])
        }
    }

    private func importDevices() {
        host?.openDocument { [weak self] url in
            guard let self else { return }
            guard let url, let text = Self.readScoped(url, encoding: .utf8) else {
                self.emitEvent(["type": "imported", "count": 0, "error": "read_error"])
                return
            }
            let (added, updated, skipped) = self.parseInto(text)
            self.emitEvent(["type": "imported", "count": added + updated,
                            "added": added, "updated": updated, "skipped": skipped])
        }
    }

    /// Windows-kompatibler Import: JSON-Array; verschlüsselte Passwörter (DPAPI) werden geleert.
    private func parseInto(_ text: String) -> (added: Int, updated: Int, skipped: Int) {
        guard let data = text.data(using: .utf8),
              let arr = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
            return (0, 0, 0)
        }
        var added = 0, updated = 0, skipped = 0
        for o in arr {
            let name = pStr(o, "name").trimmingCharacters(in: .whitespaces)
            let mac = pStr(o, "mac").trimmingCharacters(in: .whitespaces)
            if name.isEmpty || mac.isEmpty { skipped += 1; continue }
            if !Validation.isValidMac(mac) { skipped += 1; continue }
            var pw = pStr(o, "password")
            if looksEncrypted(pw) { pw = "" } // DPAPI → auf iOS nicht entschlüsselbar
            let batches: [BatchDef] = (o["batches"] as? [[String: Any]])?.compactMap { bo -> BatchDef? in
                let script = pStr(bo, "script")
                guard !script.isEmpty else { return nil }
                return BatchDef(id: pStr(bo, "id").isEmpty ? "b-import" : pStr(bo, "id"),
                                name: pStr(bo, "name"), script: script,
                                timeout: (bo["timeout"] as? Int) ?? 120)
            } ?? []
            // Überwachte Prozesse (Dashboard) — fehlend = bestehende behalten.
            // Trimmen, Dedup unter Beibehaltung der Reihenfolge, max. 8 (wie Windows).
            var watch: [String] = []
            if let raw = o["watch_processes"] as? [Any] {
                for value in raw {
                    guard let s = value as? String else { continue }
                    let trimmed = s.trimmingCharacters(in: .whitespaces)
                    if trimmed.isEmpty || watch.contains(trimmed) { continue }
                    watch.append(trimmed)
                    if watch.count >= 8 { break }
                }
            }
            let match = container.repo.snapshot.devices.first { $0.name == name }
            var dev = match ?? Device(name: name)
            dev.name = name
            dev.mac = Validation.normalizeMac(mac)
            dev.ip = pStr(o, "ip")
            dev.username = pStr(o, "username")
            dev.password = pw
            dev.enabled = pBool(o, "enabled") ?? true
            dev.batches = !batches.isEmpty ? batches : (match?.batches ?? [])
            dev.allowBatch = pBool(o, "allow_batch") ?? match?.allowBatch ?? false
            dev.watchProcesses = !watch.isEmpty ? watch : (match?.watchProcesses ?? [])
            container.repo.saveDevice(dev)
            if match != nil { updated += 1 } else { added += 1 }
        }
        return (added, updated, skipped)
    }

    /// Erkannt wie wol_app/crypto.is_encrypted: Base64, dekodierbar, ≥ 13 Bytes.
    private func looksEncrypted(_ value: String) -> Bool {
        if value.isEmpty || value.count < 18 { return false }
        return Data(base64Encoded: value).map { $0.count >= 13 } ?? false
    }

    // ── Update-Check ────────────────────────────────────────────────────────

    private func updateCheckJson() async throws -> [String: Any] {
        let current = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "2.3.0"
        switch await UpdateCheck.check(current: current) {
        case let .new(version): return ["state": "update", "version": version]
        case .latest: return ["state": "latest"]
        case .failed: return ["state": "failed"]
        }
    }

    // ── Datei-/Event-Infrastruktur ──────────────────────────────────────────

    private static func readScoped(_ url: URL, encoding: String.Encoding) -> String? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        return try? String(contentsOf: url, encoding: encoding)
    }

    /// Ergebnis an JS — callAsyncJavaScript mit Argumenten vermeidet Escaping-Probleme.
    private func postResult(_ callId: Int, _ payload: [String: Any]) {
        let clean = sanitize(payload)
        DispatchQueue.main.async { [weak self] in
            self?.webView?.callAsyncJavaScript(
                "window.__nativeResult && window.__nativeResult(arguments[0], arguments[1])",
                arguments: [callId, clean],
                contentWorld: .page,
                completionHandler: nil)
        }
    }

    /// Events an JS (Scan-Fortschritt, Wake-Ergebnisse, Status …).
    func emitEvent(_ payload: [String: Any]) {
        let clean = sanitize(payload)
        DispatchQueue.main.async { [weak self] in
            self?.webView?.callAsyncJavaScript(
                "window.__nativeEvent && window.__nativeEvent(arguments[0])",
                arguments: [clean],
                contentWorld: .page,
                completionHandler: nil)
        }
    }

    /// Nicht-JSON-taugliche Werte (Int64, NSNull ok) normalisieren.
    private func sanitize(_ value: Any) -> Any {
        if value is NSNull { return NSNull() }
        if let i = value as? Int64 { return NSNumber(value: i) }
        if let d = value as? Double, d != d { return NSNull() } // NaN
        if let arr = value as? [Any] { return arr.map { sanitize($0) } }
        if let dict = value as? [String: Any] {
            return dict.mapValues { sanitize($0) }
        }
        return value
    }

    // ── Kleine JSON-Helfer ──────────────────────────────────────────────────

    private func pStr(_ p: [String: Any], _ key: String) -> String {
        if let s = p[key] as? String { return s }
        if let n = p[key] as? NSNumber { return n.stringValue }
        return ""
    }

    private func pBool(_ p: [String: Any], _ key: String) -> Bool? {
        if let b = p[key] as? Bool { return b }
        if let n = p[key] as? NSNumber { return n.boolValue }
        return nil
    }

    private func rResult(_ r: Result<Void, Error>) throws -> Any {
        switch r {
        case .success: return true
        case let .failure(e): throw BridgeError(e.localizedDescription)
        }
    }
}

private extension Result {
    var isSuccess: Bool { if case .success = self { return true }; return false }
}
