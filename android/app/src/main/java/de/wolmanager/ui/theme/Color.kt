package de.wolmanager.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Farb-Token der Windows-App (wol_app/modern_theme.py) — exakt übernommen,
 * damit Android- und Windows-Oberfläche identisch aussehen.
 */
data class WolTokens(
    val bg: Color,
    val surface: Color,
    val surfaceHover: Color,
    val border: Color,
    val text: Color,
    val textDim: Color,
    val accent: Color,
    val accentDark: Color,
    val accentText: Color,
    val online: Color,
    val offline: Color,
    val unknown: Color,
    val danger: Color,
    val blue: Color,
    val gaugeCpu: Color,
    val gaugeRam: Color,
    val gaugeGpu: Color,
    val gaugeVram: Color,
    val svc: Color,
    val consoleBg: Color,
)

val WolDarkTokens = WolTokens(
    bg = Color(0xFF0F1115),
    surface = Color(0xFF1A1D24),
    surfaceHover = Color(0xFF232733),
    border = Color(0xFF2C303A),
    text = Color(0xFFE6E8EE),
    textDim = Color(0xFF9AA0AB),
    accent = Color(0xFF00B8A9),
    accentDark = Color(0xFF006B63),
    accentText = Color(0xFF032019),
    online = Color(0xFF22C55E),
    offline = Color(0xFFEF4444),
    unknown = Color(0xFFF59E0B),
    danger = Color(0xFFE0485A),
    blue = Color(0xFF60A5FA),
    gaugeCpu = Color(0xFF00B8A9),
    gaugeRam = Color(0xFF60A5FA),
    gaugeGpu = Color(0xFFA78BFA),
    gaugeVram = Color(0xFFF59E0B),
    svc = Color(0xFFF97316),
    consoleBg = Color(0xFF12141A),
)

val WolLightTokens = WolTokens(
    bg = Color(0xFFF3F4F7),
    surface = Color(0xFFFFFFFF),
    surfaceHover = Color(0xFFEEF0F4),
    border = Color(0xFFD8DBE2),
    text = Color(0xFF1B1E24),
    textDim = Color(0xFF5B6270),
    accent = Color(0xFF009688),
    accentDark = Color(0xFF00695F),
    accentText = Color(0xFFFFFFFF),
    online = Color(0xFF16A34A),
    offline = Color(0xFFDC2626),
    unknown = Color(0xFFD97706),
    danger = Color(0xFFDC2637),
    blue = Color(0xFF2563EB),
    gaugeCpu = Color(0xFF009688),
    gaugeRam = Color(0xFF2563EB),
    gaugeGpu = Color(0xFF7C3AED),
    gaugeVram = Color(0xFFD97706),
    svc = Color(0xFFEA580C),
    consoleBg = Color(0xFFF7F8FA),
)
