package de.wolmanager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.PowerSettingsNew
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.WolViewModel
import de.wolmanager.data.ConnState
import de.wolmanager.data.Device
import kotlin.math.abs

// Farbpalette — identisch zu wol_app/modern_theme.py (DARK-Tokens)
private val Bg = Color(0xFF0F1115)
private val SurfaceC = Color(0xFF1A1D24)
private val Hover = Color(0xFF232733)
private val Border = Color(0xFF2C303A)
private val TextC = Color(0xFFE6E8EE)
private val Dim = Color(0xFF9AA0AB)
private val Accent = Color(0xFF00B8A9)
private val AccentText = Color(0xFF032019)
private val Online = Color(0xFF22C55E)
private val Offline = Color(0xFFEF4444)
private val Unknown = Color(0xFFF59E0B)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WolApp(vm: WolViewModel) {
    val state by vm.state.collectAsState()
    var editing by remember { mutableStateOf<Device?>(null) }
    var showEditor by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<Device?>(null) }

    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(state.toast) {
        val t = state.toast ?: return@LaunchedEffect
        if (abs(System.currentTimeMillis() - t.ts) < 5000) {
            snackbar.showSnackbar(t.text)
        }
    }

    WolTheme {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("Wake-on-LAN", color = TextC, fontWeight = FontWeight.Bold)
                            val on = state.status.values.count { it == ConnState.ONLINE }
                            Text(
                                "${state.devices.size} Geräte · $on online",
                                color = Dim, fontSize = 12.sp,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = SurfaceC),
                    actions = {
                        IconButton(onClick = { showSettings = true }) {
                            Icon(Icons.Outlined.Settings, "Einstellungen", tint = Dim)
                        }
                    },
                )
            },
            containerColor = Bg,
        ) { pad ->
            Column(Modifier.padding(pad).fillMaxSize()) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "Geräte",
                        color = TextC, fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    // Graues ＋ links neben ↻ (wie im Prototyp)
                    SmallIconBtn(bg = Hover, fg = Dim, onClick = {
                        editing = null
                        showEditor = true
                    }) { Icon(Icons.Outlined.Add, "Hinzufügen", Modifier.size(18.dp)) }
                    SmallIconBtn(bg = Hover, fg = Dim, enabled = !state.checking, onClick = {
                        vm.checkAllStatuses()
                    }) {
                        if (state.checking) CircularProgressIndicator(
                            Modifier.width(16.dp).height(16.dp), color = Accent, strokeWidth = 2.dp)
                        else Icon(Icons.Outlined.Refresh, "Status prüfen", Modifier.size(18.dp))
                    }
                }

                if (state.devices.isEmpty()) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("Noch keine Geräte.\n＋ zum Hinzufügen.", color = Dim, fontSize = 14.sp)
                    }
                } else {
                    LazyColumn(
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        items(state.devices, key = { it.id }) { dev ->
                            DeviceCard(
                                device = dev,
                                conn = state.status[dev.id] ?: ConnState.UNKNOWN,
                                busy = dev.id in state.busyWaking,
                                onWake = { vm.wake(dev) },
                                onEdit = { editing = dev; showEditor = true },
                                onDelete = { pendingDelete = dev },
                            )
                        }
                    }
                }
            }
        }
    }

    if (showEditor) {
        DeviceEditorDialog(
            initial = editing,
            onDismiss = { showEditor = false },
            onSave = { d -> vm.saveDevice(d); showEditor = false },
        )
    }

    pendingDelete?.let { d ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            containerColor = SurfaceC,
            title = { Text("Löschen?", color = TextC) },
            text = { Text("„${d.name}“ wirklich entfernen?", color = Dim) },
            confirmButton = {
                TextButton(onClick = { vm.deleteDevice(d.id); pendingDelete = null }) {
                    Text("Löschen", color = Offline)
                }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("Abbrechen", color = Dim) }
            },
        )
    }

    if (showSettings) {
        SettingsDialog(prefs = state.prefs, onDismiss = { showSettings = false }, onSave = {
            vm.updatePrefs(it); showSettings = false
        })
    }
}

