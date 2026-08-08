"""Network Scanner - Discover active devices on the local subnet."""

import platform
import socket
import struct
import subprocess
import threading

from wol_app.utils import run_subprocess_safe, validate_ip, validate_mac

# Safety constants
MAX_CONCURRENT_THREADS = 16
MAX_SCAN_TIMEOUT = 2
MAX_SUBNET_SIZE = 256


def get_local_interfaces() -> list[dict]:
    """Get all local network interfaces with their IPv4 addresses and netmasks.

    Preferred path: psutil (robust, locale-independent). Falls back to parsing
    ``ipconfig`` output when psutil is unavailable.
    """
    # 1) Try psutil first — it is locale-independent and cross-platform
    try:
        import psutil  # type: ignore
        interfaces = []
        for _name, addrs in psutil.net_if_addrs().items():
            netmask = None
            ip = None
            for addr in addrs:
                if addr.family == getattr(__import__("socket"), "AF_INET", None):
                    ip = addr.address
                    netmask = addr.netmask
                    break
            if ip and netmask and not ip.startswith("127."):
                interfaces.append({"ip": ip, "netmask": netmask})
        return interfaces
    except ImportError:
        pass
    except Exception:
        pass

    # 2) Fallback: parse ipconfig output (English/German/French/Spanish labels)
    interfaces = []
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = run_subprocess_safe(
            ["ipconfig"],
            timeout=10,
            creationflags=creation_flags,
            capture_output=True,
            text=True
        )
        lines = result.stdout.splitlines()
        current_ip = None
        current_mask = None

        for line in lines:
            line_stripped = line.strip()
            lower = line_stripped.lower()
            # IPv4 address labels across languages
            ipv4_keywords = ("ipv4", "adresse ipv4", "dirección ipv4", "adresse ip")
            if any(k in lower for k in ipv4_keywords) and ":" in line_stripped:
                current_ip = line_stripped.split(":")[-1].strip()
            # Subnet mask labels across languages
            mask_keywords = ("subnet mask", "subnetzmaske", "masque de sous-réseau",
                             "máscara de subred", "masque sous-réseau")
            if any(k in lower for k in mask_keywords) and ":" in line_stripped:
                current_mask = line_stripped.split(":")[-1].strip()

            if current_ip and current_mask:
                # Skip loopback
                if not current_ip.startswith("127."):
                    interfaces.append({
                        "ip": current_ip,
                        "netmask": current_mask,
                    })
                current_ip = None
                current_mask = None
    except Exception:
        pass

    return interfaces


def netmask_to_cidr(netmask: str) -> int:
    """Convert netmask to CIDR prefix length."""
    try:
        packed = struct.unpack("!I", socket.inet_aton(netmask))[0]
        return bin(packed).count("1")
    except Exception:
        return 24


def get_subnet_range(ip: str, netmask: str) -> list[str]:
    """Get all IP addresses in the subnet."""
    cidr = netmask_to_cidr(netmask)
    ip_int = struct.unpack("!I", socket.inet_aton(ip))[0]
    network = ip_int & (0xFFFFFFFF << (32 - cidr))

    if cidr >= 30:
        hosts = 2 ** (32 - cidr) - 1
    else:
        hosts = 2 ** (32 - cidr) - 2

    return [socket.inet_ntoa(struct.pack("!I", network + i)) for i in range(1, min(hosts + 1, 254))]


