package de.wolmanager.ui.devices

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.LocalRecreate
import de.wolmanager.R
import de.wolmanager.data.ConnState
import de.wolmanager.data.Device
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.ConsoleBox
import de.wolmanager.ui.common.Pill
import de.wolmanager.ui.common.SectionHeading
import de.wolmanager.ui.common.StatusDot
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.common.WolField
import de.wolmanager.ui.common.WolSheet
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.ui.theme.MonoStyle
import kotlinx.coroutines.launch

/** Gerätebildschirm: Kachel-/Listenansicht, Suche, Sortierung, Long-Press-Menü. */
@Composable
fun DevicesScreen(devices: List<Device>, runtime: Map<String, ConnState>, toast: (String) -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current
    val scope = rememberCoroutineScope()

    var isGrid by remember { mutableStateOf(true) }
    var sortIdx by remember { mutableStateOf(0) }
    var search by remember { mutableStateOf("") }
    var menuDevice by remember { mutableStateOf<Device?>(null) }
    var editDevice by remember { mutableStateOf<Device?>(null) }
    var showAddFromMenu by remember { mutableStateOf(false) }
    var confirmWakeAll by remember { mutableStateOf(false) }
    var confirmShutdown by remember { mutableStateOf<Device?>(null) }
    var confirmDelete by remember { mutableStateOf<Device?>(null) }

    val sortOptions = listOf(
        stringResource(R.string.sort_name),
        stringResource(R.string.sort_ip),
        stringResource(R.string.sort_mac),
        stringResource(R.string.sort_status),
    )

    val wolSentMsg = stringResource(R.string.wol_sent)
    val wolFailMsg = stringResource(R.string.wol_fail)
    val wakeallDoneMsg = stringResource(R.string.wakeall_done)
    val pingOkMsg = stringResource(R.string.ping_ok)
    val pingFailMsg = stringResource(R.string.ping_fail)
    val smbNoteMsg = stringResource(R.string.dev_method_smb_note)
    val deletedMsg = stringResource(R.string.dev_deleted)
    val savedMsg = stringResource(R.string.dev_saved)
    val remoteMsg = stringResource(R.string.remote_unavailable)
    val shutdownLabel = stringResource(R.string.devices_shutdown)

    val onlineCount = devices.count { runtime[it.id] == ConnState.ONLINE }
    val filtered = remember(devices, search, sortIdx, runtime) {
        val q = search.trim().lowercase()
        val list = devices.filter {
            q.isEmpty() ||
                it.name.lowercase().contains(q) || it.ip.lowercase().contains(q) ||
                it.mac.lowercase().contains(q) || it.username.lowercase().contains(q)
        }.toMutableList()
        val rank = mapOf(ConnState.ONLINE to 0, ConnState.OFFLINE to 1, ConnState.WAKING to 2, ConnState.UNKNOWN to 3)
        when (sortIdx) {
            1 -> list.sortBy { ipKey(it.ip) }
            2 -> list.sortBy { it.mac }
            3 -> list.sortWith(compareBy({ rank[runtime[it.id]] ?: 3 }, { it.name.lowercase() }))
            else -> list.sortBy { it.name.lowercase() }
        }
        list
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        // Zusammenfassung
        Text(
            stringResource(R.string.devices_summary, devices.size, onlineCount),
            color = t.textDim, fontSize = 12.sp,
            modifier = Modifier.padding(bottom = 10.dp),
        )

        // Werkzeugleiste: Ansicht / Aktualisieren / Alle starten
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconAction(if (isGrid) "☰" else "▦", stringResource(R.string.devices_view_list)) { isGrid = !isGrid }
            Spacer(Modifier.height(0.dp))
            IconAction("⟳", stringResource(R.string.devices_refresh)) { vm.refreshAll(devices) }
            Spacer(Modifier.weight(1f))
            WolButton(
                text = stringResource(R.string.devices_wake_all),
                onClick = { confirmWakeAll = true },
                enabled = devices.any { it.enabled },
            )
        }
        Spacer(Modifier.height(8.dp))

        // Sortierung + Suche
        Row(verticalAlignment = Alignment.CenterVertically) {
            WolDropdown(
                label = "",
                options = sortOptions,
                selected = sortIdx,
                onSelect = { sortIdx = it },
                modifier = Modifier.weight(0.42f),
            )
            Spacer(Modifier.height(0.dp))
            Box(Modifier.weight(1f)) {
                SearchBox(value = search, onValueChange = { search = it }, placeholder = stringResource(R.string.devices_search))
            }
        }
        Spacer(Modifier.height(12.dp))

        if (filtered.isEmpty()) {
            EmptyBox(stringResource(R.string.devices_empty))
        } else if (isGrid) {
            DeviceGrid(filtered, runtime, onMenu = { menuDevice = it }, onWake = { d ->
                scope.launch {
                    vm.setStatus(d.id, ConnState.WAKING)
                    val ok = container.wake(d).isSuccess
                    if (ok) toast(String.format(wolSentMsg, d.name))
                    else toast(String.format(wolFailMsg, 1))
                }
            }, onShutdown = { confirmShutdown = it }, onDashboard = { vm.openDashboard(it.id) }, onRemote = { toast(remoteMsg) })
        } else {
            DeviceList(filtered, runtime, onMenu = { menuDevice = it }, onEdit = { editDevice = it }, onDashboard = { vm.openDashboard(it.id) }, onRemote = { toast(remoteMsg) })
        }
        Spacer(Modifier.height(20.dp))
    }

    // ── Long-Press-Menü ────────────────────────────────────────────────────
    menuDevice?.let { d ->
        val st = runtime[d.id] ?: ConnState.UNKNOWN
        DeviceActionSheet(
            device = d,
            status = st,
            onDismiss = { menuDevice = null },
            onRemote = { toast(remoteMsg) },
            onDashboard = { menuDevice = null; vm.openDashboard(d.id) },
            onShutdown = { menuDevice = null; confirmShutdown = d },
            onWake = {
                menuDevice = null
                scope.launch {
                    vm.setStatus(d.id, ConnState.WAKING)
                    val ok = container.wake(d).isSuccess
                    toast(if (ok) String.format(wolSentMsg, d.name) else String.format(wolFailMsg, 1))
                }
            },
            onPing = {
                menuDevice = null
                scope.launch {
                    val rtt = container.hostClient.ping(d.ip.ifBlank { d.mac })
                    toast(
                        if (rtt != null) String.format(pingOkMsg, d.ip, rtt.toString())
                        else String.format(pingFailMsg, d.ip)
                    )
                }
            },
            onEdit = { menuDevice = null; editDevice = d },
            onDelete = { menuDevice = null; confirmDelete = d },
        )
    }

    // ── Bestätigungen ──────────────────────────────────────────────────────
    if (confirmWakeAll) {
        val n = devices.count { it.enabled }
        WolConfirm(
            title = stringResource(R.string.wakeall_title),
            message = stringResource(R.string.wakeall_message, n),
            confirmLabel = stringResource(R.string.devices_wake_all),
            onConfirm = {
                confirmWakeAll = false
                scope.launch {
                    var sent = 0
                    devices.filter { it.enabled }.forEach { d ->
                        if (container.wake(d).isSuccess) sent++
                    }
                    toast(String.format(wakeallDoneMsg, sent))
                }
            },
            onDismiss = { confirmWakeAll = false },
        )
    }
    confirmShutdown?.let { d ->
        WolConfirm(
            title = stringResource(R.string.shutdown_title),
            message = "${d.name}: " + stringResource(R.string.shutdown_message),
            confirmLabel = stringResource(R.string.devices_shutdown),
            destructive = true,
            onConfirm = {
                confirmShutdown = null
                scope.launch {
                    val res = container.shutdown(d)
                    toast(
                        when {
                            res.isSuccess -> shutdownLabel + ": " + d.name
                            res.exceptionOrNull()?.message == "smb" -> smbNoteMsg
                            else -> String.format(pingFailMsg, d.name)
                        }
                    )
                }
            },
            onDismiss = { confirmShutdown = null },
        )
    }
    confirmDelete?.let { d ->
        WolConfirm(
            title = stringResource(R.string.del_title),
            message = stringResource(R.string.del_message, d.name),
            confirmLabel = stringResource(R.string.edit_delete),
            destructive = true,
            onConfirm = {
                confirmDelete = null
                container.repo.deleteDevice(d.id)
                toast(deletedMsg)
            },
            onDismiss = { confirmDelete = null },
        )
    }

    // ── Bearbeiten-Dialog ──────────────────────────────────────────────────
    editDevice?.let { d ->
        DeviceSheet(
            original = d,
            onDismiss = { editDevice = null },
            onSaved = { dev, pass ->
                val stored = dev.copy(password = pass)
                container.repo.saveDevice(stored)
                editDevice = null
                toast(savedMsg)
            },
        )
    }
}

