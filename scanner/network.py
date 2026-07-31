"""Detecção de interfaces IPv4 ativas sem chamar executáveis externos."""

import ipaddress
import socket

import psutil

from .models import NetworkInterface


def get_active_interfaces() -> list[NetworkInterface]:
    """Retorna interfaces UP com IPv4 unicast, sem loopback e sem VPNs comuns."""
    ignored = ("loopback", "tailscale", "zerotier", "vmware", "virtualbox", "docker", "wsl")
    stats = psutil.net_if_stats()
    result: list[NetworkInterface] = []
    for name, addresses in psutil.net_if_addrs().items():
        stat = stats.get(name)
        if not stat or not stat.isup or name.lower().startswith(ignored):
            continue
        for address in addresses:
            if address.family != socket.AF_INET or not address.address:
                continue
            try:
                if ipaddress.ip_address(address.address).is_loopback:
                    continue
            except ValueError:
                continue
            result.append(NetworkInterface(name, address.address, address.netmask or ""))
            break
    return result
