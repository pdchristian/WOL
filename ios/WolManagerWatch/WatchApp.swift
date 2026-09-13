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
    /// Bestätigungs-Dialog vor dem Herunterfahren.
    @Published var confirmDevice: WatchDevice?
    /// Kurze Rückmeldung (Wake gesendet, Fehler …).
    @Published var toast: String?
    /// true, wenn das iPhone zuletzt nicht erreichbar war (Warnbox).
    @Published var iPhoneUnreachable = false

    private var toastTask: Task<Void, Never>?
    private var wakePollTask: Task<Void, Never>?

    init() {
        refresh()
    }

    // MARK: - Geräte laden

    func refresh() {
        guard !loading else { return }
        loading = true
        Task {
            do {
                let fresh = await mergeLive(devices: try await WatchService.shared.loadDevices())
                iPhoneUnreachable = false
                devices = fresh
            } catch {
                // Offline-Fallback: letzter Snapshot vom iPhone.
                let cached = WatchService.shared.cachedDevices()
                if !cached.isEmpty {
                    devices = await mergeLive(devices: cached)
                }
                iPhoneUnreachable = true
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
        devices = fresh.map { d in
            var m = d
            m.waking = old[d.id]?.waking ?? false
            return m
        }
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
