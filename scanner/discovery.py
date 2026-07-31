"""Execução assíncrona do broadcast e coleta de respostas."""

import socket
import threading
import time
from collections.abc import Callable

from .models import NetworkInterface, UbiquitiDevice
from .network import get_active_interfaces
from .parser import parse_response
from .protocol import DISCOVERY_PORT, create_discovery_socket, send_discovery


class UbiquitiDiscovery:
    """Scanner cancelável que executa uma rodada por thread."""

    def __init__(self, timeout: float = 2.5):
        self.timeout = timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def interfaces() -> list[NetworkInterface]:
        return get_active_interfaces()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def stop(self) -> None:
        self._stop.set()

    def scan(self, interface: NetworkInterface, on_complete: Callable[[list[UbiquitiDevice], float], None], on_error: Callable[[str], None] | None = None) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(interface, on_complete, on_error), daemon=True)
        self._thread.start()

    def _run(self, interface: NetworkInterface, on_complete, on_error) -> None:
        started = time.perf_counter()
        devices: dict[str, UbiquitiDevice] = {}
        sock: socket.socket | None = None
        try:
            sock = create_discovery_socket(interface.address)
            sock.settimeout(0.15)
            send_discovery(sock)
            deadline = time.perf_counter() + self.timeout
            while not self._stop.is_set() and time.perf_counter() < deadline:
                try:
                    payload, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                device = parse_response(payload, address, (time.perf_counter() - started) * 1000)
                if device:
                    devices[device.key] = device
        except OSError as exc:
            if on_error:
                on_error(str(exc))
        finally:
            if sock:
                sock.close()
            on_complete(sorted(devices.values(), key=lambda item: tuple(int(part) for part in item.ip.split("."))), time.perf_counter() - started)
