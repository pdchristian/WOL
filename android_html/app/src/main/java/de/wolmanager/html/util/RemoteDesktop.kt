package de.wolmanager.html.util

/**
 * Remote-Desktop-Aufruf über die installierte **Windows App**
 * (früher „Microsoft Remote Desktop", `com.microsoft.rdc.androidx`).
 *
 * Android kann kein eigenes RDP bereitstellen, und die Windows App kennt — anders
 * als `mstsc` unter Windows — keinen Weg, einem Aufruf ein **Passwort** mitzugeben:
 * das dokumentierte URI-Schema der Client-App für macOS/iOS/Android
 * (`rdp://<attribut>=<typ>:<wert>&…`) kennt für `full address` und `username`
 * Attribute, aber keines für Passwörter (das Passwort könnte ohnehin nur der
 * Windows Credential Manager übernehmen, der Drittanbietern nicht zur Verfügung
 * steht). Die UI legt das Passwort deshalb in die Zwischenablage, damit es im
 * Verbindungsfenster eingefügt werden kann.
 *
 * Ebenso gibt es kein Attribut für den Anzeigenamen: der Eintrag in der Windows App
 * heißt wie die Adresse. Der Gerätename wird daher nur protokolliert.
 *
 * Quelle: Microsoft Learn – „Remote Desktop URI scheme" (Legacy `rdp://`-Schema,
 * Attribute `full address=s:`, `username=s:`; für Android dokumentiert).
 *
 * Rein Kotlin (kein `android.net.Uri`), damit es in JVM-Unit-Tests prüfbar ist.
 */
object RemoteDesktop {

    /** Fehler-Schlüssel: keine Windows App / kein RDP-Client installiert. */
    const val ERR_NOT_INSTALLED = "remote.notinstalled"

    /** Fehler-Schlüssel: für das Gerät ist weder IP/Hostname noch Name hinterlegt. */
    const val ERR_NO_HOST = "remote.nohost"

    /** Host-Kandidat: IP-Adresse, sonst der Gerätename (wie iOS). */
    fun hostOf(ip: String, name: String): String =
        ip.trim().ifBlank { name.trim() }

    /**
     * URI-Kandidaten in Reihenfolge ihrer Wahrscheinlichkeit. `rdp://` ist das für
     * Android dokumentierte Schema; `ms-rd://add/host/…` (iOS-Form) als Fallback für
     * App-Versionen, die zusätzlich dieses Schema registrieren.
     *
     * [mode] (`"full"` / `"win"`) wird akzeptiert, ist aber ohne Wirkung: die
     * Attributtabelle des Android-Clients enthält kein `screen mode id` (nur macOS/iOS).
     * Auf dem Smartphone ist die Sitzung ohnehin randlos.
     */
    fun candidates(host: String, username: String, mode: String = "full"): List<String> {
        val h = encodeValue(host.trim())
        if (h.isEmpty()) return emptyList()
        val u = encodeValue(username.trim())
        val attrs = buildString {
            append("full%20address=s:").append(h)
            if (u.isNotEmpty()) append("&username=s:").append(u)
        }
        return listOf(
            "rdp://$attrs",
            "ms-rd://add/host/$h" + if (u.isNotEmpty()) "?username=$u" else "",
        )
    }

    /**
     * Percent-Kodierung für Werte im Query-Teil: erhalten bleibt, was ein Hostname
     * oder Benutzername harmlos verwendet (`A-Za-z0-9`, `-._~`, `:`, `@`), alles
     * andere — insbesondere `%`, `&`, `=`, `#`, `?`, `\`, Leerzeichen und
     * Nicht-ASCII — wird als UTF-8-Einzelbyte `%XX` geschrieben.
     */
    fun encodeValue(value: String): String {
        if (value.isEmpty()) return ""
        val sb = StringBuilder(value.length + 8)
        for (ch in value) {
            when {
                ch in 'A'..'Z' || ch in 'a'..'z' || ch in '0'..'9' -> sb.append(ch)
                ch in "-._~:@/" -> sb.append(ch)
                else -> for (b in ch.toString().toByteArray(Charsets.UTF_8)) {
                    sb.append('%').append(HEX[(b.toInt() shr 4) and 0x0F]).append(HEX[b.toInt() and 0x0F])
                }
            }
        }
        return sb.toString()
    }

    /**
     * Inhalt einer `.rdp`-Datei (`KEY:TYP:WERT`, CRLF) — Format wie die Desktop-App
     * (`wol_app/utils.py`). Mit Passwort: `password:54:` = base64(UTF-16LE), wie von
     * mstsc dokumentiert. Die mobilen Clients lesen es möglicherweise nicht — dann
     * bleibt der Zwischenablage-Weg der Brücke. Anders als iOS (Freigabe-Sheet!)
     * bleibt die Datei hier im app-private Cache und wird nur der Windows App mit
     * zeitlich begrenzter Leserechte übergeben, deshalb ist das Einbetten vertretbar.
     *
     * Der Anzeigename des Profils ergibt sich aus dem **Dateinamen** (siehe
     * [sanitizedFilename]) — die `.rdp`-Spezifikation selbst kennt kein Namensfeld.
     */
    fun buildRdpContent(host: String, username: String, password: String, mode: String): String {
        val lines = mutableListOf(
            "full address:s:" + host.trim(),
            // Selbstsignierte Zertifikate (typisch für xrdp/Linux) ohne Rückfrage akzeptieren.
            "authentication level:i:0",
            // Adresse nach Redirection-Hop als Serveridentität behalten (xrdp).
            "use redirection server name:i:1",
        )
        val u = username.trim()
        if (u.isNotEmpty()) lines.add("username:s:$u")
        if (password.isNotEmpty()) {
            // java.util.Base64: ab API 26 (minSdk) verfügbar und JVM-testbar.
            val b64 = java.util.Base64.getEncoder()
                .encodeToString(password.toByteArray(Charsets.UTF_16LE))
            lines.add("password:54:$b64")
            lines.add("prompt credential:i:0")
        }
        lines.add("screen mode id:i:" + if (mode == "full") 1 else 2)
        return lines.joinToString("\r\n") + "\r\n"
    }

    /**
     * Dateiname (ohne Endung) aus dem Gerätenamen: dateisystemsicher machen. Die
     * Windows App verwendet ihn als Anzeigename der neu angelegten Verbindung.
     */
    fun sanitizedFilename(name: String): String {
        var out = name.trim().map { if (it in ('A'..'Z') || it in ('a'..'z') || it in ('0'..'9') ||
            it in " -._") it else ' ' }.joinToString("").trim()
        if (out.isEmpty()) out = "Remote-PC"
        if (out.length > 60) out = out.substring(0, 60).trim()
        return out
    }

    /** Paketname der Windows App (ehem. „Microsoft Remote Desktop", Android). */
    const val WINDOWS_APP_PACKAGE = "com.microsoft.rdc.androidx"

    private const val HEX = "0123456789ABCDEF"
}
