package de.wolmanager

import android.content.Context
import de.wolmanager.data.Device
import de.wolmanager.data.Repo
import de.wolmanager.data.SecureStore
import de.wolmanager.net.HostServiceClient
import de.wolmanager.net.MagicPacket
import de.wolmanager.net.NetworkScanner
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File

/**
 * Zentrale Abhängigkeiten (manuelle Composition Root, kein DI-Framework).
 */
class AppContainer(private val context: Context) {
    val secure = SecureStore(context)
    val repo = Repo(File(context.filesDir, "data"), secure)
    val hostClient = HostServiceClient()
    val scanner = NetworkScanner(context)
    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var tickerJob: kotlinx.coroutines.Job? = null
    private var lastFiredMinute = ""

    /**
     * In-App-Ticker: prüft alle 5 s und feuert Zeitpläne auf die exakte Minute,
     * solange die App läuft. WorkManager deckt verpasste Läufe im Hintergrund ab.
     */
    fun startScheduleTicker() {
        if (tickerJob?.isActive == true) return
        tickerJob = appScope.launch {
            while (isActive) {
                try {
                    val now = de.wolmanager.sched.ScheduleEngine.nowCalendar()
                    val minuteKey = now.timeInMillis / 60_000L
                    if (minuteKey.toString() != lastFiredMinute) {
                        val snapshot = repo.snapshot.value
                        for (sched in snapshot.schedules) {
                            if (!sched.enabled) continue
                            if (!de.wolmanager.sched.ScheduleEngine.matchesMinute(sched, now)) continue
                            val device = snapshot.devices.firstOrNull { it.id == sched.deviceId } ?: continue
                            repo.updateScheduleLastRun(sched.id, now.timeInMillis)
                            de.wolmanager.sched.ScheduleWorker.runAction(this@AppContainer, device, sched)
                        }
                        lastFiredMinute = minuteKey.toString()
                    }
                } catch (_: Exception) {
                }
                kotlinx.coroutines.delay(5_000)
            }
        }
    }

    fun stopScheduleTicker() {
        tickerJob?.cancel()
        tickerJob = null
    }

    /** Zeitplan-Änderungen übernehmen: WorkManager neu synchronisieren. */
    fun syncSchedules() {
        de.wolmanager.sched.ScheduleWorker.sync(context)
    }

    /** Einmal Wake für ein Gerät; liefert Erfolg/Fehler. */
    suspend fun wake(device: Device): Result<Unit> {
        val s = repo.snapshot.value.settings
        val res = MagicPacket.send(context, device, s.broadcastIp, s.broadcastPort)
        repo.log(device.name, "info", if (res.isSuccess) "Wake: Magic Packet (Port ${s.broadcastPort}) gesendet" else "Wake fehlgeschlagen: ${res.exceptionOrNull()?.message}")
        return res
    }

    /** Herunterfahren über Host-Service (SMB ist unter Android nicht möglich). */
    suspend fun shutdown(device: Device): Result<Unit> {
        if (device.method.name == "SMB") {
            repo.log(device.name, "error", "Shutdown fehlgeschlagen: SMB wird von Android nicht unterstützt")
            return Result.failure(UnsupportedOperationException("smb"))
        }
        val host = device.ip.ifBlank { return Result.failure(IllegalArgumentException("no ip")) }
        val pass = repo.getPassword(device.id)
        return when (val r = hostClient.shutdown(host, device.username, pass)) {
            is HostServiceClient.HostResult.Ok -> {
                repo.log(device.name, "info", "Shutdown-Befehl akzeptiert")
                Result.success(Unit)
            }
            is HostServiceClient.HostResult.Error -> {
                repo.log(device.name, "error", "Shutdown fehlgeschlagen: ${r.message}")
                Result.failure(IllegalStateException(r.message))
            }
        }
    }

    /** Status-Check: erreichbar über Host-Service? */
    suspend fun checkStatus(device: Device): Boolean {
        val host = device.ip.ifBlank { return false }
        return hostClient.status(host) is HostServiceClient.HostResult.Ok
    }
}

class WolApplication : android.app.Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        de.wolmanager.sched.ScheduleWorker.sync(this)
        container.startScheduleTicker()
    }
}
