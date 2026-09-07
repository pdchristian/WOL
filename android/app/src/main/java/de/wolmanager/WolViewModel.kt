package de.wolmanager

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import de.wolmanager.data.AppPrefs
import de.wolmanager.data.ConnState
import de.wolmanager.data.Device
import de.wolmanager.data.DeviceStore
import de.wolmanager.net.HostClient
import de.wolmanager.net.WolSender
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

data class ToastMsg(val text: String, val ok: Boolean, val ts: Long = System.currentTimeMillis())

data class UiState(
    val devices: List<Device> = emptyList(),
    val prefs: AppPrefs = AppPrefs(),
    val status: Map<String, ConnState> = emptyMap(),
    val busyWaking: Set<String> = emptySet(),
    val checking: Boolean = false,
    val toast: ToastMsg? = null,
)

class WolViewModel(private val app: Application) : ViewModel() {
    private val store = DeviceStore(File(app.filesDir, "data").apply { mkdirs() })
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    init {
        _state.value = UiState(
            devices = store.loadDevices(),
            prefs = store.loadPrefs(),
        )
    }

    private fun persist() {
        store.saveDevices(_state.value.devices)
        store.savePrefs(_state.value.prefs)
    }

    fun toast(text: String, ok: Boolean = true) {
        _state.value = _state.value.copy(toast = ToastMsg(text, ok))
    }

    fun saveDevice(device: Device) {
        val list = _state.value.devices.toMutableList()
        val idx = list.indexOfFirst { it.id == device.id }
        if (idx >= 0) list[idx] = device else list.add(device)
        _state.value = _state.value.copy(devices = list)
        persist()
        toast(if (idx >= 0) "Gerät aktualisiert" else "Gerät angelegt")
    }

    fun deleteDevice(id: String) {
        val d = _state.value.devices.firstOrNull { it.id == id }
        _state.value = _state.value.copy(devices = _state.value.devices.filter { it.id != id })
        persist()
        toast("„${d?.name ?: "?"}“ gelöscht", ok = false)
    }

    fun updatePrefs(prefs: AppPrefs) {
        _state.value = _state.value.copy(prefs = prefs)
        persist()
    }

    fun wake(device: Device) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busyWaking = _state.value.busyWaking + device.id)
            val prefs = _state.value.prefs
            val res = WolSender.send(app, device, prefs.broadcastIp, prefs.wolPort)
            _state.value = _state.value.copy(busyWaking = _state.value.busyWaking - device.id)
            res.onSuccess {
                _state.value = _state.value.copy(status = _state.value.status + (device.id to ConnState.UNKNOWN))
                toast("Wake gesendet · ${device.name}")
            }.onFailure {
                toast("Wake-Fehler ${device.name}: ${it.message}", ok = false)
            }
        }
    }

    fun checkAllStatuses() {
        viewModelScope.launch {
            val prefs = _state.value.prefs
            if (!prefs.statusCheckEnabled) {
                toast("Status-Check deaktiviert", ok = false)
                return@launch
            }
            _state.value = _state.value.copy(checking = true)
            val snapshot = _state.value.devices.filter { it.ip.isNotBlank() }
            val result = withContext(Dispatchers.IO) {
                snapshot.map { dev ->
                    val st = try {
                        val reply = HostClient.status(dev.ip, prefs.servicePort)
                        if (reply.status == "ok") ConnState.ONLINE else ConnState.UNKNOWN
                    } catch (_: Exception) {
                        ConnState.OFFLINE
                    }
                    dev.id to st
                }.toMap()
            }
            val online = result.values.count { it == ConnState.ONLINE }
            _state.value = _state.value.copy(
                status = _state.value.status + result,
                checking = false,
            )
            toast("Status-Check: $online/${snapshot.size} erreichbar")
        }
    }
}

class WolVmFactory(private val app: Application) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        if (modelClass.isAssignableFrom(WolViewModel::class.java)) WolViewModel(app) as T
        else throw IllegalArgumentException("Unknown VM: ${modelClass.name}")
}
