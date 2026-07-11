"""Network Scanner - Discover active devices on the local subnet."""

import socket
import struct
import subprocess
import platform
import threading
from typing import List, Dict, Optional


def get_local_interfaces() -> List[Dict]:
    """Get all local network interfaces with their IPv4 addresses and netmasks."""
    interfaces = []
    try:
        # Use ipconfig on Windows to get interface info
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True, timeout=10,
            creationflags=creation_flags
        )
        lines = result.stdout.splitlines()
        current_ip = None
        current_mask = None

        for line in lines:
            line_stripped = line.strip()
            # Support both English ("IPv4 Address") and German ("IPv4-Adresse")
            if "ipv4" in line_stripped.lower() and ":" in line_stripped:
                current_ip = line_stripped.split(":")[-1].strip()
            # Support both English ("Subnet Mask") and German ("Subnetzmaske")
            if ("subnet mask" in line_stripped.lower() or "subnetzmaske" in line_stripped.lower()) and ":" in line_stripped:
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


def get_subnet_range(ip: str, netmask: str) -> List[str]:
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
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(
            ["ping", param, "1", "-w", str(timeout * 1000), ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout + 1,
            creationflags=creation_flags
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_hostname(ip: str) -> Optional[str]:
    """Try to resolve hostname for an IP address."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except Exception:
        return None


def get_ipv6_from_nd(mac: str) -> Optional[str]:
    """Look up IPv6 address for a MAC from the Neighbor Discovery cache."""
    if not mac or mac == "Unknown":
        return None
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(
            ["netsh", "interface", "ipv6", "show", "neighbors"],
            capture_output=True, text=True, timeout=5,
            creationflags=creation_flags
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


def get_mac_from_arp(ip: str) -> Optional[str]:
    """Get MAC address from ARP cache after pinging the host."""
    # First ping to ensure ARP entry exists
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        subprocess.run(
            ["ping", param, "1", "-w", "1000", ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
            creationflags=creation_flags
        )
    except Exception:
        pass

    # Read ARP table
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True, text=True, timeout=5,
            creationflags=creation_flags
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


def scan_subnet(ip: str, netmask: str, timeout: int = 1,
                progress_callback=None) -> List[Dict]:
    """Scan a subnet for active hosts."""
    hosts = get_subnet_range(ip, netmask)
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
    max_threads = min(32, len(hosts))

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


def scan_network(timeout: int = 1, progress_callback=None) -> List[Dict]:
    """Scan all local subnets for active hosts."""
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
