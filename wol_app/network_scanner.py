"""Network Scanner - Discover active devices on the local subnet."""

import re
import socket
import struct
import subprocess
import platform
import threading
from typing import List, Dict, Optional


# Safety constants
MAX_CONCURRENT_THREADS = 16
MAX_SCAN_TIMEOUT = 2
MAX_SUBNET_SIZE = 256


def _validate_ip(ip: str) -> bool:
    """Validate IPv4 addresses with strict regex."""
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return bool(re.match(ipv4_pattern, ip))


def _validate_mac(mac: str) -> bool:
    """Validate MAC addresses with strict regex."""
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$'
    return bool(re.match(mac_pattern, mac))


def _run_subprocess_safe(command, timeout=5, **kwargs):
    """Safe execution of subprocess with strict limits."""
    try:
        # Set default security options
        safe_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'timeout': timeout,
            'shell': False,  # CRITICAL: shell=False prevents command injection
            **kwargs
        }
        result = subprocess.run(command, **safe_kwargs)
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out: {' '.join(command)}")
    except Exception as e:
        raise RuntimeError(f"Command failed: {' '.join(command)} - {str(e)}")


def get_local_interfaces() -> List[Dict]:
    """Get all local network interfaces with their IPv4 addresses and netmasks."""
    interfaces = []
    try:
        # Use ipconfig on Windows to get interface info
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = _run_subprocess_safe(
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
    if not _validate_ip(ip):
        return False
    if timeout > MAX_SCAN_TIMEOUT:
        timeout = MAX_SCAN_TIMEOUT
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = _run_subprocess_safe(
            ["ping", param, "1", "-w", str(timeout * 1000), ip],
            timeout=timeout + 1,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_hostname(ip: str) -> Optional[str]:
    """Try to resolve hostname for an IP address."""
    if not _validate_ip(ip):
        return None
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except Exception:
        return None


def get_ipv6_from_nd(mac: str) -> Optional[str]:
    """Look up IPv6 address for a MAC from the Neighbor Discovery cache."""
    if not mac or mac == "Unknown":
        return None
    if not _validate_mac(mac):
        return None
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = _run_subprocess_safe(
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


def get_mac_from_arp(ip: str) -> Optional[str]:
    """Get MAC address from ARP cache after pinging the host."""
    if not _validate_ip(ip):
        return None
    # First ping to ensure ARP entry exists
    try:
        param = "-n" if platform.system() == "Windows" else "-c"
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        _run_subprocess_safe(
            ["ping", param, "1", "-w", "1000", ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
            creationflags=creation_flags
        )
    except Exception:
        pass

    # Read ARP table
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = _run_subprocess_safe(
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


def find_interface_for_device(target_ip: str) -> Optional[Dict]:
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
                progress_callback=None) -> List[Dict]:
    """Scan a subnet for active hosts with safety limits."""
    if not _validate_ip(ip):
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


def scan_network(timeout: int = 1, progress_callback=None) -> List[Dict]:
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
