package de.wolmanager.ui.dashboard

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.data.BatchDef
import de.wolmanager.data.BatchResult
import de.wolmanager.data.ConnState
import de.wolmanager.data.Device
import de.wolmanager.data.MetricsSnapshot
import de.wolmanager.net.HostServiceClient
import de.wolmanager.ui.LocalViewModel
import de.wolmanager.ui.common.ConsoleBox
import de.wolmanager.ui.common.InfoBlock
import de.wolmanager.ui.common.Pill
import de.wolmanager.ui.common.SectionHeading
import de.wolmanager.ui.common.WolButton
import de.wolmanager.ui.common.WolCard
import de.wolmanager.ui.common.WolDropdown
import de.wolmanager.ui.common.WolField
import de.wolmanager.ui.common.WolToggle
import de.wolmanager.ui.theme.LocalWolTokens
import de.wolmanager.ui.theme.MonoStyle
import de.wolmanager.ui.theme.WolTokens
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Locale
import java.util.UUID

/**
 * Geräte-Dashboard: Live-Metriken (CPU/RAM/GPU/VRAM) mit Ring-Gauges + Sparklines,
 * Dienste (watch-Prozesse) mit Inferenz-Erkennung und Batches + Konsole.
 */
@Composable
fun DashboardScreen(device: Device, toast: (String) -> Unit, onBack: () -> Unit) {
    val vm = LocalViewModel.current
    val container = vm.container
    val t = LocalWolTokens.current
    val scope = rememberCoroutineScope()

    var intervalIdx by remember { mutableStateOf(1) } // 2/3/5/10 s, Default 3 s
    val intervalMs = listOf(2000, 3000, 5000, 10000)[intervalIdx]

    var metrics by remember { mutableStateOf<MetricsSnapshot?>(null) }
    var unreachable by remember { mutableStateOf(false) }
    var sparkCpu by remember { mutableStateOf<List<Float>>(emptyList()) }
    var sparkRam by remember { mutableStateOf<List<Float>>(emptyList()) }
    var sparkGpu by remember { mutableStateOf<List<Float>>(emptyList()) }
    var gpuHigh by remember { mutableStateOf(0) }

    // ── Batches ────────────────────────────────────────────────────────────
    var selBatchId by remember { mutableStateOf<String?>(null) }
    var bName by remember { mutableStateOf("") }
    var bScript by remember { mutableStateOf("") }
    var bTimeout by remember { mutableStateOf("120") }
    var conLines by remember { mutableStateOf<List<String>>(emptyList()) }
    var conRunning by remember { mutableStateOf(false) }
    var conExit by remember { mutableStateOf<Int?>(null) }
    var conDur by remember { mutableStateOf<String?>(null) }

    val hasCreds = device.username.isNotBlank()
    val showMetrics = device.enabled && device.ip.isNotBlank() && hasCreds && !unreachable

    // Live-Polling der Metriken
    LaunchedEffect(device.id, intervalMs, showMetrics) {
        metrics = null
        unreachable = false
        sparkCpu = emptyList(); sparkRam = emptyList(); sparkGpu = emptyList()
        gpuHigh = 0
        if (!showMetrics) return@LaunchedEffect
        while (true) {
            val pass = container.repo.getPassword(device.id)
            val (res, snap) = container.hostClient.metrics(device.ip, device.username, pass, device.watchProcesses)
            if (res is HostServiceClient.HostResult.Ok && snap != null) {
                metrics = snap
                unreachable = false
                vm.setStatus(device.id, ConnState.ONLINE)
                snap.cpu?.let { v -> sparkCpu = (sparkCpu + v.toFloat()).takeLast(60) }
                if (snap.ramTotal != null && snap.ramTotal > 0 && snap.ramUsed != null) {
                    sparkRam = (sparkRam + ((snap.ramUsed / snap.ramTotal) * 100).toFloat()).takeLast(60)
                }
                snap.gpu?.let { v -> sparkGpu = (sparkGpu + v.toFloat()).takeLast(60) }
                gpuHigh = if ((snap.gpu ?: 0.0) >= 60.0) gpuHigh + 1 else 0
            } else {
                unreachable = true
                metrics = null
                vm.setStatus(device.id, ConnState.OFFLINE)
            }
            delay(intervalMs.toLong())
        }
    }

    // Batch-Editor an Auswahl binden
    val batches = device.batches
    LaunchedEffect(selBatchId, batches) {
        val sel = batches.firstOrNull { it.id == selBatchId }
        if (sel != null) {
            bName = sel.name; bScript = sel.script; bTimeout = sel.timeout.toString()
        }
    }

    fun persist(updated: Device) = container.repo.saveDevice(updated.copy(password = container.repo.getPassword(device.id)))

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
    ) {
        // Kopfzeile: Zurück + Intervall
        Row(verticalAlignment = Alignment.CenterVertically) {
            WolButton(text = stringResource(R.string.dash_back), onClick = onBack, filled = false)
            Spacer(Modifier.weight(1f))
            Text(stringResource(R.string.dash_interval), color = t.textDim, fontSize = 11.sp)
            Spacer(Modifier.width(6.dp))
            WolDropdown(
                label = "",
                options = listOf("2 s", "3 s", "5 s", "10 s"),
                selected = intervalIdx,
                onSelect = { intervalIdx = it },
                modifier = Modifier.width(96.dp),
            )
        }
        Spacer(Modifier.height(10.dp))

        // Name + Status-Pill
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                device.name,
                color = t.text, fontSize = 19.sp, fontWeight = FontWeight.Bold,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.width(10.dp))
            Pill(
                text = stringResource(
                    when {
                        unreachable -> R.string.status_offline
                        else -> R.string.status_online
                    }
                ),
                fg = if (unreachable) t.offline else t.online,
                bg = (if (unreachable) t.offline else t.online).copy(alpha = 0.14f),
            )
        }
        Text(
            listOf(device.ip, device.mac).filter { it.isNotBlank() }.joinToString(" · ") +
                " · " + if ((metrics?.protocol ?: 0) >= 3) {
                    stringResource(R.string.hostv, metrics!!.protocol)
                } else "—",
            style = MonoStyle, color = t.textDim, maxLines = 1,
        )
        Spacer(Modifier.height(8.dp))

        if (!device.enabled || device.ip.isBlank()) {
            WarnBox(stringResource(R.string.dash_unreach, device.ip.ifBlank { "?" }), error = true)
        } else if (!hasCreds) {
            WarnBox(stringResource(R.string.dash_creds), error = false)
        } else if (unreachable) {
            WarnBox(stringResource(R.string.dash_unreach, device.ip), error = true)
        }

        if (showMetrics) {
            // ── Dienste ────────────────────────────────────────────────────
            SectionHeadingRow(stringResource(R.string.dash_svc), stringResource(R.string.dash_svc_sub))
            Spacer(Modifier.height(6.dp))
            if (device.watchProcesses.isEmpty()) {
                Text(stringResource(R.string.dash_svc_none), color = t.textDim, fontSize = 12.sp)
            } else {
                val m = metrics
                val models = m?.processes?.values?.flatMap { it.models }?.distinct() ?: emptyList()
                val anyReady = m?.processes?.values?.any { it.running && it.apiPortOpen == true } ?: false
                WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
                    device.watchProcesses.forEachIndexed { i, w ->
                        if (i > 0) SepRow(t)
                        val info = m?.processes?.get(w)
                        val isLlama = w.lowercase().contains("llama")
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(if (isLlama) "🦙" else "⚙️", fontSize = 19.sp)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        w.substringBefore(":"),
                                        color = t.text, fontSize = 13.sp, fontWeight = FontWeight.Medium,
                                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    )
                                    if (isLlama && gpuHigh >= 2) {
                                        Spacer(Modifier.width(6.dp))
                                        Pill(
                                            text = stringResource(R.string.dash_inferenz),
                                            fg = t.svc,
                                            bg = t.svc.copy(alpha = 0.15f),
                                        )
                                    }
                                }
                                Text(svcLine(info), style = MonoStyle, color = t.textDim, fontSize = 11.sp, maxLines = 1)
                                if (isLlama && anyReady && models.isNotEmpty()) {
                                    Text(
                                        "🧠 " + models.first() +
                                            if (models.size > 1) " +${models.size - 1}" else "",
                                        style = MonoStyle, color = t.textDim, fontSize = 11.sp, maxLines = 1,
                                    )
                                }
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(10.dp))

            // Uptime
            metrics?.uptime?.let {
                Text(
                    stringResource(R.string.d_uptime, fmtUptime(it)),
                    style = MonoStyle, color = t.textDim, fontSize = 12.sp,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }

            // ── Metrik-Karten (2×2) ────────────────────────────────────────
            val m = metrics
            val cpuV = m?.cpu?.toFloat()
            val ramV = if (m != null && m.ramTotal != null && m.ramTotal > 0 && m.ramUsed != null)
                ((m.ramUsed / m.ramTotal) * 100).toFloat() else null
            val ramDetail = if (m != null && m.ramTotal != null && m.ramTotal > 0 && m.ramUsed != null)
                stringResource(R.string.d_gb, fmt1(m.ramUsed / 1073741824.0), fmt1(m.ramTotal / 1073741824.0))
            else stringResource(R.string.d_na)
            val gpuV = m?.gpu?.toFloat()
            val vramV = if (m != null && m.vramTotal != null && m.vramTotal > 0 && m.vramUsed != null)
                ((m.vramUsed / m.vramTotal) * 100).toFloat() else null

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Box(Modifier.weight(1f)) {
                        GaugeCard(stringResource(R.string.m_cpu), t.gaugeCpu, cpuV, m?.cpuCount?.let { stringResource(R.string.d_cores, it) } ?: stringResource(R.string.d_na), sparkCpu)
                    }
                    Box(Modifier.weight(1f)) {
                        GaugeCard(stringResource(R.string.m_ram), t.gaugeRam, ramV, ramDetail, sparkRam)
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Box(Modifier.weight(1f)) {
                        GaugeCard(stringResource(R.string.m_gpu), t.gaugeGpu, gpuV, stringResource(R.string.d_na), sparkGpu)
                    }
                    Box(Modifier.weight(1f)) {
                        GaugeCard(stringResource(R.string.m_vram), t.gaugeVram, vramV, stringResource(R.string.d_na), null)
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // ── Batches ────────────────────────────────────────────────────────
        SectionHeadingRow(stringResource(R.string.batch_title), null)
        Spacer(Modifier.height(6.dp))
        val newName = stringResource(R.string.batch_newname)
        WolButton(
            text = stringResource(R.string.batch_new),
            onClick = {
                val id = UUID.randomUUID().toString()
                val nb = BatchDef(id = id, name = newName, script = "", timeout = 120)
                persist(device.copy(batches = device.batches + nb))
                selBatchId = id
            },
            filled = false,
        )
        Spacer(Modifier.height(8.dp))
        if (batches.isEmpty()) {
            Text(stringResource(R.string.batch_empty), color = t.textDim, fontSize = 12.sp)
        } else {
            WolCard(contentPadding = PaddingValues(vertical = 2.dp)) {
                batches.forEachIndexed { i, b ->
                    if (i > 0) SepRow(t)
                    val sel = b.id == selBatchId
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .background(
                                if (sel) t.accent.copy(alpha = 0.13f) else Color.Transparent,
                            )
                            .clickable { selBatchId = b.id }
                            .padding(horizontal = 12.dp, vertical = 9.dp),
                    ) {
                        Text(
                            b.name,
                            color = if (sel) t.accent else t.text, fontSize = 13.sp,
                            fontWeight = if (sel) FontWeight.SemiBold else FontWeight.Normal,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            "${b.script} · ${b.timeout} s",
                            style = MonoStyle, color = t.textDim, fontSize = 11.sp, maxLines = 1,
                        )
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                WolButton(
                    text = stringResource(R.string.batch_dup),
                    onClick = {
                        val sel = batches.firstOrNull { it.id == selBatchId } ?: return@WolButton
                        val copy = sel.copy(id = UUID.randomUUID().toString(), name = sel.name + " ⧉")
                        persist(device.copy(batches = device.batches + copy))
                        selBatchId = copy.id
                    },
                    enabled = selBatchId != null,
                    filled = false,
                )
                WolButton(
                    text = stringResource(R.string.batch_del),
                    onClick = {
                        val id = selBatchId ?: return@WolButton
                        persist(device.copy(batches = device.batches.filter { it.id != id }))
                        selBatchId = null
                    },
                    enabled = selBatchId != null,
                    filled = false,
                )
            }
        }

        // Batch-Editor
        selBatchId?.let { id ->
            Spacer(Modifier.height(10.dp))
            WolCard {
                Column {
                    WolField(label = "", value = bName, onValueChange = { bName = it }, placeholder = stringResource(R.string.batch_newname))
                    Spacer(Modifier.height(8.dp))
                    WolField(
                        label = "",
                        value = bScript,
                        onValueChange = { bScript = it },
                        placeholder = "@echo off",
                        singleLine = false,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(R.string.batch_timeout), style = MonoStyle, color = t.textDim, fontSize = 11.sp)
                        Spacer(Modifier.width(8.dp))
                        WolField(
                            label = "",
                            value = bTimeout,
                            onValueChange = { bTimeout = it.filter { c -> c.isDigit() } },
                            modifier = Modifier.width(84.dp),
                        )
                        Spacer(Modifier.weight(1f))
                        val savedMsg = stringResource(R.string.batch_save)
                        val disabledMsg = stringResource(R.string.batch_disabled)
                        WolButton(
                            text = savedMsg,
                            onClick = {
                                val timeout = bTimeout.toIntOrNull()?.coerceIn(5, 3600) ?: 120
                                val updated = device.batches.map {
                                    if (it.id == id) it.copy(name = bName.trim(), script = bScript, timeout = timeout) else it
                                }
                                persist(device.copy(batches = updated))
                                toast(savedMsg)
                            },
                            filled = false,
                        )
                        Spacer(Modifier.width(8.dp))
                        WolButton(
                            text = if (conRunning) stringResource(R.string.batch_running) else stringResource(R.string.batch_run),
                            onClick = {
                                if (conRunning) return@WolButton
                                if (!device.allowBatch) {
                                    toast(disabledMsg)
                                    return@WolButton
                                }
                                conLines = listOf("\$ $bScript")
                                conRunning = true
                                conExit = null
                                conDur = null
                                scope.launch {
                                    val pass = container.repo.getPassword(device.id)
                                    val timeout = bTimeout.toIntOrNull()?.coerceIn(5, 3600) ?: 120
                                    val (res, br) = container.hostClient.runBatch(device.ip, bScript, device.username, pass, timeout)
                                    conRunning = false
                                    when {
                                        br != null -> {
                                            val out = buildString {
                                                if (br.stdout.isNotBlank()) append(br.stdout.trimEnd())
                                                if (br.stderr.isNotBlank()) {
                                                    if (isNotEmpty()) append('\n')
                                                    append(br.stderr.trimEnd())
                                                }
                                            }
                                            if (out.isNotBlank()) conLines = conLines + out.lines()
                                            conExit = br.exitCode
                                            conDur = fmt1(br.durationMs / 1000.0)
                                            container.repo.log(
                                                device.name,
                                                if (br.exitCode == 0) "info" else "error",
                                                "$bName → Exit-Code ${br.exitCode}",
                                            )
                                        }
                                        res is HostServiceClient.HostResult.Error -> {
                                            conLines = conLines + res.message
                                            conExit = -1
                                            conDur = "0"
                                            container.repo.log(device.name, "error", "$bName → ${res.message}")
                                        }
                                    }
                                }
                            },
                            enabled = !conRunning && device.ip.isNotBlank(),
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                    WolToggle(
                        label = stringResource(R.string.batch_allow),
                        checked = device.allowBatch,
                        onCheckedChange = { on -> persist(device.copy(allowBatch = on)) },
                    )
                    if (!device.allowBatch) {
                        Text(
                            stringResource(R.string.batch_disabled),
                            color = t.unknown, fontSize = 11.sp, lineHeight = 15.sp,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
            }

            // ── Konsole ────────────────────────────────────────────────────
            Spacer(Modifier.height(12.dp))
            SectionHeadingRow(stringResource(R.string.batch_out), null)
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(bottom = 6.dp)) {
                WolButton(
                    text = stringResource(R.string.batch_clear),
                    onClick = { conLines = emptyList(); conExit = null; conDur = null },
                    filled = false,
                )
            }
            ConsoleLines(conLines, conRunning, conExit, conDur)
        }
        Spacer(Modifier.height(24.dp))
    }
}

// ── Hilfs-Composables ──────────────────────────────────────────────────────

@Composable
private fun SectionHeadingRow(title: String, sub: String?) {
    val t = LocalWolTokens.current
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Bottom,
    ) {
        SectionHeading(title)
        if (sub != null) Text(sub, color = t.textDim, fontSize = 11.sp)
    }
}

@Composable
private fun SepRow(t: WolTokens) {
    Box(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp)
            .height(1.dp)
            .background(t.border)
    )
}

@Composable
private fun WarnBox(text: String, error: Boolean) {
    val t = LocalWolTokens.current
    InfoBlock(
        text = text,
        fg = if (error) t.danger else t.unknown,
        bg = (if (error) t.danger else t.unknown).copy(alpha = 0.10f),
        modifier = Modifier.padding(bottom = 8.dp),
    )
}

/** Ring-Gauge (270°-Bogen mit Sweep-Gradient) + Wert + Detail + optionale Sparkline. */
@Composable
private fun GaugeCard(
    title: String,
    color: Color,
    value: Float?,
    detail: String,
    spark: List<Float>?,
) {
    val t = LocalWolTokens.current
    WolCard(contentPadding = PaddingValues(horizontal = 10.dp, vertical = 12.dp)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier
                        .size(7.dp)
                        .background(color, RoundedCornerShape(2.dp)),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    title,
                    color = t.textDim, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.8.sp,
                )
            }
            Spacer(Modifier.height(4.dp))
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(84.dp)) {
                GaugeRing(valuePct = value, color = color)
                Text(
                    value?.let { "${it.toInt()}%" } ?: "–%",
                    color = t.text, fontSize = 17.sp, fontWeight = FontWeight.Bold,
                )
            }
            Text(detail, color = t.textDim, fontSize = 11.sp, maxLines = 1)
            if (spark != null) {
                Spacer(Modifier.height(4.dp))
                Sparkline(spark, color, Modifier.fillMaxWidth().height(30.dp))
            }
        }
    }
}

