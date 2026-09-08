package de.wolmanager.html.net

import de.wolmanager.html.data.BatchResult
import de.wolmanager.html.data.MetricsSnapshot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets

/**
 * Client für den WOL Host Service (Protokoll v4).
 * TCP 8765, LF-terminierte JSON-Nachrichten, eine Anfrage → eine Antwort → schließen.
 * Authentifizierung pro Anfrage über username/password.
 */
class HostServiceClient(private val port: Int = DEFAULT_PORT) {

    private val json = Json { ignoreUnknownKeys = true }

    sealed interface HostResult {
        data class Ok(val body: JsonObject) : HostResult
        data class Error(val message: String) : HostResult
    }

    private suspend fun request(
        host: String,
        payload: JsonObject,
        timeoutMs: Int,
        maxBytes: Int,
    ): HostResult = withContext(Dispatchers.IO) {
        try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(host, port), timeoutMs)
                socket.soTimeout = timeoutMs
                val writer = BufferedWriter(OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))
                writer.write(json.encodeToString(JsonObject.serializer(), payload))
                writer.write("\n")
                writer.flush()

                val reader = BufferedReader(InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
                val line = readLimited(reader, maxBytes)
                    ?: return@use HostResult.Error(ERR_NO_RESPONSE)
                val obj = try {
                    json.parseToJsonElement(line).jsonObject
                } catch (_: Exception) {
                    return@use HostResult.Error(ERR_BAD_RESPONSE)
                }
                val status = obj["status"]?.jsonPrimitive?.content
                if (status == "ok") HostResult.Ok(obj)
                else HostResult.Error(obj["message"]?.jsonPrimitive?.content ?: ERR_GENERIC)
            }
        } catch (e: Exception) {
            HostResult.Error(e.message ?: ERR_GENERIC)
        }
    }

    private fun readLimited(reader: BufferedReader, maxBytes: Int): String? {
        val sb = StringBuilder()
        var total = 0
        while (true) {
            val c = reader.read()
            if (c == -1) return if (sb.isEmpty()) null else sb.toString()
            if (c == '\n'.code) return sb.toString()
            total++
            if (total > maxBytes) return sb.toString()
            sb.append(c.toChar())
        }
    }

    suspend fun status(host: String): HostResult =
        request(host, buildJsonObject { put("command", "status") }, STATUS_TIMEOUT, MAX_SMALL)

    suspend fun metrics(
        host: String,
        username: String,
        password: String,
        watch: List<String> = emptyList(),
    ): Pair<HostResult, MetricsSnapshot?> {
        val res = request(
            host,
            buildJsonObject {
                put("command", "metrics")
                put("username", username)
                put("password", password)
                if (watch.isNotEmpty()) {
                    put("watch", JsonArray(watch.map { JsonPrimitive(it) }))
                }
            },
            METRICS_TIMEOUT, MAX_METRICS,
        )
        if (res is HostResult.Error) return res to null
        val obj = (res as HostResult.Ok).body
        return try {
            res to json.decodeFromJsonElement(MetricsSnapshot.serializer(), obj)
        } catch (_: Exception) {
            HostResult.Error(ERR_BAD_RESPONSE) to null
        }
    }

    suspend fun shutdown(host: String, username: String, password: String): HostResult =
        request(host, buildJsonObject {
            put("command", "shutdown")
            put("username", username)
            put("password", password)
        }, CMD_TIMEOUT, MAX_SMALL)

    suspend fun reboot(host: String, username: String, password: String): HostResult =
        request(host, buildJsonObject {
            put("command", "reboot")
            put("username", username)
            put("password", password)
        }, CMD_TIMEOUT, MAX_SMALL)

    suspend fun runBatch(
        host: String,
        script: String,
        username: String,
        password: String,
        timeoutSec: Int,
    ): Pair<HostResult, BatchResult?> {
        val res = request(
            host,
            buildJsonObject {
                put("command", "run_batch")
                put("username", username)
                put("password", password)
                put("script", script)
                put("timeout", timeoutSec)
            },
            (timeoutSec * 1000) + 5000, MAX_BATCH,
        )
        if (res is HostResult.Error) return res to null
        val obj = (res as HostResult.Ok).body
        return try {
            val br = BatchResult(
                exitCode = obj["exit_code"]?.jsonPrimitive?.int ?: -1,
                stdout = obj["stdout"]?.jsonPrimitive?.content ?: "",
                stderr = obj["stderr"]?.jsonPrimitive?.content ?: "",
                durationMs = obj["duration_ms"]?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
                truncated = obj["truncated"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
            )
            res to br
        } catch (_: Exception) {
            HostResult.Error(ERR_BAD_RESPONSE) to null
        }
    }

    /** Schneller TCP-Erreichbarkeitstest (Ping-Ersatz). Liefert RTT in ms oder null. */
    suspend fun ping(host: String, testPort: Int = DEFAULT_PORT, timeoutMs: Int = 2000): Long? =
        withContext(Dispatchers.IO) {
            val start = System.currentTimeMillis()
            try {
                Socket().use { s -> s.connect(InetSocketAddress(host, testPort), timeoutMs) }
                System.currentTimeMillis() - start
            } catch (_: Exception) {
                null
            }
        }

    companion object {
        const val DEFAULT_PORT = 8765
        private const val STATUS_TIMEOUT = 3000
        private const val CMD_TIMEOUT = 10000
        private const val METRICS_TIMEOUT = 6000
        private const val MAX_SMALL = 4096
        private const val MAX_METRICS = 16384
        private const val MAX_BATCH = 131072
        const val ERR_NO_RESPONSE = "host_unreachable"
        const val ERR_BAD_RESPONSE = "bad_response"
        const val ERR_GENERIC = "error"
    }
}
