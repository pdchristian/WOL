package de.wolmanager.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.wolmanager.R
import de.wolmanager.ui.theme.LocalWolTokens

/** Standard-Karte im Prototyp-Look (surface + border, keine Material-Schattenflut). */
@Composable
fun WolCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    contentPadding: androidx.compose.foundation.layout.PaddingValues = androidx.compose.foundation.layout.PaddingValues(14.dp),
    content: @Composable () -> Unit,
) {
    val t = LocalWolTokens.current
    Card(
        modifier = modifier
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = t.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, t.border),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Box(Modifier.padding(contentPadding)) { content() }
    }
}

/** Abschnittsüberschrift, klein, uppercase, gedimmt — wie ".section-title" im Prototyp. */
@Composable
fun SectionHeading(text: String, modifier: Modifier = Modifier) {
    val t = LocalWolTokens.current
    Text(
        text.uppercase(),
        modifier = modifier.padding(start = 2.dp, bottom = 2.dp),
        color = t.textDim,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 1.2.sp,
    )
}

/** Status-Punkt (online/offline/unbekannt/waking). */
@Composable
fun StatusDot(color: Color, size: androidx.compose.ui.unit.Dp = 10.dp, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .size(size)
            .background(color, CircleShape)
    )
}

/** Kleine abgerundete Kennzeichnung (Pill), z. B. "Online" oder "bekannt". */
@Composable
fun Pill(text: String, fg: Color, bg: Color, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .background(bg, RoundedCornerShape(999.dp))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(text, color = fg, fontSize = 11.sp, fontWeight = FontWeight.Medium, maxLines = 1)
    }
}

/** Bottom-Sheet-Wrapper mit Titel — Basis für alle Dialoge des Prototyps. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WolSheet(
    onDismiss: () -> Unit,
    title: String,
    content: @Composable () -> Unit,
) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val t = LocalWolTokens.current
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = state,
        containerColor = t.surface,
        contentColor = t.text,
        dragHandle = null,
    ) {
        Column(Modifier.padding(horizontal = 18.dp, vertical = 16.dp)) {
            Text(
                title,
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold,
                color = t.text,
                modifier = Modifier.padding(bottom = 12.dp),
            )
            content()
            Spacer(Modifier.height(18.dp))
        }
    }
}

/** Beschriftetes Textfeld. */
@Composable
fun WolField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = "",
    singleLine: Boolean = true,
    error: String? = null,
    enabled: Boolean = true,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
) {
    val t = LocalWolTokens.current
    Column(modifier = modifier.fillMaxWidth()) {
        Text(label, color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
        Spacer(Modifier.height(4.dp))
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = singleLine,
            enabled = enabled,
            placeholder = { if (placeholder.isNotEmpty()) Text(placeholder, color = t.textDim.copy(alpha = 0.6f)) },
            isError = error != null,
            keyboardOptions = keyboardOptions,
            textStyle = MaterialTheme.typography.bodyMedium,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = t.accent,
                unfocusedBorderColor = t.border,
                disabledBorderColor = t.border,
                focusedContainerColor = t.surfaceHover.copy(alpha = 0.35f),
                unfocusedContainerColor = t.surfaceHover.copy(alpha = 0.2f),
                cursorColor = t.accent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        if (error != null) {
            Text(error, color = t.danger, fontSize = 11.sp, modifier = Modifier.padding(top = 3.dp))
        }
    }
}

/** Beschriftetes Dropdown (exposed) mit festen Optionen. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WolDropdown(
    label: String,
    options: List<String>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val t = LocalWolTokens.current
    var expanded by remember { mutableStateOf(false) }
    Column(modifier = modifier.fillMaxWidth()) {
        if (label.isNotEmpty()) {
            Text(label, color = t.textDim, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
        }
        ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { if (enabled) expanded = it }) {
            Box(
                modifier = Modifier
                    .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                    .fillMaxWidth()
                    .background(
                        t.surfaceHover.copy(alpha = if (enabled) 0.35f else 0.15f),
                        RoundedCornerShape(8.dp),
                    )
                    .border(1.dp, t.border, RoundedCornerShape(8.dp))
                    .padding(horizontal = 12.dp, vertical = 12.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        options.getOrElse(selected) { "" },
                        color = if (enabled) t.text else t.textDim,
                        fontSize = 14.sp,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Icon(Icons.Filled.ArrowDropDown, null, tint = t.textDim)
                }
            }
            ExposedDropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
                containerColor = t.surface,
            ) {
                options.forEachIndexed { idx, opt ->
                    DropdownMenuItem(
                        text = { Text(opt, color = if (idx == selected) t.accent else t.text) },
                        onClick = {
                            onSelect(idx)
                            expanded = false
                        },
                    )
                }
            }
        }
    }
}

/** Schalter-Zeile mit Label. */
@Composable
fun WolToggle(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val t = LocalWolTokens.current
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = t.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedTrackColor = t.accent,
                checkedThumbColor = t.accentText,
            ),
        )
    }
}

