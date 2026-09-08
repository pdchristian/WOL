package de.wolmanager.html

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.webkit.JavascriptInterface
import android.webkit.WebView
import de.wolmanager.html.data.AppSettings
import de.wolmanager.html.data.BatchDef
import de.wolmanager.html.data.Device
import de.wolmanager.html.data.MetricsSnapshot
import de.wolmanager.html.data.ScheduleDef
import de.wolmanager.html.net.HostServiceClient
import de.wolmanager.html.net.NetworkScanner
import de.wolmanager.html.util.Csv
import de.wolmanager.html.util.UpdResult
import de.wolmanager.html.util.UpdateCheck
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.util.Base64

/**
 * Was die Hülle (Activity) der Bridge bereitstellen muss: SAF-Dateipicker und Vibrieren.
 */
interface BridgeHost {
    fun launchCreateDocument(mime: String, suggestedName: String, cb: (Uri?) -> Unit)
    fun launchOpenDocument(cb: (Uri?) -> Unit)
    fun vibrate(ms: Long)
}

/**
 * JS ↔ native Brücke. JS ruft `Android.call(callId, method, paramsJson)`; das Ergebnis
 * kommt asynchron über `window.__nativeResult(callId, {ok,data|error})` zurück.
 * Länger laufende Vorgänge senden zusätzlich Events über `window.__nativeEvent({...})`.
 *
 * Das JSON-Gegenstück nach JS ist bewusst camelCase/flach (UI-Vertrag), unabhängig
 * vom Windows-Schlangenformat, das der Repo persistiert.
 */
