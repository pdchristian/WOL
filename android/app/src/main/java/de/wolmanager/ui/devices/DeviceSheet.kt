package de.wolmanager.ui.devices

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.data.Device
import de.wolmanager.data.ShutdownMethod
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolConfirm
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.common.WolField
import de.wolmanager.ui.common.WolSheet
import de.wolmanager.ui.common.WolToggle
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.util.Validation

/**
 * Bottom-Sheet zum Anlegen/Bearbeiten eines Geräts — Felder und Validierung
 * identisch zum Windows-Geräte-Dialog.
 */
@Composable
fun DeviceSheet(
    original: Device?,
    onDismiss: () -> Unit,
    onSaved: (Device, String) -> Unit,
) {
    val container = de.wolmanager.ui.LocalViewModel.current.container
    val t = LocalWolTokens.current
    val isEdit = original != null && original.id.isNotEmpty()

    var name by remember { mutableStateOf(original?.name ?: "") }
    var mac by remember { mutableStateOf(original?.mac ?: "") }
    var ip by remember { mutableStateOf(original?.ip ?: "") }
    var user by remember { mutableStateOf(original?.username ?: "") }
    var pass by remember {
        mutableStateOf(if (isEdit) container.repo.getPassword(original!!.id) else "")
    }
    var methodIdx by remember {
        mutableStateOf(if (original?.method == ShutdownMethod.SMB) 1 else 0)
    }
    var watch by remember { mutableStateOf((original?.watchProcesses ?: emptyList()).joinToString(", ")) }
    var enabled by remember { mutableStateOf(original?.enabled ?: true) }

    var errName by remember { mutableStateOf<String?>(null) }
    var errMac by remember { mutableStateOf<String?>(null) }
    var errIp by remember { mutableStateOf<String?>(null) }
    var dupMac by remember { mutableStateOf<String?>(null) }
    var unknownMac by remember { mutableStateOf<String?>(null) }

    val methodOptions = listOf(
        stringResource(R.string.dev_method_host),
        stringResource(R.string.dev_method_smb),
    )

    fun buildDevice(macValue: String): Device = Device(
        name = name.trim(),
        mac = macValue,
        ip = ip.trim(),
        username = user.trim(),
        password = "",
        enabled = enabled,
        batches = original?.batches ?: emptyList(),
        allowBatch = original?.allowBatch ?: false,
        id = original?.id ?: "",
        shutdownMethod = if (methodIdx == 1) "smb" else "host_service",
        watchProcesses = watch.split(",", "\n").map { it.trim() }.filter { it.isNotEmpty() },
    )

    val errNameMsg = stringResource(R.string.err_name)
    val errMacMsg = stringResource(R.string.err_mac)
    val errIpMsg = stringResource(R.string.err_ip)

    fun trySave() {
        errName = null; errMac = null; errIp = null
        var ok = true
        if (name.isBlank()) { errName = errNameMsg; ok = false }
        val normMac = Validation.normalizeMac(mac)
        if (normMac.isNotEmpty() && !Validation.isValidMac(normMac)) {
            errMac = errMacMsg; ok = false
        }
        if (!Validation.isValidIpOrHostname(ip)) { errIp = errIpMsg; ok = false }
        if (!ok) return

        // Duplikat-Prüfung über die MAC (wie Windows-Geräte-Dialog)
        if (normMac.isNotEmpty()) {
            val others = container.repo.snapshot.value.devices.filter { it.id != original?.id }
            if (Validation.macExists(normMac, others.map { it.mac })) {
                dupMac = normMac
                return
            }
            onSaved(buildDevice(normMac), pass)
        } else {
            // Fehlende MAC → Rückfrage mit Platzhalter
            unknownMac = name
        }
    }

    WolSheet(onDismiss = onDismiss, title = stringResource(if (isEdit) R.string.dev_edit else R.string.dev_add)) {
        Column(Modifier.verticalScroll(rememberScrollState())) {
            WolField(
                label = stringResource(R.string.dev_name),
                value = name, onValueChange = { name = it },
                placeholder = stringResource(R.string.ph_name),
                error = errName,
            )
            Spacer(Modifier.height(10.dp))
            WolField(
                label = stringResource(R.string.dev_mac),
                value = mac, onValueChange = { mac = it },
                placeholder = stringResource(R.string.ph_mac),
                error = errMac,
            )
            Spacer(Modifier.height(10.dp))
            WolField(
                label = stringResource(R.string.dev_ip),
                value = ip, onValueChange = { ip = it },
                placeholder = stringResource(R.string.ph_ip),
                error = errIp,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth()) {
                WolField(
                    label = stringResource(R.string.dev_user),
                    value = user, onValueChange = { user = it },
                    placeholder = stringResource(R.string.ph_user),
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.height(0.dp))
                WolField(
                    label = stringResource(R.string.dev_pass),
                    value = pass, onValueChange = { pass = it },
                    placeholder = stringResource(R.string.ph_pass),
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.height(10.dp))
            WolDropdown(
                label = stringResource(R.string.dev_method),
                options = methodOptions,
                selected = methodIdx,
                onSelect = { methodIdx = it },
            )
            if (methodIdx == 1) {
                Text(
                    stringResource(R.string.dev_method_smb_note),
                    color = t.unknown, fontSize = 11.sp,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            Spacer(Modifier.height(10.dp))
            WolField(
                label = stringResource(R.string.dev_watch),
                value = watch, onValueChange = { watch = it },
                placeholder = stringResource(R.string.ph_watch),
            )
            Spacer(Modifier.height(6.dp))
            WolToggle(
                label = stringResource(R.string.dev_enabled),
                checked = enabled,
                onCheckedChange = { enabled = it },
            )
            Spacer(Modifier.height(16.dp))
            Row(Modifier.fillMaxWidth()) {
                WolButton(
                    text = stringResource(R.string.dev_cancel),
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                    filled = false,
                )
                Spacer(Modifier.height(0.dp))
                WolButton(
                    text = stringResource(if (isEdit) R.string.dev_update else R.string.dev_save),
                    onClick = { trySave() },
                    modifier = Modifier.weight(1f),
                )
            }
        }
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
    unknownMac?.let { devName ->
        WolConfirm(
            title = stringResource(R.string.mac_unknown_title),
            message = stringResource(R.string.mac_unknown_msg, devName, ip.ifBlank { "—" }),
            confirmLabel = stringResource(R.string.dev_save),
            onConfirm = {
                unknownMac = null
                onSaved(buildDevice(""), pass)
            },
            onDismiss = { unknownMac = null },
        )
    }
}
