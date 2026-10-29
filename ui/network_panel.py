"""
CedNet Help - Painel de Informações de Rede
Exibe informações de rede sincronizadas em tempo real via NetworkManager.
"""

import customtkinter as ctk
from modules.network_manager import network_manager
from modules.utils import COLORS, FONTS


class NetworkPanel(ctk.CTkFrame):
    """Painel de Informações de Rede sincronizado em tempo real."""

    UI_POLL_INTERVAL_MS = 300

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._last_seen_version: int = -1
        self._after_id: str | None = None

        self._info_labels: dict[str, ctk.CTkLabel] = {}
        self._create_ui()
        self._start_sync()

    def _create_ui(self):
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

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
            font=("Segoe UI", 24),
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

        info_grid = ctk.CTkFrame(container, fg_color="transparent")
        info_grid.pack(fill="x", pady=(0, 10))
        info_grid.columnconfigure((0, 1), weight=1)

        fields = [
            ("ipv4",      "Endereço IPv4",         "🌐", 0, 0),
            ("gateway",   "Gateway Padrão",        "🔀", 0, 1),
            ("mask",      "Máscara de Sub-rede",   "🔢", 1, 0),
            ("dns",       "Servidores DNS",        "📋", 1, 1),
            ("interface", "Interface de Rede",     "💻", 2, 0),
            ("speed",     "Velocidade de Link",    "⚡", 2, 1),
        ]

        for key, label, icon, row, col in fields:
            card = self._create_info_card(info_grid, key, label, icon)
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

    def _create_info_card(self, parent, key: str, label: str, icon: str) -> ctk.CTkFrame:
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

    def _start_sync(self):
        self._sync_with_manager()

    def _sync_with_manager(self):
        current_version = network_manager.version

        if current_version != self._last_seen_version:
            self._last_seen_version = current_version
            state = network_manager.get_state()
            self._apply_state(state)

        self._after_id = self.after(self.UI_POLL_INTERVAL_MS, self._sync_with_manager)

    def _apply_state(self, state: dict):
        status = state.get("status", {})
        connected = status.get("connected", False)

        if connected:
            self.status_emoji.configure(text="🟢")
            self.status_label.configure(
                text="Conectado à Internet",
                text_color=COLORS["status_ok"],
            )
            self.status_detail.configure(
                text="Conexão com a internet ativa e funcional",
                text_color=COLORS["text_secondary"],
            )
        else:
            self.status_emoji.configure(text="🔴")
            self.status_label.configure(
                text="Sem Conexão com a Internet",
                text_color=COLORS["status_error"],
            )
            self.status_detail.configure(
                text="Verifique os cabos ou consulte o provedor",
                text_color=COLORS["text_secondary"],
            )

        # Os dados do NetworkManager ficam na raiz do dicionário state
        details = state.get("details", {})
        
        # Obtém os valores com fallback tanto direto da raiz quanto de details
        ipv4_val = state.get("ipv4") or details.get("ipv4") or "Não disponível"
        gateway_val = state.get("gateway") or details.get("gateway") or "Não disponível"
        mask_val = state.get("mask") or details.get("mask") or "Não disponível"
        interface_val = state.get("interface") or details.get("interface") or "Não disponível"
        speed_val = state.get("speed") or details.get("speed") or "Não disponível"
        
        # DNS pode vir como string ou lista
        dns_raw = state.get("dns") or details.get("dns")
        if isinstance(dns_raw, list):
            dns_str = ", ".join(dns_raw) if dns_raw else "Nenhum"
        elif dns_raw:
            dns_str = str(dns_raw)
        else:
            dns_str = "Nenhum"

        field_values = {
            "ipv4": ipv4_val,
            "gateway": gateway_val,
            "mask": mask_val,
            "dns": dns_str,
            "interface": interface_val,
            "speed": speed_val,
        }

        for key, val in field_values.items():
            if key in self._info_labels:
                display_text = str(val) if val else "Não disponível"
                self._info_labels[key].configure(text=display_text)

    def _on_manual_refresh(self):
        self.btn_refresh.configure(state="disabled", text="Atualizando...")
        network_manager.force_refresh()
        self.after(600, self._restore_refresh_button)

    def _restore_refresh_button(self):
        self.btn_refresh.configure(state="normal", text="Atualizar Informações")

    def stop_monitoring(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
