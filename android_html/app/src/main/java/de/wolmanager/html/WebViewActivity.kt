package de.wolmanager.html

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.VibratorManager
import android.view.View
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import de.wolmanager.html.util.RemoteDesktop
import java.io.File

/**
 * Single-Activity-Hülle: ein WebView füllt den Bildschirm, die UI kommt aus
 * file:///android_asset/app/index.html. Native Fähigkeiten über Bridge ("Android").
 */
class WebViewActivity : ComponentActivity(), BridgeHost {

    private lateinit var webView: WebView
    private lateinit var bridge: Bridge

    private var createDocCb: ((Uri?) -> Unit)? = null
    private var openDocCb: ((Uri?) -> Unit)? = null
    private var createDocLauncher: ActivityResultLauncher<String>? = null
    private var openDocLauncher: ActivityResultLauncher<Array<String>>? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        File(filesDir, "data").mkdirs()

        createDocLauncher = registerForActivityResult(
            ActivityResultContracts.CreateDocument("application/json"),
        ) { uri -> createDocCb?.invoke(uri); createDocCb = null }

        openDocLauncher = registerForActivityResult(
            ActivityResultContracts.OpenDocument(),
        ) { uri -> openDocCb?.invoke(uri); openDocCb = null }

        bridge = Bridge(this, (application as WolApplication).container, this)

        webView = WebView(this).apply {
            setBackgroundColor(0xFF0F1115.toInt())
            isVerticalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER
        }
        bridge.webView = webView
        // JS-Seite spricht die Bridge als `window.Android` an (siehe bridge.js).
        webView.addJavascriptInterface(bridge, "Android")

        configure(webView.settings)
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                // Externe Links (GitHub-Releases) im Browser öffnen, App-URLs intern laden
                val url = request.url.toString()
                return if (url.startsWith("file://")) false else {
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                    true
                }
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (request.isForMainFrame) {
                    Toast.makeText(this@WebViewActivity, R.string.webview_load_error, Toast.LENGTH_LONG).show()
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(cm: ConsoleMessage): Boolean {
                // JS-Console → Logcat (Debug)
                android.util.Log.d("WOL-HTML", "[${cm.messageLevel()}] ${cm.message()}")
                return true
            }
        }

        val root = FrameLayout(this).apply {
            addView(
                webView,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )
        }
        setContentView(root)

        // Edge-to-edge: Content zeichnet hinter Status-/Navigationsleiste.
        applyEdgeToEdge()
        webView.loadUrl("file:///android_asset/app/index.html")
    }

    private fun configure(s: WebSettings) {
        // JavaScript ist bewusst aktiv: die komplette UI ist HTML aus den eigenen Assets.
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.allowFileAccess = true
        s.allowContentAccess = false
        s.cacheMode = WebSettings.LOAD_DEFAULT
        s.mediaPlaybackRequiresUserGesture = false
        s.textZoom = 100
    }

    private fun applyEdgeToEdge() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
    }

    // ── BridgeHost ────────────────────────────────────────────────────────────

    override fun launchCreateDocument(mime: String, suggestedName: String, cb: (Uri?) -> Unit) {
        runOnUiThread {
            createDocCb = cb
            createDocLauncher?.launch(suggestedName)
        }
    }

    override fun launchOpenDocument(cb: (Uri?) -> Unit) {
        runOnUiThread {
            openDocCb = cb
            openDocLauncher?.launch(arrayOf("application/json", "text/plain", "*/*"))
        }
    }

    override fun vibrate(ms: Long) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator.vibrate(VibrationEffect.createOneShot(ms, 200))
            } else {
                @Suppress("DEPRECATION")
                val v = getSystemService(VIBRATOR_SERVICE) as android.os.Vibrator
                v.vibrate(VibrationEffect.createOneShot(ms, 200))
            }
        } catch (_: Exception) {
        }
    }

    /**
     * Externe App per ACTION_VIEW öffnen (Remote-Desktop: Windows App via rdp://).
     * false, wenn keine App das Schema bedient → die Bridge meldet "remote.notinstalled".
     */
    override fun openExternal(url: String): Boolean = try {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        true
    } catch (_: Exception) {
        false
    }

    /**
     * `.rdp`-Datei per ACTION_SEND an die Windows App (`com.microsoft.rdc.androidx`)
     * übergeben; sie legt daraus eine Verbindung mit dem Dateinamen als Anzeigename
     * an. Bewusst auf das Paket eingeschränkt: andere RDP-/Share-Empfänger würden
     * sonst das Profil erzeugen. false → Bridge fällt auf die URI-Kandidaten zurück.
     */
    override fun shareRdpFile(fileUri: Uri): Boolean = try {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/rdp"
            putExtra(Intent.EXTRA_STREAM, fileUri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            setPackage(RemoteDesktop.WINDOWS_APP_PACKAGE)
        }
        // Nur starten, wenn die Windows App den Typ auch wirklich übernimmt.
        if (intent.resolveActivity(packageManager) == null) return false
        startActivity(intent)
        true
    } catch (_: Exception) {
        false
    }

    // ── Lebenszyklus ──────────────────────────────────────────────────────────

    override fun onPause() {
        webView.onPause()
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        webView.onResume()
    }

    override fun onDestroy() {
        bridge.webView = null
        webView.destroy()
        super.onDestroy()
    }

    /** Zurück-Taste: erst Sheets/Overlays in der HTML-UI schließen lassen. */
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (bridge.sheetOpen) {
            webView.evaluateJavascript("window.onNativeBack && window.onNativeBack()", null)
        } else {
            super.onBackPressed()
        }
    }
}
