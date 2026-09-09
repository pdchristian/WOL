import Foundation

/*
 * Client für den WOL Host Service (Protokoll v4) — analog HostServiceClient.kt.
 * TCP 8765, LF-terminierte JSON-Nachrichten, eine Anfrage → eine Antwort → schließen.
 * Authentifizierung pro Anfrage über username/password.
 * Implementierung über BSD-Sockets (Blocking, auf Worker-Queue).
 */
final class HostServiceClient {

    enum HostResult {
        case ok(body: [String: Any])
        case error(String)
    }

    static let defaultPort = 8765
    private static let statusTimeout = 3000
    private static let cmdTimeout = 10000
    private static let metricsTimeout = 6000
    private static let maxSmall = 4096
    private static let maxMetrics = 16384
    private static let maxBatch = 131072
    static let errNoResponse = "host_unreachable"
    static let errBadResponse = "bad_response"
    static let errGeneric = "error"

    private let port: Int
    private let queue = DispatchQueue(label: "de.wolmanager.hostservice", attributes: .concurrent)

    init(port: Int = HostServiceClient.defaultPort) { self.port = port }

    // ── Öffentliche Befehle ─────────────────────────────────────────────────

    func status(host: String) async -> HostResult {
        await request(host: host, payload: ["command": "status"],
                      timeoutMs: Self.statusTimeout, maxBytes: Self.maxSmall)
    }

    func metrics(host: String, username: String, password: String, watch: [String] = [])
        async -> (HostResult, MetricsSnapshot?) {
        var payload: [String: Any] = ["command": "metrics", "username": username, "password": password]
        if !watch.isEmpty { payload["watch"] = watch }
        let res = await request(host: host, payload: payload,
                                timeoutMs: Self.metricsTimeout, maxBytes: Self.maxMetrics)
        guard case let .ok(body) = res else { return (res, nil) }
        guard let data = try? JSONSerialization.data(withJSONObject: body),
              let snap = try? JSONDecoder().decode(MetricsSnapshot.self, from: data) else {
            return (.error(Self.errBadResponse), nil)
        }
        return (.ok(body: body), snap)
    }

    func shutdown(host: String, username: String, password: String) async -> HostResult {
        await request(host: host, payload: ["command": "shutdown", "username": username, "password": password],
                      timeoutMs: Self.cmdTimeout, maxBytes: Self.maxSmall)
    }

    func reboot(host: String, username: String, password: String) async -> HostResult {
        await request(host: host, payload: ["command": "reboot", "username": username, "password": password],
                      timeoutMs: Self.cmdTimeout, maxBytes: Self.maxSmall)
    }

    func runBatch(host: String, script: String, username: String, password: String, timeoutSec: Int)
        async -> (HostResult, BatchResult?) {
        let res = await request(
            host: host,
            payload: ["command": "run_batch", "username": username, "password": password,
                      "script": script, "timeout": timeoutSec],
            timeoutMs: timeoutSec * 1000 + 5000, maxBytes: Self.maxBatch)
        guard case let .ok(body) = res else { return (res, nil) }
        return (.ok(body: body), Self.parseBatch(body))
    }

    /// Wire-Konvertierung: duration_ms darf String sein ("1234"), truncated ebenso ("true").
    static func parseBatch(_ body: [String: Any]) -> BatchResult {
        let exitCode = (body["exit_code"] as? Int) ?? Int((body["exit_code"] as? String) ?? "") ?? -1
        let stdout = (body["stdout"] as? String) ?? ""
        let stderr = (body["stderr"] as? String) ?? ""
        let durationMs = Int64((body["duration_ms"] as? String) ?? "")
            ?? Int64((body["duration_ms"] as? Int).map(String.init)) ?? 0
        let truncated: Bool
        if let s = body["truncated"] as? String { truncated = (s == "true") }
        else { truncated = (body["truncated"] as? Bool) ?? false }
        return BatchResult(exitCode: exitCode, stdout: stdout, stderr: stderr,
                           durationMs: durationMs, truncated: truncated)
    }

