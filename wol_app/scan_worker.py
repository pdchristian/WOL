"""Background worker for network scanning (shared by classic and modern UI)."""

from PyQt6.QtCore import QObject, pyqtSignal

from wol_app.network_scanner import scan_subnet
from wol_app.translations import Translations


class ScanWorker(QObject):
    """Scan the selected interfaces in a worker thread.

    Move to a :class:`QThread` and connect :attr:`progress` /
    :attr:`finished` before starting the thread.
    """

    progress = pyqtSignal(str, int, int)  # message, current, total
    finished = pyqtSignal(list)

    def __init__(self, interfaces: list, timeout: int = 1) -> None:
        super().__init__()
        self.interfaces = interfaces
        self.timeout: int = timeout

    def run(self) -> None:
        all_results = []
        seen_ips = set()

        for iface in self.interfaces:
            iface_msg: str = Translations.tr("scan.scanning_subnet", ip=iface["ip"])
            self.progress.emit(iface_msg, 0, 0)

            try:
                def on_progress(current, total, msg) -> None:
                    self.progress.emit(msg, current, total)

                hosts = scan_subnet(
                    iface["ip"], iface["netmask"],
                    self.timeout, progress_callback=on_progress
                )
                for host in hosts:
                    if host["ipv4"] not in seen_ips:
                        seen_ips.add(host["ipv4"])
                        all_results.append(host)
            except Exception as e:
                self.progress.emit(
                    Translations.tr("scan.error_interface", ip=iface["ip"], error=str(e)), 0, 0
                )

        self.progress.emit(
            Translations.tr("scan.total_found", count=len(all_results)), 0, 0
        )
        self.finished.emit(all_results)
