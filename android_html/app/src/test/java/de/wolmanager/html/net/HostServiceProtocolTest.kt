package de.wolmanager.html.net

import de.wolmanager.html.data.MetricsSnapshot
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Host-Service-Antworten (Protokoll v4/v5) gegen die Datenmodelle. */
class HostServiceProtocolTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun metrics_fullResponse() {
        // Beispiel analog protocol/SPEC.md (v4)
        val body = """
        {
          "status": "ok",
          "protocol": 4,
          "hostname": "BUERO-PC",
          "cpu": 12.5,
          "cpu_count": 8,
          "ram_used": 8589934592,
          "ram_total": 17179869184,
          "uptime": 3600,
          "gpu": 42.0,
          "vram_used": 2147483648,
          "vram_total": 8589934592,
          "gpu_name": "NVIDIA GeForce RTX 3060",
          "processes": {
            "llama-server.exe": {
              "running": true, "count": 1, "pid": 4242,
              "cpu": 3.2, "ram": 1073741824, "uptime": 300,
              "model": "mistral-7b.gguf", "api_port": 8080, "api_port_open": true,
              "models": ["mistral-7b.gguf"],
              "model_metrics": {
                "mistral-7b.gguf": { "prompt_tps": 261.15, "predicted_tps": 26.65, "total_tokens": 77427 }
              }
            },
            "notepad.exe": { "running": false, "count": 0 }
          }
        }
        """.trimIndent()
        val obj = json.parseToJsonElement(body)
        val m = json.decodeFromJsonElement(MetricsSnapshot.serializer(), obj)
        assertEquals(4, m.protocol)
        assertEquals("BUERO-PC", m.hostname)
        assertEquals(8, m.cpuCount)
        // Bytes → GB-Umrechnung im UI: 8 GiB / 16 GiB
        assertEquals(8.0, m.ramUsed!! / 1073741824.0, 0.001)
        assertEquals(16.0, m.ramTotal!! / 1073741824.0, 0.001)
        assertEquals(42.0, m.gpu!!, 0.001)
        assertEquals(2, m.processes.size)
        val llama = m.processes["llama-server.exe"]!!
        assertTrue(llama.running)
        assertEquals(4242, llama.pid)
        assertEquals(8080, llama.apiPort)
        assertEquals(true, llama.apiPortOpen)
        assertEquals(listOf("mistral-7b.gguf"), llama.models)
        // v5: per-model throughput (t/s) + total tokens (prompt+decode sum).
        assertEquals(261.15, llama.modelMetrics["mistral-7b.gguf"]!!.promptTps!!, 0.001)
        assertEquals(26.65, llama.modelMetrics["mistral-7b.gguf"]!!.predictedTps!!, 0.001)
        assertEquals(77427.0, llama.modelMetrics["mistral-7b.gguf"]!!.totalTokens!!, 0.001)
        val notepad = m.processes["notepad.exe"]!!
        assertEquals(false, notepad.running)
        assertEquals(null, notepad.pid)
        assertTrue(notepad.modelMetrics.isEmpty())
    }

    @Test
    fun metrics_minimalResponse() {
        val body = """{"status":"ok","protocol":4,"hostname":"PC","cpu":1.0}"""
        val m = json.decodeFromJsonElement(MetricsSnapshot.serializer(), json.parseToJsonElement(body))
        assertEquals(4, m.protocol)
        assertEquals(null, m.gpu)
        assertTrue(m.processes.isEmpty())
    }

    @Test
    fun metrics_v7PortOnlyEntry() {
        // Host-Protokoll v7: Port-only-Eintrag ohne Prozess, JSON-/metrics-Server.
        val body = """
        {
          "status": "ok", "protocol": 7, "hostname": "SERVER",
          "processes": {
            ":8081": {
              "running": false,
              "api_port": 8081, "api_port_open": true, "api_up": true,
              "api_kind": "openai",
              "api_features": ["models", "health", "metrics"],
              "api_info": { "server": "Strata 0.1.30", "context": 262144, "slots": 1 },
              "models": ["qwen3.8-flash-next-iq3_s"],
              "model_metrics": {
                "qwen3.8-flash-next-iq3_s": { "prompt_tps": 398.0, "predicted_tps": 72.2, "total_tokens": 19456405 }
              }
            }
          }
        }
        """.trimIndent()
        val m = json.decodeFromJsonElement(MetricsSnapshot.serializer(), json.parseToJsonElement(body))
        assertEquals(7, m.protocol)
        val api = m.processes[":8081"]!!
        assertEquals(false, api.running)
        assertEquals(8081, api.apiPort)
        assertEquals(true, api.apiUp)
        assertEquals("openai", api.apiKind)
        assertEquals(listOf("models", "health", "metrics"), api.apiFeatures)
        assertEquals("Strata 0.1.30", api.apiInfo!!.server)
        assertEquals(262144, api.apiInfo!!.context)
        assertEquals(1, api.apiInfo!!.slots)
        assertEquals(72.2, api.modelMetrics["qwen3.8-flash-next-iq3_s"]!!.predictedTps!!, 0.001)
    }

    @Test
    fun errorResponse_shape() {
        val body = """{"status":"error","message":"Batches sind deaktiviert. Starten Sie den Dienst mit \"--enable-batch\"."}"""
        val obj = json.parseToJsonElement(body).jsonObject
        assertEquals("error", obj["status"]?.jsonPrimitive?.content)
        assertTrue(obj["message"]?.jsonPrimitive?.content!!.contains("--enable-batch"))
    }
}

