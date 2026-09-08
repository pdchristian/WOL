package de.wolmanager.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.wolmanager.AppContainer
import de.wolmanager.R
import de.wolmanager.data.ConnState
import de.wolmanager.data.Device
import de.wolmanager.ui.dashboard.DashboardScreen
import de.wolmanager.ui.devices.DevicesScreen
import de.wolmanager.ui.logs.LogsScreen
import de.wolmanager.ui.manage.ManageScreen
import de.wolmanager.ui.schedule.ScheduleScreen
import de.wolmanager.ui.settings.SettingsScreen
import de.wolmanager.ui.theme.LocalWolTokens
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Bildschirme der App (5 Tabs + Dashboard als Detailansicht). */
enum class Screen { DEVICES, MANAGE, SCHEDULE, LOGS, SETTINGS, DASHBOARD }

/**
 * App-Zustand: Runtime-Status je Gerät + Navigation.
 * Ein Exemplar wird in MainActivity per remember erzeugt.
 */
class AppViewModel(val container: AppContainer) {
    private val _runtime = MutableStateFlow<Map<String, ConnState>>(emptyMap())
    val runtime: StateFlow<Map<String, ConnState>> = _runtime.asStateFlow()

    val screen = MutableStateFlow(Screen.DEVICES)
    val dashboardDeviceId = MutableStateFlow<String?>(null)

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var refreshJob: kotlinx.coroutines.Job? = null

    fun setStatus(id: String, state: ConnState) {
        _runtime.value = _runtime.value + (id to state)
    }

    fun openDashboard(deviceId: String) {
        dashboardDeviceId.value = deviceId
        screen.value = Screen.DASHBOARD
    }

    fun closeDashboard() {
        screen.value = Screen.DEVICES
    }

    /** Alle (aktivierten) Geräte-Status parallel prüfen. */
    fun refreshAll(devices: List<Device>) {
        val targets = devices.filter { it.enabled && it.ip.isNotBlank() }
        targets.forEach { setStatus(it.id, ConnState.UNKNOWN) }
        scope.launch {
            targets.map { d ->
                launch(Dispatchers.IO) {
                    val ok = container.checkStatus(d)
                    setStatus(d.id, if (ok) ConnState.ONLINE else ConnState.OFFLINE)
                }
            }.forEach { it.join() }
        }
    }

    /** Auto-Refresh alle 30 s, solange der Geräte-Tab sichtbar ist. */
    fun startAutoRefresh() {
        if (refreshJob?.isActive == true) return
        refreshJob = scope.launch {
            while (true) {
                refreshAll(container.repo.snapshot.value.devices)
                delay(30_000)
            }
        }
    }

    fun stopAutoRefresh() {
        refreshJob?.cancel()
        refreshJob = null
    }
}

val LocalViewModel = staticCompositionLocalOf<AppViewModel> {
    error("AppViewModel not provided")
}

/** Wurzel-Composable: Scaffold (TopBar + Bottom-Navigation) und Screen-Umschaltung. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot(viewModel: AppViewModel, snackbar: SnackbarHostState) {
    val container = viewModel.container
    val snapshot by container.repo.snapshot.collectAsStateWithLifecycle()
    val runtime by viewModel.runtime.collectAsStateWithLifecycle()
    val screen by viewModel.screen.collectAsStateWithLifecycle()
    val tokens = LocalWolTokens.current
    val uiScope = rememberCoroutineScope()

    val toast: (String) -> Unit = { msg ->
        uiScope.launch { snackbar.showSnackbar(msg) }
    }

    LaunchedEffect(screen) {
        if (screen == Screen.DEVICES) viewModel.startAutoRefresh()
        else viewModel.stopAutoRefresh()
    }

    val title = stringResource(
        when (screen) {
            Screen.DEVICES -> R.string.app_name
            Screen.MANAGE -> R.string.nav_manage
            Screen.SCHEDULE -> R.string.nav_schedule
            Screen.LOGS -> R.string.nav_logs
            Screen.SETTINGS -> R.string.nav_settings
            Screen.DASHBOARD -> R.string.app_name
        },
    )
    val subtitleRes = when (screen) {
        Screen.MANAGE -> R.string.manage_subtitle
        Screen.SCHEDULE -> R.string.sched_subtitle
        Screen.LOGS -> R.string.logs_subtitle
        Screen.SETTINGS -> R.string.set_subtitle
        else -> 0
    }

    // Wichtig: Der Provider muss den GESAMTEN Scaffold umschließen — topBar/bottomBar
    // werden in eigenen Slots komponiert und sehen einen Provider innerhalb des
    // Content-Lambda nicht (Crash "AppViewModel not provided" in WolBottomBar).
    CompositionLocalProvider(LocalViewModel provides viewModel) {
        Scaffold(
            containerColor = tokens.bg,
            snackbarHost = {
                SnackbarHost(snackbar) { data ->
                    Snackbar(
                        snackbarData = data,
                        containerColor = tokens.surfaceHover,
                        contentColor = tokens.text,
                        shape = RoundedCornerShape(10.dp),
                    )
                }
            },
            topBar = {
                if (screen != Screen.DASHBOARD) {
                    TopAppBar(
                        title = {
                            Column {
                                Text(title, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = tokens.text)
                                if (subtitleRes != 0) {
                                    Text(stringResource(subtitleRes), fontSize = 12.sp, color = tokens.textDim)
                                }
                            }
                        },
                        colors = TopAppBarDefaults.topAppBarColors(containerColor = tokens.bg),
                    )
                }
            },
            bottomBar = { WolBottomBar() },
        ) { inner ->
            Box(Modifier.padding(inner).fillMaxSize()) {
                when (screen) {
                    Screen.DEVICES -> DevicesScreen(snapshot.devices, runtime, toast)
                    Screen.MANAGE -> ManageScreen(snapshot.devices, toast)
                    Screen.SCHEDULE -> ScheduleScreen(snapshot.devices, snapshot.schedules, toast)
                    Screen.LOGS -> LogsScreen(snapshot.logs, toast)
                    Screen.SETTINGS -> SettingsScreen(snapshot.settings, toast)
                    Screen.DASHBOARD -> {
                        val devId = viewModel.dashboardDeviceId.value
                        val device = snapshot.devices.firstOrNull { it.id == devId }
                        if (device == null) viewModel.closeDashboard()
                        else DashboardScreen(device, toast, onBack = { viewModel.closeDashboard() })
                    }
                }
            }
        }
    }
}
