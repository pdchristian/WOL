"""Active network-profile detection (private vs. public).

Used to keep privileged host-service operations (shutdown / reboot /
run_batch) away from untrusted networks: on a public profile the app
switches to read-only mode (status + metrics keep working) unless the
user explicitly allows privileged commands in public networks.

- Windows: Network List Manager (NLM) via COM — the same source the
  Windows Firewall profiles are derived from (Domain/Private/Public).
- Linux: firewalld zone of active connections (``public`` ⇒ public).
- macOS / unknown: treated as private — the *host service* enforces the
  gate independently (defense in depth), the client check is a UX aid.

Results are cached for a few seconds (NLM calls are comparatively slow
and the dashboard may ask repeatedly).
"""

import os
import subprocess
import sys
import time

# Network categories (NLM NLM_NETWORK_CATEGORY).
CATEGORY_PUBLIC = 0
CATEGORY_PRIVATE = 1
CATEGORY_DOMAIN = 2

# Unknown: no connected network could be classified.
CATEGORY_UNKNOWN = -1

# How long a detection result is reused (seconds).
_CACHE_TTL_SECONDS = 10.0

_cache: tuple[float, int] = (0.0, CATEGORY_UNKNOWN)


def _category_from_nlm() -> int:
    """Category of the connected Windows network via the Network List Manager.

    Uses the CLSID directly — the ProgID ``NetworkListManager`` is not
    always registered. Early binding (gencache) exposes the collection
    items as ``GetName``/``GetCategory`` *methods*, late binding as
    properties; both shapes are handled.
    """
    import pythoncom  # noqa: F401  (CoInitialize via win32com on import)
    from win32com.client import gencache

    nlm = gencache.EnsureDispatch("{DCB00C01-570F-4A9B-8D69-199FDBA5723B}")
    enum = nlm.GetNetworks(3)  # NLM_ENUM_NETWORK_ALL

    def _attr(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    while True:
        item = enum.Next(1)
        # Next() returns (network, fetched_count) — empty tuple ends the
        # enumeration; a (None, 0) result must not loop forever.
        if not item:
            return CATEGORY_UNKNOWN
        net, fetched = (item if isinstance(item, tuple) else (item, 1))
        if net is None or not fetched:
            return CATEGORY_UNKNOWN
        try:
            if _attr(net, "IsConnected"):
                return int(_attr(net, "GetCategory"))
        except Exception:
            continue
    return CATEGORY_UNKNOWN


def _category_from_firewalld() -> int:
    """Linux: zone of active connections; "public" (or unknown) ⇒ public."""
    try:
        result = subprocess.run(
            ["firewall-cmd", "--state"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0 or result.stdout.strip() != "running":
            return CATEGORY_UNKNOWN  # firewalld absent/inactive -> unknown
        result = subprocess.run(
            ["firewall-cmd", "--active-zones"],
            capture_output=True, text=True, timeout=3,
        )
        # "active zones: public FedoraWorkstation" — any non-public zone
        # counts as trusted, mirroring how firewalld itself unions zones.
        parts = result.stdout.replace("active zones:", " ").split()
        if not parts:
            return CATEGORY_UNKNOWN
        if all(p.strip().lower() == "public" for p in parts):
            return CATEGORY_PUBLIC
        return CATEGORY_PRIVATE
    except (OSError, subprocess.SubprocessError):
        return CATEGORY_UNKNOWN


def get_network_category() -> int:
    """Category of the currently connected network (cached, see constants).

    Returns one of CATEGORY_PUBLIC / CATEGORY_PRIVATE / CATEGORY_DOMAIN /
    CATEGORY_UNKNOWN. Never raises: detection failures map to UNKNOWN,
    which callers treat as private (the host service gates independently).

    ``WOL_FORCE_NETWORK=public|private|domain|unknown`` overrides detection
    (tests / demos).
    """
    global _cache
    forced = os.environ.get("WOL_FORCE_NETWORK", "").strip().lower()
    if forced in ("public", "private", "domain", "unknown"):
        return {
            "public": CATEGORY_PUBLIC,
            "private": CATEGORY_PRIVATE,
            "domain": CATEGORY_DOMAIN,
        }.get(forced, CATEGORY_UNKNOWN)

    now = time.monotonic()
    if now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]

    category = CATEGORY_UNKNOWN
    try:
        if sys.platform == "win32":
            category = _category_from_nlm()
        elif sys.platform.startswith("linux"):
            category = _category_from_firewalld()
    except Exception:
        category = CATEGORY_UNKNOWN

    _cache = (now, category)
    return category


def is_public_network() -> bool:
    """True when the connected network is classified as PUBLIC.

    Unknown/undetectable networks count as private (the service-side gate
    is the authoritative check; the client must not lock the user out of
    a working home LAN just because detection failed).
    """
    return get_network_category() == CATEGORY_PUBLIC


def is_privileged_command_blocked(allow_override: bool = False) -> bool:
    """Whether privileged host commands must be blocked on the client now.

    True only on an explicitly PUBLIC network while the per-app override
    (settings → allow privileged commands on public networks) is off.
    status/metrics are never covered — only shutdown/reboot/run_batch.
    """
    if allow_override:
        return False
    return is_public_network()


def reset_cache_for_tests() -> None:
    """Drop the cached category (used by tests)."""
    global _cache
    _cache = (0.0, CATEGORY_UNKNOWN)


def describe_network() -> str:
    """Short human-readable label for the current network (status displays)."""
    category = get_network_category()
    if category == CATEGORY_PUBLIC:
        return "public"
    if category == CATEGORY_PRIVATE:
        return "private"
    if category == CATEGORY_DOMAIN:
        return "domain"
    return "unknown"
