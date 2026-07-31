"""Constantes e construção do pacote UDP de descoberta Ubiquiti."""

import socket
from typing import BinaryIO


DISCOVERY_PORT = 10001
BROADCAST_ADDRESS = "255.255.255.255"
# Cabeçalho usado pelo Ubiquiti Discovery Protocol (UDP/10001).
DISCOVERY_REQUEST = b"\x01\x00\x00\x00\x00\x00\x00\x00"


def create_discovery_socket(local_address: str) -> socket.socket:
    """Cria um socket UDP vinculado à interface local selecionada."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((local_address, 0))
    return sock


def send_discovery(sock: socket.socket) -> None:
    """Envia uma solicitação somente de descoberta, sem autenticação."""
    sock.sendto(DISCOVERY_REQUEST, (BROADCAST_ADDRESS, DISCOVERY_PORT))
