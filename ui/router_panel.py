"""
CedNet Help - Painel do Roteador (Sincronizado)
Consome os dados centralizados do NetworkManager para exibir o gateway,
status de conexão e log de diagnóstico em tempo real, sem redundância de varredura.
"""

import customtkinter as ctk
from modules.router import open_router_page
from modules.network_manager import network_manager
from modules.utils import COLORS, FONTS


class RouterPanel(ctk.CTkFrame):
    """Painel para detecção e acesso à interface web do roteador."""

    UI_POLL_INTERVAL_MS = 300

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._last_seen_version: int = -1
        self._after_id: str | None = None
        self._gateway: str = ""

        self._create_ui()
        self._start_sync()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface completa do painel."""
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- Cabeçalho ----
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            header,
            text="📡  Abrir Roteador",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            header,
            text="Atualizar",
            font=FONTS["body_bold"],
            width=140,
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._on_manual_refresh,
        )
        self.btn_refresh.pack(side="right")

        # ---- Card de Status do Gateway ----
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
            text="⏳",
            font=("Segoe UI", 28),
        )
        self.status_emoji.pack(side="left", padx=(0, 12))

        status_text_frame = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_text_frame.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            status_text_frame,
            text="Verificando Gateway...",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.status_label.pack(anchor="w")

        self.status_detail = ctk.CTkLabel(
            status_text_frame,
            text="Sincronizando com a rede",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.status_detail.pack(anchor="w")

        # ---- Card do Gateway Detectado ----
        gateway_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        gateway_card.pack(fill="x", pady=(0, 15))

        gw_inner = ctk.CTkFrame(gateway_card, fg_color="transparent")
        gw_inner.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            gw_inner,
            text="Gateway Detectado:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w")

        self.gateway_label = ctk.CTkLabel(
            gw_inner,
            text="Verificando...",
            font=FONTS["mono_large"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        )
        self.gateway_label.pack(anchor="w", pady=(4, 10))

        # Botão de abrir roteador
        self.btn_open = ctk.CTkButton(
            gw_inner,
            text="Abrir Interface do Roteador",
            font=FONTS["body_bold"],
            height=45,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._open_router,
            state="disabled",
        )
        self.btn_open.pack(fill="x")

        # Label de feedback
        self.feedback_label = ctk.CTkLabel(
            container,
            text="",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        )
        self.feedback_label.pack(pady=(0, 10))

        # ---- Card de Log ----
        log_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        log_card.pack(fill="x", pady=(0, 15))

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            log_header,
            text="🔍  Log de Diagnóstico",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.log_textbox = ctk.CTkTextbox(
            log_card,
            font=FONTS["mono"],
            fg_color=COLORS["entry_bg"],
            text_color=COLORS["text_secondary"],
            corner_radius=8,
            height=160,
            state="disabled",
            wrap="word",
        )
        self.log_textbox.pack(fill="x", padx=20, pady=(0, 15))



    # ================================================================
    # Sincronização em Tempo Real (via NetworkManager)
    # ================================================================

    def _start_sync(self):
        """Inicia a sincronização de dados com o NetworkManager."""
        self._check_network_manager()

    def _check_network_manager(self):
        """
        Polling thread-safe na GUI thread.
        Sincroniza os widgets do roteador assim que o NetworkManager atualiza.
        """
        current_version = network_manager.version

        if current_version != self._last_seen_version:
            self._last_seen_version = current_version
            self._render_state(network_manager.get_state())

        self._after_id = self.after(self.UI_POLL_INTERVAL_MS, self._check_network_manager)

    def _render_state(self, state: dict):
        """Atualiza a UI com o estado sincronizado da rede."""
        gateway = state.get("gateway", "")
        status = state.get("status", {})
        has_gateway = bool(
            status.get("connected", False)
            and state.get("ipv4") not in ("", "Não disponível", "Carregando...")
            and gateway
        )
        log_text = state.get("log_text", "")
        self._gateway = gateway if has_gateway else ""

        self._update_log(log_text)

        if has_gateway:
            # 🟢 Gateway encontrado
            self.status_emoji.configure(text="🟢")
            self.status_label.configure(
                text="Gateway Detectado",
                text_color=COLORS["status_ok"],
            )
            self.status_detail.configure(text=f"Pronto para abrir http://{gateway}")
            self.status_card.configure(border_width=2, border_color=COLORS["status_ok"])
            self.gateway_label.configure(
                text=f"http://{gateway}",
                text_color=COLORS["accent_cyan"],
            )
            self.btn_open.configure(state="normal")
        else:
            # 🔴 Gateway não encontrado
            self.status_emoji.configure(text="🔴")
            self.status_label.configure(
                text="Nenhum roteador detectado.",
                text_color=COLORS["status_error"],
            )
            self.status_detail.configure(text="Verifique se há uma interface conectada")
            self.status_card.configure(border_width=2, border_color=COLORS["status_error"])
            self.gateway_label.configure(
                text="Nenhum roteador detectado.",
                text_color=COLORS["status_error"],
            )
            self.btn_open.configure(state="disabled")

    def _on_manual_refresh(self):
        """Atualização manual forçada no NetworkManager."""
        network_manager.force_refresh()

    def _open_router(self):
        """Abre a interface do roteador."""
        if not self._gateway:
            self.feedback_label.configure(
                text="❌  Nenhum gateway detectado. Verifique a rede.",
                text_color=COLORS["status_error"],
            )
            return

        success, message, _ = open_router_page(self._gateway)

        if success:
            self.feedback_label.configure(
                text=f"✅  {message}",
                text_color=COLORS["status_ok"],
            )
        else:
            self.feedback_label.configure(
                text=f"❌  {message}",
                text_color=COLORS["status_error"],
            )

        self.after(8000, lambda: self.feedback_label.configure(text=""))

    def _update_log(self, text: str):
        """Atualiza o conteúdo do textbox de log."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.insert("1.0", text if text else "Log de varredura não disponível.")
        self.log_textbox.configure(state="disabled")

    def stop_monitoring(self):
        """Cancela o polling da GUI."""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
