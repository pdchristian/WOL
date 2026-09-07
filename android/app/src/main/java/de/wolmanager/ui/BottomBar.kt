package de.wolmanager.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.wolmanager.R
import de.wolmanager.ui.theme.LocalWolTokens

private data class TabDef(val screen: Screen, val icon: String, val labelRes: Int)

private val TABS = listOf(
    TabDef(Screen.DEVICES, "💻", R.string.nav_devices),
    TabDef(Screen.MANAGE, "🔧", R.string.nav_manage),
    TabDef(Screen.SCHEDULE, "🕒", R.string.nav_schedule),
    TabDef(Screen.LOGS, "📋", R.string.nav_logs),
    TabDef(Screen.SETTINGS, "⚙️", R.string.nav_settings),
)

/**
 * Bottom-Navigation wie im Prototyp: 5 Tabs, Emoji-Icons, aktiver Tab in Akzentfarbe.
 */
@Composable
fun WolBottomBar(modifier: Modifier = Modifier) {
    val vm = LocalViewModel.current
    val current by vm.screen.collectAsStateWithLifecycle()
    val t = LocalWolTokens.current

    Column(modifier = modifier.fillMaxWidth()) {
        HorizontalDivider(color = t.border, thickness = 1.dp)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(62.dp)
                .padding(horizontal = 2.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            for (tab in TABS) {
                val active = current == tab.screen
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                    modifier = Modifier
                        .weight(1f)
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                        ) { vm.screen.value = tab.screen },
                ) {
                    Text(tab.icon, fontSize = 19.sp)
                    Text(
                        stringResource(tab.labelRes),
                        fontSize = 10.sp,
                        fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (active) t.accent else t.textDim,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}
