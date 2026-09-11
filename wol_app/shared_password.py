"""Shared logic for the "apply password to devices with the same username" feature.

When the user saves a device with a non-empty username and password, the UI
asks whether the password should also be applied to every other device that
uses the same username. The candidate detection lives here so the modern
dialog, the classic dialog and the tests share one implementation.
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
