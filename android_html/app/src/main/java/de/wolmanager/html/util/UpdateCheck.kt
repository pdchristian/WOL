package de.wolmanager.html.util

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.net.HttpURLConnection
import java.net.URL

/** Ergebnis des GitHub-Release-Checks. */
sealed interface UpdResult {
    data object Latest : UpdResult
    data class New(val version: String) : UpdResult
    data object Failed : UpdResult
}

/** GitHub-Release-Check gegen pdchristian/WOL. */
object UpdateCheck {

    private const val API = "https://api.github.com/repos/pdchristian/WOL/releases/latest"

    suspend fun check(current: String): UpdResult = withContext(Dispatchers.IO) {
        try {
            val conn = URL(API).openConnection() as HttpURLConnection
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.setRequestProperty("Accept", "application/vnd.github+json")
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            val tag = (Json.parseToJsonElement(body) as? kotlinx.serialization.json.JsonObject)
                ?.get("tag_name")?.jsonPrimitive?.content ?: ""
            val latest = tag.removePrefix("v").removePrefix("V")
            when {
                latest.isBlank() -> UpdResult.Failed
                isNewer(latest, current) -> UpdResult.New(latest)
                else -> UpdResult.Latest
            }
        } catch (_: Exception) {
            UpdResult.Failed
        }
    }

    /** Versionsvergleich "2.3.1" > "2.3.0". */
    fun isNewer(latest: String, current: String): Boolean {
        val a = latest.split(".").map { it.toIntOrNull() ?: 0 }
        val b = current.split(".").map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }
}
