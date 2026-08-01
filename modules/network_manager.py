"""
CedNet Help - Gerenciador Central de Rede (NetworkManager)
Serviço centralizado responsável por monitorar periodicamente a interface de rede,
manter o estado atualizado em tempo real e fornecer os dados para todas as telas (Rede, Roteador, etc.).

Utiliza padrão Singleton com thread de monitoramento em background.
"""

import threading
import time
from typing import Optional, Callable
from modules.network import NetworkInfo


class NetworkManager:
    """
    Gerenciador Central de Rede.
    Monitora a rede em segundo plano e mantém o estado único compartilhado.
    """

    _instance: Optional["NetworkManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self.network_info = NetworkInfo()

        # Estado único compartilhado
        self.state: dict = {
            "ipv4": "Carregando...",
            "gateway": "Carregando...",
            "mask": "Carregando...",
            "dns": "Carregando...",
            "interface": "Carregando...",
            "status": {"connected": False, "label": "Verificando...", "emoji": "⚪"},
            "speed": "Carregando...",
            "log_text": "Iniciando monitoramento de rede...",
        }

        # Controle de versão de estado para sincronização thread-safe com a UI
        self.version: int = 0

        # Controle da thread de monitoramento
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._refresh_requested: bool = False

        # Listeners cadastrados
        self._listeners: list[Callable[[dict], None]] = []

    # ================================================================
    # Controle de Ciclo de Vida
    # ================================================================

    def start_monitoring(self, interval_seconds: float = 1.5):
        """Inicia a thread de monitoramento em segundo plano."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True,
            name="NetworkManagerThread",
        )
        self._thread.start()

    def stop_monitoring(self):
        """Encerra a thread de monitoramento."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def force_refresh(self):
        """Solicita uma atualização imediata do estado em segundo plano."""
        self._refresh_requested = True

    # ================================================================
    # Loop de Monitoramento em Background
    # ================================================================

    def _monitor_loop(self, interval_seconds: float):
        """
        Loop continuo de monitoramento executado na thread de background.
        Coleta informações e notifica quando qualquer dado se alterar.
        """
        # Primeira coleta síncrona para disponibilizar dados imediatamente
        self._update_state()

        while self._running:
            time.sleep(interval_seconds)

            if not self._running:
                break

            # Se houve solicitação de refresh manual ou passagem do intervalo
            self._update_state()

    def _update_state(self):
        """
        Coleta dados atuais de rede e atualiza o estado se houver mudanças.
        """
        try:
            new_info = self.network_info.get_all_info()

            # Extrai log de detecção do gateway se disponível
            log_text = ""
            if self.network_info.last_detection_log:
                log_text = self.network_info.last_detection_log.get_full_log()

            # Prepara o novo estado
            gateway = new_info.get("gateway", "")
            status = new_info.get("status", {})
            if (gateway == "Não disponível"
                    or not status.get("connected", False)
                    or new_info.get("ipv4") in ("", "Não disponível")):
                gateway = ""

            new_state = {
                "ipv4": str(new_info.get("ipv4", "Não disponível")),
                "gateway": gateway,
                "mask": str(new_info.get("mask", "Não disponível")),
                "dns": str(new_info.get("dns", "Não disponível")),
                "interface": str(new_info.get("interface", "Não detectada")),
                "status": status,
                "speed": str(new_info.get("speed", "N/A")),
                "log_text": log_text,
            }

            # Compara com o estado anterior
            state_changed = False
            for k, v in new_state.items():
                if self.state.get(k) != v:
                    state_changed = True
                    break

            if state_changed or self._refresh_requested or self.version == 0:
                self._refresh_requested = False
                self.state = new_state
                self.version += 1

        except Exception as e:
            # Uma falha de coleta não pode manter o gateway da coleta anterior.
            self.state = {
                "ipv4": "Não disponível",
                "gateway": "",
                "mask": "Não disponível",
                "dns": "Não disponível",
                "interface": "Não detectada",
                "status": {"connected": False, "label": "Status desconhecido", "emoji": "⚪"},
                "speed": "N/A",
                "log_text": f"Falha ao atualizar informações de rede: {e}",
            }
            self.version += 1

    # ================================================================
    # Consulta de Estado
    # ================================================================

    def get_state(self) -> dict:
        """Retorna uma cópia do estado atual da rede."""
        return self.state.copy()


# Instância global Singleton
network_manager = NetworkManager()
