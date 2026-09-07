package de.wolmanager

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.wolmanager.ui.AppRoot
import de.wolmanager.ui.AppViewModel
import de.wolmanager.ui.theme.WolTheme
import de.wolmanager.util.LocaleUtil
import de.wolmanager.util.QuickSettings
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

/**
 * Single-Activity-Host. Sprache wird über createConfigurationContext angewandt
 * (Wechsel → recreate()), Anzeigemodus (hell/dunkel/auto) reaktiv über WolTheme.
 */
class MainActivity : ComponentActivity() {

    override fun attachBaseContext(newBase: Context) {
        val settings = QuickSettings.read(newBase)
        super.attachBaseContext(LocaleUtil.wrap(newBase, settings.language))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as WolApplication
        val container = app.container
        val viewModel = AppViewModel(container)
        val initialLanguage = QuickSettings.read(this).language

        setContent {
            val snapshot by container.repo.snapshot.collectAsStateWithLifecycle()
            WolTheme(displayMode = snapshot.settings.displayMode) {
                val snackbar = remember { SnackbarHostState() }
                CompositionLocalProvider(LocalRecreate provides { recreate() }) {
                    AppRoot(viewModel, snackbar)
                }
                val context = LocalContext.current
                LaunchedEffect(snapshot.settings.language) {
                    if (snapshot.settings.language != initialLanguage) {
                        // Neue Sprache erfordert ein frisches Context/Theme
                        recreate()
                    }
                }
            }
        }
    }
}

/** Wird von den Einstellungen aufgerufen, um die Activity neu zu erzeugen (Sprachwechsel). */
val LocalRecreate = staticCompositionLocalOf<() -> Unit> { { } }
