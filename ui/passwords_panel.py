"""
CedNet Help - Painel de Senhas Padrão
Exibe uma lista pesquisável de senhas padrão de roteadores e equipamentos de rede.
Filtragem em tempo real enquanto o usuário digita.
"""

import customtkinter as ctk
from modules.passwords import search_passwords, get_all_passwords
from modules.utils import COLORS, FONTS


class PasswordsPanel(ctk.CTkFrame):
    """Painel de senhas padrão de equipamentos de rede com pesquisa."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._password_widgets: list[ctk.CTkFrame] = []
        self._create_ui()
        self._display_passwords()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface do painel de senhas."""
        # ---- Cabeçalho: título + campo de pesquisa ----
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=5, pady=(5, 10))

        ctk.CTkLabel(
            top_frame,
            text="🔑  Senhas Padrão",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        # Campo de pesquisa
        search_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        search_frame.pack(side="right")

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍  Pesquisar marca...",
            font=FONTS["body"],
            width=260,
            height=38,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
        )
        self.search_entry.pack()
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ---- Header da tabela ----
        header_card = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=10,
            height=44,
        )
        header_card.pack(fill="x", padx=5, pady=(0, 5))
        header_card.pack_propagate(False)

        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=15, pady=10)
        header_inner.columnconfigure((0, 1, 2), weight=1)

        columns = ["Marca", "Usuário", "Senha"]
        for col, text in enumerate(columns):
            ctk.CTkLabel(
                header_inner,
                text=text,
                font=FONTS["body_bold"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=0, column=col, sticky="w", padx=5)

        # ---- Lista scrollável de senhas ----
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5)
        self.scroll_frame.columnconfigure(0, weight=1)

    # ================================================================
    # Exibição de Senhas
    # ================================================================

    def _display_passwords(self, passwords: list[dict] | None = None):
        """
        Renderiza a lista de senhas no scroll frame.
        Limpa a lista anterior antes de exibir.

        Args:
            passwords: Lista de dicts ou None para exibir todas.
        """
        # Limpa widgets existentes
        for widget in self._password_widgets:
            widget.destroy()
        self._password_widgets.clear()

        if passwords is None:
            passwords = get_all_passwords()

        # Mensagem de "sem resultados"
        if not passwords:
            no_result = ctk.CTkLabel(
                self.scroll_frame,
                text="😕  Nenhum resultado encontrado",
                font=FONTS["body"],
                text_color=COLORS["text_secondary"],
            )
            no_result.pack(pady=30)
            self._password_widgets.append(no_result)
            return

        # Cria um card para cada senha
        for i, pw in enumerate(passwords):
            card = self._create_password_row(pw, i)
            card.pack(fill="x", pady=2)
            self._password_widgets.append(card)

    def _create_password_row(self, pw: dict, index: int) -> ctk.CTkFrame:
        """
        Cria uma linha (card) para uma senha.

        Args:
            pw: Dicionário com marca, usuario, senha.
            index: Índice da linha (para alternar cor de fundo).

        Returns:
            CTkFrame representando a linha.
        """
        # Alterna cores de fundo para melhor legibilidade
        bg = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_card_alt"]

        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=bg,
            corner_radius=8,
            height=48,
        )
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)
        inner.columnconfigure((0, 1, 2), weight=1)

        # Marca
        ctk.CTkLabel(
            inner,
            text=f"🏷️  {pw['marca']}",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=5)

        # Usuário
        ctk.CTkLabel(
            inner,
            text=pw["usuario"],
            font=FONTS["mono"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=5)

        # Senha
        ctk.CTkLabel(
            inner,
            text=pw["senha"],
            font=FONTS["mono"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=5)

        return card

    # ================================================================
    # Pesquisa
    # ================================================================

    def _on_search(self, event=None):
        """Callback de pesquisa — filtra em tempo real ao digitar."""
        query = self.search_entry.get()
        results = search_passwords(query)
        self._display_passwords(results)
