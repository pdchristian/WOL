"""Shared logic for the "apply this secret to the other devices" prompts.

When the user saves a device with a non-empty username and password, the UI
asks whether the password should also be applied to every other device that
uses the same username. The dashboard API key works the same way, but there
is no username to scope it by — that offer covers *all* other devices. The
candidate detection lives here so the dialogs and the tests share one
implementation.
"""

from typing import Any


def collect_share_targets(config: Any, username: str, password: str,
                          exclude_id: str | None = None) -> list:
    """Devices that share ``username`` but do not already have ``password``.

    Returns an empty list when username or password is empty (nothing to
    offer) or when every matching device already stores the same password
    (no change would happen, so the confirmation popup would be noise).
    """
    if not (username or "").strip() or not password:
        return []
    targets = []
    for dev in config.get_devices_by_username(username, exclude_id=exclude_id):
        if (dev.get("password") or "") != password:
            targets.append(dev)
    return targets


def apply_password(config: Any, targets: list, password: str) -> int:
    """Apply ``password`` to every device in ``targets``. Returns the count."""
    applied = 0
    for dev in targets:
        if config.update_device(dev["id"], password=password):
            applied += 1
    return applied


def collect_api_key_share_targets(config: Any, api_key: str,
                                  exclude_id: str | None = None) -> list:
    """Every other device whose API key differs from ``api_key``.

    An API key belongs to the inference server, not to a login, so the offer
    is not scoped by username — it covers all other devices. Returns an empty
    list when the key is empty (nothing to offer) or when every other device
    already stores the same key (the confirmation popup would be noise).
    """
    if not (api_key or "").strip():
        return []
    targets = []
    for dev in config.get_devices():
        if dev.get("id") == exclude_id:
            continue
        if (dev.get("api_key") or "") != api_key:
            targets.append(dev)
    return targets


def apply_api_key(config: Any, targets: list, api_key: str) -> int:
    """Apply ``api_key`` to every device in ``targets``. Returns the count."""
    applied = 0
    for dev in targets:
        if config.set_device_api_key(dev["id"], api_key):
            applied += 1
    return applied
