"""
CedNet Help - Janela Principal
Gerencia o layout principal da aplicação: sidebar + área de conteúdo.
Coordena a navegação entre os painéis dos módulos e gerencia o ciclo de vida do NetworkManager.
"""

import customtkinter as ctk
import sys
import os
from modules.utils import (
    COLORS, FONTS, SIDEBAR_WIDTH, WINDOW_SIZE, WINDOW_MIN_SIZE, APP_NAME, APP_VERSION,
)
from modules.network_manager import network_manager
from modules.update_checker import check_for_update_async, launch_updater, get_app_dir
from ui.sidebar import Sidebar
from ui.network_panel import NetworkPanel
from ui.router_panel import RouterPanel
from ui.ip_config_panel import IPConfigPanel
from ui.scanner_panel import ScannerPanel
from ui.wifi_panel import WiFiPanel
from ui.dns_panel import DNSPanel
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

        # ---- Verificação de atualização em background ----
        self._pending_update = None
        check_for_update_async(self._on_update_check_result)

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
        self.panels["dns_test"] = DNSPanel(self.main_area)
        self.panels["speedtest"] = SpeedTestPanel(self.main_area)



    # ================================================================
    # Navegação
    # ================================================================

    def _navigate(self, panel_name: str):
        """
        Navega para um painel específico, escondendo o anterior.

        Args:
            panel_name: Identificador do painel (ex: 'network', 'router').
        """
        # Esconde o painel atual
        if self._current_panel and self._current_panel in self.panels:
            self.panels[self._current_panel].grid_remove()

        # Mostra o painel solicitado
        if panel_name in self.panels:
            self.panels[panel_name].grid(row=0, column=0, sticky="nsew")
            self._current_panel = panel_name

    # ================================================================
    # Verificação de Atualizações
    # ================================================================

    def _on_update_check_result(self, update_info):
        """Callback (chamado da thread) quando a verificação de atualização termina."""
        if update_info:
            self._pending_update = update_info
            # Agenda a exibição do modal na thread principal
            try:
                self.after(0, self._show_update_modal)
            except RuntimeError:
                pass

    def _show_update_modal(self):
        """Exibe modal informando que há uma nova versão disponível."""
        info = self._pending_update
        if not info:
            return

        modal = ctk.CTkToplevel(self)
        modal.title("Atualização Disponível")
        modal.geometry("500x420")
        modal.resizable(False, False)
        modal.configure(fg_color=COLORS["bg_main"])
        modal.attributes("-topmost", True)
        modal.grab_set()

        # Card principal
        card = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=14)
        card.pack(fill="both", expand=True, padx=15, pady=15)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        # Título
        ctk.CTkLabel(
            inner, text="Nova Versão Disponível!",
            font=FONTS["title"], text_color=COLORS["accent_cyan"],
        ).pack(anchor="w", pady=(0, 10))

        # Versões
        ver_frame = ctk.CTkFrame(inner, fg_color=COLORS["entry_bg"], corner_radius=8)
        ver_frame.pack(fill="x", pady=(0, 12))

        ver_inner = ctk.CTkFrame(ver_frame, fg_color="transparent")
        ver_inner.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            ver_inner,
            text=f"Versão Instalada:   v{info.get('current_version', APP_VERSION)}",
            font=FONTS["mono"], text_color=COLORS["text_secondary"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            ver_inner,
            text=f"Nova Versão:        v{info.get('version', '?')}",
            font=FONTS["mono"], text_color=COLORS["status_ok"], anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        # Changelog
        changelog = info.get("changelog", [])
        if changelog:
            ctk.CTkLabel(
                inner, text="Novidades:",
                font=FONTS["body_bold"], text_color=COLORS["text_primary"], anchor="w",
            ).pack(anchor="w", pady=(0, 4))

            log_box = ctk.CTkTextbox(
                inner, font=FONTS["small"], fg_color=COLORS["entry_bg"],
                text_color=COLORS["text_secondary"], corner_radius=8, height=100,
                state="normal", wrap="word",
            )
            log_box.pack(fill="x", pady=(0, 12))
            for item in changelog:
                log_box.insert("end", f"  •  {item}\n")
            log_box.configure(state="disabled")

        # Botões
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")

        def _dismiss():
            modal.destroy()

        def _accept():
            modal.destroy()
            self._start_update_process(info)

        ctk.CTkButton(
            btn_frame, text="Depois", font=FONTS["body_bold"],
            height=40, corner_radius=8, fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["border"], command=_dismiss,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btn_frame, text="Atualizar Agora", font=FONTS["body_bold"],
            height=40, corner_radius=8, fg_color=COLORS["status_ok"],
            hover_color="#388e3c", command=_accept,
        ).pack(side="right", fill="x", expand=True, padx=(5, 0))

    def _start_update_process(self, info: dict):
        """Fecha o CedNet Help e inicia o CedNet Updater."""
        app_dir = get_app_dir()
        launched = launch_updater(info, app_dir)

        if launched:
            # Encerra o CedNet Help para permitir a atualização
            self._on_closing()
        else:
            # Updater não encontrado — exibe mensagem amigável
            error_modal = ctk.CTkToplevel(self)
            error_modal.title("Updater Não Encontrado")
            error_modal.geometry("400x180")
            error_modal.resizable(False, False)
            error_modal.configure(fg_color=COLORS["bg_main"])
            error_modal.attributes("-topmost", True)
            error_modal.grab_set()

            ctk.CTkLabel(
                error_modal, text="CedNet Updater não encontrado",
                font=FONTS["subtitle"], text_color=COLORS["status_error"],
            ).pack(pady=(25, 10))

            ctk.CTkLabel(
                error_modal,
                text="O arquivo CedNet_Updater.exe não foi encontrado.\n"
                     "Certifique-se de que ele está na mesma pasta do CedNet Help.",
                font=FONTS["small"], text_color=COLORS["text_secondary"],
                wraplength=350,
            ).pack(pady=(0, 15))

            ctk.CTkButton(
                error_modal, text="OK", font=FONTS["body_bold"],
                height=36, fg_color=COLORS["accent"], command=error_modal.destroy,
            ).pack()

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
