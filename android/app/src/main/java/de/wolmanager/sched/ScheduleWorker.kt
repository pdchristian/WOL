package de.wolmanager.sched

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import de.wolmanager.WolApplication
import de.wolmanager.data.Device
import java.util.concurrent.TimeUnit

/**
 * Periodischer Zeitplan-Lauf (alle 15 min) + Nachholen verpasster Aktionen.
 * Solange die App lebt, sorgt zusätzlich ein In-App-Ticker für den exakten Minute-Treffer.
 */
class ScheduleWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as WolApplication
        val container = app.container
        val snapshot = container.repo.snapshot.value
        val now = ScheduleEngine.nowCalendar()
        // Auf die volle Minute runden
        now.set(java.util.Calendar.SECOND, 0)
        now.set(java.util.Calendar.MILLISECOND, 0)

        for (sched in snapshot.schedules) {
            if (!sched.enabled) continue
            if (!ScheduleEngine.dueForCatchUp(sched, now, CATCH_UP_WINDOW_MS, sched.lastRun)) continue
            val device = snapshot.devices.firstOrNull { it.id == sched.deviceId } ?: continue
            container.repo.updateScheduleLastRun(sched.id, now.timeInMillis)
            runAction(container, device, sched)
        }
        return Result.success()
    }

    companion object {
        const val WORK_NAME = "wol_schedule"
        const val CATCH_UP_WINDOW_MS = 20L * 60_000L

        suspend fun runAction(
            container: de.wolmanager.AppContainer,
            device: Device,
            sched: de.wolmanager.data.ScheduleDef,
        ) {
            if (sched.isWake) container.wake(device) else container.shutdown(device)
        }

        fun sync(context: Context) {
            val request = PeriodicWorkRequestBuilder<ScheduleWorker>(15, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME, ExistingPeriodicWorkPolicy.UPDATE, request,
            )
        }
    }
}
