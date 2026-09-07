package de.wolmanager.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Zugriff auf die aktiven Wol-Tokens (dunkel/hell) innerhalb des Kompositionsbaums. */
val LocalWolTokens = staticCompositionLocalOf { WolDarkTokens }

private val WolTypography = Typography()

private fun darkScheme(t: WolTokens) = darkColorScheme(
    primary = t.accent,
    onPrimary = t.accentText,
    secondary = t.blue,
    onSecondary = t.bg,
    background = t.bg,
    onBackground = t.text,
    surface = t.surface,
    onSurface = t.text,
    surfaceVariant = t.surfaceHover,
    onSurfaceVariant = t.textDim,
    error = t.danger,
    onError = Color.White,
    outline = t.border,
    outlineVariant = t.border,
)

private fun lightScheme(t: WolTokens) = lightColorScheme(
    primary = t.accent,
    onPrimary = t.accentText,
    secondary = t.blue,
    onSecondary = Color.White,
    background = t.bg,
    onBackground = t.text,
    surface = t.surface,
    onSurface = t.text,
    surfaceVariant = t.surfaceHover,
    onSurfaceVariant = t.textDim,
    error = t.danger,
    onError = Color.White,
    outline = t.border,
    outlineVariant = t.border,
)

/**
 * [displayMode]: "auto" | "light" | "dark" — wie der Anzeigemodus der Windows-App.
 */
@Composable
fun WolTheme(
    displayMode: String = "auto",
    content: @Composable () -> Unit,
) {
    val dark = when (displayMode) {
        "light" -> false
        "dark" -> true
        else -> isSystemInDarkTheme()
    }
    val tokens = if (dark) WolDarkTokens else WolLightTokens
    MaterialTheme(
        colorScheme = if (dark) darkScheme(tokens) else lightScheme(tokens),
        typography = WolTypography,
        shapes = MaterialTheme.shapes,
    ) {
        CompositionLocalProvider(LocalWolTokens provides tokens, content = content)
    }
}

/** Monospace-Stil für Konsole/MAC-Adressen analog zum Windows-QSS. */
val MonoStyle = TextStyle(
    fontFamily = FontFamily.Monospace,
    fontSize = 12.sp,
    fontWeight = FontWeight.Normal,
)
