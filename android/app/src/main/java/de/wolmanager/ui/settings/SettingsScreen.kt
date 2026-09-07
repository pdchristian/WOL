package de.wolmanager.ui.settings

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.BuildConfig
import de.wolmanager.LocalRecreate
import de.wolmanager.R
import de.wolmanager.data.AppSettings
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.InfoBlock
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.common.WolField
import de.wolmanager.ui.common.WolToggle
import de.wolmanager.ui.theme.LocalWolTokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonPrimitive
import java.net.HttpURLConnection
import java.net.URL

/**
 * Einstellungen + Info/About-Block unten.
 * Sprachwechsel → recreate(); Anzeigemodus wirkt reaktiv über WolTheme.
 */
@Composable
fun SettingsScreen(settings: AppSettings, toast: (String) -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val recreateActivity = LocalRecreate.current

    var broadcastIp by remember { mutableStateOf(settings.broadcastIp) }
    var broadcastPort by remember { mutableStateOf(settings.broadcastPort.toString()) }
    var langIdx by remember { mutableStateOf(langIndexOf(settings.language)) }
    var dispIdx by remember { mutableStateOf(dispIndexOf(settings.displayMode)) }
    var autoUpdate by remember { mutableStateOf(settings.autoUpdate) }
    var intervalIdx by remember { mutableStateOf(intervalIndexOf(settings.interval)) }
    var maxLogs by remember { mutableStateOf(settings.maxLogs.toString()) }
    var methodIdx by remember { mutableStateOf(if (settings.defaultShutdownMethod == "smb") 1 else 0) }

    var errIp by remember { mutableStateOf<String?>(null) }
    var errPort by remember { mutableStateOf<String?>(null) }
    var errMaxLogs by remember { mutableStateOf<String?>(null) }
    var savedDialog by remember { mutableStateOf(false) }
    var resetDialog by remember { mutableStateOf(false) }
    var updState by remember { mutableStateOf<UpdResult?>(null) } // null=idle
    var updBusy by remember { mutableStateOf(false) }

    val langOptions = listOf(
        stringResource(R.string.set_language_system), "Deutsch", "English", "Français", "Español",
    )
    val dispOptions = listOf(
        stringResource(R.string.disp_auto), stringResource(R.string.disp_light), stringResource(R.string.disp_dark),
    )
    val intervalOptions = listOf(
        stringResource(R.string.int_day), stringResource(R.string.int_week), stringResource(R.string.int_month),
    )
    val methodOptions = listOf(
        stringResource(R.string.dev_method_host), stringResource(R.string.dev_method_smb),
    )

    val errIpMsg = stringResource(R.string.err_ip_msg)
    val errPortMsg = stringResource(R.string.err_port_msg)
    val errMaxLogsMsg = stringResource(R.string.err_maxlogs_msg)
    val updNewMsg = stringResource(R.string.upd_new)

    fun validate(): AppSettings? {
        errIp = null; errPort = null; errMaxLogs = null
        if (!de.wolmanager.util.Validation.isValidIpv4(broadcastIp)) {
            errIp = errIpMsg; return null
        }
        val port = broadcastPort.toIntOrNull()
        if (port == null || !de.wolmanager.util.Validation.isValidPort(port)) {
            errPort = errPortMsg; return null
        }
        val maxLogsV = maxLogs.toIntOrNull()
        if (maxLogsV == null || maxLogsV !in 10..10000) {
            errMaxLogs = errMaxLogsMsg; return null
        }
        return AppSettings(
            broadcastIp = broadcastIp.trim(),
            broadcastPort = port,
            language = listOf("", "de", "en", "fr", "es")[langIdx],
            displayMode = listOf("auto", "light", "dark")[dispIdx],
            autoUpdate = autoUpdate,
            interval = listOf("24", "168", "720")[intervalIdx],
            maxLogs = maxLogsV,
            defaultShutdownMethod = if (methodIdx == 1) "smb" else "host_service",
        )
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        WolCard {
            Column {
                WolField(
                    label = stringResource(R.string.set_broadcast_ip),
                    value = broadcastIp, onValueChange = { broadcastIp = it },
                    error = errIp,
                )
                Spacer(Modifier.height(10.dp))
                WolField(
                    label = stringResource(R.string.set_broadcast_port),
                    value = broadcastPort, onValueChange = { broadcastPort = it },
                    error = errPort,
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                        keyboardType = androidx.compose.ui.text.input.KeyboardType.Number,
                    ),
                )
                Spacer(Modifier.height(10.dp))
                WolDropdown(
                    label = stringResource(R.string.set_language),
                    options = langOptions, selected = langIdx, onSelect = { langIdx = it },
                )
                Spacer(Modifier.height(10.dp))
                WolDropdown(
                    label = stringResource(R.string.set_display),
                    options = dispOptions, selected = dispIdx, onSelect = { dispIdx = it },
                )
                Spacer(Modifier.height(6.dp))
                WolToggle(
                    label = stringResource(R.string.set_auto_update),
                    checked = autoUpdate, onCheckedChange = { autoUpdate = it },
                )
                WolDropdown(
                    label = stringResource(R.string.set_interval),
                    options = intervalOptions, selected = intervalIdx, onSelect = { intervalIdx = it },
                )
                Spacer(Modifier.height(10.dp))
                WolField(
                    label = stringResource(R.string.set_max_logs),
                    value = maxLogs, onValueChange = { maxLogs = it },
                    error = errMaxLogs,
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                        keyboardType = androidx.compose.ui.text.input.KeyboardType.Number,
                    ),
                )
                Spacer(Modifier.height(10.dp))
                WolDropdown(
                    label = stringResource(R.string.set_method),
                    options = methodOptions, selected = methodIdx, onSelect = { methodIdx = it },
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp)) {
                    WolButton(
                        text = stringResource(R.string.set_reset),
                        onClick = { resetDialog = true },
                        modifier = Modifier.weight(1f),
                        filled = false,
                    )
                    WolButton(
                        text = stringResource(R.string.set_save),
                        onClick = {
                            val s = validate() ?: return@WolButton
                            val langChanged = s.language != settings.language
                            container.repo.saveSettings(s)
                            if (langChanged) {
                                recreateActivity()
                            } else {
                                savedDialog = true
                            }
                        },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        Spacer(Modifier.height(14.dp))
        InfoBlock(text = stringResource(R.string.set_info), icon = "ℹ️")
        Spacer(Modifier.height(14.dp))

        // ── Info / About ───────────────────────────────────────────────────
        WolCard {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier
                            .size(44.dp)
                            .background(t.accent.copy(alpha = 0.15f), RoundedCornerShape(11.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("⚡", fontSize = 22.sp)
                    }
                    Spacer(Modifier.height(0.dp))
                    Column(Modifier.padding(start = 12.dp)) {
                        Text(stringResource(R.string.about_name), color = t.text, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                        Text(
                            stringResource(R.string.about_version, BuildConfig.VERSION_NAME),
                            color = t.textDim, fontSize = 12.sp,
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    stringResource(R.string.about_desc),
                    color = t.textDim, fontSize = 12.sp, lineHeight = 17.sp,
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp)) {
                    WolButton(
                        text = if (updBusy) stringResource(R.string.upd_checking) else stringResource(R.string.upd_check),
                        onClick = {
                            updBusy = true
                            updState = null
                            scope.launch {
                                val result = checkForUpdate(BuildConfig.VERSION_NAME)
                                updBusy = false
                                updState = result
                                if (result is UpdResult.New) {
                                    toast(String.format(updNewMsg, result.version))
                                }
                            }
                        },
                        modifier = Modifier.weight(1f),
                        enabled = !updBusy,
                    )
                    WolButton(
                        text = stringResource(R.string.upd_changelog),
                        onClick = {
                            try {
                                context.startActivity(
                                    Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/pdchristian/WOL/releases")),
                                )
                            } catch (_: Exception) {
                            }
                        },
                        modifier = Modifier.weight(1f),
                        filled = false,
                    )
                }
                updState?.let { res ->
                    Spacer(Modifier.height(10.dp))
                    Text(
                        when (res) {
                            is UpdResult.New -> stringResource(R.string.upd_new, res.version)
                            UpdResult.Latest -> stringResource(R.string.upd_ok)
                            UpdResult.Failed -> stringResource(R.string.upd_err, stringResource(R.string.upd_err_msg))
                        },
                        color = t.textDim,
                        fontSize = 12.sp,
                    )
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    if (savedDialog) {
        WolConfirm(
            title = stringResource(R.string.set_saved_title),
            message = stringResource(R.string.set_saved_msg),
            confirmLabel = stringResource(R.string.dev_save),
            onConfirm = { savedDialog = false },
            onDismiss = { savedDialog = false },
        )
    }
    if (resetDialog) {
        WolConfirm(
            title = stringResource(R.string.set_reset_title),
            message = stringResource(R.string.set_reset_msg),
            confirmLabel = stringResource(R.string.set_reset),
            destructive = true,
            onConfirm = {
                resetDialog = false
                container.repo.resetSettings()
                broadcastIp = AppSettings().broadcastIp
                broadcastPort = AppSettings().broadcastPort.toString()
                langIdx = 0; dispIdx = 0; autoUpdate = true; intervalIdx = 1
                maxLogs = AppSettings().maxLogs.toString(); methodIdx = 0
                recreateActivity()
            },
            onDismiss = { resetDialog = false },
        )
    }
}

private fun langIndexOf(lang: String): Int = listOf("", "de", "en", "fr", "es").indexOf(lang).coerceAtLeast(0)
private fun dispIndexOf(mode: String): Int = listOf("auto", "light", "dark").indexOf(mode).coerceAtLeast(0)
private fun intervalIndexOf(v: String): Int = listOf("24", "168", "720").indexOf(v).coerceAtLeast(0)

/** Ergebnis des GitHub-Release-Checks. */
sealed interface UpdResult {
    data object Latest : UpdResult
    data class New(val version: String) : UpdResult
    data object Failed : UpdResult
}

/** GitHub-Release-Check. */
private suspend fun checkForUpdate(current: String): UpdResult = withContext(Dispatchers.IO) {
    try {
        val conn = URL("https://api.github.com/repos/pdchristian/WOL/releases/latest")
            .openConnection() as HttpURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.setRequestProperty("Accept", "application/vnd.github+json")
        val body = conn.inputStream.bufferedReader().use { it.readText() }
        val tag = (Json.parseToJsonElement(body) as? kotlinx.serialization.json.JsonObject)
            ?.get("tag_name")?.jsonPrimitive?.content ?: ""
        val latest = tag.removePrefix("v").removePrefix("V")
        when {
            latest.isBlank() -> UpdResult.Failed
            isNewer(latest, current) -> UpdResult.New(latest)
            else -> UpdResult.Latest
        }
    } catch (_: Exception) {
        UpdResult.Failed
    }
}

/** Versionsvergleich "2.3.1" > "2.3.0". */
internal fun isNewer(latest: String, current: String): Boolean {
    val a = latest.split(".").map { it.toIntOrNull() ?: 0 }
    val b = current.split(".").map { it.toIntOrNull() ?: 0 }
    for (i in 0 until maxOf(a.size, b.size)) {
        val x = a.getOrElse(i) { 0 }
        val y = b.getOrElse(i) { 0 }
        if (x != y) return x > y
    }
    return false
}
