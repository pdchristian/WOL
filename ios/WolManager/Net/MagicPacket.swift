import Foundation

/*
 * Magic Packet — drahtidentisch zu wol_app/wol_engine.py:
 * 6× 0xFF gefolgt von 16× der MAC-Adresse. UDP-Broadcast auf Port 9 (konfigurierbar).
 * iOS: zusätzlich gerichtete Broadcast-IPs je Interface (getifaddrs), Socket an
 * lokale IP gebunden — wie der Windows-Client.
 */
enum MagicPacket {

    enum MpError: Error { case invalidMac, sendFailed(String) }

    /// Baut das 102-Byte-Paket. Erwartet eine normale MAC (Doppelpunkte/Bindestriche egal).
    static func build(mac: String) throws -> Data {
        guard let bytes = macBytes(mac) else { throw MpError.invalidMac }
        var packet = [UInt8](repeating: 0xFF, count: 6)
        for _ in 0..<16 { packet.append(contentsOf: bytes) }
        return Data(packet)
    }

    static func macBytes(_ mac: String) -> [UInt8]? {
        let norm = mac.trimmingCharacters(in: .whitespaces)
            .uppercased()
            .replacingOccurrences(of: "-", with: ":")
            .replacingOccurrences(of: " ", with: ":")
        let parts = norm.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 6 else { return nil }
        var out = [UInt8]()
        for p in parts {
            // wie Kotlin toInt(16).toByte(): 1-2 Hex-Ziffern, leer/ungültig/>255 → nil
            guard !p.isEmpty, p.count <= 2, let b = UInt8(p, radix: 16) else { return nil }
            out.append(b)
        }
        return out
    }

    /// Reicht die MAC für ein Wake aus?
    static func canWake(_ device: Device) -> Bool { macBytes(device.mac) != nil }

    /// Sendet das Magic Packet: globaler Broadcast + gerichtete Broadcasts je Interface.
    /// Gibt die Anzahl erfolgreich gesendeter Kopien zurück (min. 1 = Erfolg).
    @discardableResult
    static func send(device: Device, broadcastIp: String, port: Int) throws -> Int {
        let bytes: Data
        do {
            bytes = try build(mac: Validation.normalizeMac(device.mac))
        } catch {
            throw MpError.invalidMac
        }
        var sent = 0
        var lastError: String?

        // 1) Globaler Broadcast (255.255.255.255 oder konfiguriert)
        do {
            try sendPacket(bytes, to: broadcastIp.isEmpty ? "255.255.255.255" : broadcastIp, port: port, bindTo: nil)
            sent += 1
        } catch let e as MpError {
            lastError = e.localizedDescription
        } catch { lastError = error.localizedDescription }

        // 2) Gerichtete Broadcast-Adressen je Interface (wie Windows)
        for iface in InterfaceHelper.ipv4Interfaces() {
            guard let bcast = directedBroadcast(ip: iface.ip, netmask: iface.netmask) else { continue }
            do {
                try sendPacket(bytes, to: bcast, port: port, bindTo: iface.ip)
                sent += 1
            } catch {
                lastError = error.localizedDescription
            }
        }

        if sent == 0 { throw MpError.sendFailed(lastError ?? "send failed") }
        return sent
    }

    private static func sendPacket(_ payload: Data, to host: String, port: Int, bindTo: String?) throws {
        let fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        guard fd >= 0 else { throw MpError.sendFailed("socket") }
        defer { close(fd) }

        var on = Int32(1)
        setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &on, socklen_t(MemoryLayout<Int32>.size))

        if let bindIp = bindTo {
            var addr = sockaddr_in()
            addr.sin_family = sa_family_t(AF_INET)
            addr.sin_port = 0
            addr.sin_addr = in_addr(s_addr: inet_addr(bindIp))
            withUnsafePointer(to: &addr) { p in
                p.withMemoryRebound(to: sockaddr.self, capacity: 1) { _ = bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
            }
        }

        var dest = sockaddr_in()
        dest.sin_family = sa_family_t(AF_INET)
        dest.sin_port = in_port_t(port).bigEndian
        guard inet_pton(AF_INET, host, &dest.sin_addr) == 1 else {
            // Hostname (selten) per inet_addr auflösen
            dest.sin_addr.s_addr = inet_addr(host)
        }

        let res: Int = payload.withUnsafeBytes { raw in
            withUnsafePointer(to: &dest) { p in
                p.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                    sendto(fd, raw.baseAddress, payload.count, 0, sa, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
        }
        if res < 0 { throw MpError.sendFailed("sendto \(host)") }
    }

    /// Gerichtete Broadcast-Adresse: Netzwerk-Adresse OR ~Maske.
    static func directedBroadcast(ip: String, netmask: String) -> String? {
        guard let ipNum = ipv4ToUInt(ip), let maskNum = ipv4ToUInt(netmask) else { return nil }
        let bcast = (ipNum & maskNum) | (~maskNum)
        return uIntToIPv4(bcast)
    }

    static func ipv4ToUInt(_ s: String) -> UInt32? {
        var addr = in_addr()
        guard inet_pton(AF_INET, s, &addr) == 1 else { return nil }
        return UInt32(bigEndian: addr.s_addr)
    }

    static func uIntToIPv4(_ v: UInt32) -> String {
        "\(v >> 24 & 0xFF).\(v >> 16 & 0xFF).\(v >> 8 & 0xFF).\(v & 0xFF)"
    }
}

/* Interface-Auflistung über getifaddrs (en0, en1, … ohne Loopback/APIPA). */
enum InterfaceHelper {

    struct IPv4Interface {
        var name: String
        var ip: String
        var netmask: String
    }

    static func ipv4Interfaces() -> [IPv4Interface] {
        var result: [IPv4Interface] = []
        var ifaddrPtr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddrPtr) == 0 else { return [] }
        defer { freeifaddrs(ifaddrPtr) }

        var names: [String: (ip: String, mask: String?)] = [:]
        var order: [String] = []
        var ptr = ifaddrPtr
        while let cur = ptr {
            defer { ptr = cur.pointee.ifa_next }
            guard let sa = cur.pointee.ifa_addr, sa.pointee.sa_family == UInt8(AF_INET) else { continue }
            let name = String(cString: cur.pointee.ifa_name)
            var addr = sa.pointee.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { $0.pointee }
            let ip = String(cString: inet_ntoa(addr.sin_addr))
            var mask: String? = nil
            if let ma = cur.pointee.ifa_netmask {
                mask = ma.pointee.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { m in
                    var mm = m.pointee
                    return String(cString: inet_ntoa(mm.sin_addr))
                }
            }
            if names[name] == nil { order.append(name) }
            names[name] = (ip, mask)
        }
        for n in order {
            guard let entry = names[n] else { continue }
            if entry.ip.hasPrefix("169.254.") { continue } // APIPA
            result.append(IPv4Interface(name: n, ip: entry.ip, netmask: entry.mask ?? "255.255.255.0"))
        }
        _ = names
        return result
    }

    /// Prefix-Länge aus der Netzmaske (z. B. 255.255.255.0 → 24).
    static func prefix(fromNetmask mask: String) -> Int {
        guard let m = MagicPacket.ipv4ToUInt(mask) else { return 24 }
        var count = 0, v = m
        while v != 0 { count += Int(v & 1); v >>= 1 }
        return count
    }
}