def ping_host(ip: str, timeout: int = 1) -> bool:
    """Ping a host and return True if reachable."""
    if not validate_ip(ip):
        return False
    if timeout > MAX_SCAN_TIMEOUT:
        timeout = MAX_SCAN_TIMEOUT
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = run_subprocess_safe(
            ["ping", param, "1", "-w", str(timeout * 1000), ip],
            timeout=timeout + 1,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def _parse_dns_servers_from_ipconfig() -> list[dict]:
    """Parse ``ipconfig /all`` into per-interface DNS server lists.

    Returns a list of dicts: ``{"ip": iface_ip, "dns_servers": [server, ...]}``.
    IPv4 servers are collected before IPv6 servers per interface so callers
    can prefer IPv4 when available.

    Handles multi-line DNS values (continuation lines) and the
    ``(Bevorzugt)``/``(Preferred)`` suffixes on IPv4 addresses.
    """
    entries: list[dict] = []
    current: dict | None = None
    collecting_dns = False
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = run_subprocess_safe(
            ["ipconfig", "/all"],
            timeout=10,
            creationflags=creation_flags,
            capture_output=True,
        )
        # Decode bytes manually to survive non-ASCII / locale-specific output
        output = result.stdout.decode("utf-8", errors="replace")

        # Locale-independent labels for interface sections
        section_keywords = ("ethernet adapter", "wireless lan adapter", "local area connection",
                            "drahtlose lan", "lan-verbindung", "ethernet-adapter",
                            "connexion au réseau", "adaptateur", "conexión de área local",
                            "adaptador", "connexion réseau")
        ipv4_keywords = ("ipv4", "adresse ipv4", "dirección ipv4", "adresse ip")
        dns_keywords = ("dns servers", "dns-server", "dns-servers",
                        "serveurs dns", "serveur dns",
                        "servidores dns", "servidor dns")

        lines = output.splitlines()
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Start a new interface section when a new adapter header appears
            if any(k in lower for k in section_keywords) and ":" in stripped:
                current = {"ip": "", "dns_servers": []}
                entries.append(current)
                collecting_dns = False
                continue

            if current is None:
                continue

            # Capture the interface IPv4 address (strip (Preferred) suffix)
            if any(k in lower for k in ipv4_keywords) and ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                value = value.split("(")[0].strip()
                if validate_ip(value):
                    current["ip"] = value
                collecting_dns = False
                continue

            # DNS servers may span multiple continuation lines
            if any(k in lower for k in dns_keywords) and ":" in stripped:
                collecting_dns = True
                value = stripped.split(":", 1)[1].strip()
                for token in value.replace(",", " ").split():
                    _append_dns_token(current, token)
                continue

            # Continuation lines of the DNS server list (indented, no label)
            if collecting_dns and stripped and ":" not in stripped:
                for token in stripped.replace(",", " ").split():
                    _append_dns_token(current, token)
                continue

            # Any other labelled line ends the DNS continuation
            if ":" in stripped:
                collecting_dns = False
    except Exception:
        pass

    return entries


def _append_dns_token(current: dict, token: str) -> None:
    """Append a single DNS server token (IPv4 or IPv6) to the current entry."""
    candidate = token.split("%")[0]
    if validate_ip(candidate):
        current["dns_servers"].append(candidate)
    elif ":" in candidate:
        try:
            socket.inet_pton(socket.AF_INET6, candidate)
            current["dns_servers"].append(candidate)
        except (OSError, ValueError):
            return


def get_dns_servers() -> list[str]:
    """Return the configured DNS server IPs from the local system.

    IPv4 servers are listed before IPv6 servers so callers naturally prefer
    IPv4 when both are configured.
    """
    servers: list[str] = []
    for entry in _parse_dns_servers_from_ipconfig():
        ipv4 = [s for s in entry["dns_servers"] if validate_ip(s)]
        ipv6 = [s for s in entry["dns_servers"] if ":" in s and not validate_ip(s)]
        servers.extend(ipv4)
        servers.extend(ipv6)
    return servers


def get_dns_servers_for_interface(iface_ip: str) -> list[str]:
    """Return the DNS servers configured for the interface with *iface_ip*.

    IPv4 servers are preferred and listed first; IPv6 servers follow only if
    no IPv4 server is available for that interface.
    """
    for entry in _parse_dns_servers_from_ipconfig():
        if entry["ip"] == iface_ip:
            ipv4 = [s for s in entry["dns_servers"] if validate_ip(s)]
            ipv6 = [s for s in entry["dns_servers"] if ":" in s and not validate_ip(s)]
            return ipv4 + ipv6
    return []


def _strip_domain(name: str | None) -> str | None:
    """Strip the domain part from a resolved hostname (FQDN).

    Returns only the first label before the first dot (e.g.
    ``pc.example.local`` -> ``pc``). IP addresses are returned unchanged
    as a safety guard, and empty/None inputs are returned as-is.
    """
    if not name:
        return name
    if validate_ip(name):
        return name
    return name.split(".", 1)[0]


def resolve_hostname(ip: str) -> str | None:
    """Try to resolve the hostname for an IP address.

    1. First uses ``socket.gethostbyaddr`` (system reverse-DNS lookup).
    2. Falls back to querying each configured DNS server directly via
       ``nslookup`` for the PTR record, so name resolution works even
       when the system resolver fails.

    The resolved FQDN is reduced to the bare hostname (without domain)
    via :func:`_strip_domain`.
    """
    if not validate_ip(ip):
        return None

    # 1) System reverse-DNS lookup
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        if hostname:
            return _strip_domain(hostname)
    except Exception:
        pass

    # 2) Query each configured DNS server directly via nslookup
    for dns_server in get_dns_servers():
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = run_subprocess_safe(
                ["nslookup", ip, dns_server],
                timeout=5,
                creationflags=creation_flags,
                capture_output=True,
                text=True,
            )
            output = result.stdout + "\n" + result.stderr
            for line in output.splitlines():
                lower = line.strip().lower()
                # nslookup prints the resolved name as: "Name:   hostname"
                if lower.startswith("name:") and ":" in line:
                    name = line.split(":", 1)[1].strip()
                    if name and name.lower() != ip.lower():
                        return _strip_domain(name)
        except Exception:
            continue

    return None


def get_ipv6_from_nd(mac: str) -> str | None:
    """Look up IPv6 address for a MAC from the Neighbor Discovery cache."""
    if not mac or mac == "Unknown":
        return None
    if not validate_mac(mac):
        return None
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = run_subprocess_safe(
            ["netsh", "interface", "ipv6", "show", "neighbors"],
            timeout=5,
            creationflags=creation_flags,
            capture_output=True,
            text=True
        )
        # Normalize MAC: remove all separators and uppercase for comparison
        mac_normalized = mac.replace(":", "").replace("-", "").upper()
        for line in result.stdout.splitlines():
            if mac_normalized in line.upper().replace(":", "").replace("-", ""):
                parts = line.split()
                for part in parts:
                    # IPv6 addresses contain colons and hex digits
                    if ":" in part and len(part) >= 8:
                        try:
                            socket.inet_pton(socket.AF_INET6, part)
                            return part
                        except (OSError, ValueError):
                            continue
    except Exception:
        pass
    return None


def get_mac_from_arp(ip: str) -> str | None:
    """Get MAC address from ARP cache after pinging the host."""
    if not validate_ip(ip):
        return None
    # First ping to ensure ARP entry exists
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        run_subprocess_safe(
            ["ping", param, "1", "-w", "1000", ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
            creationflags=creation_flags
        )
    except Exception:
        pass

    # Read ARP table
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = run_subprocess_safe(
            ["arp", "-a"],
            timeout=5,
            creationflags=creation_flags,
            capture_output=True,
            text=True
        )
        for line in result.stdout.splitlines():
            if ip.lower() in line.lower():
                # Extract MAC address (format: xx-xx-xx-xx-xx-xx)
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.lower() == ip.lower():
                        if i + 1 < len(parts):
                            mac = parts[i + 1].replace("-", ":")
                            return mac.upper()
    except Exception:
        pass

    return None


def calculate_broadcast_address(ip: str, netmask: str) -> str:
    """Calculate the directed broadcast address for a subnet."""
    try:
        ip_int = struct.unpack("!I", socket.inet_aton(ip))[0]
        mask_int = struct.unpack("!I", socket.inet_aton(netmask))[0]
        network = ip_int & mask_int
        broadcast = network | (mask_int ^ 0xFFFFFFFF)
        return socket.inet_ntoa(struct.pack("!I", broadcast))
    except Exception:
        return "255.255.255.255"


def ip_in_subnet(ip: str, subnet_ip: str, netmask: str) -> bool:
    """Check if an IP address belongs to a given subnet."""
    try:
        ip_int = struct.unpack("!I", socket.inet_aton(ip))[0]
        subnet_int = struct.unpack("!I", socket.inet_aton(subnet_ip))[0]
        mask_int = struct.unpack("!I", socket.inet_aton(netmask))[0]
        return (ip_int & mask_int) == (subnet_int & mask_int)
    except Exception:
        return False


def find_interface_for_device(target_ip: str) -> dict | None:
    """
    Find the local network interface that can reach the target IP.
    Returns dict with 'local_ip', 'netmask', and 'broadcast_ip' or None if no match.
    """
    if not target_ip:
        return None

    interfaces = get_local_interfaces()
    for iface in interfaces:
        if ip_in_subnet(target_ip, iface["ip"], iface["netmask"]):
            broadcast = calculate_broadcast_address(iface["ip"], iface["netmask"])
            return {
                "local_ip": iface["ip"],
                "netmask": iface["netmask"],
                "broadcast_ip": broadcast,
            }
    return None


def scan_subnet(ip: str, netmask: str, timeout: int = 1,
                progress_callback=None) -> list[dict]:
    """Scan a subnet for active hosts with safety limits."""
    if not validate_ip(ip):
        return []
    if timeout > MAX_SCAN_TIMEOUT:
        timeout = MAX_SCAN_TIMEOUT
    try:
        hosts = get_subnet_range(ip, netmask)
        # Limit the number of hosts to scan
        if len(hosts) > MAX_SUBNET_SIZE:
            hosts = hosts[:MAX_SUBNET_SIZE]
    except Exception:
        return []
    
    results = []

    def scan_host(target_ip: str):
        if ping_host(target_ip, timeout):
            hostname = resolve_hostname(target_ip)
            mac = get_mac_from_arp(target_ip)
            ipv6_addr = get_ipv6_from_nd(mac) or ""
            results.append({
                "hostname": hostname or "Unknown",
                "ipv4": target_ip,
                "ipv6": ipv6_addr,
                "mac": mac or "Unknown",
            })

    threads = []
    # Limit concurrent threads to avoid overwhelming the network
    max_threads = min(MAX_CONCURRENT_THREADS, len(hosts))

    for i, host_ip in enumerate(hosts):
        if progress_callback:
            progress_callback(i + 1, len(hosts), host_ip)
        thread = threading.Thread(target=scan_host, args=(host_ip,))
        threads.append(thread)
        if len(threads) >= max_threads or i == len(hosts) - 1:
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=timeout + 3)
            threads = []

    return results


def scan_network(timeout: int = 1, progress_callback=None) -> list[dict]:
    """Scan all local subnets for active hosts."""
    if timeout > MAX_SCAN_TIMEOUT:
        timeout = MAX_SCAN_TIMEOUT
    interfaces = get_local_interfaces()
    all_results = []
    seen_ips = set()

    for iface in interfaces:
        if progress_callback:
            progress_callback(None, None, f"Scanne Subnetz {iface['ip']}...")
        hosts = scan_subnet(iface["ip"], iface["netmask"], timeout,
                           progress_callback)
        for host in hosts:
            if host["ipv4"] not in seen_ips:
                seen_ips.add(host["ipv4"])
                all_results.append(host)

    return all_results
