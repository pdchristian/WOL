package de.wolmanager.ui.manage

import androidx.compose.foundation.background
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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.data.Device
import de.wolmanager.data.DiscoveredHost
import de.wolmanager.net.NetworkScanner
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.Pill
import de.wolmanager.ui.common.SectionHeading
import de.wolmanager.ui.common.StatusDot
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.devices.DeviceSheet
import de.wolmanager.ui.devices.SearchBox
import de.wolmanager.ui.devices.TileBtn
import de.wolmanager.ui.devices.statusColor
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.ui.theme.MonoStyle
import de.wolmanager.util.Validation
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Verwalten: Geräte-Liste (✏️ 🗑️) + Netzwerk-Scan (TCP-Sweep) mit Ergebnissen.
 */
@Composable
fun ManageScreen(devices: List<Device>, toast: (String) -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current
    val scope = rememberCoroutineScope()
    val savedMsg = stringResource(R.string.dev_saved)
    val deletedMsg = stringResource(R.string.dev_deleted)
    val noIfaceMsg = stringResource(R.string.manage_scan_none_msg)
    val dnsFmt = stringResource(R.string.manage_dns)
    val disabledLabel = stringResource(R.string.device_disabled)

    var search by remember { mutableStateOf("") }
    var editDevice by remember { mutableStateOf<Device?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf<Device?>(null) }

    // Scan-Zustand
    var ifaces by remember { mutableStateOf(container.scanner.activeInterfaces()) }
    var running by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf(0f) }
    var results by remember { mutableStateOf<List<DiscoveredHost>>(emptyList()) }
    var shown by remember { mutableStateOf(false) }
    var scanJob by remember { mutableStateOf<Job?>(null) }
    var dupMac by remember { mutableStateOf<String?>(null) }
    var unknownHost by remember { mutableStateOf<DiscoveredHost?>(null) }

    DisposableEffect(Unit) {
        ifaces = container.scanner.activeInterfaces()
        onDispose { scanJob?.cancel() }
    }

    val filtered = remember(devices, search) {
        val q = search.trim().lowercase()
        devices.filter {
            q.isEmpty() || it.name.lowercase().contains(q) || it.ip.lowercase().contains(q) ||
                it.mac.lowercase().contains(q) || it.username.lowercase().contains(q)
        }.sortedBy { it.name.lowercase() }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        // ── Geräte-Verwaltung ──────────────────────────────────────────────
        SectionHeading(stringResource(R.string.manage_sec_devices))
        Spacer(Modifier.height(6.dp))
        WolButton(text = stringResource(R.string.manage_add), onClick = { showAdd = true })
        Spacer(Modifier.height(8.dp))
        SearchBox(value = search, onValueChange = { search = it }, placeholder = stringResource(R.string.devices_search))
        Spacer(Modifier.height(10.dp))
        if (filtered.isEmpty()) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(t.surface.copy(alpha = 0.5f), RoundedCornerShape(14.dp))
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(stringResource(R.string.devices_empty), color = t.textDim, fontSize = 13.sp)
            }
        } else {
            WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
                filtered.forEachIndexed { i, d ->
                    if (i > 0) Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp)
                            .height(1.dp)
                            .background(t.border)
                    )
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusDot(statusColor(t, vm.runtime.value[d.id] ?: de.wolmanager.data.ConnState.UNKNOWN), 10.dp)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                d.name + if (!d.enabled) "  · " + disabledLabel else "",
                                color = if (d.enabled) t.text else t.textDim,
                                fontSize = 14.sp, fontWeight = FontWeight.Medium,
                                maxLines = 1, overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                listOf(d.ip, d.mac).filter { it.isNotBlank() }.joinToString(" · ").ifBlank { "—" },
                                style = MonoStyle, color = t.textDim, maxLines = 1,
                            )
                        }
                        TileBtn("✏️", enabled = true) { editDevice = d }
                        TileBtn("🗑️", enabled = true) { confirmDelete = d }
                    }
                }
            }
        }

        Spacer(Modifier.height(18.dp))

        // ── Netzwerk-Scan ──────────────────────────────────────────────────
        SectionHeading(stringResource(R.string.manage_sec_scan))
        Spacer(Modifier.height(6.dp))
        WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
            if (ifaces.isEmpty()) {
                Box(Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(stringResource(R.string.manage_scan_none_msg), color = t.textDim, fontSize = 12.sp)
                }
            }
            ifaces.forEachIndexed { i, f ->
                if (i > 0) Box(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp)
                        .height(1.dp)
                        .background(t.border)
                )
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            "${f.ip} / ${f.prefix}" +
                                if (f.dns.isNotBlank()) String.format(dnsFmt, f.dns) else "",
                            style = MonoStyle, color = t.text, fontSize = 12.sp,
                        )
                    }
                    androidx.compose.material3.Switch(
                        checked = f.checked,
                        onCheckedChange = { checked ->
                            ifaces = ifaces.mapIndexed { idx, x -> if (idx == i) x.copy(checked = checked) else x }
                        },
                        colors = androidx.compose.material3.SwitchDefaults.colors(
                            checkedTrackColor = t.accent,
                            checkedThumbColor = t.accentText,
                        ),
                    )
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            WolButton(
                text = stringResource(if (running) R.string.manage_scan_stop else R.string.manage_scan_start),
                onClick = {
                    if (running) {
                        scanJob?.cancel()
                        running = false
                    } else {
                        if (ifaces.none { it.checked }) {
                            toast(noIfaceMsg)
                        } else {
                            running = true
                            results = emptyList()
                            shown = false
                            progress = 0f
                            scanJob = scope.launch {
                                container.scanner.scan(ifaces).collect { ev ->
                                    when (ev) {
                                        is NetworkScanner.ScanEvent.Progress ->
                                            progress = if (ev.total > 0) ev.done.toFloat() / ev.total else 0f
                                        is NetworkScanner.ScanEvent.Found ->
                                            results = results + ev.host.copy(
                                                known = devices.any { it.ip == ev.host.ipv4 },
                                            )
                                        is NetworkScanner.ScanEvent.Done -> {
                                            running = false
                                            shown = true
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                enabled = !running || true,
                filled = !running,
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            when {
                running -> stringResource(R.string.manage_scan_running)
                shown -> stringResource(R.string.manage_scan_done, results.size)
                else -> stringResource(R.string.manage_scan_initial)
            },
            color = t.textDim, fontSize = 12.sp,
        )
        if (running) {
            Spacer(Modifier.height(6.dp))
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(5.dp),
                color = t.accent,
                trackColor = t.surfaceHover,
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(stringResource(R.string.manage_scan_note), color = t.textDim.copy(alpha = 0.8f), fontSize = 11.sp, lineHeight = 15.sp)
        Spacer(Modifier.height(10.dp))

        if (shown && results.isNotEmpty()) {
            WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
                results.forEachIndexed { i, r ->
                    if (i > 0) Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp)
                            .height(1.dp)
                            .background(t.border)
                    )
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusDot(t.online, 10.dp)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    r.hostname,
                                    color = t.text, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                )
                                Spacer(Modifier.width(6.dp))
                                Pill(
                                    text = stringResource(if (r.known) R.string.scan_known else R.string.scan_new),
                                    fg = if (r.known) t.blue else t.accent,
                                    bg = if (r.known) t.blue.copy(alpha = 0.14f) else t.accent.copy(alpha = 0.14f),
                                )
                            }
                            Text(
                                listOf(r.ipv4, r.mac).filter { it.isNotBlank() }.joinToString(" · "),
                                style = MonoStyle, color = t.textDim, maxLines = 1,
                            )
                        }
                        WolButton(
                            text = stringResource(R.string.manage_add_btn),
                            onClick = {
                                if (Validation.macExists(r.mac, devices.map { it.mac })) {
                                    dupMac = r.mac
                                } else if (r.mac.isBlank()) {
                                    unknownHost = r
                                } else {
                                    addScanned(container, r, devices, savedMsg, toast)
                                }
                            },
                            enabled = !r.known,
                            filled = false,
                        )
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    // ── Dialoge ────────────────────────────────────────────────────────────
    if (showAdd) {
        DeviceSheet(original = null, onDismiss = { showAdd = false }, onSaved = { dev, pass ->
            container.repo.saveDevice(dev.copy(password = pass))
            showAdd = false
            toast(savedMsg)
        })
    }
    editDevice?.let { d ->
        DeviceSheet(original = d, onDismiss = { editDevice = null }, onSaved = { dev, pass ->
            container.repo.saveDevice(dev.copy(password = pass))
            editDevice = null
            toast(savedMsg)
        })
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
    dupMac?.let { m ->
        WolConfirm(
            title = stringResource(R.string.mac_dup_title),
            message = stringResource(R.string.mac_dup_msg, m),
            confirmLabel = stringResource(R.string.dev_cancel),
            onConfirm = { dupMac = null },
            onDismiss = { dupMac = null },
        )
    }
    unknownHost?.let { r ->
        WolConfirm(
            title = stringResource(R.string.mac_unknown_title),
            message = stringResource(R.string.mac_unknown_msg, r.hostname, r.ipv4),
            confirmLabel = stringResource(R.string.manage_add_btn),
            onConfirm = {
                unknownHost = null
                addScanned(container, r.copy(mac = ""), devices, savedMsg, toast)
            },
            onDismiss = { unknownHost = null },
        )
    }
}

private fun addScanned(
    container: de.wolmanager.AppContainer,
    r: DiscoveredHost,
    devices: List<Device>,
    savedMsg: String,
    toast: (String) -> Unit,
) {
    val base = r.hostname.ifBlank { r.ipv4 }
    var name = base
    var n = 2
    val existing = devices.map { it.name.lowercase() }.toSet()
    while (name.lowercase() in existing) {
        name = "$base-$n"
        n++
    }
    container.repo.saveDevice(
        Device(name = name, mac = r.mac, ip = r.ipv4, shutdownMethod = "host_service")
    )
    toast(savedMsg)
}
