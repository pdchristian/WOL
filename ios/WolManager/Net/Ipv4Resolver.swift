import Foundation

/*
 * Host-Name → IPv4-Auflösung für den IPv4-only Host Service — analog Ipv4Resolver.kt
 * und wol_app/utils.resolve_ipv4_all.
 *
 * Grund: Der WOL Host Service lauscht auf 0.0.0.0:8765 (nur IPv4). Ein Name kann
 * mehrere A-Records haben (veraltete DHCP-Lease + aktuelle Adresse) in nicht
 * vorhersagbarer Reihenfolge, und ein Dual-Stack-Name kann AAAA bevorzugen.
 * Deshalb werden gezielt alle IPv4-Kandidaten ermittelt und der Reihe nach
 * ausprobiert — sonst erscheint ein Gerät fälschlich als offline.
 */
enum Ipv4Resolver {

    /// Alle IPv4-Adressen, die `value` auflöst (IPv4-Literal → sich selbst).
    static func resolveAll(_ value: String) -> [String] {
        let v = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if v.isEmpty { return [] }
        if isIpv4Literal(v) { return [v] }

        var hints = addrinfo(ai_flags: 0, ai_family: AF_INET, ai_socktype: SOCK_STREAM,
                             ai_protocol: IPPROTO_TCP, ai_addrlen: 0, ai_canonname: nil,
                             ai_addr: nil, ai_next: nil)
        var res: UnsafeMutablePointer<addrinfo>?
        guard getaddrinfo(v, nil, &hints, &res) == 0 else { return [] }
        defer { if let r = res { freeaddrinfo(r) } }

        var ips: [String] = []
        var cur = res
        while let r = cur {
            if let sa = r.pointee.ai_addr,
               sa.pointee.sa_family == sa_family_t(AF_INET),
               let ip = ipString(from: sa), !ips.contains(ip) {
                ips.append(ip)
            }
            cur = r.pointee.ai_next
        }
        return ips
    }

    /// true für IPv4-Literale im Dotted-Quad-Format (0.0.0.0 … 255.255.255.255).
    static func isIpv4Literal(_ value: String) -> Bool {
        let parts = value.trimmingCharacters(in: .whitespacesAndNewlines)
            .split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { return false }
        return parts.allSatisfy { p in
            guard !p.isEmpty, p.count <= 3,
                  p.allSatisfy({ $0.isASCII && $0.isNumber }) else { return false }
            guard let n = Int(p) else { return false }
            return (0...255).contains(n)
        }
    }

    /// Textform einer IPv4-Adresse aus einem sockaddr.
    static func ipString(from sa: UnsafePointer<sockaddr>) -> String? {
        var buf = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
        let sin = sa.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { $0.pointee }
        var addr = sin.sin_addr
        guard inet_ntop(AF_INET, &addr, &buf, socklen_t(INET_ADDRSTRLEN)) != nil else { return nil }
        return String(cString: buf)
    }
}
