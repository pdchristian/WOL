import Foundation

/* Validierungsregeln — spiegeln settings_dialog/device_io der Windows-App. */
enum Validation {

    private static let macRE = try! NSRegularExpression(pattern: "^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
    private static let ipv4RE = try! NSRegularExpression(
        pattern: "^((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\.){3}(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)$")
    private static let hostnameRE = try! NSRegularExpression(
        pattern: "^[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?)*$")

    private static func matches(_ re: NSRegularExpression, _ s: String) -> Bool {
        re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }

    static func isValidMac(_ mac: String) -> Bool {
        matches(macRE, mac.trimmingCharacters(in: .whitespaces))
    }

    static func isValidIpOrHostname(_ value: String) -> Bool {
        let v = value.trimmingCharacters(in: .whitespaces)
        if v.isEmpty { return true } // IP ist optional
        return matches(ipv4RE, v) || matches(hostnameRE, v)
    }

    static func isValidIpv4(_ value: String) -> Bool {
        matches(ipv4RE, value.trimmingCharacters(in: .whitespaces))
    }

    static func isValidPort(_ port: Int) -> Bool { (1...65535).contains(port) }

    static func normalizeMac(_ mac: String) -> String {
        mac.trimmingCharacters(in: .whitespaces)
            .uppercased()
            .replacingOccurrences(of: "-", with: ":")
            .replacingOccurrences(of: " ", with: ":")
    }

    /// true, wenn die (bereits normalisierte) MAC bereits unter einer anderen Geräte-ID existiert.
    static func macExists(_ mac: String, existing: [String], excludeId: String? = nil) -> Bool {
        let norm = normalizeMac(mac)
        return existing.contains { normalizeMac($0) == norm }
    }
}
