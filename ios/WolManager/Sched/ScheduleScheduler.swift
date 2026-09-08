import Foundation
import BackgroundTasks

/*
 * Hintergrund-Zeitplan-Refresh (BGAppRefreshTask) — iOS-Äquivalent zu
 * ScheduleWorker (WorkManager, 15 min). Best-Effort: iOS entscheidet über den
 * Zeitpunkt. Solange die App lebt, übernimmt der In-App-Ticker (AppContainer).
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
            task.setTaskCompleted(success: true)
        }

        task.expirationHandler = {
            work.cancel()
            task.setTaskCompleted(success: false)
        }
    }
}
