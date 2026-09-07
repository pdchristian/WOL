package de.wolmanager.ui.schedule

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberTimePickerState
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.data.Device
import de.wolmanager.data.ScheduleDef
import de.wolmanager.sched.ScheduleEngine
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.common.WolSheet
import de.wolmanager.ui.common.WolToggle
import de.wolmanager.ui.theme.LocalWolTokens

/**
 * Bottom-Sheet zum Anlegen/Bearbeiten eines Zeitplans:
 * Gerät, Aktion, Zeit, Wochentage (Chips), Aktivierung.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleSheet(
    original: ScheduleDef?,
    devices: List<Device>,
    onDismiss: () -> Unit,
    onSaved: (ScheduleDef) -> Unit,
) {
    val t = LocalWolTokens.current
    val isEdit = original != null && original.id.isNotEmpty()

    var deviceId by remember { mutableStateOf(original?.deviceId ?: devices.firstOrNull()?.id ?: "") }
    var actionWake by remember { mutableStateOf(original?.isWake ?: true) }
    var hour by remember { mutableStateOf(original?.hour ?: 7) }
    var minute by remember { mutableStateOf(original?.minute ?: 30) }
    var days by remember { mutableStateOf(original?.days ?: ScheduleEngine.DAY_KEYS.toList()) }
    var enabled by remember { mutableStateOf(original?.enabled ?: true) }
    var showTime by remember { mutableStateOf(false) }
    var noDays by remember { mutableStateOf(false) }

    val deviceNames = devices.map { it.name }
    val deviceIdx = devices.indexOfFirst { it.id == deviceId }.coerceAtLeast(0)
    val dayLabels = listOf(
        stringResource(R.string.day_mon), stringResource(R.string.day_tue), stringResource(R.string.day_wed),
        stringResource(R.string.day_thu), stringResource(R.string.day_fri), stringResource(R.string.day_sat),
        stringResource(R.string.day_sun),
    )

    WolSheet(onDismiss = onDismiss, title = stringResource(if (isEdit) R.string.sc_edit else R.string.sc_add)) {
        Column(Modifier.verticalScroll(rememberScrollState())) {
            Text(stringResource(R.string.sc_device), color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
            WolDropdown(
                label = "",
                options = if (deviceNames.isEmpty()) listOf("—") else deviceNames,
                selected = deviceIdx,
                onSelect = { deviceId = devices[it].id },
            )
            Spacer(Modifier.height(12.dp))

            Text(stringResource(R.string.sc_action), color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SegChip(stringResource(R.string.sc_act_wake), actionWake) { actionWake = true }
                SegChip(stringResource(R.string.sc_act_shutdown), !actionWake) { actionWake = false }
            }
            Spacer(Modifier.height(12.dp))

            Text(stringResource(R.string.sc_time), color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(t.surfaceHover.copy(alpha = 0.35f), RoundedCornerShape(8.dp))
                    .clickable { showTime = true }
                    .padding(horizontal = 12.dp, vertical = 13.dp),
            ) {
                Text(
                    ScheduleEngine.formatTime(hour, minute),
                    color = t.text, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
                )
            }
            Spacer(Modifier.height(12.dp))

            Text(stringResource(R.string.sc_days), color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                ScheduleEngine.DAY_KEYS.forEachIndexed { i, key ->
                    val on = days.contains(key)
                    DayChip(dayLabels[i], on) {
                        days = if (on) days - key else days + key
                    }
                }
            }
            Spacer(Modifier.height(10.dp))

            WolToggle(
                label = stringResource(R.string.sc_enabled),
                checked = enabled,
                onCheckedChange = { enabled = it },
            )
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                WolButton(
                    text = stringResource(R.string.dev_cancel),
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                    filled = false,
                )
                WolButton(
                    text = stringResource(R.string.dev_save),
                    onClick = {
                        if (days.isEmpty()) { noDays = true; return@WolButton }
                        onSaved(
                            ScheduleDef(
                                id = original?.id ?: "",
                                deviceId = deviceId,
                                hour = hour,
                                minute = minute,
                                days = ScheduleEngine.DAY_KEYS.filter { days.contains(it) },
                                enabled = enabled,
                                action = if (actionWake) "wake" else "shutdown",
                                lastRun = original?.lastRun ?: 0L,
                            )
                        )
                    },
                    modifier = Modifier.weight(1f),
                )
            }
            if (noDays) {
                Text(
                    stringResource(R.string.sc_no_days_msg),
                    color = t.danger, fontSize = 12.sp,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
        }
    }

    if (showTime) {
        val state = rememberTimePickerState(initialHour = hour, initialMinute = minute, is24Hour = true)
        WolSheet(onDismiss = { showTime = false }, title = stringResource(R.string.sc_time)) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                TimePicker(state)
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    WolButton(
                        text = stringResource(R.string.dev_cancel),
                        onClick = { showTime = false },
                        modifier = Modifier.weight(1f),
                        filled = false,
                    )
                    WolButton(
                        text = stringResource(R.string.dev_save),
                        onClick = {
                            hour = state.hour
                            minute = state.minute
                            showTime = false
                        },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun SegChip(label: String, selected: Boolean, onClick: () -> Unit) {
    val t = LocalWolTokens.current
    Box(
        Modifier
            .alpha(if (selected) 1f else 0.6f)
            .background(
                if (selected) t.accent.copy(alpha = 0.18f) else t.surfaceHover.copy(alpha = 0.4f),
                RoundedCornerShape(999.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
    ) {
        Text(
            label,
            color = if (selected) t.accent else t.textDim,
            fontSize = 13.sp,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}

@Composable
private fun DayChip(label: String, selected: Boolean, onClick: () -> Unit) {
    val t = LocalWolTokens.current
    Box(
        Modifier
            .background(
                if (selected) t.accent else t.surfaceHover.copy(alpha = 0.5f),
                RoundedCornerShape(999.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 11.dp, vertical = 7.dp),
    ) {
        Text(
            label,
            color = if (selected) t.accentText else t.textDim,
            fontSize = 12.sp,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}
