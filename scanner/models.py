"""Modelos de dados usados pelo scanner Ubiquiti."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NetworkInterface:
    """Interface local apta a receber o broadcast de descoberta."""

    name: str
    address: str
    netmask: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.address})"


@dataclass
class UbiquitiDevice:
    """Dados anunciados por um equipamento Ubiquiti."""

    ip: str
    mac: str = ""
    model: str = ""
    system_name: str = ""
    firmware: str = ""
    protocol_version: str = ""
    hardware_address: str = ""
    platform: str = ""
    response_ms: float | None = None
    discovered_at: datetime = field(default_factory=datetime.now)
    raw_fields: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def key(self) -> str:
        return (self.mac or self.ip).lower()

    def search_text(self) -> str:
        return " ".join((self.ip, self.mac, self.model, self.system_name, self.firmware)).lower()
