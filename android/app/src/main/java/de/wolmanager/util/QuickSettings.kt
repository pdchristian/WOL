package de.wolmanager.util

import android.content.Context
import de.wolmanager.data.AppSettings
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Liest die Einstellungen direkt von der Datei (synchron, vor Compose-Start),
 * z. B. für Sprach- und Theme-Anwendung in MainActivity.attachBaseContext.
 */
object QuickSettings {

    private val json = Json { ignoreUnknownKeys = true }

    fun read(context: Context): AppSettings = try {
        val f = File(File(context.filesDir, "data"), "settings.json")
        if (f.exists()) json.decodeFromString(AppSettings.serializer(), f.readText()) else AppSettings()
    } catch (_: Exception) {
        AppSettings()
    }
}
