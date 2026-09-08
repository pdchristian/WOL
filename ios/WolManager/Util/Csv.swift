import Foundation

/* CSV-Export analog zur Windows-App: Semikolon-getrennt, UTF-8 mit BOM. */
enum Csv {

    private static let tsFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        f.locale = Locale(identifier: "en_US")
        f.timeZone = TimeZone.current
        return f
    }()

    static func logsToCsv(_ entries: [LogEntry]) -> String {
        var sb = "\u{FEFF}" // BOM wie in der Windows-App
        sb += "Zeit;Gerät;Level;Nachricht\r\n"
        for e in entries {
            sb += esc(tsFormatter.string(from: Date(timeIntervalSince1970: Double(e.ts) / 1000))) + ";"
            sb += esc(e.device) + ";"
            sb += esc(e.level) + ";"
            sb += esc(e.msg) + "\r\n"
        }
        return sb
    }

    private static func esc(_ v: String) -> String {
        let needsQuotes = v.contains(where: { $0 == ";" || $0 == "\"" || $0 == "\n" || $0 == "\r" })
        var cleaned = v.replacingOccurrences(of: "\r\n", with: " ")
        cleaned = cleaned.replacingOccurrences(of: "\n", with: " ")
        cleaned = cleaned.replacingOccurrences(of: "\r", with: " ")
        if needsQuotes || cleaned.contains("\"") {
            return "\"" + cleaned.replacingOccurrences(of: "\"", with: "\"\"") + "\""
        }
        return cleaned
    }
}
