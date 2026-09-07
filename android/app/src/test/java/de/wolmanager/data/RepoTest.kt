package de.wolmanager.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class RepoTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun repo() = Repo(tmp.root, secure = null)

    @Test
    fun saveDevice_assignsIdAndPersists() {
        val r = repo()
        r.saveDevice(Device(name = "PC1", mac = "AA:BB:CC:DD:EE:01", ip = "192.168.1.10", password = "secret"))
        val snap = r.snapshot.value
        assertEquals(1, snap.devices.size)
        val d = snap.devices.first()
        assertTrue(d.id.isNotEmpty())
        // devices.json auf der Platte darf kein Passwort enthalten
        val raw = tmp.root.resolve("devices.json").readText()
        assertFalse(raw.contains("secret"))
        // JSON-Array wie in der Windows-App
        val arr = Json.parseToJsonElement(raw).jsonArray
        assertEquals(1, arr.size)
        assertEquals("PC1", arr[0].jsonObject["name"]?.jsonPrimitive?.content)
    }

    @Test
    fun saveDevice_updatesExistingById() {
        val r = repo()
        r.saveDevice(Device(name = "Alt", mac = "AA:BB:CC:DD:EE:02", id = "fix-id"))
        r.saveDevice(Device(name = "Neu", mac = "AA:BB:CC:DD:EE:02", id = "fix-id"))
        val devs = r.snapshot.value.devices
        assertEquals(1, devs.size)
        assertEquals("Neu", devs.first().name)
    }

    @Test
    fun password_neverStoredInJson() {
        val r = repo()
        r.saveDevice(Device(name = "P", mac = "AA:BB:CC:DD:EE:03", password = "geheim"))
        val stored = r.snapshot.value.devices.first()
        assertEquals("", stored.password)
        assertEquals("", r.getPassword(stored.id)) // ohne SecureStore leer
    }

    @Test
    fun deleteDevice_removesSchedules() {
        val r = repo()
        r.saveDevice(Device(name = "D", mac = "AA:BB:CC:DD:EE:04", id = "dev-x"))
        r.saveSchedule(ScheduleDef(deviceId = "dev-x", hour = 7, minute = 0))
        r.saveSchedule(ScheduleDef(deviceId = "other", hour = 8, minute = 0))
        r.deleteDevice("dev-x")
        val snap = r.snapshot.value
        assertTrue(snap.devices.isEmpty())
        assertEquals(1, snap.schedules.size)
        assertEquals("other", snap.schedules.first().deviceId)
    }

    @Test
    fun log_prependsAndCaps() {
        val r = repo()
        // Repo.log erzwingt ein Minimum von 10 Einträgen (coerceAtLeast(10))
        r.saveSettings(AppSettings(maxLogs = 10))
        for (i in 1..15) r.log("PC", "info", "M$i")
        val logs = r.snapshot.value.logs
        assertEquals(10, logs.size)
        assertEquals("M15", logs.first().msg) // neueste zuerst
        assertEquals("M6", logs.last().msg)
    }

    @Test
    fun clearLogs_empties() {
        val r = repo()
        r.log("PC", "info", "x")
        r.clearLogs()
        assertTrue(r.snapshot.value.logs.isEmpty())
    }

    @Test
    fun settings_roundTrip() {
        val r = repo()
        r.saveSettings(AppSettings(broadcastIp = "192.168.99.255", broadcastPort = 7, maxLogs = 500))
        // Neue Instanz liest denselben Ordner
        val r2 = repo()
        val s = r2.snapshot.value.settings
        assertEquals("192.168.99.255", s.broadcastIp)
        assertEquals(7, s.broadcastPort)
        assertEquals(500, s.maxLogs)

        r2.resetSettings()
        assertEquals("255.255.255.255", r2.snapshot.value.settings.broadcastIp)
    }

    @Test
    fun updateScheduleLastRun() {
        val r = repo()
        r.saveSchedule(ScheduleDef(id = "s1", deviceId = "d", hour = 6, minute = 45))
        r.updateScheduleLastRun("s1", 123456789L)
        assertNotNull(r.snapshot.value.schedules.first { it.id == "s1" })
        assertEquals(123456789L, r.snapshot.value.schedules.first { it.id == "s1" }.lastRun)
    }

    @Test
    fun load_corruptFile_yieldsEmpty() {
        tmp.root.mkdirs()
        tmp.root.resolve("devices.json").writeText("{ kein array")
        val r = repo()
        assertTrue(r.snapshot.value.devices.isEmpty())
    }
}