/** Bestätigungsdialog (Titel/Nachricht, Abbrechen/OK). */
@Composable
fun WolConfirm(
    title: String,
    message: String,
    confirmLabel: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    destructive: Boolean = false,
) {
    val t = LocalWolTokens.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, fontWeight = FontWeight.Bold) },
        text = { Text(message) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(confirmLabel, color = if (destructive) t.danger else t.accent, fontWeight = FontWeight.SemiBold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel), color = t.textDim) }
        },
        containerColor = t.surface,
        titleContentColor = t.text,
        textContentColor = t.text,
    )
}

/** Info-Block (abgerundeter Hinweiskasten), z. B. Warnung/Beschreibung. */
@Composable
fun InfoBlock(
    text: String,
    modifier: Modifier = Modifier,
    fg: Color? = null,
    bg: Color? = null,
    icon: String = "",
) {
    val t = LocalWolTokens.current
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(bg ?: t.surfaceHover.copy(alpha = 0.5f), RoundedCornerShape(10.dp))
            .padding(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        if (icon.isNotEmpty()) {
            Text(icon, fontSize = 14.sp, color = fg ?: t.textDim)
            Spacer(Modifier.width(8.dp))
        }
        Text(text, color = fg ?: t.textDim, fontSize = 12.sp, lineHeight = 17.sp)
    }
}

/** Konsolenfeld (mono, consoleBg) für Batch-Ausgaben. */
@Composable
fun ConsoleBox(text: String, modifier: Modifier = Modifier) {
    val t = LocalWolTokens.current
    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(t.consoleBg, RoundedCornerShape(10.dp))
            .border(1.dp, t.border, RoundedCornerShape(10.dp))
            .padding(12.dp),
    ) {
        Text(
            text.ifEmpty { "—" },
            style = de.wolmanager.ui.theme.MonoStyle,
            color = t.text,
        )
    }
}

/** Zeile aus Icon-Buttons (⋯ Menüs etc.) — kleiner Touch-Button. */
@Composable
fun IconTextButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val t = LocalWolTokens.current
    Text(
        text,
        modifier = modifier
            .background(t.surfaceHover.copy(alpha = 0.6f), RoundedCornerShape(8.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 7.dp),
        color = if (enabled) t.text else t.textDim.copy(alpha = 0.5f),
        fontSize = 12.sp,
        fontWeight = FontWeight.Medium,
    )
}

/** Primärer Action-Knopf (gefüllt, accent). */
@Composable
fun WolButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    filled: Boolean = true,
) {
    val t = LocalWolTokens.current
    Box(
        modifier = modifier
            .background(
                if (!enabled) t.surfaceHover else if (filled) t.accent else Color.Transparent,
                RoundedCornerShape(10.dp),
            )
            .then(
                if (filled) Modifier else Modifier.border(1.dp, if (enabled) t.accent else t.border, RoundedCornerShape(10.dp))
            )
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 11.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = when {
                !enabled -> t.textDim
                filled -> t.accentText
                else -> t.accent
            },
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
        )
    }
}

/** Zeile mit Label links und Wert rechts (Detailzeilen). */
@Composable
fun LabeledValue(label: String, value: String, modifier: Modifier = Modifier, mono: Boolean = false) {
    val t = LocalWolTokens.current
    Row(modifier = modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = t.textDim, fontSize = 12.sp)
        Text(
            value,
            color = t.text,
            fontSize = if (mono) 12.sp else 13.sp,
            fontFamily = if (mono) androidx.compose.ui.text.font.FontFamily.Monospace else null,
        )
    }
}