@Composable
private fun GaugeRing(valuePct: Float?, color: Color) {
    val t = LocalWolTokens.current
    Canvas(Modifier.fillMaxSize()) {
        val stroke = 8.dp.toPx()
        val arcSize = androidx.compose.ui.geometry.Size(size.width - stroke, size.height - stroke)
        val top = Offset(stroke / 2, stroke / 2)
        // Hintergrundbogen (voll, 270°)
        drawArc(
            color = t.border,
            startAngle = 135f,
            sweepAngle = 270f,
            useCenter = false,
            topLeft = top,
            size = arcSize,
            style = Stroke(width = stroke, cap = StrokeCap.Round),
        )
        val v = (valuePct ?: 0f).coerceIn(0f, 100f)
        if (v > 0f) {
            val brush = Brush.sweepGradient(
                0f to color.copy(alpha = 0.55f),
                1f to color,
            )
            drawArc(
                brush = brush,
                startAngle = 135f,
                sweepAngle = 270f * v / 100f,
                useCenter = false,
                topLeft = top,
                size = arcSize,
                style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
        }
    }
}

@Composable
private fun Sparkline(values: List<Float>, color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        if (values.size < 2) return@Canvas
        val path = Path()
        val n = values.size
        for (i in 0 until n) {
            val x = size.width * i / (n - 1)
            val y = size.height - (values[i].coerceIn(0f, 100f) / 100f) * (size.height - 2f) - 1f
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color, style = Stroke(width = 2.dp.toPx()))
    }
}

