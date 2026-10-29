"""
CedNet Help - Janela Principal
Layout principal: sidebar + área de conteúdo.
Coordena navegação dos módulos e ciclo de vida do monitoramento de rede.
"""

import customtkinter as ctk
import os
import ctypes

try:
    myappid = "cednet.help.app.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

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
from ui.scanner_page import UbiquitiScannerPage


class CedNetApp(ctk.CTk):
    """Janela principal do CedNet Help."""

    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.minsize(*WINDOW_MIN_SIZE)
        self._center_window()

        app_dir = get_app_dir()
        icon_path = os.path.join(app_dir, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Tema padrão da aplicação: Escuro
        self.current_theme = "dark"
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["bg_main"])

        network_manager.start_monitoring(interval_seconds=1.5)

        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, on_navigate=self._navigate, on_toggle_theme=self.toggle_theme)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.main_area = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_main"],
            corner_radius=0,
        )
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        self.panels: dict[str, ctk.CTkFrame] = {}
        self._current_panel: str | None = None
        self._init_panels()

        self._navigate("network")
        self.sidebar.set_active("network")

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._pending_update = None
        check_for_update_async(self._on_update_check_result)

        self._center_window()

    def _center_window(self):
        """Calcula as coordenadas e posiciona a janela centralizada na tela do usuário."""
        try:
            parts = WINDOW_SIZE.split("x")
            win_w = int(parts[0])
            win_h = int(parts[1])
        except Exception:
            win_w, win_h = 1050, 680

        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def toggle_theme(self):
        """Alterna entre os modos Claro e Escuro dinamicamente."""
        new_mode = "light" if self.current_theme == "dark" else "dark"
        self.set_theme(new_mode)

    def set_theme(self, mode: str):
        """Aplica o tema selecionado ('dark' ou 'light')."""
        self.current_theme = mode
        ctk.set_appearance_mode(mode)

        # Notifica painéis que utilizam elementos Tkinter nativos (como Canvas do velocímetro ou Treeview)
        for panel in self.panels.values():
            if hasattr(panel, "on_theme_changed"):
                try:
                    panel.on_theme_changed(mode)
                except Exception:
                    pass

    def _init_panels(self):
        """Inicializa os módulos registrados."""
        self.panels["network"] = NetworkPanel(self.main_area)
        self.panels["router"] = RouterPanel(self.main_area)
        self.panels["ip_config"] = IPConfigPanel(self.main_area)
        self.panels["scanner"] = ScannerPanel(self.main_area)
        self.panels["wifi"] = WiFiPanel(self.main_area)
        self.panels["dns_test"] = DNSPanel(self.main_area)
        self.panels["speedtest"] = SpeedTestPanel(self.main_area)
        self.panels["ubiquiti_scanner"] = UbiquitiScannerPage(self.main_area)

    def _navigate(self, panel_name: str):
        """Alterna a exibição para o painel selecionado."""
        if self._current_panel and self._current_panel in self.panels:
            self.panels[self._current_panel].grid_remove()

        if panel_name in self.panels:
            self.panels[panel_name].grid(row=0, column=0, sticky="nsew")
            self._current_panel = panel_name

    def _on_update_check_result(self, update_info):
        """Recebe resultado assíncrono da checagem de versões."""
        if update_info:
            self._pending_update = update_info
            try:
                self.after(0, self._show_update_modal)
            except RuntimeError:
                pass

    def _show_update_modal(self):
        """Exibe modal de atualização disponível com suporte a atalhos de teclado."""
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

        card = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=14)
        card.pack(fill="both", expand=True, padx=15, pady=15)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            inner, text="Nova Versão Disponível!",
            font=FONTS["title"], text_color=COLORS["accent_cyan"],
        ).pack(anchor="w", pady=(0, 10))

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

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")

        def _dismiss():
            modal.destroy()

        def _accept():
            modal.destroy()
            self._start_update_process(info)

        btn_dismiss = ctk.CTkButton(
            btn_frame, text="Depois (Esc)", font=FONTS["body_bold"],
            height=40, corner_radius=8, fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["border"], command=_dismiss,
        )
        btn_dismiss.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_accept = ctk.CTkButton(
            btn_frame, text="Atualizar Agora (Enter)", font=FONTS["body_bold"],
            height=40, corner_radius=8, fg_color=COLORS["btn_success"],
            hover_color=COLORS["btn_success_hover"], command=_accept,
        )
        btn_accept.pack(side="right", fill="x", expand=True, padx=(5, 0))

        modal.bind("<Escape>", lambda e: _dismiss())
        modal.bind("<Return>", lambda e: _accept())
        btn_accept.focus_set()

    def _start_update_process(self, info: dict):
        """Fecha o CedNet Help e inicia o executável updater."""
        app_dir = get_app_dir()
        launched = launch_updater(info, app_dir)

        if launched:
            self._on_closing()
        else:
            error_modal = ctk.CTkToplevel(self)
            error_modal.title("Updater Não Encontrado")
            error_modal.geometry("400x190")
            error_modal.resizable(False, False)
            error_modal.configure(fg_color=COLORS["bg_main"])
            error_modal.attributes("-topmost", True)
            error_modal.grab_set()

            ctk.CTkLabel(
                error_modal, text="CedNet Updater não encontrado",
                font=FONTS["subtitle"], text_color=COLORS["status_error"],
            ).pack(pady=(20, 10))

            ctk.CTkLabel(
                error_modal,
                text="O arquivo CedNet_Updater.exe não foi encontrado.\n"
                     "Certifique-se de que ele está na mesma pasta do CedNet Help.",
                font=FONTS["small"], text_color=COLORS["text_secondary"],
                wraplength=350,
            ).pack(pady=(0, 15))

            btn_ok = ctk.CTkButton(
                error_modal, text="OK (Esc)", font=FONTS["body_bold"],
                height=36, fg_color=COLORS["accent"], command=error_modal.destroy,
            )
            btn_ok.pack()

            error_modal.bind("<Escape>", lambda e: error_modal.destroy())
            error_modal.bind("<Return>", lambda e: error_modal.destroy())
            btn_ok.focus_set()

    def _on_closing(self):
        """Finaliza threads ativas de monitoramento antes de encerrar."""
        for panel in self.panels.values():
            if hasattr(panel, "stop_monitoring"):
                panel.stop_monitoring()

        network_manager.stop_monitoring()
        self.destroy()
