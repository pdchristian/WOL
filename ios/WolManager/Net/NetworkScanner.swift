import Foundation

/*
 * Netzwerk-Scan ohne Root: ICMP/ARP stehen iOS nicht zur Verfügung, daher
 * TCP-Port-Sweep über alle aktiven Netze. Ein Host gilt als gefunden, wenn einer
 * der SCAN_PORTS erreichbar antwortet. Hostname via Reverse-DNS, MAC nicht ermittelbar.
 * Analog zu NetworkScanner.kt.
 */
final class NetworkScanner {

    struct Iface {
        var name: String
        var ip: String
        var prefix: Int
        var dns: String
        var checked: Bool = true
    }

    enum ScanEvent {
        case progress(done: Int, total: Int, current: String)
        case found(DiscoveredHost)
        case done(count: Int)
    }

    private static let scanPorts = [HostServiceClient.defaultPort, 445, 135, 80, 443, 22]
    private static let portTimeoutMs = 300
    private static let maxParallel = 64

    private let scanQueue = DispatchQueue(label: "de.wolmanager.scan", attributes: .concurrent)
    private var cancelFlag = false
    private let cancelLock = NSLock()

    var isCancelled: Bool {
        cancelLock.lock(); defer { cancelLock.unlock() }
        return cancelFlag
    }

    func cancel() {
        cancelLock.lock(); cancelFlag = true; cancelLock.unlock()
    }

    /// Liefert das aktiven WLAN-IPv4-Netz (en0) via getifaddrs. Bewusst NUR en0:
    /// awdl (Bluetooth-AP), utun (VPN) und andere virtuelle Interfaces würden sonst
    /// als Dummy-Netze (172.*) in der Scanliste auftauchen. APIPA/Virtualisierungs-
    /// Bereiche (169.x/172.x) zusätzlich gefiltert — Parität zur Desktop-App.
    func activeInterfaces() -> [Iface] {
        var result: [Iface] = []
        var seen = Set<String>()
        for iface in InterfaceHelper.ipv4Interfaces() {
            guard iface.name == "en0" else { continue } // nur die WLAN-Verbindung
            guard Self.isScannable(iface.ip) else { continue }
            guard !seen.contains(iface.ip) else { continue }
            seen.insert(iface.ip)
            let prefix = InterfaceHelper.prefix(fromNetmask: iface.netmask)
            let pfx = (8...30).contains(prefix) ? prefix : 24
            result.append(Iface(name: iface.name, ip: iface.ip, prefix: pfx, dns: "", checked: true))
        }
        return result
    }

    /// Blendet Dummy-/Virtualisierungs-Bereiche aus (Parität zur Desktop-App,
    /// siehe wol_app/network_scanner.py is_real_interface): 169.x = APIPA/link-local,
    /// 172.x = VMware/Hyper-V/Docker/VPN-Adapter (per Nutzerentscheid komplett).
    static func isScannable(_ ip: String?) -> Bool {
        guard let ip, !ip.isEmpty else { return false }
        return !ip.hasPrefix("169.") && !ip.hasPrefix("172.")
    }

    /// Host-Adressen eines Netzes, ohne Netzwerk-/Broadcast-Adresse.
    private func hostAddresses(base: String, prefix: Int) -> [String] {
        let parts = base.split(separator: ".").compactMap { Int($0) }
        guard parts.count == 4 else { return [] }
        let network = (UInt32(parts[0]) << 24) | (UInt32(parts[1]) << 16) | (UInt32(parts[2]) << 8) | UInt32(parts[3])
        let mask: UInt32 = prefix >= 32 ? 0xFFFF_FFFF : ~(UInt32(0xFFFF_FFFF) >> prefix)
        let netStart = network & mask
        let hostCount = Int(UInt64(1) << UInt64(32 - prefix))
        if hostCount > 1024 { return [] } // sehr große Netze überspringen
        var list = [String]()
        for i in 1..<max(hostCount - 1, 1) {
            let addr = netStart + UInt32(i)
            list.append(MagicPacket.uIntToIPv4(addr))
        }
        return list
    }

    /// Führt den Sweep aus und ruft [onEvent] (Serialisierung intern) auf.
    /// completion kommt genau einmal, nach dem letzten Event.
    func scan(ifaces: [Iface], onEvent: @escaping (ScanEvent) -> Void, completion: @escaping () -> Void) {
        cancelLock.lock(); cancelFlag = false; cancelLock.unlock()

        let targets = ifaces.filter { $0.checked }
            .flatMap { hostAddresses(base: $0.ip, prefix: $0.prefix) }
        let unique = Array(Set(targets))
        let total = unique.count
        let doneCounter = AtomicCounter()
        let foundCounter = AtomicCounter()
        let eventLock = NSLock()

        // Feste Worker-Pool-Größe: alle Targets werden über einen atomaren Index
        // abgearbeitet. Vorher blockierten bis zu 254 GCD-Blöcke auf einem Semaphore,
        // was Threads band und den Scan zusätzlich ausbremste.
        let nextIndex = AtomicCounter()
        let workerCount = min(Self.maxParallel, max(unique.count, 1))
        let group = DispatchGroup()
        for _ in 0..<workerCount {
            group.enter()
            scanQueue.async {
                defer { group.leave() }
                while true {
                    let i = nextIndex.bump() - 1
                    if i >= unique.count || self.isCancelled { return }
                    let ip = unique[i]
                    let open = Self.scanPorts.filter { port in
                        if self.isCancelled { return false }
                        return HostServiceClient.tcpConnect(host: ip, port: port, timeoutMs: Self.portTimeoutMs)
                    }
                    // progress + found in EINEM kritischen Abschnitt emittieren —
                    // niemals zweimal lock() ohne unlock() (NSLock ist nicht rekursiv!).
                    eventLock.lock()
                    onEvent(.progress(done: doneCounter.bump(), total: total, current: ip))
                    if !open.isEmpty {
                        _ = foundCounter.bump()
                        onEvent(.found(DiscoveredHost(
                            hostname: Self.reverseDns(ip),
                            ipv4: ip,
                            mac: "",
                            openPorts: open,
                            known: open.contains(HostServiceClient.defaultPort))))
                    }
                    eventLock.unlock()
                }
            }
        }
        group.notify(queue: scanQueue) {
            onEvent(.done(count: foundCounter.value()))
            completion()
        }
    }

    private static func reverseDns(_ ip: String) -> String {
        var hostBuf = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        guard inet_pton(AF_INET, ip, &addr.sin_addr) == 1 else { return "Unbekannt" }
        let res = withUnsafePointer(to: &addr) { p -> Int32 in
            p.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                getnameinfo(sa, socklen_t(MemoryLayout<sockaddr_in>.size), &hostBuf, socklen_t(NI_MAXHOST), nil, 0, NI_NAMEREQD)
            }
        }
        if res != 0 { return "Unbekannt" }
        let name = String(cString: hostBuf)
        if name.isEmpty || name == ip { return "Unbekannt" }
        return String(name.split(separator: ".").first.map(String.init) ?? name)
    }
}

/* Kleiner atomarer Zähler (NSLock-basiert, iOS 16-kompatibel). */
final class AtomicCounter {
    private var v: Int = 0
    private let lock = NSLock()
    func bump() -> Int { lock.lock(); defer { lock.unlock() }; v += 1; return v }
    func value() -> Int { lock.lock(); defer { lock.unlock() }; return v }
}
