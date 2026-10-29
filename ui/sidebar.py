"""
CedNet Help - Sidebar de Navegação
Menu lateral com navegação entre os módulos do aplicativo.
"""

import customtkinter as ctk
from modules.utils import COLORS, FONTS, SIDEBAR_WIDTH, APP_NAME, APP_VERSION


class Sidebar(ctk.CTkFrame):
    """Menu lateral de navegação do CedNet Help."""

    def __init__(self, parent, on_navigate: callable, on_toggle_theme: callable = None):
        super().__init__(
            parent,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
        )
        self.on_navigate = on_navigate
        self.on_toggle_theme = on_toggle_theme
        self.buttons: dict[str, ctk.CTkButton] = {}
        self.active_button: str | None = None

        self.grid_propagate(False)

        self._create_header()
        self._create_nav_buttons()
        self._create_footer()

    def _create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(25, 5))

        ctk.CTkLabel(
            header_frame,
            text="🛠️",
            font=("Segoe UI", 32),
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            header_frame,
            text=APP_NAME,
            font=FONTS["sidebar_title"],
            text_color=COLORS["text_primary"],
        ).pack()

        ctk.CTkLabel(
            header_frame,
            text="Suporte Técnico",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(pady=(2, 0))

        ctk.CTkFrame(
            self,
            height=2,
            fg_color=COLORS["border"],
        ).pack(fill="x", padx=20, pady=(15, 10))

    def _create_nav_buttons(self):
        nav_items = [
            ("network",          "🌐  Rede"),
            ("router",           "🔀  Roteador"),
            ("ip_config",        "⚙️  Config. IP"),
            ("scanner",          "🔍  Scanner"),
            ("ubiquiti_scanner", "📡  Ubiquiti Discovery"),
            ("wifi",             "📶  Canais Wi-Fi"),
            ("dns_test",         "⏱️  Teste de DNS"),
            ("speedtest",        "⚡  Speed Test"),
        ]

        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=5)

        for key, label in nav_items:
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                font=FONTS["sidebar_btn"],
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_card"],
                command=lambda k=key: self._on_click(k),
            )
            btn.pack(fill="x", padx=5, pady=2)
            self.buttons[key] = btn

    def _create_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=15, pady=15)

        # Alternador de Tema (Modo Escuro / Modo Claro)
        theme_frame = ctk.CTkFrame(footer, fg_color="transparent")
        theme_frame.pack(fill="x", pady=(0, 10))

        self.theme_var = ctk.StringVar(value="dark")
        self.theme_switch = ctk.CTkSwitch(
            theme_frame,
            text="Modo Claro",
            font=FONTS["small_bold"],
            text_color=COLORS["text_secondary"],
            command=self._on_theme_switch,
            onvalue="light",
            offvalue="dark",
            variable=self.theme_var,
            progress_color=COLORS["accent"],
        )
        self.theme_switch.pack(anchor="w", padx=5)

        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=5)

    def _on_theme_switch(self):
        mode = self.theme_var.get()
        if self.on_toggle_theme:
            self.on_toggle_theme()

    def _on_click(self, key: str):
        self.set_active(key)
        self.on_navigate(key)

    def set_active(self, key: str):
        for btn in self.buttons.values():
            btn.configure(
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
            )

        if key in self.buttons:
            self.buttons[key].configure(
                fg_color=COLORS["accent"],
                text_color=COLORS["text_primary"],
            )
            self.active_button = key