private fun ipKey(ip: String): String =
    ip.split(".").joinToString(".") { n -> n.length.toString().padStart(2, '0') + n }

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun IconAction(symbol: String, contentDesc: String, onClick: () -> Unit) {
    val t = LocalWolTokens.current
    Box(
        modifier = Modifier
            .padding(end = 6.dp)
            .background(t.surfaceHover.copy(alpha = 0.6f), RoundedCornerShape(9.dp))
            .combinedClickable(onClick = onClick, onLongClick = null)
            .padding(horizontal = 11.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(symbol, fontSize = 15.sp, color = t.text)
    }
}

@Composable
fun SearchBox(value: String, onValueChange: (String) -> Unit, placeholder: String) {
    val t = LocalWolTokens.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(t.surfaceHover.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
            .border(1.dp, t.border, RoundedCornerShape(10.dp))
            .padding(horizontal = 10.dp, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("🔍", fontSize = 13.sp)
        androidx.compose.foundation.text.BasicTextField(
            value = value,
            onValueChange = onValueChange,
            maxLines = 1,
            textStyle = androidx.compose.ui.text.TextStyle(fontSize = 13.sp, color = t.text),
            modifier = Modifier.padding(start = 6.dp, top = 10.dp, bottom = 10.dp).fillMaxWidth(),
            decorationBox = { inner ->
                Box {
                    if (value.isEmpty()) Text(placeholder, color = t.textDim.copy(alpha = 0.6f), fontSize = 13.sp)
                    inner()
                }
            },
        )
    }
}

@Composable
fun EmptyBox(text: String) {
    val t = LocalWolTokens.current
    Box(
        Modifier
            .fillMaxWidth()
            .background(t.surface.copy(alpha = 0.5f), RoundedCornerShape(14.dp))
            .border(1.dp, t.border, RoundedCornerShape(14.dp))
            .padding(28.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = t.textDim, fontSize = 13.sp)
    }
}

fun statusColor(t: de.wolmanager.ui.theme.WolTokens, s: ConnState): Color = when (s) {
    ConnState.ONLINE -> t.online
    ConnState.OFFLINE -> t.offline
    ConnState.WAKING -> t.blue
    ConnState.UNKNOWN -> t.unknown
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DeviceGrid(
    devices: List<Device>,
    runtime: Map<String, ConnState>,
    onMenu: (Device) -> Unit,
    onWake: (Device) -> Unit,
    onShutdown: (Device) -> Unit,
    onDashboard: (Device) -> Unit,
    onRemote: () -> Unit,
) {
    val t = LocalWolTokens.current
    // Kein Lazy: Ansicht ist in eine scrollbare Spalte eingebettet; Gerätezahl ist klein.
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        devices.chunked(2).forEach { rowDevs ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                rowDevs.forEach { d ->
                    val st = runtime[d.id] ?: ConnState.UNKNOWN
                    val enabled = d.enabled
                    WolCard(
                        modifier = Modifier
                            .weight(1f)
                            .alpha(if (enabled) 1f else 0.55f)
                            .combinedClickable(onClick = { }, onLongClick = { onMenu(d) }),
                        contentPadding = PaddingValues(12.dp),
                    ) {
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                StatusDot(statusColor(t, st), 10.dp)
                                Spacer(Modifier.width(6.dp))
                                Text(
                                    d.name,
                                    color = t.text, fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f, fill = false),
                                )
                            }
                            if (!enabled) {
                                Text(
                                    stringResource(R.string.device_disabled),
                                    color = t.textDim, fontSize = 10.sp,
                                )
                            }
                            if (d.ip.isNotBlank()) {
                                Text(d.ip, style = MonoStyle, color = t.textDim, maxLines = 1)
                            }
                            Text(d.mac, style = MonoStyle, color = t.textDim, maxLines = 1)
                            Spacer(Modifier.height(8.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                TileBtn("🖥️", enabled = st == ConnState.ONLINE) { onRemote() }
                                TileBtn("🪟", enabled = st == ConnState.ONLINE) { onRemote() }
                                TileBtn("📊", enabled = st == ConnState.ONLINE) { onDashboard(d) }
                            }
                            Spacer(Modifier.height(8.dp))
                            if (st == ConnState.ONLINE) {
                                WolButton(
                                    text = stringResource(R.string.devices_shutdown),
                                    onClick = { onShutdown(d) },
                                    modifier = Modifier.fillMaxWidth(),
                                    filled = false,
                                )
                            } else {
                                WolButton(
                                    text = stringResource(R.string.devices_wake),
                                    onClick = { onWake(d) },
                                    modifier = Modifier.fillMaxWidth(),
                                    enabled = enabled && st != ConnState.WAKING,
                                    filled = false,
                                )
                            }
                        }
                    }
                }
                if (rowDevs.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DeviceList(
    devices: List<Device>,
    runtime: Map<String, ConnState>,
    onMenu: (Device) -> Unit,
    onEdit: (Device) -> Unit,
    onDashboard: (Device) -> Unit,
    onRemote: () -> Unit,
) {
    val t = LocalWolTokens.current
    WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
        devices.forEachIndexed { i, d ->
            if (i > 0) Box(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp)
                    .height(1.dp)
                    .background(t.border)
            )
            val st = runtime[d.id] ?: ConnState.UNKNOWN
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .combinedClickable(
                        onClick = { onMenu(d) },
                        onLongClick = { onMenu(d) },
                    )
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusDot(statusColor(t, st), 10.dp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        d.name + if (!d.enabled) "  · " + stringResource(R.string.device_disabled) else "",
                        color = if (d.enabled) t.text else t.textDim,
                        fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        listOf(d.ip, d.mac).filter { it.isNotBlank() }.joinToString(" · "),
                        style = MonoStyle, color = t.textDim, maxLines = 1,
                    )
                }
                TileBtn("🖥️", enabled = st == ConnState.ONLINE) { onRemote() }
                TileBtn("📊", enabled = st == ConnState.ONLINE) { onDashboard(d) }
                TileBtn("✏️", enabled = true) { onEdit(d) }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TileBtn(symbol: String, enabled: Boolean, onClick: () -> Unit) {
    val t = LocalWolTokens.current
    Box(
        modifier = Modifier
            .padding(start = 4.dp)
            .background(
                if (enabled) t.surfaceHover.copy(alpha = 0.8f) else t.surfaceHover.copy(alpha = 0.3f),
                RoundedCornerShape(8.dp),
            )
            .then(if (enabled) Modifier.combinedClickable(onClick = onClick) else Modifier)
            .padding(horizontal = 8.dp, vertical = 5.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(symbol, fontSize = 13.sp, color = if (enabled) t.text else t.textDim.copy(alpha = 0.4f))
    }
}

/** Long-Press-Kontextmenü (Bottom-Sheet) — entspricht dem Rechtsklick-Menü der Windows-App. */
@Composable
private fun DeviceActionSheet(
    device: Device,
    status: ConnState,
    onDismiss: () -> Unit,
    onRemote: () -> Unit,
    onDashboard: () -> Unit,
    onShutdown: () -> Unit,
    onWake: () -> Unit,
    onPing: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    val t = LocalWolTokens.current
    val online = status == ConnState.ONLINE
    WolSheet(onDismiss = onDismiss, title = device.name) {
        MenuRow("🖥️", stringResource(R.string.button_remote_fullscreen), enabled = false, onClick = onRemote)
        MenuRow("🪟", stringResource(R.string.button_remote_window), enabled = false, onClick = onRemote)
        MenuRow("📊", stringResource(R.string.button_dashboard), enabled = online, onClick = onDashboard)
        if (online) {
            MenuRow("⏻", stringResource(R.string.devices_shutdown), enabled = true, onClick = onShutdown, destructive = true)
        } else {
            MenuRow("⚡", stringResource(R.string.devices_wake), enabled = device.enabled, onClick = onWake)
        }
        MenuRow("📡", stringResource(R.string.button_ping), enabled = device.ip.isNotBlank(), onClick = onPing)
        MenuRow("✏️", stringResource(R.string.edit_title), enabled = true, onClick = onEdit)
        MenuRow("🗑️", stringResource(R.string.edit_delete), enabled = true, onClick = onDelete, destructive = true)
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MenuRow(icon: String, label: String, enabled: Boolean, destructive: Boolean = false, onClick: () -> Unit) {
    val t = LocalWolTokens.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(if (enabled) 1f else 0.45f)
            .then(if (enabled) Modifier.combinedClickable(onClick = onClick) else Modifier)
            .padding(vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(icon, fontSize = 16.sp, modifier = Modifier.padding(end = 12.dp))
        Text(
            label,
            color = when {
                destructive -> t.danger
                else -> t.text
            },
            fontSize = 14.sp,
        )
    }
}
