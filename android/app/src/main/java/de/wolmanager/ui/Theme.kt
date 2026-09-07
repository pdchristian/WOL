package de.wolmanager.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// DARK-Tokens aus wol_app/modern_theme.py
private val WolDarkScheme = darkColorScheme(
    primary = Color(0xFF00B8A9),
    onPrimary = Color(0xFF032019),
    secondary = Color(0xFF006B63),
    background = Color(0xFF0F1115),
    onBackground = Color(0xFFE6E8EE),
    surface = Color(0xFF1A1D24),
    onSurface = Color(0xFFE6E8EE),
    surfaceVariant = Color(0xFF232733),
    outline = Color(0xFF2C303A),
    error = Color(0xFFE0485A),
)

@Composable
fun WolTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = WolDarkScheme,
        typography = Typography(),
        content = content,
    )
}
