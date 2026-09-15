import Foundation
import BackgroundTasks
import WatchConnectivity

/*
 * Hintergrund-Zeitplan-Refresh (BGAppRefreshTask) — iOS-Äquivalent zu
 * ScheduleWorker (WorkManager, 15 min). Best-Effort: iOS entscheidet über den
 * Zeitpunkt. Solange die App lebt, übernimmt der In-App-Ticker (AppContainer).
 * Zusätzlich: Geräte-Status im Hintergrund prüfen und als letzter Stand zur
 * Watch pushen — die Watch zeigt dann auch ohne aktiven Abruf aktuellen Stand.
 */
enum ScheduleScheduler {

    static let taskIdentifier = "de.wolmanager.schedule-refresh"

    /// Registriert den Handler — MUSS vor didFinishLaunching aufgerufen werden
    /// (AppDelegate.willFinishLaunchingWithOptions).
    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskIdentifier, using: nil) { task in
            guard let refresh = task as? BGAppRefreshTask else { return }
            handle(refresh)
        }
    }

    /// Plant den nächsten Hintergrund-Lauf (nach Zeitplan-Änderungen & beim In-den-Hintergrund-Gehen).
    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date().addingTimeInterval(15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }

    /// Kurzer Statuslauf: alle aktivierten Geräte mit IP gegen den Host-Service
    /// prüfen und das Ergebnis als letzten Stand an die Watch-Brücke übergeben.
    /// Läuft im Hintergrund-Fenster, damit der Watch-Snapshot nie deutlich
    /// älter ist als das BGTask-Intervall (~15 min) — ganz ohne iPhone-Nutzung.
    static func refreshStatusForWatch(container: AppContainer) async {
        let devs = container.repo.snapshot.devices.filter { $0.enabled && !$0.ip.isEmpty }
        guard !devs.isEmpty else { return }
        var statuses: [String: Bool] = [:]
        await withTaskGroup(of: (String, Bool).self) { group in
            for d in devs {
                group.addTask { (d.id, await container.checkStatus(device: d)) }
            }
            for await (id, isOnline) in group { statuses[id] = isOnline }
        }
        if WCSession.isSupported() {
            WatchBridgeService.shared.noteOnline(statuses)
            WatchBridgeService.shared.syncApplicationContext()
        }
    }

    private static func handle(_ task: BGAppRefreshTask) {
        // Nächsten Lauf sofort wieder einplanen (Apple-Empfehlung).
        schedule()

        let work = Task {
            let container = AppContainer.shared
            container.repo.reload()
            let snap = container.repo.snapshot
            var now = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: Date())
            now.second = 0
            let nowDate = Calendar.current.date(from: now) ?? Date()
            let nowMs = Int64(nowDate.timeIntervalSince1970 * 1000)

            for sched in snap.schedules where sched.enabled {
                guard ScheduleEngine.dueForCatchUp(sched, now: nowDate,
                                                   windowMs: 20 * 60_000,
                                                   lastRunMs: sched.lastRun) else { continue }
                guard let device = snap.devices.first(where: { $0.id == sched.deviceId }) else { continue }
                container.repo.updateScheduleLastRun(id: sched.id, ts: nowMs)
                await AppContainer.runAction(container: container, device: device, sched: sched)
            }
            // Watch: aktuellen Gerätestatus als letzten Stand nachliefern.
            await refreshStatusForWatch(container: container)
            task.setTaskCompleted(success: true)
        }

        task.expirationHandler = {
            work.cancel()
            task.setTaskCompleted(success: false)
        }
    }
}
