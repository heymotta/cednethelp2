"""
CedNet Help - Modelos de Dados para Teste de DNS (modules/dns_models.py)
Define as estruturas de dados para provedores de DNS e resultados de medição de latência.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class DNSProvider:
    """Representa um provedor de servidor DNS público."""
    id: str
    name: str
    primary_ip: str
    secondary_ip: str
    category: str = "Público"
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "primary_ip": self.primary_ip,
            "secondary_ip": self.secondary_ip,
            "category": self.category,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DNSProvider":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Desconhecido"),
            primary_ip=data.get("primary_ip", ""),
            secondary_ip=data.get("secondary_ip", ""),
            category=data.get("category", "Público"),
            enabled=data.get("enabled", True),
        )


@dataclass
class DNSTestResult:
    """Resultado de medição de um único provedor de DNS."""
    provider: DNSProvider
    status: str = "Aguardando"  # Aguardando, Testando..., Concluído, Timeout, Erro
    latency_ms: Optional[float] = None  # Latência mediana em milissegundos
    queries_tested: int = 0
    successful_queries: int = 0
    error_message: Optional[str] = None

    @property
    def formatted_latency(self) -> str:
        """Formata a latência para exibição (ex: '12 ms', 'Timeout', '-- ms')."""
        if self.status == "Aguardando":
            return "-- ms"
        if self.status == "Testando...":
            return "Testando..."
        if self.status == "Timeout":
            return "Timeout"
        if self.status == "Erro":
            return "Erro"
        if self.latency_ms is not None:
            return f"{round(self.latency_ms)} ms" if self.latency_ms >= 10 else f"{self.latency_ms:.1f} ms"
        return "-- ms"


@dataclass
class DNSBenchmarkSummary:
    """Resumo consolidado do teste de benchmark de DNS."""
    results: List[DNSTestResult] = field(default_factory=list)
    best_result: Optional[DNSTestResult] = None
    completed: bool = False
    cancelled: bool = False
    total_time_seconds: float = 0.0
