import UIKit
import WebKit

/*
 * Single-View-Hülle: ein WKWebView füllt den Bildschirm, die UI kommt aus
 * WebApp/index.html (App-Bundle). Native Fähigkeiten über Bridge ("Android").
 * Analog zu WebViewActivity.kt.
 */
final class WebViewController: UIViewController, BridgeHost, WKNavigationDelegate, WKUIDelegate {

    private var webView: WKWebView!
    private var bridge: Bridge!
    private let documentPicker = DocumentPicker()
    private var loadErrorShown = false

    override var preferredStatusBarStyle: UIStatusBarStyle {
        // Dunkles Theme → helle Statusleiste; helles Theme → dunkle Statusleiste.
        traitCollection.userInterfaceStyle == .dark ? .lightContent : .darkContent
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0x0F / 255.0, green: 0x11 / 255.0, blue: 0x15 / 255.0, alpha: 1)

        let config = WKWebViewConfiguration()
        let controller = WKUserContentController()
        bridge = Bridge(container: AppContainer.shared, host: self)
        controller.add(WeakMessageHandler(target: bridge), name: "Android")
        controller.add(WeakMessageHandler(target: bridge), name: "AndroidSetSheet")
        controller.addUserScript(Bridge.userScript) // VOR bridge.js → window.Android existiert
        config.userContentController = controller
        config.defaultWebpagePreferences.allowsContentJavaScript = true

        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.backgroundColor = UIColor(red: 0x0F / 255.0, green: 0x11 / 255.0, blue: 0x15 / 255.0, alpha: 1)
        webView.isOpaque = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.bounces = false
        if #available(iOS 16.4, *) {
            webView.isInspectable = true // Debug über Safari
        }
        webView.navigationDelegate = self
        webView.uiDelegate = self
        view.addSubview(webView)

        bridge.webView = webView

        documentPicker.presenter = self

        loadApp()
    }

    private func loadApp() {
        // WebApp-Ordner als Bundleressource; relativ ladende CSS/JS funktionieren.
        if let index = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "WebApp") {
            webView.loadFileURL(index, allowingReadAccessTo: index.deletingLastPathComponent())
        } else if let index = Bundle.main.url(forResource: "index", withExtension: "html") {
            webView.loadFileURL(index, allowingReadAccessTo: index.deletingLastPathComponent())
        }
    }

    override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        setNeedsStatusBarAppearanceUpdate()
    }

    // ── WKNavigationDelegate ────────────────────────────────────────────────

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        // Externe Links (GitHub-Releases) in Safari öffnen, App-URLs intern laden.
        if let url = navigationAction.request.url, url.isFileURL == false {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError: Error) {
        showErrorOnce()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
                 withError: Error) {
        showErrorOnce()
    }

    private func showErrorOnce() {
        guard !loadErrorShown else { return }
        loadErrorShown = true
        let alert = UIAlertController(title: "Fehler",
                                      message: "Die App-Oberfläche konnte nicht geladen werden.",
                                      preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    // ── BridgeHost ──────────────────────────────────────────────────────────

    func exportDocument(suggestedName: String, data: Data, completion: @escaping (Bool) -> Void) {
        DispatchQueue.main.async { [weak self] in
            self?.documentPicker.exportDocument(suggestedName: suggestedName, data: data, completion: completion)
        }
    }

    func openDocument(completion: @escaping (URL?) -> Void) {
        DispatchQueue.main.async { [weak self] in
            self?.documentPicker.openDocument(completion: completion)
        }
    }

    // ── Lebenszyklus ────────────────────────────────────────────────────────

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        AppContainer.shared.startScheduleTicker()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        // Ticker bleibt aktiv, solange die View lebt (Hintergrund → BGTask).
    }
}

/*
 * WKUserContentController hält starke Referenzen auf Message-Handler → zyklischer
 * Halt (Controller → WebView → Configuration → Handler → Bridge → WebView).
 * Dieser Proxy leitet nur weiter und hält das Ziel schwach.
 */
final class WeakMessageHandler: NSObject, WKScriptMessageHandler {
    private weak var target: WKScriptMessageHandler?
    init(target: WKScriptMessageHandler?) { self.target = target }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        target?.userContentController(userContentController, didReceive: message)
    }
}
