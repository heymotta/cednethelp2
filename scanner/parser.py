"""Parser tolerante para respostas do Ubiquiti Discovery Protocol.

As versões de firmware variam nos nomes dos campos. O parser aceita os
formatos TLV e texto ``chave=valor`` observados nas respostas UDP/10001.
"""

import ipaddress
import re
from datetime import datetime

from .models import UbiquitiDevice

_ALIASES = {
    "model": ("model", "product", "devicetype", "device_type", "board"),
    "system_name": ("hostname", "systemname", "system_name", "name", "host"),
    "firmware": ("firmware", "version", "swversion", "software"),
    "mac": ("mac", "macaddress", "hwaddr", "hardwareaddress", "hardware_address"),
    "platform": ("platform", "arch", "architecture"),
    "protocol_version": ("protocol", "protocolversion", "discoveryversion"),
}


def _normal_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _fields(payload: bytes) -> dict[str, str]:
    text = payload.decode("utf-8", errors="ignore").replace("\x00", "\n")
    fields: dict[str, str] = {}
    for match in re.finditer(r"([A-Za-z][A-Za-z0-9_. -]{1,30})\s*[:=]\s*([^\r\n\x00]+)", text):
        fields[_normal_key(match.group(1))] = match.group(2).strip(" \t\x00\"'")

    # Algumas respostas são TLV ASCII: [length][key][value]. Também extraímos
    # os tokens para aproveitar respostas cujo comprimento não é padronizado.
    tokens = [t.strip(" \t\r\n\x00\"'") for t in re.split(r"[^A-Za-z0-9:._/-]+", text) if t.strip()]
    for token in tokens:
        if ":" in token or "=" in token:
            key, value = re.split(r"[:=]", token, maxsplit=1)
            if value:
                fields.setdefault(_normal_key(key), value)
    return fields


def _find(fields: dict[str, str], name: str) -> str:
    for alias in _ALIASES[name]:
        if _normal_key(alias) in fields:
            return fields[_normal_key(alias)]
    return ""


def parse_response(payload: bytes, address: tuple[str, int], elapsed_ms: float | None = None) -> UbiquitiDevice | None:
    """Converte uma resposta UDP em dispositivo; ignora tráfego não reconhecido."""
    try:
        ipaddress.ip_address(address[0])
    except ValueError:
        return None
    fields = _fields(payload)
    mac = _find(fields, "mac").replace("-", ":").upper()
    if re.fullmatch(r"[0-9A-F]{12}", mac):
        mac = ":".join(mac[i:i + 2] for i in range(0, 12, 2))
    # Respostas binárias podem não conter chaves, mas um IP/marca válido ainda
    # deve ser exibido para diagnóstico.
    if not fields and b"ubiquiti" not in payload.lower() and not mac and address[1] != 10001:
        return None
    return UbiquitiDevice(
        ip=address[0], mac=mac, model=_find(fields, "model"),
        system_name=_find(fields, "system_name"), firmware=_find(fields, "firmware"),
        protocol_version=_find(fields, "protocol_version"),
        hardware_address=mac, platform=_find(fields, "platform"),
        response_ms=elapsed_ms, discovered_at=datetime.now(), raw_fields=fields,
    )
