import Foundation

/* Ergebnis des GitHub-Release-Checks. */
enum UpdResult {
    case latest
    case new(version: String)
    case failed
}

/* GitHub-Release-Check gegen pdchristian/WOL — analog UpdateCheck.kt. */
enum UpdateCheck {

    private static let api = "https://api.github.com/repos/pdchristian/WOL/releases/latest"

    /* GitHub-Tag ("v2.3.5" oder "v.2.3.5") → "2.3.5". */
    static func normalizeTag(_ tag: String) -> String {
        var s = tag.trimmingCharacters(in: .whitespaces)
        while let f = s.first, f == "v" || f == "V" || f == "." { s.removeFirst() }
        return s.trimmingCharacters(in: .whitespaces)
    }

    static func check(current: String) async -> UpdResult {
        guard let url = URL(string: api) else { return .failed }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        do {
            let (data, _) = try await URLSession.shared.data(for: req)
            guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let tag = obj["tag_name"] as? String else { return .failed }
            var latest = normalizeTag(tag)
            if latest.isEmpty { return .failed }
            return isNewer(latest, current) ? .new(version: latest) : .latest
        } catch {
            return .failed
        }
    }

    /// Versionsvergleich "2.3.1" > "2.3.0".
    static func isNewer(_ latest: String, _ current: String) -> Bool {
        let a = latest.split(separator: ".").map { Int($0) ?? 0 }
        let b = current.split(separator: ".").map { Int($0) ?? 0 }
        for i in 0..<max(a.count, b.count) {
            let x = i < a.count ? a[i] : 0
            let y = i < b.count ? b[i] : 0
            if x != y { return x > y }
        }
        return false
    }
}
