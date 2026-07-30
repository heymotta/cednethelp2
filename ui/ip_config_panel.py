"""
CedNet Help - Painel de Configuração de IP (Sincronizado)
Permite ao técnico alterar o IP estático ou restaurar DHCP de forma simplificada,
mantendo todas as informações de rede e status da interface 100% sincronizadas
em tempo real com o NetworkManager.
"""

import customtkinter as ctk
import threading
import ipaddress
from modules.ip_config import (
    get_all_interfaces,
    get_default_interface_name,
    get_interface_config,
    set_static_ip,
    restore_dhcp,
    is_admin,
)
from modules.network_manager import network_manager
from modules.utils import COLORS, FONTS


class IPConfigPanel(ctk.CTkFrame):
    """
    Painel simplificado de configuração de IP.
    Sincronizado em tempo real com o NetworkManager centralizado.
    """

    UI_POLL_INTERVAL_MS = 300

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._interfaces: list[dict] = []
        self._selected_iface: str = ""
        self._is_applying: bool = False
        self._last_seen_version: int = -1
        self._after_id: str | None = None

        # Variáveis para threading segura do botão aplicar/restaurar
        self._operation_done: bool = False
        self._operation_result: tuple = (False, "")
        self._operation_type: str = ""

        self._create_ui()
        self._start_sync()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface simplificada e responsiva."""
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
            text="⚙️  Configuração de IP",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        # ---- Aviso de admin (se não for administrador) ----
        if not is_admin():
            admin_frame = ctk.CTkFrame(
                container,
                fg_color="#3d1a1a",
                corner_radius=10,
                border_width=1,
                border_color=COLORS["status_error"],
            )
            admin_frame.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(
                admin_frame,
                text="⚠️  Execute como Administrador para alterar configurações de rede.\n"
                     "     Clique direito no programa → Executar como administrador.",
                font=FONTS["small"],
                text_color=COLORS["status_error"],
                anchor="w",
                justify="left",
                wraplength=650,
            ).pack(padx=15, pady=10)

        # ---- Card de Info Atual Sincronizado ----
        self.info_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        self.info_card.pack(fill="x", pady=(0, 12))

        info_inner = ctk.CTkFrame(self.info_card, fg_color="transparent")
        info_inner.pack(fill="x", padx=20, pady=15)

        info_header = ctk.CTkFrame(info_inner, fg_color="transparent")
        info_header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            info_header,
            text="📋  Configuração Atual (Sincronizada)",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.config_type_label = ctk.CTkLabel(
            info_header,
            text="Verificando...",
            font=FONTS["small_bold"],
            anchor="e",
        )
        self.config_type_label.pack(side="right")

        # Info grid
        info_grid = ctk.CTkFrame(info_inner, fg_color="transparent")
        info_grid.pack(fill="x")
        info_grid.columnconfigure((0, 1, 2), weight=1)

        self._info_labels: dict[str, ctk.CTkLabel] = {}
        info_fields = [
            ("ipv4",    "IPv4",     0),
            ("mask",    "Máscara",  1),
            ("gateway", "Gateway",  2),
        ]

        for key, label, col in info_fields:
            cell = ctk.CTkFrame(info_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
            cell.grid(row=0, column=col, padx=3, pady=3, sticky="nsew")

            inner = ctk.CTkFrame(cell, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=8)

            ctk.CTkLabel(
                inner, text=label,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w")

            val = ctk.CTkLabel(
                inner, text="Carregando...",
                font=FONTS["mono"],
                text_color=COLORS["accent_cyan"],
                anchor="w",
            )
            val.pack(anchor="w", pady=(2, 0))
            self._info_labels[key] = val

        # ---- Card Principal — Configuração ----
        config_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        config_card.pack(fill="x", pady=(0, 12))

        config_inner = ctk.CTkFrame(config_card, fg_color="transparent")
        config_inner.pack(fill="x", padx=25, pady=20)

        # Interface de rede
        ctk.CTkLabel(
            config_inner,
            text="Interface de Rede",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.iface_combo = ctk.CTkComboBox(
            config_inner,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            height=40,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_sidebar"],
            dropdown_hover_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            command=self._on_interface_changed,
            state="readonly",
        )
        self.iface_combo.pack(fill="x", pady=(0, 15))

        # Endereço IP
        ctk.CTkLabel(
            config_inner,
            text="Endereço IP Desejado",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.ip_entry = ctk.CTkEntry(
            config_inner,
            font=("Consolas", 16),
            height=46,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="Ex: 192.168.1.10",
            justify="center",
        )
        self.ip_entry.pack(fill="x", pady=(0, 5))

        # Info de cálculo automático
        self.auto_info = ctk.CTkLabel(
            config_inner,
            text="Máscara, gateway e DNS serão configurados automaticamente",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        )
        self.auto_info.pack(pady=(0, 15))

        # Botões de Ação
        self.btn_apply = ctk.CTkButton(
            config_inner,
            text="Aplicar IP",
            font=FONTS["body_bold"],
            height=48,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._apply_ip,
        )
        self.btn_apply.pack(fill="x", pady=(0, 8))

        self.btn_dhcp = ctk.CTkButton(
            config_inner,
            text="Restaurar DHCP (Automático)",
            font=FONTS["body_bold"],
            height=48,
            corner_radius=10,
            fg_color="#1b5e20",
            hover_color="#2e7d32",
            command=self._confirm_restore_dhcp,
        )
        self.btn_dhcp.pack(fill="x")

        # ---- Feedback ----
        self.feedback_label = ctk.CTkLabel(
            container,
            text="",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            wraplength=700,
        )
        self.feedback_label.pack(pady=(5, 5))

        # ---- Log ----
        log_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        log_card.pack(fill="x")

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            log_header,
            text="📝  Log de Operações",
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
            height=120,
            state="disabled",
            wrap="word",
        )
        self.log_textbox.pack(fill="x", padx=20, pady=(0, 15))

    # ================================================================
    # Sincronização em Tempo Real com NetworkManager
    # ================================================================

    def _start_sync(self):
        """Inicia a sincronização automatizada com o NetworkManager."""
        self._check_network_manager()

    def _check_network_manager(self):
        """
        Polling thread-safe na GUI thread.
        Sincroniza as interfaces e as informações de IP sempre que
        houver qualquer mudança na rede detectada pelo NetworkManager.
        """
        current_version = network_manager.version

        if current_version != self._last_seen_version:
            self._last_seen_version = current_version
            self._sync_state(network_manager.get_state())

        self._after_id = self.after(self.UI_POLL_INTERVAL_MS, self._check_network_manager)

    def _sync_state(self, state: dict):
        """Sincroniza a lista de interfaces e os dados exibidos."""
        # 1. Recarrega a lista de interfaces no ComboBox com os status atualizados (🟢/🔴)
        self._interfaces = get_all_interfaces()

        if not self._interfaces:
            self.iface_combo.configure(values=["Nenhuma interface encontrada"])
            self._render_disconnected_state()
            return

        names = [
            f"{'🟢' if iface['is_up'] else '🔴'} {iface['name']} ({iface['type_hint']})"
            for iface in self._interfaces
        ]
        self.iface_combo.configure(values=names)

        # Se nenhuma interface foi selecionada pelo usuário ainda, escolhe a padrão
        if not self._selected_iface:
            default_iface = get_default_interface_name()
            for i, iface in enumerate(self._interfaces):
                if iface["name"] == default_iface:
                    self.iface_combo.set(names[i])
                    self._selected_iface = default_iface
                    break
            else:
                self.iface_combo.set(names[0])
                self._selected_iface = self._interfaces[0]["name"]
        else:
            # Mantém a seleção do usuário sincronizada no ComboBox
            for i, iface in enumerate(self._interfaces):
                if iface["name"] == self._selected_iface:
                    self.iface_combo.set(names[i])
                    break

        # 2. Atualiza a exibição da interface selecionada
        self._update_displayed_config(state)

    def _update_displayed_config(self, state: dict):
        """
        Atualiza as labels de IPv4, Máscara, Gateway e DHCP/Estático
        de acordo com o estado central sincronizado.
        """
        if not self._selected_iface:
            self._render_disconnected_state()
            return

        # Verifica se a interface selecionada é a ativa que o NetworkManager está monitorando
        active_iface = state.get("interface", "")

        if self._selected_iface == active_iface:
            # Consome diretamente o estado centralizado do NetworkManager
            status_dict = state.get("status", {})
            is_connected = status_dict.get("connected", False)

            if is_connected:
                ipv4 = state.get("ipv4", "")
                mask = state.get("mask", "")
                gateway = state.get("gateway", "")

                self._info_labels["ipv4"].configure(
                    text=ipv4 if ipv4 and ipv4 != "Não disponível" else "—",
                    text_color=COLORS["accent_cyan"],
                )
                self._info_labels["mask"].configure(
                    text=mask if mask and mask != "Não disponível" else "—",
                    text_color=COLORS["accent_cyan"],
                )
                self._info_labels["gateway"].configure(
                    text=gateway if gateway and gateway != "Não disponível" else "—",
                    text_color=COLORS["accent_cyan"],
                )

                # Tipo de Configuração (DHCP ou Estático)
                cfg = get_interface_config(self._selected_iface)
                if cfg.get("is_dhcp", True):
                    self.config_type_label.configure(
                        text="🟢 DHCP (Automático)",
                        text_color=COLORS["status_ok"],
                    )
                else:
                    self.config_type_label.configure(
                        text="🟡 IP Estático (Manual)",
                        text_color=COLORS["status_warning"],
                    )
            else:
                self._render_disconnected_state()
        else:
            # Caso a interface selecionada seja secundária, busca sua config via netsh
            cfg = get_interface_config(self._selected_iface)
            if cfg.get("status") == "Conectada":
                self._info_labels["ipv4"].configure(text=cfg.get("ipv4") or "—", text_color=COLORS["accent_cyan"])
                self._info_labels["mask"].configure(text=cfg.get("mask") or "—", text_color=COLORS["accent_cyan"])
                self._info_labels["gateway"].configure(text=cfg.get("gateway") or "—", text_color=COLORS["accent_cyan"])
                if cfg.get("is_dhcp"):
                    self.config_type_label.configure(text="🟢 DHCP", text_color=COLORS["status_ok"])
                else:
                    self.config_type_label.configure(text="🟡 IP Estático", text_color=COLORS["status_warning"])
            else:
                self._render_disconnected_state()

    def _render_disconnected_state(self):
        """Atualiza a UI para refletir estado de desconexão."""
        self._info_labels["ipv4"].configure(text="— (Desconectado)", text_color=COLORS["status_error"])
        self._info_labels["mask"].configure(text="—", text_color=COLORS["text_secondary"])
        self._info_labels["gateway"].configure(text="—", text_color=COLORS["text_secondary"])
        self.config_type_label.configure(text="🔴 Desconectada", text_color=COLORS["status_error"])

    def _on_interface_changed(self, selection: str):
        """Callback quando o usuário altera manualmente a interface no ComboBox."""
        for iface in self._interfaces:
            if iface["name"] in selection:
                self._selected_iface = iface["name"]
                break
        self._update_displayed_config(network_manager.get_state())

    # ================================================================
    # Cálculo Automático
    # ================================================================

    @staticmethod
    def _auto_calculate(ip_str: str) -> tuple[str, str, str, str, str]:
        """
        Calcula máscara, gateway e DNS a partir do IP informado.

        Args:
            ip_str: Endereço IP (ex: "192.168.1.10")

        Returns:
            Tupla (ip, mask, gateway, dns1, dns2)
        """
        mask = "255.255.255.0"
        parts = ip_str.strip().rsplit(".", 1)
        gateway = f"{parts[0]}.1"
        dns1 = gateway
        dns2 = "8.8.8.8"
        return ip_str.strip(), mask, gateway, dns1, dns2

    # ================================================================
    # Aplicar IP Estático
    # ================================================================

    def _apply_ip(self):
        """Valida o IP, calcula o restante e aplica."""
        if self._is_applying:
            return

        if not self._selected_iface:
            self._show_feedback("❌ Nenhuma interface selecionada.", error=True)
            return

        ip = self.ip_entry.get().strip()

        if not ip:
            self._show_feedback("❌ Informe um endereço IP.", error=True)
            return

        try:
            addr = ipaddress.IPv4Address(ip)
            if addr.is_loopback or addr.is_unspecified:
                self._show_feedback("❌ Endereço IP inválido.", error=True)
                return
        except (ipaddress.AddressValueError, ValueError):
            self._show_feedback("❌ Formato de IP inválido. Use ex: 192.168.1.10", error=True)
            return

        ip, mask, gateway, dns1, dns2 = self._auto_calculate(ip)

        self._is_applying = True
        self._operation_done = False
        self._operation_type = "static"
        self.btn_apply.configure(state="disabled", text="⏳  Aplicando...")
        self.btn_dhcp.configure(state="disabled")

        self._append_log(
            f"\nAplicando IP estático em '{self._selected_iface}':\n"
            f"  IP: {ip}  Máscara: {mask}\n"
            f"  Gateway: {gateway}  DNS: {dns1}, {dns2}\n"
        )

        thread = threading.Thread(
            target=self._run_operation_thread,
            args=("static", self._selected_iface, ip, mask, gateway, dns1, dns2),
            daemon=True,
        )
        thread.start()

        self._poll_operation_result()

    # ================================================================
    # Restaurar DHCP
    # ================================================================

    def _confirm_restore_dhcp(self):
        """Exibe confirmação antes de restaurar DHCP."""
        if self._is_applying or not self._selected_iface:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirmar Restauração")
        dialog.geometry("420x200")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_main"])
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="⚠️  Restaurar DHCP?",
            font=FONTS["subtitle"],
            text_color=COLORS["status_warning"],
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text=f"A interface '{self._selected_iface}' voltará a\n"
                 f"obter IP automaticamente (DHCP).",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            justify="center",
        ).pack(pady=(0, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30)
        btn_frame.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            font=FONTS["body_bold"],
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=dialog.destroy,
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew")

        ctk.CTkButton(
            btn_frame,
            text="Confirmar",
            font=FONTS["body_bold"],
            height=38,
            corner_radius=8,
            fg_color="#1b5e20",
            hover_color="#2e7d32",
            command=lambda: self._do_restore_dhcp(dialog),
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _do_restore_dhcp(self, dialog):
        """Executa restauração DHCP."""
        dialog.destroy()

        self._is_applying = True
        self._operation_done = False
        self._operation_type = "dhcp"
        self.btn_apply.configure(state="disabled")
        self.btn_dhcp.configure(state="disabled", text="⏳  Restaurando...")

        self._append_log(f"\nRestaurando DHCP em '{self._selected_iface}'...\n")

        thread = threading.Thread(
            target=self._run_operation_thread,
            args=("dhcp", self._selected_iface),
            daemon=True,
        )
        thread.start()

        self._poll_operation_result()

    # ================================================================
    # Threading Segura — Polling Pattern
    # ================================================================

    def _run_operation_thread(self, op_type: str, iface: str, *args):
        """Thread de operação de rede."""
        try:
            if op_type == "static":
                ip, mask, gw, dns1, dns2 = args
                success, log_text = set_static_ip(iface, ip, mask, gw, dns1, dns2)
            else:
                success, log_text = restore_dhcp(iface)
        except Exception as e:
            success = False
            log_text = f"❌ Erro inesperado: {str(e)}"

        self._operation_result = (success, log_text)
        self._operation_done = True

    def _poll_operation_result(self):
        """Polling na thread principal — verifica término de aplicar/restaurar."""
        if self._operation_done:
            success, log_text = self._operation_result
            self._on_operation_complete(success, log_text)
        else:
            self.after(200, self._poll_operation_result)

    def _on_operation_complete(self, success: bool, log_text: str):
        """Callback pós-operação — força refresh no NetworkManager."""
        self._is_applying = False
        self._append_log(log_text)

        self.btn_apply.configure(state="normal", text="Aplicar IP")
        self.btn_dhcp.configure(state="normal", text="Restaurar DHCP (Automático)")

        if success:
            op = "IP aplicado" if self._operation_type == "static" else "DHCP restaurado"
            self._show_feedback(f"✅ {op} com sucesso!", error=False)
            # Força o NetworkManager a atualizar imediatamente para propagar a todas as abas
            network_manager.force_refresh()
        else:
            self._show_feedback("❌ Falha na operação. Veja o log.", error=True)

    # ================================================================
    # Feedback, Log e Encerramento
    # ================================================================

    def _show_feedback(self, message: str, error: bool = False):
        """Exibe mensagem temporária de feedback."""
        color = COLORS["status_error"] if error else COLORS["status_ok"]
        self.feedback_label.configure(text=message, text_color=color)
        self.after(8000, lambda: self.feedback_label.configure(text=""))

    def _append_log(self, text: str):
        """Adiciona texto ao log de operações."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def stop_monitoring(self):
        """Cancela o polling da GUI thread ao fechar o app."""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
