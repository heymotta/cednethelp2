"""
CedNet Help - Repositório de Provedores DNS (modules/dns_repository.py)
Gerencia o carregamento e salvamento dos servidores DNS em arquivo de configuração JSON.
"""

import os
import json
from typing import List
from modules.dns_models import DNSProvider

DEFAULT_PROVIDERS = [
    {"id": "cednet", "name": "CedNet DNS", "primary_ip": "191.37.34.202", "secondary_ip": "191.37.34.202", "category": "CedNet Telecom", "enabled": True},
    {"id": "cloudflare", "name": "Cloudflare", "primary_ip": "1.1.1.1", "secondary_ip": "1.0.0.1", "category": "Público / Rápido", "enabled": True},
    {"id": "google", "name": "Google Public DNS", "primary_ip": "8.8.8.8", "secondary_ip": "8.8.4.4", "category": "Público / Global", "enabled": True},
    {"id": "opendns", "name": "OpenDNS", "primary_ip": "208.67.222.222", "secondary_ip": "208.67.220.220", "category": "Segurança / Cisco", "enabled": True},
    {"id": "quad9", "name": "Quad9", "primary_ip": "9.9.9.9", "secondary_ip": "149.112.112.112", "category": "Segurança & Privacidade", "enabled": True},
    {"id": "comodo", "name": "Comodo Secure DNS", "primary_ip": "8.26.56.26", "secondary_ip": "8.20.247.20", "category": "Segurança", "enabled": True},
    {"id": "adguard", "name": "AdGuard DNS", "primary_ip": "94.140.14.14", "secondary_ip": "94.140.15.15", "category": "Filtro de Anúncios", "enabled": True},
    {"id": "cleanbrowsing", "name": "CleanBrowsing", "primary_ip": "185.228.168.9", "secondary_ip": "185.228.169.9", "category": "Filtro de Conteúdo", "enabled": True},
    {"id": "yandex", "name": "Yandex DNS", "primary_ip": "77.88.8.8", "secondary_ip": "77.88.8.1", "category": "Público", "enabled": True},
    {"id": "neustar", "name": "Neustar UltraDNS", "primary_ip": "156.154.70.1", "secondary_ip": "156.154.71.1", "category": "Corporativo", "enabled": True},
    {"id": "controld", "name": "Control D", "primary_ip": "76.76.2.0", "secondary_ip": "76.76.10.0", "category": "Privacidade", "enabled": True},
    {"id": "verisign", "name": "Verisign", "primary_ip": "64.6.64.6", "secondary_ip": "64.6.65.6", "category": "Estabilidade", "enabled": True},
    {"id": "safedns", "name": "SafeDNS", "primary_ip": "195.46.39.39", "secondary_ip": "195.46.39.40", "category": "Segurança", "enabled": True},
]


class DNSRepository:
    """Gerenciador do repositório de provedores DNS."""

    def __init__(self, file_path: str = ""):
        if not file_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, "data", "dns_providers.json")
        self.file_path = file_path

    def load_providers(self) -> List[DNSProvider]:
        """Carrega os provedores de DNS garantindo CedNet DNS e removendo Alternate e DNS.WATCH."""
        providers = []
        if not os.path.exists(self.file_path):
            providers = [DNSProvider.from_dict(p) for p in DEFAULT_PROVIDERS]
            self.save_providers(providers)
            return providers

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded = [DNSProvider.from_dict(p) for p in data if isinstance(p, dict)]

            # Filtra removidos (alternate e dnswatch)
            filtered = [p for p in loaded if p.id not in ("alternate", "dnswatch")]

            # Garante que CedNet DNS esteja presente no topo
            if not any(p.id == "cednet" for p in filtered):
                cednet_prov = DNSProvider.from_dict(DEFAULT_PROVIDERS[0])
                filtered.insert(0, cednet_prov)

            self.save_providers(filtered)
            return filtered
        except Exception:
            return [DNSProvider.from_dict(p) for p in DEFAULT_PROVIDERS]

    def save_providers(self, providers: List[DNSProvider]):
        """Salva a lista de provedores no arquivo JSON."""
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in providers], f, indent=4, ensure_ascii=False)
        except Exception:
            pass