    /// Schneller TCP-Erreichbarkeitstest (Ping-Ersatz, kein ICMP auf iOS).
    /// Liefert RTT in ms oder nil.
    func ping(host: String, testPort: Int? = nil, timeoutMs: Int = 2000) async -> Int64? {
        let p = testPort ?? Self.defaultPort
        return await withCheckedContinuation { cont in
            queue.async {
                let start = Int64(Date().timeIntervalSince1970 * 1000)
                if let fd = Self.connectIpv4(host: host, port: p, timeoutMs: timeoutMs) {
                    close(fd)
                    cont.resume(returning: Int64(Date().timeIntervalSince1970 * 1000) - start)
                } else {
                    cont.resume(returning: nil)
                }
            }
        }
    }

    // ── Kern: 1 request = 1 response = close ────────────────────────────────

    func request(host: String, payload: [String: Any], timeoutMs: Int, maxBytes: Int) async -> HostResult {
        await withCheckedContinuation { cont in
            queue.async {
                cont.resume(returning: Self.requestSync(host: host, port: self.port, payload: payload,
                                                        timeoutMs: timeoutMs, maxBytes: maxBytes))
            }
        }
    }

    /// Blockierend (Worker-Queue): verdrahtet identisch zu Kotlin request().
    static func requestSync(host: String, port: Int, payload: [String: Any],
                            timeoutMs: Int, maxBytes: Int) -> HostResult {
        // IPv4 gezielt auflösen und jeden A-Record probieren (siehe connectIpv4),
        // damit Host-Namen mit mehreren Adressen / Dual-Stack nicht offline wirken.
        guard let fd = connectIpv4(host: host, port: port, timeoutMs: timeoutMs) else {
            return .error(errNoResponse)
        }
        defer { close(fd) }

        guard let jsonLine = try? JSONSerialization.data(withJSONObject: payload),
              var sendStr = String(data: jsonLine, encoding: .utf8) else {
            return .error(errGeneric)
        }
        sendStr += "\n"
        let payloadBytes = [UInt8](sendStr.utf8)
        let sentAll: Bool = payloadBytes.withUnsafeBufferPointer { buf in
            var off = 0
            while off < buf.count {
                let n = Darwin.send(fd, buf.baseAddress! + off, buf.count - off, 0)
                if n <= 0 { return false }
                off += n
            }
            return true
        }
        if !sentAll { return .error(errNoResponse) }

        guard let line = readLimited(fd, maxBytes: maxBytes) else { return .error(errNoResponse) }
        guard let data = line.data(using: .utf8),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return .error(errBadResponse)
        }
        if (obj["status"] as? String) == "ok" { return .ok(body: obj) }
        if let msg = obj["message"] as? String { return .error(msg) }
        return .error(errGeneric)
    }

    /// Liest bis LF, max maxBytes Zeichen. nil bei sofortigem EOF.
    private static func readLimited(_ fd: Int32, maxBytes: Int) -> String? {
        var buf = [UInt8]()
        var byte = [UInt8](repeating: 0, count: 1)
        while true {
            let n = read(fd, &byte, 1)
            if n <= 0 { return buf.isEmpty ? nil : String(decoding: buf, as: UTF8.self) }
            if byte[0] == UInt8(ascii: "\n") { return String(decoding: buf, as: UTF8.self) }
            buf.append(byte[0])
            if buf.count > maxBytes { return String(decoding: buf, as: UTF8.self) }
        }
    }

    /// TCP-Connect-Helfer (Status/Ping). true = Verbindung möglich.
    static func tcpConnect(host: String, port: Int, timeoutMs: Int) -> Bool {
        let fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        guard fd >= 0 else { return false }
        defer { close(fd) }

        var tv = timeval(tv_sec: timeoutMs / 1000, tv_usec: (timeoutMs % 1000) * 1000)
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))

        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        if inet_pton(AF_INET, host, &addr.sin_addr) != 1 {
            addr.sin_addr.s_addr = inet_addr(host)
            if addr.sin_addr.s_addr == INADDR_NONE, let resolved = resolveHost(host) {
                addr.sin_addr.s_addr = resolved
            }
        }
        return withUnsafePointer(to: &addr) { p in
            p.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                connect(fd, sa, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
    }

    /// DNS-Auflösung (erster IPv4-Treffer) — für Aufrufer, die nur eine Adresse brauchen.
    static func resolveHost(_ host: String) -> in_addr_t? {
        var hints = addrinfo(ai_flags: 0, ai_family: AF_INET, ai_socktype: SOCK_STREAM,
                             ai_protocol: IPPROTO_TCP, ai_addrlen: 0, ai_canonname: nil, ai_addr: nil, ai_next: nil)
        var res: UnsafeMutablePointer<addrinfo>?
        guard getaddrinfo(host, nil, &hints, &res) == 0, let r = res else { return nil }
        defer { freeaddrinfo(res) }
        guard let sa = r.pointee.ai_addr else { return nil }
        let sin = sa.pointee.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { $0.pointee.sin_addr }
        return sin.s_addr
    }

    /// Verbindet sich zur ersten erreichbaren IPv4-Adresse von `host`. Host-Namen
    /// werden explizit zu IPv4 aufgelöst und jeder A-Record mit einem frischen
    /// Socket probiert (ein fehlgeschlagener connect schließt seinen Socket), damit
    /// ein Gerät mit zusätzlichem IPv6 (AAAA) oder veralteter A-Adresse trotzdem
    /// den IPv4-only Host Service erreicht. Liefert den verbundenen fd oder nil.
    static func connectIpv4(host: String, port: Int, timeoutMs: Int) -> Int32? {
        for ip in Ipv4Resolver.resolveAll(host) {
            let fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
            guard fd >= 0 else { continue }
            var tv = timeval(tv_sec: timeoutMs / 1000, tv_usec: (timeoutMs % 1000) * 1000)
            var recvTv = tv
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &recvTv, socklen_t(MemoryLayout<timeval>.size))

            var addr = sockaddr_in()
            addr.sin_family = sa_family_t(AF_INET)
            addr.sin_port = in_port_t(port).bigEndian
            var okAddr = false
            if inet_pton(AF_INET, ip, &addr.sin_addr) == 1 {
                okAddr = true
            } else {
                let n = inet_addr(ip)
                if n != INADDR_NONE { addr.sin_addr.s_addr = n; okAddr = true }
            }
            guard okAddr else { close(fd); continue }

            let connOk: Bool = withUnsafePointer(to: &addr) { p in
                p.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                    connect(fd, sa, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
                }
            }
            if connOk { return fd }
            close(fd)
        }
        return nil
    }

    /// Diagnose für die UI: DNS-Auflösung + TCP-Erreichbarkeit pro IPv4-Kandidat.
    /// Zeigt, WARUM ein Gerät offline ist (Name nicht auflösbar vs. Dienst antwortet nicht).
    struct CandidateResult { let address: String; let ok: Bool; let rttMs: Int64; let error: String }
    struct HostDiagnosis { let host: String; let resolved: Bool; let candidates: [CandidateResult]; let resolveError: String }

    func diagnose(host: String, timeoutMs: Int = 2000) async -> HostDiagnosis {
        await withCheckedContinuation { cont in
            queue.async {
                let ips = Ipv4Resolver.resolveAll(host)
                if host.trimmingCharacters(in: .whitespaces).isEmpty {
                    cont.resume(returning: HostDiagnosis(host: host, resolved: false, candidates: [], resolveError: "no_ip"))
                    return
                }
                if ips.isEmpty {
                    cont.resume(returning: HostDiagnosis(host: host, resolved: false, candidates: [], resolveError: "no_ipv4_record"))
                    return
                }
                let results = ips.map { ip -> CandidateResult in
                    let start = Int64(Date().timeIntervalSince1970 * 1000)
                    if let fd = Self.connectOne(ip: ip, port: self.port, timeoutMs: timeoutMs) {
                        close(fd)
                        return CandidateResult(address: ip, ok: true, rttMs: Int64(Date().timeIntervalSince1970 * 1000) - start, error: "")
                    }
                    return CandidateResult(address: ip, ok: false, rttMs: Int64(Date().timeIntervalSince1970 * 1000) - start, error: "unreachable")
                }
                cont.resume(returning: HostDiagnosis(host: host, resolved: true, candidates: results, resolveError: ""))
            }
        }
    }

    /// Einzelnen IPv4-Punkt verbinden (für Diagnose); aufrufenderseitig schließen.
    private static func connectOne(ip: String, port: Int, timeoutMs: Int) -> Int32? {
        let fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        guard fd >= 0 else { return nil }
        var tv = timeval(tv_sec: timeoutMs / 1000, tv_usec: (timeoutMs % 1000) * 1000)
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        guard inet_pton(AF_INET, ip, &addr.sin_addr) == 1 else { close(fd); return nil }
        let ok: Bool = withUnsafePointer(to: &addr) { p in
            p.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                connect(fd, sa, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
        if !ok { close(fd); return nil }
        return fd
    }
}
