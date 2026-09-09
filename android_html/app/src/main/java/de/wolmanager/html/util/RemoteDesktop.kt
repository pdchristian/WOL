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

    private const val HEX = "0123456789ABCDEF"
}