@Composable
private fun SmallIconBtn(
    bg: Color,
    fg: Color,
    enabled: Boolean = true,
    onClick: () -> Unit,
    content: @Composable () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = bg,
        contentColor = fg,
        modifier = Modifier.height(36.dp).width(36.dp),
    ) {
        Box(contentAlignment = Alignment.Center) {
            IconButton(onClick = onClick, enabled = enabled, modifier = Modifier.padding(0.dp)) {
                content()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeviceCard(
    device: Device,
    conn: ConnState,
    busy: Boolean,
    onWake: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = SurfaceC),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.width(10.dp).height(10.dp)
                        .background(dotColor(conn), CircleShape),
                )
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(device.name, color = TextC, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    Text(
                        buildString {
                            append(device.mac)
                            if (device.ip.isNotBlank()) append("  ·  ${device.ip}")
                        },
                        color = Dim, fontSize = 12.sp,
                    )
                }
                Text(
                    when (conn) {
                        ConnState.ONLINE -> "online"
                        ConnState.OFFLINE -> "offline"
                        ConnState.UNKNOWN -> "unbekannt"
                    },
                    color = dotColor(conn), fontSize = 12.sp,
                )
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onWake,
                    enabled = !busy && device.enabled,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Accent, contentColor = AccentText),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    if (busy) CircularProgressIndicator(Modifier.width(16.dp).height(16.dp),
                        color = AccentText, strokeWidth = 2.dp)
                    else Icon(Icons.Outlined.PowerSettingsNew, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Aufwecken")
                }
                IconButton(onClick = onEdit) {
                    Icon(Icons.Outlined.Edit, "Bearbeiten", tint = Dim)
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Outlined.Delete, "Löschen", tint = Offline)
                }
            }
            if (!device.enabled) {
                Text("deaktiviert", color = Dim, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

private fun dotColor(conn: ConnState): Color = when (conn) {
    ConnState.ONLINE -> Online
    ConnState.OFFLINE -> Offline
    ConnState.UNKNOWN -> Unknown
}

@Composable
private fun DeviceEditorDialog(
    initial: Device?,
    onDismiss: () -> Unit,
    onSave: (Device) -> Unit,
) {
    var name by remember { mutableStateOf(initial?.name ?: "") }
    var mac by remember { mutableStateOf(initial?.mac ?: "") }
    var ip by remember { mutableStateOf(initial?.ip ?: "") }
    var enabled by remember { mutableStateOf(initial?.enabled ?: true) }
    var err by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = SurfaceC,
        title = { Text(if (initial == null) "Neues Gerät" else "Gerät bearbeiten", color = TextC) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                DarkField("Name", name, { name = it; err = null })
                DarkField("MAC-Adresse", mac, { mac = it.uppercase(); err = null },
                    placeholder = "AA:BB:CC:DD:EE:FF")
                DarkField("IP (optional)", ip, { ip = it; err = null },
                    placeholder = "192.168.1.10")
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("aktiv", color = TextC, fontSize = 14.sp, modifier = Modifier.weight(1f))
                    Switch(
                        checked = enabled,
                        onCheckedChange = { enabled = it },
                        colors = SwitchDefaults.colors(checkedTrackColor = Accent),
                    )
                }
                err?.let { Text(it, color = Offline, fontSize = 12.sp) }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val m = mac.trim()
                when {
                    name.isBlank() -> err = "Name fehlt"
                    !de.wolmanager.net.WolSender.isValidMac(m) -> err = "MAC-Format: 12 hexadezimale Ziffern"
                    else -> onSave(Device(
                        id = initial?.id ?: java.util.UUID.randomUUID().toString(),
                        name = name.trim(), mac = m, ip = ip.trim(),
                        username = initial?.username ?: "", password = initial?.password ?: "",
                        enabled = enabled,
                    ))
                }
            }) { Text("Speichern", color = Accent) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen", color = Dim) } },
    )
}

@Composable
private fun SettingsDialog(
    prefs: de.wolmanager.data.AppPrefs,
    onDismiss: () -> Unit,
    onSave: (de.wolmanager.data.AppPrefs) -> Unit,
) {
    var port by remember { mutableStateOf(prefs.servicePort.toString()) }
    var bcast by remember { mutableStateOf(prefs.broadcastIp) }
    var wolPort by remember { mutableStateOf(prefs.wolPort.toString()) }
    var check by remember { mutableStateOf(prefs.statusCheckEnabled) }
    var err by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = SurfaceC,
        title = { Text("Einstellungen", color = TextC) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                DarkField("Host-Service-Port", port, { port = it.filter { c -> c.isDigit() }; err = null })
                DarkField("Broadcast-IP", bcast, { bcast = it; err = null })
                DarkField("WOL-Port", wolPort, { wolPort = it.filter { c -> c.isDigit() }; err = null })
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Status-Check aktiv", color = TextC, fontSize = 14.sp, modifier = Modifier.weight(1f))
                    Switch(
                        checked = check,
                        onCheckedChange = { check = it },
                        colors = SwitchDefaults.colors(checkedTrackColor = Accent),
                    )
                }
                err?.let { Text(it, color = Offline, fontSize = 12.sp) }
                Text(
                    "Hinweis: Status-Check nutzt Host-Service v4 (TCP, Befehl „status“). " +
                        "Ohne Dienst bleibt der Status „unbekannt“.",
                    color = Dim, fontSize = 11.sp,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val p = port.toIntOrNull()
                val w = wolPort.toIntOrNull()
                when {
                    p == null || p !in 1..65535 -> err = "Port 1–65535"
                    w == null || w !in 1..65535 -> err = "WOL-Port 1–65535"
                    bcast.isBlank() -> err = "Broadcast-IP fehlt"
                    else -> onSave(
                        prefs.copy(servicePort = p, broadcastIp = bcast.trim(), wolPort = w,
                            statusCheckEnabled = check)
                    )
                }
            }) { Text("Speichern", color = Accent) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen", color = Dim) } },
    )
}

@Composable
private fun DarkField(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    placeholder: String = "",
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label, color = Dim) },
        placeholder = { if (placeholder.isNotEmpty()) Text(placeholder, color = Dim.copy(alpha = 0.6f)) },
        singleLine = true,
        textStyle = androidx.compose.ui.text.TextStyle(color = TextC, fontSize = 14.sp),
        colors = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
            focusedBorderColor = Accent,
            unfocusedBorderColor = Border,
            focusedLabelColor = Accent,
            cursorColor = Accent,
        ),
        modifier = Modifier.fillMaxWidth(),
    )
}
