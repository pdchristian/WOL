"""Platform detection for LAN devices (Windows / macOS / Ubuntu-Linux).

Two independent sources feed the ``os`` value shown in the scan dialog and
stored per device:

* **Authoritative** — the WOL Host Service reports its own platform in the
  unauthenticated ``status`` response (protocol v8, see
  :func:`wol_app.host_service_client.get_host_os`).
* **Passive fingerprint** — used when no (or an older) host service answers:
  the ICMP reply TTL, an SMB-port probe, the reverse-DNS name shape and the
  MAC vendor prefix. Heuristic by nature: Windows and macOS separate well,
  while "Ubuntu" and "some other Linux" cannot be told apart remotely.

All network probes are bounded and fail closed — an unreachable or silent
host simply yields fewer signals instead of raising.
"""

import platform
import re
import socket
import subprocess

from wol_app.utils import (
    OS_LINUX,
    OS_MACOS,
    OS_WINDOWS,
    build_ping_args,
    run_subprocess_safe,
    validate_ip,
)

# Confidence levels for a fingerprint result.
CONFIDENCE_HIGH = "high"      # reported by the host service itself
CONFIDENCE_MEDIUM = "medium"  # TTL plus at least one corroborating signal
CONFIDENCE_LOW = "low"        # a single weak signal (OUI / name only)

# Default TTLs of the stacks we care about. Linux >= 6.x ships 64 (older
# kernels 64 as well), Windows 128, network gear 255. macOS also uses 64,
# which is why TTL alone never separates macOS from Linux.
DEFAULT_TTL_WINDOWS = 128
DEFAULT_TTL_UNIX = 64
DEFAULT_TTL_NETWORK_GEAR = 255

# Seconds for the auxiliary TCP probes. A closed port answers instantly on a
# LAN; only filtered ones cost the full timeout.
PROBE_TIMEOUT_S = 0.4
# TCP port of the WOL Host Service (same default as host_service_client).
HOST_SERVICE_PORT = 8765
# SMB/TCP — Windows file sharing, open on virtually every desktop Windows.
SMB_PORT = 445

# TTL token in the localized ``ping`` output. Windows writes ``TTL=128``,
# Linux/macOS ``ttl=64``; matching is case-insensitive and tolerant of the
# comma/space separated surroundings (see the 2.2.3 cross-platform fix).
_TTL_RE = re.compile(r"ttl\s*[:=]\s*(\d{1,3})", re.IGNORECASE)

# MAC vendor prefixes that are strong platform hints. Only vendors whose
# interfaces ship essentially preloaded with one OS are listed, so a hit is
# meaningful without a full OUI database. Keys are the first 24 bits of the
# MAC, uppercase, without separators.
OUI_HINTS = {
    "B8:C7:5D": OS_MACOS,  # Apple
    "F0:18:98": OS_MACOS,  # Apple
    "88:E9:FE": OS_MACOS,  # Apple
    "A4:83:E7": OS_MACOS,  # Apple
    "3C:22:FB": OS_MACOS,  # Apple
    "00:15:5D": OS_WINDOWS,  # Microsoft (Surface / Hyper-V adapters)
    "00:0D:3A": OS_WINDOWS,  # Microsoft
}


# Host-name patterns that identify an Apple machine. The TTL cannot separate
# macOS from Linux, so a product name in the (reverse) DNS name is what breaks
# that tie. Deliberately specific: a bare "mac" would also match "mac-server"
# or "macintosh-support" and pull Windows/Linux boxes into macOS.
MACOS_NAME_HINTS = (
    "macbook", "imac", "macmini", "mac-mini", "macpro", "mac-pro",
    "macstudio", "mac-studio",
)


def ttl_from_ping_output(text: str) -> int | None:
    """Extract the reply TTL from ``ping`` output ("" or no token -> None)."""
    if not text:
        return None
    match = _TTL_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:  # pragma: no cover - regex guarantees digits
        return None


def oui_hint(mac: str) -> str:
    """Return the platform implied by the MAC vendor prefix ("" = unknown)."""
    if not mac:
        return ""
    compact = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(compact) < 6:
        return ""
    prefix = ":".join(compact[i:i + 2] for i in range(0, 6, 2))
    return OUI_HINTS.get(prefix, "")


