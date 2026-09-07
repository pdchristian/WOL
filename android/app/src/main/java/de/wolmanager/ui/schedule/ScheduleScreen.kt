package de.wolmanager.ui.schedule

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import de.wolmanager.data.ScheduleDef
import de.wolmanager.sched.ScheduleEngine
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.StatusDot
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.devices.SearchBox
import de.wolmanager.ui.devices.TileBtn
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.ui.theme.MonoStyle

/**
 * Zeitplan: Liste + Erstellen/Bearbeiten im Bottom-Sheet.
 * Actions: wake/shutdown — Ausführung durch In-App-Ticker + WorkManager.
 */
@Composable
fun ScheduleScreen(devices: List<Device>, schedules: List<ScheduleDef>, toast: (String) -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current

    var search by remember { mutableStateOf("") }
    var editSchedule by remember { mutableStateOf<ScheduleDef?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf<ScheduleDef?>(null) }
    var noDevices by remember { mutableStateOf(false) }

    val dayLabels = listOf(
        stringResource(R.string.day_mon), stringResource(R.string.day_tue), stringResource(R.string.day_wed),
        stringResource(R.string.day_thu), stringResource(R.string.day_fri), stringResource(R.string.day_sat),
        stringResource(R.string.day_sun),
    )
    val everyMsg = stringResource(R.string.sched_days_every)
    val weekdaysMsg = stringResource(R.string.sched_days_weekdays)
    val savedMsg = stringResource(R.string.sc_saved)

    fun daysText(days: List<String>): String {
        return when {
            days.size == 7 -> everyMsg
            days == listOf("Mon", "Tue", "Wed", "Thu", "Fri") -> weekdaysMsg
            else -> ScheduleEngine.DAY_KEYS.filter { days.contains(it) }
                .joinToString(", ") { k -> dayLabels[ScheduleEngine.DAY_KEYS.indexOf(k)] }
        }
    }

    val sorted = remember(schedules) { schedules.sortedBy { ScheduleEngine.formatTime(it.hour, it.minute) } }
    val filtered = remember(sorted, search, devices) {
        val q = search.trim().lowercase()
        if (q.isEmpty()) sorted
        else sorted.filter { s ->
            val name = devices.firstOrNull { it.id == s.deviceId }?.name ?: ""
            (name + " " + ScheduleEngine.formatTime(s.hour, s.minute) + " " + daysText(s.days))
                .lowercase().contains(q)
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        WolButton(
            text = stringResource(R.string.sched_add),
            onClick = {
                if (devices.isEmpty()) noDevices = true else showAdd = true
            },
        )
        Spacer(Modifier.height(8.dp))
        SearchBox(value = search, onValueChange = { search = it }, placeholder = stringResource(R.string.sched_search))
        Spacer(Modifier.height(10.dp))

        if (filtered.isEmpty()) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(t.surface.copy(alpha = 0.5f), RoundedCornerShape(14.dp))
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(stringResource(R.string.sched_empty), color = t.textDim, fontSize = 13.sp)
            }
        } else {
            WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
                filtered.forEachIndexed { i, s ->
                    if (i > 0) Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp)
                            .height(1.dp)
                            .background(t.border)
                    )
                    val device = devices.firstOrNull { it.id == s.deviceId }
                    val isWake = s.isWake
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .alpha(if (s.enabled) 1f else 0.55f)
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusDot(if (isWake) t.accent else t.danger, 9.dp)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                device?.name ?: stringResource(R.string.sc_unknown),
                                color = t.text, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                                maxLines = 1, overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                "${daysText(s.days)} · ${ScheduleEngine.formatTime(s.hour, s.minute)} · " +
                                    stringResource(if (isWake) R.string.sched_wake else R.string.sched_shutdown),
                                style = MonoStyle, color = t.textDim, maxLines = 1,
                            )
                        }
                        androidx.compose.material3.Switch(
                            checked = s.enabled,
                            onCheckedChange = { on ->
                                container.repo.saveSchedule(s.copy(enabled = on))
                                container.syncSchedules()
                            },
                            colors = androidx.compose.material3.SwitchDefaults.colors(
                                checkedTrackColor = t.accent,
                                checkedThumbColor = t.accentText,
                            ),
                        )
                        TileBtn("✏️", enabled = true) { editSchedule = s }
                        TileBtn("🗑️", enabled = true) { confirmDelete = s }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    if (showAdd) {
        ScheduleSheet(
            original = null,
            devices = devices,
            onDismiss = { showAdd = false },
            onSaved = { s ->
                container.repo.saveSchedule(s)
                container.syncSchedules()
                showAdd = false
                toast(savedMsg)
            },
        )
    }
    editSchedule?.let { s ->
        ScheduleSheet(
            original = s,
            devices = devices,
            onDismiss = { editSchedule = null },
            onSaved = { saved ->
                container.repo.saveSchedule(saved)
                container.syncSchedules()
                editSchedule = null
                toast(savedMsg)
            },
        )
    }
    confirmDelete?.let { s ->
        val name = devices.firstOrNull { it.id == s.deviceId }?.name ?: ""
        WolConfirm(
            title = stringResource(R.string.sched_del_title),
            message = stringResource(R.string.sched_del_message, name),
            confirmLabel = stringResource(R.string.edit_delete),
            destructive = true,
            onConfirm = {
                confirmDelete = null
                container.repo.deleteSchedule(s.id)
                container.syncSchedules()
            },
            onDismiss = { confirmDelete = null },
        )
    }
    if (noDevices) {
        WolConfirm(
            title = stringResource(R.string.sched_no_dev_title),
            message = stringResource(R.string.sched_no_dev_msg),
            confirmLabel = stringResource(R.string.dev_cancel),
            onConfirm = { noDevices = false },
            onDismiss = { noDevices = false },
        )
    }
}

