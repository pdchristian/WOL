package de.wolmanager.util

import de.wolmanager.data.LogEntry
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** CSV-Export analog zur Windows-App: Semikolon-getrennt, UTF-8 mit BOM. */
object Csv {

    private val TS = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)

    fun logsToCsv(entries: List<LogEntry>): String {
        val sb = StringBuilder("\uFEFF") // BOM wie in der Windows-App
        sb.append("Zeit;Gerät;Level;Nachricht\r\n")
        for (e in entries) {
            sb.append(esc(TS.format(Date(e.ts)))).append(';')
                .append(esc(e.device)).append(';')
                .append(esc(e.level)).append(';')
                .append(esc(e.msg)).append("\r\n")
        }
        return sb.toString()
    }

    private fun esc(v: String): String {
        val needsQuotes = v.any { it == ';' || it == '"' || it == '\n' || it == '\r' }
        val cleaned = v.replace("\r\n", " ").replace('\n', ' ').replace('\r', ' ')
        return if (needsQuotes || cleaned.contains('"')) "\"" + cleaned.replace("\"", "\"\"") + "\"" else cleaned
    }
}
