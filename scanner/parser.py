"""Parser TLV binário para respostas do Ubiquiti Discovery Protocol (UDP/10001).

Formato do pacote de resposta:
  Header (4 bytes): [version:u8] [command:u8] [payload_length:u16be]
  Payload: sequência contígua de blocos TLV
    [type:u8] [length:u16be] [value: N bytes]

TLV Field IDs documentados:
  0x01 = Hardware MAC (6 bytes)
  0x02 = IP Info (6 bytes MAC + 4 bytes IPv4)
  0x03 = Firmware Version (string)
  0x0A = Uptime (uint32 big-endian)
  0x0B = Hostname / System Name (string)
  0x0C = Short Model / Platform (string)
  0x0D = ESSID (string)
  0x14 = Model Name (string)
  0x15 = Model Name alternativo (string)
  0x17 = Is Default State (uint8 boolean)
"""

import socket
import struct
from datetime import datetime

from .models import UbiquitiDevice


def _format_mac(raw: bytes) -> str:
    """Formata 6 bytes binários em string MAC 'AA:BB:CC:DD:EE:FF'."""
    if len(raw) >= 6:
        return ":".join(f"{b:02X}" for b in raw[:6])
    return ""


def _decode_string(raw: bytes) -> str:
    """Decodifica bytes em string UTF-8, removendo nulos e espaços."""
    return raw.decode("utf-8", errors="ignore").strip(" \t\r\n\x00")


def parse_tlv_payload(data: bytes, offset: int) -> dict[int, bytes]:
    """Extrai todos os blocos TLV do payload binário retornando {type_id: value_bytes}."""
    fields: dict[int, bytes] = {}
    while offset + 3 <= len(data):
        tag_type = data[offset]
        try:
            tag_len = struct.unpack(">H", data[offset + 1:offset + 3])[0]
        except struct.error:
            break
        offset += 3

        if offset + tag_len > len(data):
            break

        value = data[offset:offset + tag_len]
        offset += tag_len

        # Mantém o primeiro valor encontrado para cada type_id
        if tag_type not in fields:
            fields[tag_type] = value

    return fields


def parse_response(payload: bytes, address: tuple[str, int], elapsed_ms: float | None = None) -> UbiquitiDevice | None:
    """Converte uma resposta UDP em UbiquitiDevice parseando o TLV binário real.

    Ignora pacotes menores que 4 bytes ou com versão inválida.
    """
    if len(payload) < 4:
        return None

    # Header: version(u8), command(u8), payload_length(u16be)
    version = payload[0]
    command = payload[1]

    # Versões válidas: 1 ou 2. Comando de resposta é tipicamente 0x00, 0x01 ou 0x06.
    if version not in (1, 2):
        return None

    # Extrair campos TLV do payload (começa no offset 4)
    fields = parse_tlv_payload(payload, 4)

    # Se não extraiu nenhum campo TLV, não é uma resposta válida
    if not fields:
        return None

    # --- Decodificar cada campo TLV ---

    # MAC Address (0x01): 6 bytes binários
    mac = ""
    if 0x01 in fields:
        mac = _format_mac(fields[0x01])

    # IP Info (0x02): 6 bytes MAC + 4 bytes IPv4
    ip = address[0]
    if 0x02 in fields and len(fields[0x02]) >= 10:
        ip_bytes = fields[0x02][6:10]
        try:
            ip = socket.inet_ntoa(ip_bytes)
        except (OSError, ValueError):
            pass
        # Se o MAC ainda está vazio, extrair do campo 0x02
        if not mac:
            mac = _format_mac(fields[0x02][:6])

    # Firmware (0x03)
    firmware = _decode_string(fields[0x03]) if 0x03 in fields else ""

    # Uptime (0x0A): uint32 big-endian
    uptime = None
    if 0x0A in fields:
        raw = fields[0x0A]
        try:
            if len(raw) == 4:
                uptime = struct.unpack(">I", raw)[0]
            elif len(raw) >= 8:
                uptime = struct.unpack(">Q", raw)[0]
        except struct.error:
            pass

    # Hostname / System Name (0x0B)
    system_name = _decode_string(fields[0x0B]) if 0x0B in fields else ""

    # Platform / Short Model (0x0C)
    platform = _decode_string(fields[0x0C]) if 0x0C in fields else ""

    # ESSID (0x0D)
    essid = _decode_string(fields[0x0D]) if 0x0D in fields else ""

    # Model Name (0x14 ou 0x15)
    model = ""
    if 0x14 in fields:
        model = _decode_string(fields[0x14])
    elif 0x15 in fields:
        model = _decode_string(fields[0x15])

    # Se model está vazio mas platform tem valor, usar platform como modelo
    if not model and platform:
        model = platform

    # Is Default State (0x17)
    is_default = False
    if 0x17 in fields and fields[0x17]:
        is_default = bool(fields[0x17][0])

    # Protocol version da resposta
    proto_version = f"v{version}"

    return UbiquitiDevice(
        ip=ip,
        mac=mac,
        model=model,
        system_name=system_name,
        firmware=firmware,
        protocol_version=proto_version,
        hardware_address=mac,
        platform=platform,
        essid=essid,
        uptime=uptime,
        is_default=is_default,
        response_ms=elapsed_ms,
        discovered_at=datetime.now(),
        raw_fields=fields,
    )
