package de.wolmanager.html.util

import de.wolmanager.html.data.LogEntry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CsvTest {

    @Test
    fun logsToCsv_headerAndBom() {
        val csv = Csv.logsToCsv(listOf(LogEntry(ts = 0L, device = "PC", level = "info", msg = "Hallo")))
        assertTrue(csv.startsWith("\uFEFF")) // BOM
        val lines = csv.removePrefix("\uFEFF").split("\r\n").filter { it.isNotEmpty() }
        assertEquals("Zeit;Gerät;Level;Nachricht", lines[0])
        assertEquals(2, lines.size)
        val cols = lines[1].split(";")
        assertEquals(4, cols.size)
        assertEquals("PC", cols[1])
        assertEquals("info", cols[2])
        assertEquals("Hallo", cols[3])
    }

    @Test
    fun logsToCsv_escapesQuotesAndSeparators() {
        val csv = Csv.logsToCsv(listOf(LogEntry(ts = 0L, device = "A;B", level = "warn", msg = "sag \"hi\"")))
        assertTrue(csv.contains("\"A;B\""))
        assertTrue(csv.contains("\"sag \"\"hi\"\"\""))
    }

    @Test
    fun logsToCsv_empty() {
        val csv = Csv.logsToCsv(emptyList())
        assertEquals("\uFEFFZeit;Gerät;Level;Nachricht\r\n", csv)
    }
}

