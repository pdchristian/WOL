import SwiftUI
import WatchConnectivity

/*
 * Apple-Watch-App (watchOS 10+). Geräte als Karten/Liste mit Power-Icon zum
 * Aufwecken/Herunterfahren, vereinfachtes Dashboard (Dienste + CPU/RAM/GPU/VRAM).
 * Alle Aktionen laufen über das iPhone (WatchService → WatchBridgeService).
 */
@main
struct WolWatchApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            DeviceListView()
                .environmentObject(state)
        }
    }
}

/// Zentraler Zustand: Geräte, Ansicht-Modus, Aktionen, Fehler/Toast.
@MainActor
final class AppState: ObservableObject {

    enum ViewMode: String { case cards, list }

    @Published var devices: [WatchDevice] = []
    @Published var viewMode: ViewMode = .cards
    @Published var loading = false
    /// Listensortierung aus der iOS-App-Einstellung (name|ip|mac|status).
    @Published var sort: String = "name"
    /// Bestätigungs-Dialog vor dem Herunterfahren.
    @Published var confirmDevice: WatchDevice?
    /// Kurze Rückmeldung (Wake gesendet, Fehler …).
    @Published var toast: String?
    /// true, wenn das iPhone zuletzt nicht erreichbar war (Warnbox).
    @Published var iPhoneUnreachable = false

    private var toastTask: Task<Void, Never>?
    private var wakePollTask: Task<Void, Never>?

