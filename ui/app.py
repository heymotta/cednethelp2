"""
CedNet Help - Janela Principal
Gerencia o layout principal da aplicação: sidebar + área de conteúdo.
Coordena a navegação entre os painéis dos módulos e gerencia o ciclo de vida do NetworkManager.
"""

import customtkinter as ctk
from modules.utils import (
    COLORS, SIDEBAR_WIDTH, WINDOW_SIZE, WINDOW_MIN_SIZE, APP_NAME,
)
from modules.network_manager import network_manager
from ui.sidebar import Sidebar
from ui.network_panel import NetworkPanel
from ui.router_panel import RouterPanel
from ui.ip_config_panel import IPConfigPanel
from ui.scanner_panel import ScannerPanel
from ui.wifi_panel import WiFiPanel
from ui.automation_panel import AutomationPanel
from ui.speedtest_panel import SpeedTestPanel


class CedNetApp(ctk.CTk):
    """Janela principal do CedNet Help."""

    def __init__(self):
        super().__init__()

        # ---- Configuração da Janela ----
        self.title(APP_NAME)
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN_SIZE)

        # Tema escuro profissional
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Cor de fundo da janela principal
        self.configure(fg_color=COLORS["bg_main"])

        # ---- Inicia o Serviço Central de Monitoramento de Rede ----
        network_manager.start_monitoring(interval_seconds=1.5)

        # ---- Layout Grid: Sidebar (col 0) + Conteúdo (col 1) ----
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- Sidebar ----
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ---- Área Principal ----
        self.main_area = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_main"],
            corner_radius=0,
        )
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        # ---- Painéis dos Módulos ----
        self.panels: dict[str, ctk.CTkFrame] = {}
        self._current_panel: str | None = None
        self._init_panels()

        # ---- Estado Inicial: mostra o painel de rede ----
        self._navigate("network")
        self.sidebar.set_active("network")

        # ---- Evento de fechamento ----
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ================================================================
    # Inicialização dos Painéis
    # ================================================================

    def _init_panels(self):
        """
        Inicializa todos os painéis dos módulos.
        Novos módulos devem ser registrados aqui.
        """
        self.panels["network"] = NetworkPanel(self.main_area)
        self.panels["router"] = RouterPanel(self.main_area)
        self.panels["ip_config"] = IPConfigPanel(self.main_area)
        self.panels["scanner"] = ScannerPanel(self.main_area)
        self.panels["wifi"] = WiFiPanel(self.main_area)
        self.panels["automation"] = AutomationPanel(self.main_area)
        self.panels["speedtest"] = SpeedTestPanel(self.main_area)

    # ================================================================
    # Navegação
    # ================================================================

    def _navigate(self, panel_name: str):
        """
        Navega para um painel específico, escondendo o anterior.

        Args:
            panel_name: Identificador do painel (ex: 'network', 'router', 'passwords').
        """
        # Esconde o painel atual
        if self._current_panel and self._current_panel in self.panels:
            self.panels[self._current_panel].grid_remove()

        # Mostra o painel solicitado
        if panel_name in self.panels:
            self.panels[panel_name].grid(row=0, column=0, sticky="nsew")
            self._current_panel = panel_name

    # ================================================================
    # Ciclo de Vida
    # ================================================================

    def _on_closing(self):
        """
        Callback executado ao fechar a aplicação.
        Encerra threads de monitoramento antes de destruir a janela.
        """
        # Para o monitoramento de cada painel
        for panel in self.panels.values():
            if hasattr(panel, "stop_monitoring"):
                panel.stop_monitoring()

        # Para a thread central do NetworkManager
        network_manager.stop_monitoring()

        self.destroy()
