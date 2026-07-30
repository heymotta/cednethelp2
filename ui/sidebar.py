"""
CedNet Help - Sidebar de Navegação
Menu lateral com botões de navegação entre os módulos do aplicativo.
Inclui cabeçalho com logo, botões de navegação e rodapé com versão.
"""

import customtkinter as ctk
from modules.utils import COLORS, FONTS, SIDEBAR_WIDTH, APP_NAME, APP_VERSION


class Sidebar(ctk.CTkFrame):
    """Menu lateral de navegação do CedNet Help."""

    def __init__(self, parent, on_navigate: callable):
        """
        Args:
            parent: Widget pai.
            on_navigate: Callback chamado ao clicar em um botão (recebe key: str).
        """
        super().__init__(
            parent,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
        )
        self.on_navigate = on_navigate
        self.buttons: dict[str, ctk.CTkButton] = {}
        self.active_button: str | None = None

        # Impede o frame de encolher com o conteúdo
        self.grid_propagate(False)

        self._create_header()
        self._create_nav_buttons()
        self._create_footer()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_header(self):
        """Cria o cabeçalho com ícone e título do app."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(25, 5))

        # Ícone do aplicativo
        ctk.CTkLabel(
            header_frame,
            text="🛠️",
            font=("Segoe UI", 32),
        ).pack(pady=(0, 5))

        # Nome do app
        ctk.CTkLabel(
            header_frame,
            text=APP_NAME,
            font=FONTS["sidebar_title"],
            text_color=COLORS["text_primary"],
        ).pack()

        # Subtítulo
        ctk.CTkLabel(
            header_frame,
            text="Suporte Técnico",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(pady=(2, 0))

        # Linha separadora
        ctk.CTkFrame(
            self,
            height=2,
            fg_color=COLORS["border"],
        ).pack(fill="x", padx=20, pady=(15, 10))

    def _create_nav_buttons(self):
        """Cria os botões de navegação dos módulos."""
        nav_items = [
            ("network",    "🌐  Rede"),
            ("router",     "📡  Roteador"),
            ("ip_config",  "⚙️  Config. IP"),
            ("scanner",    "🔍  Scanner"),
            ("wifi",       "📡  Canais Wi-Fi"),
            ("dns_test",   "⚡  Teste de DNS"),
            ("speedtest",  "⚡  Speed Test"),
        ]



        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=5)

        for key, label in nav_items:
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                font=FONTS["sidebar_btn"],
                anchor="w",
                height=42,
                corner_radius=8,
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_card"],
                command=lambda k=key: self._on_click(k),
            )
            btn.pack(fill="x", padx=5, pady=3)
            self.buttons[key] = btn

    def _create_footer(self):
        """Cria o rodapé com a versão do app."""
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack()

    # ================================================================
    # Navegação
    # ================================================================

    def _on_click(self, key: str):
        """Callback interno ao clicar em um botão de navegação."""
        self.set_active(key)
        self.on_navigate(key)

    def set_active(self, key: str):
        """
        Define visualmente o botão ativo na sidebar.

        Args:
            key: Identificador do módulo (ex: 'network', 'router', 'passwords').
        """
        # Reseta todos os botões para o estado inativo
        for btn in self.buttons.values():
            btn.configure(
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
            )

        # Destaca o botão selecionado
        if key in self.buttons:
            self.buttons[key].configure(
                fg_color=COLORS["accent"],
                text_color=COLORS["text_primary"],
            )
            self.active_button = key
