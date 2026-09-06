# Ubuntu VM Test Guide (Phase 5)

This guide verifies the `.deb` package on a real Ubuntu VM/host.
The repository is at `c:\Python\WOL` (Windows). The VM is the only place
where the package is built and installed.

## 1. Prepare the VM

- Ubuntu 22.04 or 24.04 Desktop (GNOME).
- Get the code onto the VM (git clone or rsync), then `cd` into it:

```bash
git clone <your-repo-url> wol && cd wol   # or rsync/scp the working tree
git checkout Ubuntu-Version
```

## 2. Build the .deb

```bash
bash packaging/build_deb.sh
ls -l dist/wake-on-lan-manager_*.deb
```

Expected: `dist/wake-on-lan-manager_2.2.1-1_all.deb`.

## 3. Install

```bash
sudo apt install ./dist/wake-on-lan-manager_2.2.1-1_all.deb
```

## 4. Smoke checks

| Area | Check |
|---|---|
| App start | GNOME app grid → "Wake-on-LAN Manager" opens the Modern UI (no classic window). |
| Devices | Add/edit/remove a device, card + list view, sort drop-down. |
| WOL | Wake a device individually and "wake all" (parallel). |
| Scanner | Network scan discovers devices (`ip`/`ip neigh`). |
| Dashboard | 📊 tile → live CPU/RAM/GPU/VRAM gauges, 2–10 s polling. |
| Watched procs | Dashboard service chips show watched processes; `name:port` shows "starting"→"running". |
| Remote shutdown | Device with host-service creds → shutdown/reboot confirm dialog fires. |
| Remote desktop | xfreerdp connects; wrong password → fast-exit prompt "reconnect without password". |
| Logs | Activity log shows entries; CSV export works. |
| Language | Switch en/de/fr/es in settings; no missing strings. |
| Update check | About/Update screen links to the GitHub release page. |

## 5. Host service checks

```bash
wol-host-service --status          # reports running/disabled
systemctl status wol-host-service  # active (enabled by postinst)
ss -ltnp | grep 8765               # TCP 8765 listening
wol-host-service --enable-batch    # opt-in for remote scripts
```

Test from another machine (Windows app or `nc`):

```bash
printf '{"command":"status"}\n' | nc <vm-ip> 8765   # -> {"status":"ok",...}
```

## 6. Test suite on Linux

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q
```

All tests must pass (headless/offscreen).

## 7. Release

- Tag `v2.2.1`, build the `.deb`, attach it to the GitHub Release.
- Install command in the release notes:
  `sudo apt install ./wake-on-lan-manager_2.2.1-1_all.deb`