def probe_tcp_port(ip: str, port: int, timeout: float = PROBE_TIMEOUT_S) -> bool:
    """True when a TCP connect to *ip*:*port* succeeds. Never raises."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def probe_host_service_os(
    ip: str,
    port: int = HOST_SERVICE_PORT,
    timeout: float = PROBE_TIMEOUT_S,
) -> str:
    """Ask the WOL Host Service for its platform ("" when absent/old).

    Imported lazily: the client opens sockets, and unit tests for this
    module should not have to stub that out.
    """
    try:
        from wol_app.host_service_client import get_host_os

        return get_host_os(ip, port=port, timeout=timeout) or ""
    except Exception:
        return ""


def get_ping_ttl(ip: str, timeout: int = 1) -> int | None:
    """Ping *ip* once and return the reply TTL (None when unreachable).

    Uses the same platform-correct argv as the reachability probe, but keeps
    the output so the TTL token can be read out.
    """
    if not validate_ip(ip):
        return None
    creation_flags = (
        subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    )
    try:
        result = run_subprocess_safe(
            build_ping_args(ip, 1, timeout * 1000),
            timeout=timeout + 1,
            creationflags=creation_flags,
        )
    except (TimeoutError, OSError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or b"") + (result.stderr or b"")
    return ttl_from_ping_output(out.decode("utf-8", errors="replace"))


def score_platforms(
    ttl: int | None = None,
    smb_open: bool | None = None,
    hostname: str = "",
    mac: str = "",
) -> dict[str, int]:
    """Weighted votes per platform from the available fingerprint signals.

    Only signals that were actually observed contribute, so callers can pass
    whatever they managed to collect.
    """
    scores = {OS_WINDOWS: 0, OS_MACOS: 0, OS_LINUX: 0}

    if ttl is not None:
        if ttl == DEFAULT_TTL_WINDOWS:
            scores[OS_WINDOWS] += 3
        elif ttl == DEFAULT_TTL_UNIX:
            scores[OS_MACOS] += 2
            scores[OS_LINUX] += 2
        elif ttl == DEFAULT_TTL_NETWORK_GEAR:
            # Router / switch / printer stack — not one of our targets.
            pass
        else:
            scores[OS_LINUX] += 1

    if smb_open:
        scores[OS_WINDOWS] += 2

    name = (hostname or "").lower()
    if name.endswith(".local"):
        # Bonjour-style reverse name, characteristic for macOS.
        scores[OS_MACOS] += 2
    if any(pattern in name for pattern in MACOS_NAME_HINTS):
        # Apple product names in the (reverse) DNS name — the TTL cannot
        # separate macOS from Linux, so this is what breaks that tie.
        scores[OS_MACOS] += 2

    hint = oui_hint(mac)
    if hint:
        scores[hint] += 2

    return scores


def infer_os(
    ttl: int | None = None,
    smb_open: bool | None = None,
    hostname: str = "",
    mac: str = "",
) -> tuple[str, str]:
    """Best-effort ``(os, confidence)`` from the passive signals.

    ``("", "")`` means "nothing usable was observed" — better than guessing.
    """
    scores = score_platforms(ttl=ttl, smb_open=smb_open, hostname=hostname, mac=mac)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best, best_score = ranked[0]
    runner_up = ranked[1][1]

    if best_score == 0:
        return "", ""

    if best_score >= 4 and runner_up == 0:
        confidence = CONFIDENCE_MEDIUM
    else:
        confidence = CONFIDENCE_LOW
    return best, confidence


def fingerprint_host(
    ip: str,
    hostname: str = "",
    mac: str = "",
    ping_timeout: int = 1,
    probe_port: bool = True,
) -> tuple[str, str, str]:
    """Detect the platform of *ip*.

    Returns ``(os, confidence, source)`` with ``source`` one of
    ``"service"`` (authoritative), ``"fingerprint"`` or ``""`` (unknown).
    The host service is asked first; a definitive answer skips the heuristics.
    """
    service_os = probe_host_service_os(ip)
    if service_os:
        return service_os, CONFIDENCE_HIGH, "service"

    ttl = get_ping_ttl(ip, timeout=ping_timeout)
    smb_open = probe_tcp_port(ip, SMB_PORT) if probe_port else None
    os_id, confidence = infer_os(ttl=ttl, smb_open=smb_open,
                                 hostname=hostname, mac=mac)
    return os_id, confidence, ("fingerprint" if os_id else "")