class Bridge(
    context: Context,
    private val container: AppContainer,
    private val host: BridgeHost,
) {
    private val app = context.applicationContext
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val main = Handler(Looper.getMainLooper())
    private val json = Json { ignoreUnknownKeys = true }

    @Volatile
    var webView: WebView? = null

    /** HTML meldet offenes Sheet/Overlay → Zurück-Taste schließt erst dieses. */
    @Volatile
    var sheetOpen: Boolean = false
        private set

    private var scanJob: Job? = null

    @JavascriptInterface
    fun setSheetOpen(open: Boolean) {
        sheetOpen = open
    }

    // ── Einstiegspunkt aus JS ────────────────────────────────────────────────

    @JavascriptInterface
    fun call(callId: Int, method: String, paramsJson: String) {
        val p = try {
            if (paramsJson.isBlank()) JsonObject(emptyMap())
            else json.parseToJsonElement(paramsJson).jsonObject
        } catch (_: Exception) {
            JsonObject(emptyMap())
        }
        scope.launch {
            try {
                val data = dispatch(method, p)
                postResult(callId, buildJsonObject { put("ok", true); put("data", data) })
            } catch (e: Exception) {
                postResult(callId, buildJsonObject { put("ok", false); put("error", e.message ?: "error") })
            }
        }
    }

    private suspend fun dispatch(method: String, p: JsonObject): JsonElement = when (method) {
        "snapshot" -> snapshotJson()
        "info" -> infoJson()
        "saveDevice" -> { container.repo.saveDevice(parseDevice(p)); devicesJson() }
        "deleteDevice" -> { container.repo.deleteDevice(p.str("id")); devicesJson() }
        "getPassword" -> JsonPrimitive(container.repo.getPassword(p.str("id")))
        "saveSchedule" -> { container.repo.saveSchedule(parseSchedule(p)); container.syncSchedules(); schedulesJson() }
        "deleteSchedule" -> { container.repo.deleteSchedule(p.str("id")); container.syncSchedules(); schedulesJson() }
        "saveSettings" -> { container.repo.saveSettings(parseSettings(p)); JsonPrimitive(true) }
        "resetSettings" -> { container.repo.resetSettings(); JsonPrimitive(true) }
        "clearLogs" -> { container.repo.clearLogs(); logsJson() }
        "log" -> { container.repo.log(p.str("device"), p.str("level"), p.str("msg")); JsonPrimitive(true) }
        "wake" -> container.wake(device(p.str("id"))).toElement()
        "shutdown" -> container.shutdown(device(p.str("id"))).toElement()
        "status" -> JsonPrimitive(container.checkStatus(device(p.str("id"))))
        "ping" -> {
            val d = device(p.str("id"))
            if (d.ip.isBlank()) fail("no_ip")
            JsonPrimitive(container.hostClient.ping(d.ip) ?: fail("host_unreachable"))
        }
        "metrics" -> metricsJson(p.str("id"))
        "runBatch" -> runBatchJson(p.str("id"), p.str("batchId"))
        "scanIfaces" -> ifacesJson()
        "scanStart" -> { startScan(); JsonPrimitive(true) }
        "scanStop" -> { scanJob?.cancel(); scanJob = null; JsonPrimitive(true) }
        "wakeAll" -> { startWakeAll(); JsonPrimitive(true) }
        "refreshStatus" -> { startRefreshStatus(); JsonPrimitive(true) }
        "exportDevices" -> { exportDevices(); JsonPrimitive(true) }
        "exportCsv" -> { exportCsv(); JsonPrimitive(true) }
        "importDevices" -> { importDevices(); JsonPrimitive(true) }
        "updateCheck" -> updateCheckJson()
        "vibrate" -> { host.vibrate(p.opt("ms")?.jsonPrimitive?.intOrNull?.toLong() ?: 12); JsonPrimitive(true) }
        else -> fail("unknown_method:$method")
    }

    // ── Snapshot ──────────────────────────────────────────────────────────────

    private fun snapshotJson(): JsonObject {
        val s = container.repo.snapshot.value
        return buildJsonObject {
            put("devices", devicesJson())
            put("schedules", schedulesJson())
            put("logs", logsJson())
            put("settings", settingsToJson(s.settings))
        }
    }

    private fun devicesJson(): JsonArray {
        val devs = container.repo.snapshot.value.devices
        return JsonArray(devs.map { deviceToJson(it) })
    }

    private fun schedulesJson(): JsonArray {
        val list = container.repo.snapshot.value.schedules
        return JsonArray(list.map { scheduleToJson(it) })
    }

    private fun logsJson(): JsonArray {
        val logs = container.repo.snapshot.value.logs
        return JsonArray(logs.map { l ->
            buildJsonObject {
                put("ts", l.ts); put("device", l.device); put("level", l.level); put("msg", l.msg)
            }
        })
    }

    private fun deviceToJson(d: Device): JsonObject = buildJsonObject {
        put("id", d.id); put("name", d.name); put("mac", d.mac); put("ip", d.ip)
        put("username", d.username); put("enabled", d.enabled)
        put("hasPassword", container.repo.getPassword(d.id).isNotEmpty())
        put("watch", JsonArray(d.watchProcesses.map { JsonPrimitive(it) }))
        put("allow_batch", d.allowBatch)
        put("batches", JsonArray(d.batches.map { b ->
            buildJsonObject { put("id", b.id); put("name", b.name); put("script", b.script); put("timeout", b.timeout) }
        }))
    }

    private fun scheduleToJson(s: ScheduleDef): JsonObject = buildJsonObject {
        put("id", s.id); put("deviceId", s.deviceId)
        put("action", if (s.isWake) "wake" else "shutdown")
        put("time", String.format(java.util.Locale.US, "%02d:%02d", s.hour, s.minute))
        put("days", JsonArray(s.days.map { JsonPrimitive(it) }))
        put("enabled", s.enabled)
    }

    private fun settingsToJson(s: AppSettings): JsonObject = buildJsonObject {
        put("broadcastIp", s.broadcastIp); put("broadcastPort", s.broadcastPort)
        put("language", s.language); put("displayMode", s.displayMode)
        put("autoUpdate", s.autoUpdate); put("interval", s.interval); put("maxLogs", s.maxLogs)
    }

    private fun infoJson(): JsonObject = buildJsonObject {
        put("versionName", BuildConfig.VERSION_NAME)
        put("versionCode", BuildConfig.VERSION_CODE)
        put("protocol", 4)
    }

    private fun device(id: String): Device =
        container.repo.snapshot.value.devices.firstOrNull { it.id == id } ?: fail("device_not_found")

    private fun parseDevice(p: JsonObject): Device {
        val existing = p.str("id").let { id -> container.repo.snapshot.value.devices.firstOrNull { it.id == id } }
        // Leeres Passwortfeld beim Bearbeiten = gespeichertes Passwort behalten (UI sendet es nicht zurück).
        val pw = p.str("password").ifBlank { existing?.let { container.repo.getPassword(it.id) } ?: "" }
        return Device(
            name = p.str("name"),
            mac = p.str("mac"),
            ip = p.str("ip"),
            username = p.str("username"),
            password = pw,
            enabled = p.opt("enabled")?.jsonPrimitive?.booleanOrNull ?: true,
            batches = (p["batches"] as? JsonArray)?.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                val script = o.str("script")
                if (script.isBlank()) null
                else BatchDef(
                    id = o.str("id").ifBlank { "b" + System.currentTimeMillis() },
                    name = o.str("name"), script = script,
                    timeout = o.opt("timeout")?.jsonPrimitive?.intOrNull ?: 120,
                )
            } ?: (existing?.batches ?: emptyList()),
            allowBatch = p.opt("allow_batch")?.jsonPrimitive?.booleanOrNull ?: (existing?.allowBatch ?: false),
            id = p.str("id"),
            shutdownMethod = "host_service",
            watchProcesses = (p["watch"] as? JsonArray)?.mapNotNull { it.jsonPrimitive.contentOrNullSafe() }
                ?: (existing?.watchProcesses ?: emptyList()),
        )
    }

    private fun parseSchedule(p: JsonObject): ScheduleDef {
        val existing = p.str("id").let { id -> container.repo.snapshot.value.schedules.firstOrNull { it.id == id } }
        val (h, m) = de.wolmanager.html.sched.ScheduleEngine.parseTime(p.str("time")) ?: (0 to 0)
        return ScheduleDef(
            id = p.str("id"),
            deviceId = p.str("deviceId"),
            hour = h, minute = m,
            days = (p["days"] as? JsonArray)?.mapNotNull { it.jsonPrimitive.contentOrNullSafe() }
                ?: listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
            enabled = p.opt("enabled")?.jsonPrimitive?.booleanOrNull ?: true,
            action = p.str("action").ifBlank { "wake" },
            lastRun = existing?.lastRun ?: 0L,
        )
    }

    private fun parseSettings(p: JsonObject): AppSettings {
        val cur = container.repo.snapshot.value.settings
        return AppSettings(
            broadcastIp = p.str("broadcastIp").ifBlank { cur.broadcastIp },
            broadcastPort = p.opt("broadcastPort")?.jsonPrimitive?.intOrNull ?: cur.broadcastPort,
            language = p.str("language"),
            displayMode = p.str("displayMode").ifBlank { cur.displayMode },
            autoUpdate = p.opt("autoUpdate")?.jsonPrimitive?.booleanOrNull ?: cur.autoUpdate,
            interval = p.str("interval").ifBlank { cur.interval },
            maxLogs = p.opt("maxLogs")?.jsonPrimitive?.intOrNull ?: cur.maxLogs,
        )
    }

    // ── Metriken / Batch ──────────────────────────────────────────────────────

    private suspend fun metricsJson(id: String): JsonElement {
        val d = device(id)
        if (d.ip.isBlank()) fail("no_ip")
        val pass = container.repo.getPassword(d.id)
        val (res, snap) = container.hostClient.metrics(d.ip, d.username, pass, d.watchProcesses)
        if (res is HostServiceClient.HostResult.Error) fail(res.message)
        return metricsToJson(snap!!)
    }

    private fun metricsToJson(m: MetricsSnapshot): JsonObject {
        val ramTotal = m.ramTotal ?: 0.0
        val ramPct = if (ramTotal > 0) (m.ramUsed ?: 0.0) / ramTotal * 100.0 else 0.0
        val vramTotal = m.vramTotal ?: 0.0
        val vramPct = if (vramTotal > 0) (m.vramUsed ?: 0.0) / vramTotal * 100.0 else 0.0
        return buildJsonObject {
            put("protocol", m.protocol)
            put("hostname", m.hostname)
            put("cpu", m.cpu?.let { Math.round(it) })
            put("cpuCount", m.cpuCount)
            put("ram", Math.round(ramPct))
            put("ramUsedGB", round1((m.ramUsed ?: 0.0) / GB))
            put("ramTotalGB", round1(ramTotal / GB))
            put("uptime", m.uptime?.toLong())
            put("gpu", m.gpu?.let { Math.round(it) })
            put("vram", if (vramTotal > 0) Math.round(vramPct) else null)
            put("vramUsedGB", m.vramUsed?.let { round1(it / GB) })
            put("vramTotalGB", m.vramTotal?.let { round1(it / GB) })
            put("gpuName", m.gpuName)
            put("processes", JsonArray(m.processes.entries.map { (key, w) ->
                buildJsonObject {
                    put("key", key)
                    put("running", w.running)
                    put("pid", w.pid)
                    put("cpu", w.cpu?.let { Math.round(it) })
                    put("ram", w.ram?.let { round1(it / GB) })
                    put("uptime", w.uptime?.toLong())
                    put("model", w.model)
                    put("apiPort", w.apiPort)
                    put("apiPortOpen", w.apiPortOpen)
                    put("models", JsonArray(w.models.map { JsonPrimitive(it) }))
                }
            }))
        }
    }

    private suspend fun runBatchJson(id: String, batchId: String): JsonElement {
        val d = device(id)
        if (d.ip.isBlank()) fail("no_ip")
        val batch = d.batches.firstOrNull { it.id == batchId } ?: fail("batch_not_found")
        val pass = container.repo.getPassword(d.id)
        val (res, br) = container.hostClient.runBatch(d.ip, batch.script, d.username, pass, batch.timeout)
        if (res is HostServiceClient.HostResult.Error) fail(res.message)
        val r = br!!
        return buildJsonObject {
            put("exitCode", r.exitCode); put("stdout", r.stdout); put("stderr", r.stderr)
            put("durationMs", r.durationMs); put("truncated", r.truncated)
        }
    }

    // ── Scan / Wake-All / Status (Event-Streaming) ───────────────────────────

    private fun startScan() {
        scanJob?.cancel()
        scanJob = scope.launch {
            container.scanner.scan(container.scanner.activeInterfaces()).collectLatest { ev ->
                when (ev) {
                    is NetworkScanner.ScanEvent.Progress -> emitEvent(buildJsonObject {
                        put("type", "scan-progress"); put("done", ev.done); put("total", ev.total); put("current", ev.current)
                    })
                    is NetworkScanner.ScanEvent.Found -> emitEvent(buildJsonObject {
                        put("type", "scan-found"); put("ip", ev.host.ipv4); put("host", ev.host.hostname)
                        put("known", ev.host.known); put("mac", ev.host.mac)
                    })
                    is NetworkScanner.ScanEvent.Done -> emitEvent(buildJsonObject {
                        put("type", "scan-done"); put("count", ev.count)
                    })
                }
            }
        }
    }

    private fun ifacesJson(): JsonArray = buildJsonArray {
        for (i in container.scanner.activeInterfaces()) {
            add(buildJsonObject {
                put("name", i.name); put("ip", i.ip); put("prefix", i.prefix); put("dns", i.dns); put("checked", i.checked)
            })
        }
    }

    private fun startWakeAll() {
        scope.launch {
            val devs = container.repo.snapshot.value.devices.filter { de.wolmanager.html.net.MagicPacket.canWake(it) }
            for (d in devs) {
                val r = container.wake(d)
                emitEvent(buildJsonObject {
                    put("type", "wake-result"); put("id", d.id); put("ok", r.isSuccess)
                    r.exceptionOrNull()?.let { put("error", it.message ?: "error") }
                })
            }
            emitEvent(buildJsonObject { put("type", "wake-all-done"); put("count", devs.size) })
        }
    }

    private fun startRefreshStatus() {
        scope.launch {
            val devs = container.repo.snapshot.value.devices
            for (d in devs) {
                val online = container.checkStatus(d)
                emitEvent(buildJsonObject { put("type", "status"); put("id", d.id); put("online", online) })
            }
            emitEvent(buildJsonObject { put("type", "status-done") })
        }
    }

    // ── Import / Export (SAF) ─────────────────────────────────────────────────

    private fun exportDevices() {
        host.launchCreateDocument("application/json", "devices.json") { uri ->
            if (uri == null) return@launchCreateDocument
            val devs = container.repo.snapshot.value.devices
            val arr = buildJsonArray {
                for (d in devs) {
                    add(buildJsonObject {
                        put("name", d.name); put("mac", d.mac); put("ip", d.ip)
                        put("username", d.username)
                        put("password", container.repo.getPassword(d.id)) // Klartext → Windows-Import liest beides
                        put("enabled", d.enabled)
                        if (d.batches.isNotEmpty()) {
                            put("batches", JsonArray(d.batches.map { b ->
                                buildJsonObject { put("id", b.id); put("name", b.name); put("script", b.script); put("timeout", b.timeout) }
                            }))
                            put("allow_batch", d.allowBatch)
                        }
                    })
                }
            }
            val text = json.encodeToString(JsonArray.serializer(), arr)
            writeText(uri, text)
            emitEvent(buildJsonObject { put("type", "exported"); put("name", "devices.json"); put("count", devs.size) })
        }
    }

    private fun exportCsv() {
        host.launchCreateDocument("text/csv", "wol_logs.csv") { uri ->
            if (uri == null) return@launchCreateDocument
            val logs = container.repo.snapshot.value.logs
            writeText(uri, Csv.logsToCsv(logs))
            emitEvent(buildJsonObject { put("type", "exported"); put("name", "wol_logs.csv"); put("count", logs.size) })
        }
    }

    private fun importDevices() {
        host.launchOpenDocument { uri ->
            if (uri == null) return@launchOpenDocument
            val text = readText(uri)
            if (text == null) {
                emitEvent(buildJsonObject { put("type", "imported"); put("count", 0); put("error", "read_error") })
                return@launchOpenDocument
            }
            val (added, updated, skipped) = parseInto(text)
            emitEvent(buildJsonObject {
                put("type", "imported"); put("count", added + updated)
                put("added", added); put("updated", updated); put("skipped", skipped)
            })
        }
    }

    /** Windows-kompatibler Import: JSON-Array; verschlüsselte Passwörter (DPAPI) werden geleert. */
    private fun parseInto(text: String): Triple<Int, Int, Int> {
        val arr = try {
            json.parseToJsonElement(text).let { if (it is JsonArray) it else null }
        } catch (_: Exception) {
            null
        } ?: return Triple(0, 0, 0)
        var added = 0
        var updated = 0
        var skipped = 0
        for (el in arr) {
            val o = el as? JsonObject ?: continue
            val name = o.str("name").trim()
            val mac = o.str("mac").trim()
            if (name.isBlank() || mac.isBlank()) { skipped++; continue }
            if (!de.wolmanager.html.util.Validation.isValidMac(mac)) { skipped++; continue }
            var pw = o.str("password")
            if (looksEncrypted(pw)) pw = "" // DPAPI → auf Android nicht entschlüsselbar
            val batches = (o["batches"] as? JsonArray)?.mapNotNull { b ->
                val bo = b as? JsonObject ?: return@mapNotNull null
                val script = bo.str("script")
                if (script.isBlank()) null
                else BatchDef(
                    id = bo.str("id").ifBlank { "b-import" }, name = bo.str("name"),
                    script = script, timeout = bo.opt("timeout")?.jsonPrimitive?.intOrNull ?: 120,
                )
            } ?: emptyList()
            val match = container.repo.snapshot.value.devices.firstOrNull { it.name == name }
            val dev = (match ?: Device(name = name)).copy(
                mac = de.wolmanager.html.util.Validation.normalizeMac(mac),
                ip = o.str("ip"),
                username = o.str("username"),
                password = pw,
                enabled = o.opt("enabled")?.jsonPrimitive?.booleanOrNull ?: true,
                batches = if (batches.isNotEmpty()) batches else (match?.batches ?: emptyList()),
                allowBatch = o.opt("allow_batch")?.jsonPrimitive?.booleanOrNull ?: (match?.allowBatch ?: false),
            )
            container.repo.saveDevice(dev)
            if (match != null) updated++ else added++
        }
        return Triple(added, updated, skipped)
    }

    /** Erkannt wie wol_app/crypto.is_encrypted: Base64, dekodierbar, ≥ 13 Bytes. */
    private fun looksEncrypted(value: String): Boolean {
        if (value.isBlank() || value.length < 18) return false
        return try {
            Base64.getDecoder().decode(value).size >= 13
        } catch (_: Exception) {
            false
        }
    }

    // ── Update-Check ──────────────────────────────────────────────────────────

    private suspend fun updateCheckJson(): JsonElement = when (val r = UpdateCheck.check(BuildConfig.VERSION_NAME)) {
        is UpdResult.New -> buildJsonObject { put("state", "update"); put("version", r.version) }
        UpdResult.Latest -> buildJsonObject { put("state", "latest") }
        UpdResult.Failed -> buildJsonObject { put("state", "failed") }
    }

    // ── Datei-/Event-Infrastruktur ───────────────────────────────────────────

    private fun writeText(uri: Uri, text: String) {
        try {
            app.contentResolver.openOutputStream(uri, "wt")?.use { it.write(text.toByteArray(Charsets.UTF_8)) }
        } catch (_: Exception) {
        }
    }

    private fun readText(uri: Uri): String? = try {
        app.contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) }
    } catch (_: Exception) {
        null
    }

    private fun postResult(callId: Int, payload: JsonObject) {
        val wv = webView ?: return
        val s = json.encodeToString(JsonObject.serializer(), payload)
        main.post { wv.evaluateJavascript("window.__nativeResult && window.__nativeResult($callId,$s)", null) }
    }

    private fun emitEvent(payload: JsonObject) {
        val wv = webView ?: return
        val s = json.encodeToString(JsonObject.serializer(), payload)
        main.post { wv.evaluateJavascript("window.__nativeEvent && window.__nativeEvent($s)", null) }
    }

    private fun Result<Unit>.toElement(): JsonElement =
        if (isSuccess) JsonPrimitive(true) else fail(exceptionOrNull()?.message ?: "error")

    private fun JsonObject.str(key: String): String = opt(key)?.jsonPrimitive?.contentOrNullSafe() ?: ""
    private fun JsonObject.opt(key: String): JsonElement? = this[key]
    private fun JsonPrimitive.contentOrNullSafe(): String? = if (this is JsonNull) null else content

    private fun fail(msg: String): Nothing = throw IllegalArgumentException(msg)

    private fun round1(v: Double): Double = Math.round(v * 10) / 10.0

    companion object {
        private const val GB = 1024.0 * 1024 * 1024
    }
}
