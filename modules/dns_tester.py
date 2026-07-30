"""
CedNet Help - Motor de Medição de Latência DNS (modules/dns_tester.py)
Utiliza a biblioteca dnspython para realizar consultas de resolução real de domínios
em segundo plano, calculando a mediana de latência de cada servidor.
"""

import time
import statistics
import threading
import queue
from typing import Callable, List, Optional
import dns.resolver
import dns.exception

from modules.dns_models import DNSProvider, DNSTestResult, DNSBenchmarkSummary
from modules.dns_repository import DNSRepository

TEST_DOMAINS = ["google.com", "cloudflare.com", "openai.com", "microsoft.com"]


class DNSTester:
    """Motor de medição de latência DNS em thread separada."""

    def __init__(self, repository: Optional[DNSRepository] = None):
        self.repository = repository or DNSRepository()
        self._is_running: bool = False
        self._stop_requested: bool = False
        self._worker_thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        return self._is_running

    def stop_test(self):
        """Solicita o cancelamento gracioso do teste em andamento."""
        self._stop_requested = True
        self._is_running = False

    def start_test(
        self,
        on_provider_start: Callable[[DNSProvider], None],
        on_provider_complete: Callable[[DNSTestResult], None],
        on_progress: Callable[[float, int, int], None],
        on_finish: Callable[[DNSBenchmarkSummary], None],
        on_error: Callable[[str], None],
    ):
        """Inicia a sequência de testes de benchmark DNS em thread dedicada."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_requested = False

        self._worker_thread = threading.Thread(
            target=self._run_benchmark_thread,
            args=(on_provider_start, on_provider_complete, on_progress, on_finish, on_error),
            daemon=True,
            name="DNSBenchmarkWorker",
        )
        self._worker_thread.start()

    def _run_benchmark_thread(
        self,
        on_provider_start: Callable[[DNSProvider], None],
        on_provider_complete: Callable[[DNSTestResult], None],
        on_progress: Callable[[float, int, int], None],
        on_finish: Callable[[DNSBenchmarkSummary], None],
        on_error: Callable[[str], None],
    ):
        """Executa a medição de todos os provedores em sequência."""
        start_benchmark_time = time.time()
        providers = self.repository.load_providers()
        enabled_providers = [p for p in providers if p.enabled]
        total_providers = len(enabled_providers)

        if total_providers == 0:
            self._is_running = False
            on_error("Nenhum servidor DNS habilitado para teste.")
            return

        results: List[DNSTestResult] = []

        for idx, provider in enumerate(enabled_providers, start=1):
            if self._stop_requested:
                self._is_running = False
                summary = DNSBenchmarkSummary(
                    results=results,
                    best_result=self._find_best_result(results),
                    completed=False,
                    cancelled=True,
                    total_time_seconds=time.time() - start_benchmark_time,
                )
                on_finish(summary)
                return

            # Notifica início do teste do provedor
            on_provider_start(provider)

            # Executa a medição do provedor atual
            test_result = self._measure_provider_latency(provider)
            results.append(test_result)

            # Notifica conclusão individual
            on_provider_complete(test_result)

            # Notifica progresso geral (porcentagem, atual, total)
            pct = idx / total_providers
            on_progress(pct, idx, total_providers)

            # Pausa curta para evitar saturação da placa de rede
            time.sleep(0.05)

        self._is_running = False
        total_elapsed = time.time() - start_benchmark_time
        best = self._find_best_result(results)

        summary = DNSBenchmarkSummary(
            results=results,
            best_result=best,
            completed=True,
            cancelled=False,
            total_time_seconds=total_elapsed,
        )

        on_finish(summary)

    def _measure_provider_latency(self, provider: DNSProvider) -> DNSTestResult:
        """
        Mede a latência de resolução de domínios via dnspython para um único provedor.
        Calcula a mediana entre 3 a 4 consultas válidas.
        """
        res_obj = DNSTestResult(provider=provider, status="Testando...")
        latencies: List[float] = []
        successful_count = 0
        tested_count = 0

        # Cria resolver exclusivo para o IP do provedor
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [provider.primary_ip]
        resolver.timeout = 2.0
        resolver.lifetime = 2.0

        for domain in TEST_DOMAINS:
            if self._stop_requested:
                break

            tested_count += 1
            t_start = time.perf_counter()
            try:
                # Consulta de registro A
                answers = resolver.resolve(domain, "A")
                dt_ms = (time.perf_counter() - t_start) * 1000.0
                
                # Valida que recebemos resposta válida
                if answers and len(answers) > 0:
                    latencies.append(dt_ms)
                    successful_count += 1
            except (dns.resolver.Timeout, dns.resolver.LifetimeTimeout):
                pass
            except Exception:
                pass

        res_obj.queries_tested = tested_count
        res_obj.successful_queries = successful_count

        if latencies:
            # Mediana das consultas válidas
            res_obj.latency_ms = float(statistics.median(latencies))
            res_obj.status = "Concluído"
        else:
            res_obj.status = "Timeout"
            res_obj.latency_ms = None

        return res_obj

    @staticmethod
    def _find_best_result(results: List[DNSTestResult]) -> Optional[DNSTestResult]:
        """Identifica o resultado válido com a menor latência em milissegundos."""
        valid_results = [r for r in results if r.status == "Concluído" and r.latency_ms is not None]
        if not valid_results:
            return None
        return min(valid_results, key=lambda r: r.latency_ms)
