package de.wolmanager.html.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Datenmodelle — kompatibel zum Windows-Format (devices.json / config.json).
 * devices.json ist ein JSON-ARRAY von [Device] (ohne [Device.id]/Laufzeitfelder).
 */

enum class ConnState { UNKNOWN, ONLINE, OFFLINE, WAKING }

@Serializable
data class BatchDef(
    val id: String = "",
    val name: String = "",
    val script: String = "",
    val timeout: Int = 120,
)

/**
 * Persistiertes Geräteformat. [password] wird vor dem Schreiben geleert und separat
 * verschlüsselt in [de.wolmanager.html.data.SecureStore] abgelegt. [id] und die Runtime-Felder
 * [shutdownMethod]/[watchProcesses] entsprechen dem Windows-config.json-Schema.
 * Hinweis: Unter Android wird ausschließlich der Host-Service genutzt; [shutdownMethod]
 * wird nur der Windows-Roundtrip-Kompatibilität willen mitgeführt und nie ausgewertet.
 */
@Serializable
data class Device(
    val name: String = "",
    val mac: String = "",
    val ip: String = "",
    val username: String = "",
    val password: String = "",
    val enabled: Boolean = true,
    val batches: List<BatchDef> = emptyList(),
    @SerialName("allow_batch") val allowBatch: Boolean = false,
    val id: String = "",
    @SerialName("shutdown_method") val shutdownMethod: String = "host_service",
    @SerialName("watch_processes") val watchProcesses: List<String> = emptyList(),
)

/** Laufzeit-Zustand eines Geräts (nicht persistiert). */
data class DeviceRuntime(
    val status: ConnState = ConnState.UNKNOWN,
    val metrics: MetricsSnapshot? = null,
    val sparkCpu: List<Float> = emptyList(),
    val sparkRam: List<Float> = emptyList(),
    val sparkGpu: List<Float> = emptyList(),
    val gpuHighTicks: Int = 0,
    val checking: Boolean = false,
)

@Serializable
data class ScheduleDef(
    val id: String = "",
    @SerialName("device_id") val deviceId: String = "",
    val hour: Int = 0,
    val minute: Int = 0,
    val days: List<String> = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    val enabled: Boolean = true,
    val action: String = "wake",
    @SerialName("last_run") val lastRun: Long = 0L,
) {
    val isWake: Boolean get() = !action.equals("shutdown", ignoreCase = true)
}

@Serializable
data class LogEntry(
    val ts: Long = 0L,
    val device: String = "",
    val level: String = "info",
    val msg: String = "",
) {
    val isError: Boolean get() = level == "error"
    val isWarn: Boolean get() = level == "warn"
}

@Serializable
data class AppSettings(
    @SerialName("broadcast_ip") val broadcastIp: String = "255.255.255.255",
    @SerialName("broadcast_port") val broadcastPort: Int = 9,
    val language: String = "",           // "" = Systemsprache
    @SerialName("display_mode") val displayMode: String = "auto",
    @SerialName("auto_update") val autoUpdate: Boolean = true,
    val interval: String = "168",        // Prüfintervall in Stunden
    @SerialName("max_logs") val maxLogs: Int = 100,
    @SerialName("default_shutdown_method") val defaultShutdownMethod: String = "host_service",
)

/** Vom Netzwerk-Scanner gefundener Host. */
data class DiscoveredHost(
    val hostname: String,
    val ipv4: String,
    val mac: String,
    val openPorts: List<Int> = emptyList(),
    val known: Boolean = false,
)

/** Antwort des Host-Service-Befehls "metrics". */
@Serializable
data class MetricsSnapshot(
    val protocol: Int = 0,
    val hostname: String = "",
    val cpu: Double? = null,
    @SerialName("cpu_count") val cpuCount: Int? = null,
    @SerialName("ram_used") val ramUsed: Double? = null,
    @SerialName("ram_total") val ramTotal: Double? = null,
    val uptime: Double? = null,
    val gpu: Double? = null,
    @SerialName("vram_used") val vramUsed: Double? = null,
    @SerialName("vram_total") val vramTotal: Double? = null,
    @SerialName("gpu_name") val gpuName: String? = null,
    val processes: Map<String, WatchInfo> = emptyMap(),
)

/** Ein Eintrag aus metrics.processes. */
/** Durchsatz eines geladenen llama.cpp-Modells (Host-Protokoll v5). */
@Serializable
data class ModelMetric(
    @SerialName("prompt_tps") val promptTps: Double? = null,
    @SerialName("predicted_tps") val predictedTps: Double? = null,
)

@Serializable
data class WatchInfo(
    val running: Boolean = false,
    val count: Int? = null,
    val pid: Int? = null,
    val cpu: Double? = null,
    val ram: Double? = null,
    val uptime: Double? = null,
    val model: String? = null,
    @SerialName("api_port") val apiPort: Int? = null,
    @SerialName("api_port_open") val apiPortOpen: Boolean? = null,
    val models: List<String> = emptyList(),
    @SerialName("model_metrics") val modelMetrics: Map<String, ModelMetric> = emptyMap(),
)

/** Antwort des Host-Service-Befehls "run_batch". */
@Serializable
data class BatchResult(
    val exitCode: Int = -1,
    val stdout: String = "",
    val stderr: String = "",
    @SerialName("duration_ms") val durationMs: Long = 0L,
    val truncated: Boolean = false,
)