@Composable
private fun ConsoleLines(lines: List<String>, running: Boolean, exit: Int?, dur: String?) {
    val t = LocalWolTokens.current
    Box(
        Modifier
            .fillMaxWidth()
            .background(t.consoleBg, RoundedCornerShape(10.dp))
            .border(1.dp, t.border, RoundedCornerShape(10.dp))
            .padding(12.dp),
    ) {
        Column {
            if (lines.isEmpty() && !running && exit == null) {
                Text("—", style = MonoStyle, color = t.textDim)
            }
            lines.forEach { line ->
                val isErr = line.contains("fehler", ignoreCase = true) || line.contains("error", ignoreCase = true)
                Text(line, style = MonoStyle, color = if (isErr) t.danger else t.text)
            }
            if (running) Text(stringResource(R.string.batch_running), style = MonoStyle, color = t.textDim)
            if (exit != null) {
                Text(
                    stringResource(R.string.batch_exit, exit) +
                        (dur?.let { " · " + stringResource(R.string.batch_dur, it) } ?: ""),
                    style = MonoStyle, color = t.textDim,
                )
            }
        }
    }
}

// ── Formatierung ───────────────────────────────────────────────────────────

private fun fmt1(v: Double): String = String.format(Locale.US, "%.1f", v)

/** Uptime "s" → "7d 03:24" (wie Prototyp). */
internal fun fmtUptime(seconds: Double): String {
    val s = seconds.toLong()
    val d = s / 86400
    val h = (s % 86400) / 3600
    val m = (s % 3600) / 60
    return (if (d > 0) "${d}d " else "") + String.format(Locale.US, "%02d:%02d", h, m)
}

/** Statuszeile eines überwachten Prozesses — analog zu svcLine() im Prototyp. */
@Composable
private fun svcLine(info: de.wolmanager.data.WatchInfo?): String {
    if (info == null) return "…"
    return when {
        !info.running -> stringResource(R.string.svc_gone)
        info.apiPort != null && info.apiPortOpen == true ->
            stringResource(R.string.svc_ready, info.pid ?: 0, info.apiPort)
        info.apiPort != null && info.apiPortOpen == false ->
            stringResource(R.string.svc_unreach, info.pid ?: 0, info.apiPort)
        else -> stringResource(R.string.svc_running, info.pid ?: 0)
    }
}
