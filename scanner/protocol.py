"""Constantes e construção do pacote UDP de descoberta Ubiquiti.

Protocolo real: UDP broadcast na porta 10001 com probes TLV de 4 bytes.
Suporta v1 (0x01) e v2 (0x02) para máxima compatibilidade de firmware.
"""

import socket


DISCOVERY_PORT = 10001
BROADCAST_ADDRESS = "255.255.255.255"

# Probe v1: Header de 4 bytes (version=1, command=0, payload_length=0)
DISCOVERY_V1 = b"\x01\x00\x00\x00"

# Probe v2: Header de 4 bytes (version=2, command=8, payload_length=0)
DISCOVERY_V2 = b"\x02\x08\x00\x00"


def create_discovery_socket(local_address: str) -> socket.socket:
    """Cria um socket UDP vinculado à interface local selecionada."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((local_address, 0))
    return sock


def send_discovery(sock: socket.socket) -> None:
    """Envia probes v1 e v2 para maximizar compatibilidade com todos os firmwares."""
    sock.sendto(DISCOVERY_V1, (BROADCAST_ADDRESS, DISCOVERY_PORT))
    sock.sendto(DISCOVERY_V2, (BROADCAST_ADDRESS, DISCOVERY_PORT))