    init() {
        sort = WatchService.shared.cachedContext().sort
        refresh()
        NotificationCenter.default.addObserver(
            forName: WatchService.contextDidChange, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.applyIncomingContext() }
        }
    }

    /// applicationContext vom iPhone: Sortierung + letzter Status live übernehmen.
    private func applyIncomingContext() {
        let ctx = WatchService.shared.cachedContext()
        var changed = false
        if ctx.sort != sort { sort = ctx.sort; changed = true }
        if !ctx.statuses.isEmpty {
            for i in devices.indices {
                if let s = ctx.statuses[devices[i].id], devices[i].online != s {
                    devices[i].online = s
                    changed = true
                }
            }
        }
        if changed { devices = sorted(devices) }
    }

    // MARK: - Sortierung (spiegelt sortDevices() aus app.js)

    /// Reihenfolge wie in der iOS-App: name/ip/mac oder Status (online zuerst).
    func sorted(_ list: [WatchDevice]) -> [WatchDevice] {
        switch sort {
        case "ip":
            return list.sorted { ipKey($0.ip) < ipKey($1.ip) || ($0.ip == $1.ip && $0.name < $1.name) }
        case "mac":
            return list.sorted { macKey($0.mac) < macKey($1.mac) || ($0.mac == $1.mac && $0.name < $1.name) }
        case "status":
            return list.sorted { rank($0) < rank($1) || (rank($0) == rank($1) && $0.name < $1.name) }
        default:
            return list.sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
        }
    }

    /// IP numerisch vergleichen (2.10 < 2.9), wie der ipKey in app.js.
    private func ipKey(_ ip: String) -> String {
        ip.split(separator: ".").map { String($0).replacingOccurrences(of: "^0+", with: "", options: .regularExpression) }
            .map { String(repeating: "0", count: max(0, 3 - $0.count)) + $0 }
            .joined(separator: ".")
    }

    private func macKey(_ mac: String) -> String {
        mac.uppercased().filter { $0.isLetter || $0.isNumber }
    }

    private func rank(_ d: WatchDevice) -> Int {
        if d.waking { return 2 }
        switch d.online {
        case true: return 0
        case false: return 1
        case nil: return 3
        }
    }

    // MARK: - Geräte laden

    func refresh() {
        guard !loading else { return }
        loading = true
        Task {
            do {
                let fresh = await mergeLive(devices: try await WatchService.shared.loadDevices())
                iPhoneUnreachable = false
                devices = sorted(fresh)
            } catch {
                // Offline-Fallback: letzter Snapshot vom iPhone inkl. Status.
                let ctx = WatchService.shared.cachedContext()
                if !ctx.devices.isEmpty {
                    var merged = await mergeLive(devices: ctx.devices)
                    for i in merged.indices where merged[i].online == nil {
                        merged[i].online = ctx.statuses[merged[i].id]
                    }
                    devices = sorted(merged)
                }
                if ctx.sort != sort { sort = ctx.sort }
                iPhoneUnreachable = true
                // Kaltstart: iPhone-App läuft oft noch nicht bzw. die Session
                // aktiviert erst ~1–2 s nach dem Watch-Start — dann automatisch
                // nachfassen, statt den leeren Cache stehen zu lassen.
                if devices.isEmpty {
                    try? await Task.sleep(nanoseconds: 3_000_000_000)
                    loading = false
                    if devices.isEmpty { refresh(); return }
                }
            }
            loading = false
            scheduleWakePollingIfNeeded()
        }
    }

    /// Lokale Live-Zustände (waking, bekannt online) über frische Daten legen.
    private func mergeLive(devices fresh: [WatchDevice]) async -> [WatchDevice] {
        let old = Dictionary(uniqueKeysWithValues: devices.map { ($0.id, $0) })
        return fresh.map { d in
            var m = d
            m.waking = old[d.id]?.waking ?? false
            if m.online == nil { m.online = old[d.id]?.online }
            return m
        }
    }

    // MARK: - Aktionen

    func wake(_ device: WatchDevice) {
        guard let i = index(of: device) else { return }
        devices[i].waking = true
        Task {
            do {
                try await WatchService.shared.wake(id: device.id)
                showToast(NSLocalizedString("wol.sent", value: "Wake gesendet", comment: ""))
                iPhoneUnreachable = false
                pollUntilOnline(id: device.id)
            } catch {
                devices[i].waking = false
                showToast(error.localizedDescription)
            }
        }
    }

    func requestShutdown(_ device: WatchDevice) {
        confirmDevice = device
    }

    func confirmShutdown() {
        guard let device = confirmDevice, let i = index(of: device) else { return }
        confirmDevice = nil
        Task {
            do {
                try await WatchService.shared.shutdown(id: device.id)
                devices[i].online = false
                iPhoneUnreachable = false
            } catch {
                showToast(error.localizedDescription)
            }
        }
    }

    // MARK: - Wake-Polling (Online-Status nach Magic Packet)

    private func pollUntilOnline(id: String) {
        wakePollTask?.cancel()
        wakePollTask = Task { [weak self] in
            // Hochfahren dauert: bis zu 60 s nach Status fragen.
            for _ in 0..<12 {
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                guard let self, self.isWaking(id) else { return }
                await self.refreshQuiet()
            }
            guard let self else { return }
            self.clearWaking(id)
        }
    }

    private func isWaking(_ id: String) -> Bool {
        devices.first { $0.id == id }?.waking ?? false
    }

    private func clearWaking(_ id: String) {
        guard let i = devices.firstIndex(where: { $0.id == id }) else { return }
        devices[i].waking = false
    }

    /// Stiller Refresh ohne Ladezustand (Polling).
    private func refreshQuiet() async {
        guard let fresh = try? await WatchService.shared.loadDevices() else { return }
        let old = Dictionary(uniqueKeysWithValues: devices.map { ($0.id, $0) })
        devices = sorted(fresh.map { d in
            var m = d
            m.waking = old[d.id]?.waking ?? false
            return m
        })
        // Online → waking beenden.
        for i in devices.indices where devices[i].online == true {
            devices[i].waking = false
        }
    }

    private func scheduleWakePollingIfNeeded() {
        for d in devices where d.waking && d.online != true {
            pollUntilOnline(id: d.id)
            break
        }
    }

    // MARK: - Helpers

    private func index(of device: WatchDevice) -> Int? {
        devices.firstIndex { $0.id == device.id }
    }

    private func showToast(_ text: String) {
        toastTask?.cancel()
        toast = text
        toastTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            if !Task.isCancelled { self?.toast = nil }
        }
    }
}
