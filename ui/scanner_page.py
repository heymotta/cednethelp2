"""Página do scanner nativo de descoberta Ubiquiti."""

import ctypes
import ipaddress
import queue
import subprocess
import threading
import time
import webbrowser
from tkinter import ttk

import customtkinter as ctk

from modules.utils import COLORS, FONTS
from scanner.discovery import UbiquitiDiscovery
from scanner.models import NetworkInterface, UbiquitiDevice


def _is_admin() -> bool:
    """Verifica se o processo está sendo executado como Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _set_static_ip(interface_name: str, ip: str, mask: str) -> tuple[bool, str]:
    """Altera o IP da interface de rede via netsh (requer privilégios de admin)."""
    try:
        cmd = (
            f'netsh interface ip set address name="{interface_name}" '
            f'static {ip} {mask}'
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="cp850",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=15,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
    except subprocess.TimeoutExpired:
        return False, "Tempo esgotado ao alterar o IP da interface."
    except Exception as exc:
        return False, str(exc)


def _compute_tech_ip(device_ip: str, suffix: int = 245) -> str:
    """Calcula o IP do técnico: mesma sub-rede do dispositivo com último octeto = suffix."""
    parts = device_ip.split(".")
    if len(parts) == 4:
        parts[3] = str(suffix)
        return ".".join(parts)
    return ""


class UbiquitiScannerPage(ctk.CTkFrame):
    """Interface não bloqueante para o protocolo UDP de descoberta Ubiquiti."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.discovery = UbiquitiDiscovery()
        self.interfaces: list[NetworkInterface] = []
        self.devices: dict[str, UbiquitiDevice] = {}
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._auto_id: str | None = None
        self._poll_id: str | None = None
        self._started = 0.0
        self._build()
        self._refresh_interfaces()
        self._poll_queue()

    def _build(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=5, pady=5)
        header = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        header.pack(fill="x", pady=(0, 10))
        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=14)
        ctk.CTkLabel(top, text="📡  Scanner Ubiquiti", font=FONTS["title"], text_color=COLORS["text_primary"]).pack(side="left")
        self.auto_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Atualizar automaticamente (5s)", variable=self.auto_var, font=FONTS["small_bold"], command=self._toggle_auto).pack(side="right")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkLabel(controls, text="Interface:", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.interface_var = ctk.StringVar()
        self.interface_combo = ctk.CTkComboBox(controls, variable=self.interface_var, values=["Detectando..."], width=260, state="readonly")
        self.interface_combo.pack(side="left", padx=(0, 8))
        self.scan_button = ctk.CTkButton(controls, text="Escanear", width=105, command=self._start_scan)
        self.scan_button.pack(side="left", padx=3)
        self.stop_button = ctk.CTkButton(controls, text="Parar", width=90, fg_color=COLORS["status_error"], hover_color="#c62828", command=self._stop_scan, state="disabled")
        self.stop_button.pack(side="left", padx=3)
        ctk.CTkButton(controls, text="Atualizar", width=105, fg_color=COLORS["bg_card_alt"], hover_color=COLORS["bg_card_hover"], command=self._refresh_and_scan).pack(side="left", padx=3)

        status = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=9)
        status.pack(fill="x", pady=(0, 8))
        self.count_label = ctk.CTkLabel(status, text="Dispositivos encontrados: 0", font=FONTS["body_bold"], text_color=COLORS["accent_cyan"])
        self.count_label.pack(side="left", padx=14, pady=9)
        self.time_label = ctk.CTkLabel(status, text="Tempo do scan: 0.0 segundos", font=FONTS["small"], text_color=COLORS["text_secondary"])
        self.time_label.pack(side="right", padx=14)

        search = ctk.CTkEntry(container, placeholder_text="Pesquisar por IP, nome, modelo ou firmware...", height=36, fg_color=COLORS["entry_bg"], border_color=COLORS["border"])
        search.pack(fill="x", pady=(0, 8))
        self.search_entry = search
        search.bind("<KeyRelease>", lambda _event: self._render())

        table_frame = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=9)
        table_frame.pack(fill="both", expand=True)
        columns = ("model", "ip", "mac", "name", "firmware", "protocol")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Ubiquiti.Treeview",
            background=COLORS["bg_card"],
            fieldbackground=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "Ubiquiti.Treeview.Heading",
            background=COLORS["bg_sidebar"],
            foreground=COLORS["text_primary"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            "Ubiquiti.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["text_primary"])],
        )

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", style="Ubiquiti.Treeview")
        headings = {"model": "Modelo", "ip": "Endereço IP", "mac": "MAC Address", "name": "Nome do equipamento", "firmware": "Firmware", "protocol": "Protocolo"}
        widths = {"model": 150, "ip": 120, "mac": 145, "name": 175, "firmware": 150, "protocol": 90}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tree.bind("<Double-1>", self._show_details)

    def _refresh_interfaces(self):
        self.interfaces = UbiquitiDiscovery.interfaces()
        values = [item.label for item in self.interfaces] or ["Nenhuma interface IPv4 ativa"]
        self.interface_combo.configure(values=values)
        self.interface_var.set(values[0])

    def _selected_interface(self) -> NetworkInterface | None:
        selected = self.interface_var.get()
        return next((item for item in self.interfaces if item.label == selected), None)

    def _refresh_and_scan(self):
        """Atualiza interfaces e inicia uma nova descoberta."""
        self._refresh_interfaces()
        self._start_scan()

    def _start_scan(self):
        interface = self._selected_interface()
        if not interface or self.discovery.is_running():
            return
        self._started = time.perf_counter()
        self.scan_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.discovery.scan(interface, lambda devices, elapsed: self._queue.put(("complete", (devices, elapsed))), lambda error: self._queue.put(("error", error)))

    def _stop_scan(self):
        self.discovery.stop()
        self.stop_button.configure(state="disabled")

    def _toggle_auto(self):
        if self.auto_var.get():
            self._schedule_auto()
        elif self._auto_id:
            self.after_cancel(self._auto_id)
            self._auto_id = None

    def _schedule_auto(self):
        if self.auto_var.get():
            self._auto_id = self.after(5000, self._auto_scan)

    def _auto_scan(self):
        self._auto_id = None
        self._start_scan()
        self._schedule_auto()

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "complete":
                    devices, elapsed = payload
                    self.devices.update({device.key: device for device in devices})
                    self.count_label.configure(text=f"Dispositivos encontrados: {len(self.devices)}")
                    self.time_label.configure(text=f"Tempo do scan: {elapsed:.1f} segundos")
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._render()
                elif kind == "error":
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.time_label.configure(text=f"Erro: {payload}")
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll_queue)

    def _render(self):
        query = self.search_entry.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)
        devices = sorted(self.devices.values(), key=lambda device: ipaddress.ip_address(device.ip))
        for device in devices:
            if query and query not in device.search_text():
                continue
            self.tree.insert("", "end", iid=device.key, values=(device.model or "-", device.ip, device.mac or "-", device.system_name or "-", device.firmware or "-", device.protocol_version or "-"))

    # ================================================================
    # Janela de Detalhes do Equipamento (Design Profissional)
    # ================================================================

    def _show_details(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        device = self.devices.get(selected[0])
        if not device:
            return

        interface = self._selected_interface()

        modal = ctk.CTkToplevel(self)
        modal.title(f"Detalhes — {device.system_name or device.ip}")
        modal.geometry("560x520")
        modal.configure(fg_color=COLORS["bg_main"])
        modal.transient(self.winfo_toplevel())
        modal.resizable(False, False)
        modal.grab_set()

        # ── Header com identidade do equipamento ──
        header_frame = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=14)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))

        header_inner = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_inner.pack(fill="x", padx=20, pady=18)

        # Ícone + info lado a lado
        icon_label = ctk.CTkLabel(
            header_inner, text="📡", font=("Segoe UI", 38),
            text_color=COLORS["accent_cyan"],
        )
        icon_label.pack(side="left", padx=(0, 16))

        info_block = ctk.CTkFrame(header_inner, fg_color="transparent")
        info_block.pack(side="left", fill="x", expand=True)

        # Nome do equipamento (destaque)
        device_name = device.system_name or "Dispositivo Ubiquiti"
        ctk.CTkLabel(
            info_block, text=device_name,
            font=("Segoe UI", 18, "bold"), text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        # Modelo
        if device.model:
            ctk.CTkLabel(
                info_block, text=device.model,
                font=("Segoe UI", 13), text_color=COLORS["accent_cyan"],
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        # IP em destaque
        ctk.CTkLabel(
            info_block, text=device.ip,
            font=("Consolas", 14, "bold"), text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        # ── Card: Informações do Equipamento ──
        equip_card = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=12)
        equip_card.pack(fill="x", padx=20, pady=(14, 0))

        ctk.CTkLabel(
            equip_card, text="🔧  Informações do Equipamento",
            font=("Segoe UI", 13, "bold"), text_color=COLORS["accent_cyan"],
            anchor="w",
        ).pack(anchor="w", padx=18, pady=(14, 8))

        equip_grid = ctk.CTkFrame(equip_card, fg_color="transparent")
        equip_grid.pack(fill="x", padx=18, pady=(0, 14))

        equip_fields = [
            ("Modelo", device.model),
            ("Nome (System Name)", device.system_name),
            ("Firmware", device.firmware),
            ("Plataforma", device.platform),
        ]
        for row_idx, (label, value) in enumerate(equip_fields):
            ctk.CTkLabel(
                equip_grid, text=f"{label}:", width=160, anchor="w",
                font=("Segoe UI", 12), text_color=COLORS["text_secondary"],
            ).grid(row=row_idx, column=0, sticky="w", pady=3)
            ctk.CTkLabel(
                equip_grid, text=value or "—", anchor="w",
                font=("Consolas", 12), text_color=COLORS["text_primary"],
            ).grid(row=row_idx, column=1, sticky="w", padx=(8, 0), pady=3)

        # ── Card: Informações de Rede ──
        net_card = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=12)
        net_card.pack(fill="x", padx=20, pady=(10, 0))

        ctk.CTkLabel(
            net_card, text="🌐  Informações de Rede",
            font=("Segoe UI", 13, "bold"), text_color=COLORS["accent_cyan"],
            anchor="w",
        ).pack(anchor="w", padx=18, pady=(14, 8))

        net_grid = ctk.CTkFrame(net_card, fg_color="transparent")
        net_grid.pack(fill="x", padx=18, pady=(0, 14))

        interface_label = interface.name if interface else "—"
        response_text = f"{device.response_ms:.1f} ms" if device.response_ms is not None else "—"
        discovered_text = device.discovered_at.strftime("%d/%m/%Y %H:%M:%S")

        net_fields = [
            ("Endereço IP", device.ip),
            ("MAC Address", device.mac),
            ("Interface utilizada", interface_label),
            ("Tempo de resposta", response_text),
            ("Última descoberta", discovered_text),
        ]
        for row_idx, (label, value) in enumerate(net_fields):
            ctk.CTkLabel(
                net_grid, text=f"{label}:", width=160, anchor="w",
                font=("Segoe UI", 12), text_color=COLORS["text_secondary"],
            ).grid(row=row_idx, column=0, sticky="w", pady=3)
            ctk.CTkLabel(
                net_grid, text=value or "—", anchor="w",
                font=("Consolas", 12), text_color=COLORS["text_primary"],
            ).grid(row=row_idx, column=1, sticky="w", padx=(8, 0), pady=3)

        # ── Botões na parte inferior ──
        btn_frame = ctk.CTkFrame(modal, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(16, 20))

        ctk.CTkButton(
            btn_frame, text="🌐  Abrir Interface Web", width=200,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=lambda: self._open_web_interface(device, interface, modal),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="📋  Copiar IP", width=120,
            font=("Segoe UI", 13),
            fg_color=COLORS["bg_card_alt"], hover_color=COLORS["bg_card_hover"],
            command=lambda: self._copy_to_clipboard(device.ip, modal),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="✕  Fechar", width=100,
            font=("Segoe UI", 13),
            fg_color="#2a2a3e", hover_color="#3a3a50",
            command=modal.destroy,
        ).pack(side="right")

    # ================================================================
    # Copiar IP para a área de transferência
    # ================================================================

    def _copy_to_clipboard(self, text: str, modal: ctk.CTkToplevel):
        """Copia o texto para a área de transferência e dá feedback visual."""
        modal.clipboard_clear()
        modal.clipboard_append(text)
        modal.update()

        # Feedback visual temporário no title bar
        original_title = modal.title()
        modal.title("✓  IP copiado!")
        modal.after(1500, lambda: modal.title(original_title))

    # ================================================================
    # Abrir Interface Web com troca automática de IP
    # ================================================================

    def _open_web_interface(self, device: UbiquitiDevice, interface: NetworkInterface | None, modal: ctk.CTkToplevel):
        """Configura o IP da interface para a mesma sub-rede do rádio (.245) e abre o navegador."""
        if not interface:
            self._show_status_message(modal, "Nenhuma interface de rede selecionada.", is_error=True)
            return

        tech_ip = _compute_tech_ip(device.ip, suffix=245)
        if not tech_ip:
            self._show_status_message(modal, "Não foi possível calcular o IP do técnico.", is_error=True)
            return

        # Verificar se a interface já está na sub-rede correta (mesmo /24 com .245)
        current_ip = interface.address
        current_subnet = ".".join(current_ip.split(".")[:3])
        target_subnet = ".".join(device.ip.split(".")[:3])

        if current_subnet == target_subnet and current_ip.split(".")[-1] == "245":
            # Já está configurado corretamente — abrir direto
            webbrowser.open(f"http://{device.ip}")
            return

        # Verificar permissões de administrador
        if not _is_admin():
            self._show_status_message(
                modal,
                "⚠  Permissão necessária!\n\n"
                "Para alterar o IP da interface de rede automaticamente, "
                "o CedNet Help precisa ser executado como Administrador.\n\n"
                "Clique com o botão direito no atalho → Executar como administrador.",
                is_error=True,
                large=True,
            )
            return

        # Mostrar progresso no modal
        self._show_ip_change_progress(modal, device, interface, tech_ip)

    def _show_ip_change_progress(
        self,
        modal: ctk.CTkToplevel,
        device: UbiquitiDevice,
        interface: NetworkInterface,
        tech_ip: str,
    ):
        """Exibe progresso da alteração de IP e executa em background."""
        # Criar overlay de progresso sobre o modal
        overlay = ctk.CTkFrame(modal, fg_color=COLORS["bg_main"])
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        inner = ctk.CTkFrame(overlay, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            inner, text="🔄", font=("Segoe UI", 42),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            inner, text="Configurando rede...",
            font=("Segoe UI", 16, "bold"), text_color=COLORS["text_primary"],
        ).pack(pady=(0, 8))

        status_label = ctk.CTkLabel(
            inner,
            text=f"Alterando IP da interface '{interface.name}'\npara {tech_ip} / 255.255.255.0",
            font=("Segoe UI", 12), text_color=COLORS["text_secondary"],
            justify="center",
        )
        status_label.pack(pady=(0, 16))

        progress = ctk.CTkProgressBar(inner, width=300, mode="indeterminate")
        progress.pack(pady=(0, 8))
        progress.start()

        def _worker():
            mask = "255.255.255.0"
            success, error_msg = _set_static_ip(interface.name, tech_ip, mask)

            if success:
                # Aguardar o Windows aplicar a configuração
                time.sleep(2.0)
                # Abrir o navegador
                webbrowser.open(f"http://{device.ip}")

                # Atualizar UI no thread principal
                modal.after(0, lambda: _on_success())
            else:
                modal.after(0, lambda: _on_error(error_msg))

        def _on_success():
            progress.stop()
            status_label.configure(
                text=f"✅  IP alterado para {tech_ip}\nAbrindo http://{device.ip} no navegador...",
                text_color=COLORS["status_ok"],
            )
            # Fechar overlay após 2 segundos
            modal.after(2000, overlay.destroy)

        def _on_error(error_msg: str):
            progress.stop()
            progress.pack_forget()
            status_label.configure(
                text=f"❌  Erro ao alterar o IP da interface\n\n{error_msg}",
                text_color=COLORS["status_error"],
            )
            ctk.CTkButton(
                inner, text="Fechar", width=100,
                fg_color=COLORS["bg_card_alt"], hover_color=COLORS["bg_card_hover"],
                command=overlay.destroy,
            ).pack(pady=(8, 0))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_status_message(
        self,
        modal: ctk.CTkToplevel,
        message: str,
        is_error: bool = False,
        large: bool = False,
    ):
        """Exibe uma mensagem de status ou erro em um overlay temporário."""
        overlay = ctk.CTkFrame(modal, fg_color=COLORS["bg_main"])
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        inner = ctk.CTkFrame(overlay, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        icon = "❌" if is_error else "✅"
        color = COLORS["status_error"] if is_error else COLORS["status_ok"]

        ctk.CTkLabel(
            inner, text=icon, font=("Segoe UI", 36),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            inner, text=message,
            font=("Segoe UI", 12), text_color=color,
            justify="center", wraplength=420 if large else 320,
        ).pack(pady=(0, 16))

        ctk.CTkButton(
            inner, text="Entendi", width=100,
            fg_color=COLORS["bg_card_alt"], hover_color=COLORS["bg_card_hover"],
            command=overlay.destroy,
        ).pack()

    def stop_monitoring(self):
        self.auto_var.set(False)
        if self._auto_id:
            self.after_cancel(self._auto_id)
            self._auto_id = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self.discovery.stop()
