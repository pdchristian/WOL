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


def get_dns_servers() -> list[str]:
    """Return the configured DNS server IPs from the local system.

    Parses ``ipconfig /all`` output, matching the existing locale-independent
    parsing pattern used for interfaces. psutil does not expose DNS servers,
    so ``ipconfig /all`` is the primary source.
    """
    dns_servers: list[str] = []
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
        for line in output.splitlines():
            lower = line.strip().lower()
            # DNS server labels across languages (English/German/French/Spanish)
            dns_keywords = (
                "dns servers", "dns-server", "dns-servers",
                "dns-server", "serveurs dns", "serveur dns",
                "servidores dns", "servidor dns",
            )
            if any(k in lower for k in dns_keywords) and ":" in line:
                value = line.split(":", 1)[1].strip()
                # Multiple servers may be separated by commas or spaces
                for token in value.replace(",", " ").split():
                    # Accept IPv4 servers, or IPv6 servers (strip %scope suffix)
                    candidate = token.split("%")[0]
                    if validate_ip(candidate):
                        dns_servers.append(candidate)
                    elif ":" in candidate:
                        try:
                            socket.inet_pton(socket.AF_INET6, candidate)
                            dns_servers.append(candidate)
                        except (OSError, ValueError):
                            continue
    except Exception:
        pass

    return dns_servers


def resolve_hostname(ip: str) -> str | None:
    """Try to resolve the hostname for an IP address.

    1. First uses ``socket.gethostbyaddr`` (system reverse-DNS lookup).
    2. Falls back to querying each configured DNS server directly via
       ``nslookup`` for the PTR record, so name resolution works even
       when the system resolver fails.
    """
    if not validate_ip(ip):
        return None

    # 1) System reverse-DNS lookup
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        if hostname:
            return hostname
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
                        return name
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
