package de.wolmanager.ui.logs

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.data.LogEntry
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.Pill
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.devices.SearchBox
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.ui.theme.MonoStyle
import de.wolmanager.util.Csv
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Protokolle: Level-Filter, Suche, CSV-Export, Leeren.
 * Badges: info=dim, warn=unknown, error=danger — wie im Prototyp.
 */
@Composable
fun LogsScreen(logs: List<LogEntry>, toast: (String) -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current
    val context = LocalContext.current

    var levelIdx by remember { mutableStateOf(0) }
    var search by remember { mutableStateOf("") }
    var confirmClear by remember { mutableStateOf(false) }

    val levels = listOf(
        stringResource(R.string.logs_level_all),
        stringResource(R.string.logs_level_info),
        stringResource(R.string.logs_level_warn),
        stringResource(R.string.logs_level_error),
    )
    val levelKey = when (levelIdx) {
        1 -> "info"
        2 -> "warn"
        3 -> "error"
        else -> null
    }
    val filtered = remember(logs, levelKey, search) {
        val q = search.trim().lowercase()
        logs.filter { e ->
            (levelKey == null || e.level == levelKey) &&
                (q.isEmpty() || e.msg.lowercase().contains(q) || e.device.lowercase().contains(q))
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/csv"),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        try {
            val csv = Csv.logsToCsv(logs)
            context.contentResolver.openOutputStream(uri)?.use { out ->
                out.write(csv.toByteArray(Charsets.UTF_8))
            }
            toast(context.getString(R.string.logs_exported, "CSV"))
        } catch (_: Exception) {
            toast(context.getString(R.string.logs_export_failed))
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            WolDropdown(
                label = "",
                options = levels,
                selected = levelIdx,
                onSelect = { levelIdx = it },
                modifier = Modifier.weight(0.45f),
            )
            Spacer(Modifier.height(0.dp))
            Box(Modifier.weight(1f)) {
                SearchBox(value = search, onValueChange = { search = it }, placeholder = stringResource(R.string.logs_search))
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
            WolButton(
                text = stringResource(R.string.logs_export),
                onClick = { exportLauncher.launch("wol-protokolle.csv") },
                enabled = logs.isNotEmpty(),
                filled = false,
            )
            WolButton(
                text = stringResource(R.string.logs_clear),
                onClick = { confirmClear = true },
                enabled = logs.isNotEmpty(),
                filled = false,
            )
        }
        Spacer(Modifier.height(10.dp))

        if (filtered.isEmpty()) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(t.surface.copy(alpha = 0.5f), RoundedCornerShape(14.dp))
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(stringResource(R.string.logs_empty), color = t.textDim, fontSize = 13.sp)
            }
        } else {
            WolCard(contentPadding = PaddingValues(vertical = 4.dp)) {
                filtered.forEachIndexed { i, e ->
                    if (i > 0) Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp)
                            .height(1.dp)
                            .background(t.border)
                    )
                    val (fg, bg) = when {
                        e.isError -> t.danger to t.danger.copy(alpha = 0.13f)
                        e.isWarn -> t.unknown to t.unknown.copy(alpha = 0.13f)
                        else -> t.textDim to t.textDim.copy(alpha = 0.10f)
                    }
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 9.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Pill(
                            text = e.level.uppercase(Locale.US),
                            fg = fg,
                            bg = bg,
                        )
                        Spacer(Modifier.height(0.dp))
                        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
                            Text(e.msg, color = t.text, fontSize = 13.sp)
                            Text(
                                (e.device.ifBlank { stringResource(R.string.logs_unknown) }) +
                                    " · " + TIME_FMT.format(Date(e.ts)),
                                style = MonoStyle, color = t.textDim, fontSize = 11.sp, maxLines = 1,
                            )
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    if (confirmClear) {
        WolConfirm(
            title = stringResource(R.string.logs_clear_title),
            message = stringResource(R.string.logs_clear_message),
            confirmLabel = stringResource(R.string.logs_clear),
            destructive = true,
            onConfirm = {
                confirmClear = false
                container.repo.clearLogs()
            },
            onDismiss = { confirmClear = false },
        )
    }
}

private val TIME_FMT = SimpleDateFormat("dd.MM.yyyy HH:mm:ss", Locale.getDefault())
