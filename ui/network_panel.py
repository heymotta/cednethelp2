"""
CedNet Help - Painel de Informações de Rede (Centralizado)
Exibe informações de rede (IPv4, Gateway, Máscara, DNS, Interface, Status, Velocidade)
com atualização em tempo real sincronizada via NetworkManager.
"""

import customtkinter as ctk
from modules.network_manager import network_manager
from modules.utils import COLORS, FONTS


class NetworkPanel(ctk.CTkFrame):
    """
    Painel de Informações de Rede.
    Sincronizado automaticamente em tempo real com o NetworkManager.
    """

    # Frequência de verificação da versão do estado da UI em milissegundos
    UI_POLL_INTERVAL_MS = 300

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._last_seen_version: int = -1
        self._after_id: str | None = None

        self._info_labels: dict[str, ctk.CTkLabel] = {}
        self._create_ui()
        self._start_sync()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta toda a interface do painel de rede."""
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- Cabeçalho com título + botão atualizar ----
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            header,
            text="🌐  Informações de Rede",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            header,
            text="Atualizar Informações",
            font=FONTS["body_bold"],
            width=180,
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._on_manual_refresh,
        )
        self.btn_refresh.pack(side="right")

        # ---- Card de Status (destaque principal) ----
        self.status_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        self.status_card.pack(fill="x", pady=(0, 15))

        status_inner = ctk.CTkFrame(self.status_card, fg_color="transparent")
        status_inner.pack(fill="x", padx=20, pady=15)

        self.status_emoji = ctk.CTkLabel(
            status_inner,
            text="⚪",
            font=("Segoe UI", 28),
        )
        self.status_emoji.pack(side="left", padx=(0, 12))

        status_text_frame = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_text_frame.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            status_text_frame,
            text="Verificando...",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.status_label.pack(anchor="w")

        self.status_detail = ctk.CTkLabel(
            status_text_frame,
            text="Aguardando informações da rede",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.status_detail.pack(anchor="w")

        # ---- Grid de cards com informações ----
        info_grid = ctk.CTkFrame(container, fg_color="transparent")
        info_grid.pack(fill="x", pady=(0, 10))
        info_grid.columnconfigure((0, 1), weight=1)

        fields = [
            ("ipv4",      "Endereço IPv4",      "💻", 0, 0),
            ("gateway",   "Gateway Padrão",     "🚪", 0, 1),
            ("mask",      "Máscara de Rede",    "🎭", 1, 0),
            ("dns",       "Servidores DNS",     "📋", 1, 1),
            ("interface", "Interface de Rede",  "🔌", 2, 0),
            ("speed",     "Velocidade",         "⚡", 2, 1),
        ]

        for key, label, icon, row, col in fields:
            card = self._create_info_card(info_grid, key, label, icon)
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

    def _create_info_card(self, parent, key: str, label: str, icon: str) -> ctk.CTkFrame:
        """Cria um card individual de informação de rede."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
        )

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)

        ctk.CTkLabel(
            inner,
            text=f"{icon}  {label}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            inner,
            text="Carregando...",
            font=FONTS["mono"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        )
        value_label.pack(anchor="w", pady=(4, 0))

        self._info_labels[key] = value_label
        return card

    # ================================================================
    # Sincronização em Tempo Real (via NetworkManager)
    # ================================================================

    def _start_sync(self):
        """Inicia a sincronização automatizada com o NetworkManager."""
        self._check_network_manager()

    def _check_network_manager(self):
        """
        Polling thread-safe na thread principal (GUI).
        Compara a versão do NetworkManager com a última versão renderizada.
        Se houve alteração de estado, atualiza TODOS os campos da interface.
        """
        current_version = network_manager.version

        if current_version != self._last_seen_version:
            self._last_seen_version = current_version
            self._render_state(network_manager.get_state())

        # Agenda a próxima verificação na GUI thread
        self._after_id = self.after(self.UI_POLL_INTERVAL_MS, self._check_network_manager)

    def _render_state(self, state: dict):
        """Atualiza todos os widgets visuais com o estado atual da rede."""
        # Atualiza cards de valores (IPv4, Gateway, Máscara, DNS, Interface, Speed)
        for key in ("ipv4", "gateway", "mask", "dns", "interface", "speed"):
            if key in self._info_labels:
                val = state.get(key, "")
                if not val or val == "Não disponível":
                    val = "Não disponível"
                self._info_labels[key].configure(
                    text=str(val),
                    text_color=COLORS["accent_cyan"],
                )

        # Atualiza card de status principal
        status = state.get("status", {})
        connected = status.get("connected", False)
        label = status.get("label", "Desconhecido")
        emoji = status.get("emoji", "⚪")

        self.status_emoji.configure(text=emoji)
        self.status_label.configure(
            text=label,
            text_color=COLORS["status_ok"] if connected else COLORS["status_error"],
        )

        if connected:
            self.status_detail.configure(text="Conexão ativa e funcionando")
            self.status_card.configure(
                border_width=2,
                border_color=COLORS["status_ok"],
            )
        else:
            self.status_detail.configure(text="Verifique o cabo ou adaptador de rede")
            self.status_card.configure(
                border_width=2,
                border_color=COLORS["status_error"],
            )

    def _on_manual_refresh(self):
        """Callback do botão de atualização manual."""
        network_manager.force_refresh()

    def stop_monitoring(self):
        """Cancela o agendamento do polling da GUI."""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
