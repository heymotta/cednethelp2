"""Página do scanner nativo de descoberta Ubiquiti."""

import ctypes
import ipaddress
import queue
import subprocess
import threading
import time
import tkinter as tk
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


# ================================================================
# Detecção do Rádio Conectado Diretamente ao Notebook
# ================================================================

def _get_arp_macs_for_interface(interface_ip: str) -> set[str]:
    """Obtém os MAC Addresses da tabela ARP para uma interface específica.

    Executa `arp -a -N <interface_ip>` e extrai os MACs encontrados.
    Retorna um set de MACs normalizados em uppercase (AA:BB:CC:DD:EE:FF).
    """
    macs: set[str] = set()
    try:
        output = subprocess.check_output(
            f"arp -a -N {interface_ip}",
            encoding="cp850",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=3,
        )
        import re
        # Padrão de MAC no ARP do Windows: aa-bb-cc-dd-ee-ff
        for match in re.finditer(r"([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})", output):
            mac = match.group(1).upper().replace("-", ":")
            # Ignorar broadcast FF:FF:FF:FF:FF:FF
            if mac != "FF:FF:FF:FF:FF:FF":
                macs.add(mac)
    except Exception:
        pass
    return macs


def _identify_connected_device(
    devices: list[UbiquitiDevice],
    interface: NetworkInterface | None,
) -> UbiquitiDevice | None:
    """Identifica qual dispositivo está fisicamente conectado ao notebook.

    Algoritmo multi-critério com pontuação:
    1. Tabela ARP: se o MAC do dispositivo está na ARP da interface → +40 pontos
    2. Menor tempo de resposta (response_ms) → +30 pontos (apenas para o mais rápido)
    3. Resposta extremamente rápida (<5ms) → +20 pontos
    4. Diferença significativa de latência vs segundo mais rápido → +10 pontos

    Limiar de confiança: precisa de pelo menos 50 pontos para ser considerado confiável.
    """
    if not devices or not interface:
        return None

    # Filtrar apenas dispositivos com response_ms válido
    valid_devices = [d for d in devices if d.response_ms is not None and d.mac]
    if not valid_devices:
        return None

    # Se há apenas um dispositivo, é certamente o conectado
    if len(valid_devices) == 1:
        return valid_devices[0]

    # Critério 1: Tabela ARP da interface
    arp_macs = _get_arp_macs_for_interface(interface.address)

    # Calcular pontuação para cada dispositivo
    scores: dict[str, float] = {}
    for device in valid_devices:
        score = 0.0
        mac_normalized = device.mac.upper().replace("-", ":")

        # ARP: MAC presente na tabela ARP da interface (+40)
        if arp_macs and mac_normalized in arp_macs:
            score += 40.0

        scores[device.key] = score

    # Critério 2 & 3: Latência
    sorted_by_latency = sorted(valid_devices, key=lambda d: d.response_ms or 9999)
    fastest = sorted_by_latency[0]

    # O mais rápido ganha +30
    scores[fastest.key] = scores.get(fastest.key, 0) + 30.0

    # Se a latência é extremamente baixa (<5ms), +20
    if fastest.response_ms is not None and fastest.response_ms < 5.0:
        scores[fastest.key] += 20.0

    # Critério 4: Diferença significativa vs o segundo
    if len(sorted_by_latency) >= 2:
        second = sorted_by_latency[1]
        if (fastest.response_ms is not None and second.response_ms is not None
                and second.response_ms > 0):
            ratio = second.response_ms / max(fastest.response_ms, 0.1)
            # Se o segundo é pelo menos 2x mais lento → +10
            if ratio >= 2.0:
                scores[fastest.key] += 10.0

    # Encontrar o dispositivo com maior pontuação
    if not scores:
        return None

    best_key = max(scores, key=lambda k: scores[k])
    best_score = scores[best_key]

    # Limiar de confiança: mínimo 50 pontos
    if best_score < 50.0:
        return None

    return next((d for d in valid_devices if d.key == best_key), None)


# ================================================================
# Classe Principal: UbiquitiScannerPage
# ================================================================

class UbiquitiScannerPage(ctk.CTkFrame):
    """Interface não bloqueante para o protocolo UDP de descoberta Ubiquiti."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.discovery = UbiquitiDiscovery()
        self.interfaces: list[NetworkInterface] = []
        self.devices: dict[str, UbiquitiDevice] = {}
        self._connected_device: UbiquitiDevice | None = None
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

        # ── Header ──
        header = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        header.pack(fill="x", pady=(0, 10))
        self.header_frame = header
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

        # ── Card do equipamento conectado (inicialmente oculto) ──
        self.connected_card = ctk.CTkFrame(container, fg_color="#0d3b66", corner_radius=10, border_width=1, border_color="#1a73e8")
        # NÃO empacotar ainda — será mostrado apenas quando houver detecção

        self.connected_card_inner = ctk.CTkFrame(self.connected_card, fg_color="transparent")
        self.connected_card_inner.pack(fill="x", padx=16, pady=12)

        # Ícone + título
        self.cc_header = ctk.CTkFrame(self.connected_card_inner, fg_color="transparent")
        self.cc_header.pack(fill="x")

        ctk.CTkLabel(
            self.cc_header, text="⭐", font=("Segoe UI", 20),
        ).pack(side="left", padx=(0, 8))

        self.cc_title_block = ctk.CTkFrame(self.cc_header, fg_color="transparent")
        self.cc_title_block.pack(side="left", fill="x", expand=True)

        self.cc_label_title = ctk.CTkLabel(
            self.cc_title_block, text="Equipamento Conectado",
            font=("Segoe UI", 11, "bold"), text_color="#4caf50", anchor="w",
        )
        self.cc_label_title.pack(anchor="w")

        self.cc_label_name = ctk.CTkLabel(
            self.cc_title_block, text="—",
            font=("Segoe UI", 14, "bold"), text_color=COLORS["text_primary"], anchor="w",
        )
        self.cc_label_name.pack(anchor="w")

        # Info grid
        self.cc_info = ctk.CTkFrame(self.connected_card_inner, fg_color="transparent")
        self.cc_info.pack(fill="x", pady=(8, 0))

        self.cc_fields: dict[str, ctk.CTkLabel] = {}
        field_defs = [
            ("IP", 0, 0), ("Firmware", 0, 2),
            ("MAC", 1, 0), ("Interface", 1, 2),
        ]
        for label, row, col in field_defs:
            lbl = ctk.CTkLabel(
                self.cc_info, text=f"{label}:", anchor="w",
                font=("Segoe UI", 10), text_color=COLORS["text_secondary"],
            )
            lbl.grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 20, 4), pady=2)
            val = ctk.CTkLabel(
                self.cc_info, text="—", anchor="w",
                font=("Consolas", 10, "bold"), text_color=COLORS["text_primary"],
            )
            val.grid(row=row, column=col + 1, sticky="w", pady=2)
            self.cc_fields[label] = val

        # ── Status bar ──
        status = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=9)
        status.pack(fill="x", pady=(0, 8))
        self.count_label = ctk.CTkLabel(status, text="Dispositivos encontrados: 0", font=FONTS["body_bold"], text_color=COLORS["accent_cyan"])
        self.count_label.pack(side="left", padx=14, pady=9)
        self.time_label = ctk.CTkLabel(status, text="Tempo do scan: 0.0 segundos", font=FONTS["small"], text_color=COLORS["text_secondary"])
        self.time_label.pack(side="right", padx=14)

        # ── Search ──
        search = ctk.CTkEntry(container, placeholder_text="Pesquisar por IP, nome, modelo ou firmware...", height=36, fg_color=COLORS["entry_bg"], border_color=COLORS["border"])
        search.pack(fill="x", pady=(0, 8))
        self.search_entry = search
        search.bind("<KeyRelease>", lambda _event: self._render())

        # ── Table ──
        table_frame = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=9)
        table_frame.pack(fill="both", expand=True)
        columns = ("status", "model", "ip", "mac", "name", "firmware")
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
        headings = {
            "status": "",
            "model": "Modelo",
            "ip": "Endereço IP",
            "mac": "MAC Address",
            "name": "Nome do equipamento",
            "firmware": "Firmware",
        }
        widths = {
            "status": 28,
            "model": 160,
            "ip": 120,
            "mac": 145,
            "name": 175,
            "firmware": 150,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "center" if col == "status" else "w"
            self.tree.column(col, width=widths[col], anchor=anchor, minwidth=widths[col])

        # Tag para linha do dispositivo conectado (destaque visual)
        self.tree.tag_configure("connected", background="#0d3b66", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("normal", background=COLORS["bg_card"], foreground=COLORS["text_primary"])

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

    # ================================================================
    # Interface / Scan Controls
    # ================================================================

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
        # Limpar cache e registros antigos completamente para nova varredura
        self.devices.clear()
        self._connected_device = None
        self._hide_connected_card()
        self.count_label.configure(text="Dispositivos encontrados: 0")
        self.time_label.configure(text="Escaneando...")
        self._render()
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
                    # Substituir completamente os dispositivos encontrados nesta varredura
                    self.devices = {device.key: device for device in devices}
                    self.count_label.configure(text=f"Dispositivos encontrados: {len(self.devices)}")
                    self.time_label.configure(text=f"Tempo do scan: {elapsed:.1f} segundos")
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    # Detectar rádio conectado
                    self._detect_connected_device()
                    self._render()
                elif kind == "error":
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.time_label.configure(text=f"Erro: {payload}")
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll_queue)

    # ================================================================
    # Detecção do Rádio Conectado
    # ================================================================

    def _detect_connected_device(self):
        """Executa a detecção do rádio conectado diretamente ao notebook."""
        interface = self._selected_interface()
        all_devices = list(self.devices.values())

        self._connected_device = _identify_connected_device(all_devices, interface)

        if self._connected_device:
            self._show_connected_card(self._connected_device, interface)
        else:
            self._hide_connected_card()

    def _show_connected_card(self, device: UbiquitiDevice, interface: NetworkInterface | None):
        """Exibe o card com informações do rádio conectado."""
        name = device.system_name or device.model or "Dispositivo Ubiquiti"
        self.cc_label_name.configure(text=f"⭐  {name}")

        self.cc_fields["IP"].configure(text=device.ip)
        self.cc_fields["Firmware"].configure(text=device.firmware or "—")
        self.cc_fields["MAC"].configure(text=device.mac or "—")
        self.cc_fields["Interface"].configure(text=interface.name if interface else "—")

        if not self.connected_card.winfo_ismapped():
            self.connected_card.pack(fill="x", pady=(0, 8), after=self.header_frame)

    def _hide_connected_card(self):
        """Oculta o card do rádio conectado."""
        if self.connected_card.winfo_ismapped():
            self.connected_card.pack_forget()

    # ================================================================
    # Renderização da Tabela
    # ================================================================

    def _render(self):
        query = self.search_entry.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        def _safe_ip_key(device: UbiquitiDevice):
            try:
                return ipaddress.ip_address(device.ip)
            except Exception:
                return ipaddress.ip_address("0.0.0.0")

        all_devices = sorted(self.devices.values(), key=_safe_ip_key)

        # Separar: conectado primeiro, depois os demais
        connected_key = self._connected_device.key if self._connected_device else None
        connected_list = []
        other_list = []

        for device in all_devices:
            if query and query not in device.search_text():
                continue
            if device.key == connected_key:
                connected_list.append(device)
            else:
                other_list.append(device)

        # Renderizar: conectado no topo, depois os demais
        for device in connected_list + other_list:
            is_connected = device.key == connected_key
            status_icon = "⭐" if is_connected else ""
            model_text = device.model or "-"
            tag = "connected" if is_connected else "normal"

            self.tree.insert(
                "", "end", iid=device.key,
                values=(
                    status_icon,
                    model_text,
                    device.ip,
                    device.mac or "-",
                    device.system_name or "-",
                    device.firmware or "-",
                ),
                tags=(tag,),
            )

        self.update_idletasks()

    # ================================================================
    # Menu de Contexto (Botão Direito)
    # ================================================================

    def _on_right_click(self, event):
        """Exibe o menu de contexto ao clicar com o botão direito em um dispositivo."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # Selecionar a linha clicada
        self.tree.selection_set(item)
        self.tree.focus(item)

        device = self.devices.get(item)
        if not device:
            return

        # Criar menu de contexto nativo
        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["text_primary"],
                       font=("Segoe UI", 10),
                       relief="flat", bd=1)

        menu.add_command(
            label="🌐  Abrir Interface Web",
            command=lambda: self._open_web_for_device(device),
            font=("Segoe UI", 10, "bold"),
        )
        menu.add_separator()
        menu.add_command(
            label="📋  Copiar IP",
            command=lambda: self._copy_to_clipboard(device.ip),
        )
        menu.add_command(
            label="📋  Copiar MAC",
            command=lambda: self._copy_to_clipboard(device.mac or ""),
        )

        # Exibir na posição do cursor
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ================================================================
    # Duplo Clique → Abrir Interface Web diretamente
    # ================================================================

    def _on_double_click(self, _event=None):
        """Duplo clique abre a interface web do rádio selecionado."""
        selected = self.tree.selection()
        if not selected:
            return
        device = self.devices.get(selected[0])
        if not device:
            return
        self._open_web_for_device(device)

    # ================================================================
    # Copiar para a área de transferência
    # ================================================================

    def _copy_to_clipboard(self, text: str):
        """Copia o texto para a área de transferência com feedback visual na status bar."""
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        # Feedback visual na barra de status
        original = self.time_label.cget("text")
        self.time_label.configure(text=f"✓  Copiado: {text}", text_color=COLORS["status_ok"])
        self.after(2000, lambda: self.time_label.configure(text=original, text_color=COLORS["text_secondary"]))

    # ================================================================
    # Abrir Interface Web com troca automática de IP
    # ================================================================

    def _open_web_for_device(self, device: UbiquitiDevice):
        """Ponto de entrada para abrir a interface web de um dispositivo."""
        interface = self._selected_interface()
        if not interface:
            self._show_toast("Nenhuma interface de rede selecionada.", is_error=True)
            return

        tech_ip = _compute_tech_ip(device.ip, suffix=245)
        if not tech_ip:
            self._show_toast("Não foi possível calcular o IP do técnico.", is_error=True)
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
            self._show_toast(
                "⚠  Permissão necessária!\n"
                "Execute o CedNet Help como Administrador\n"
                "para alterar o IP automaticamente.",
                is_error=True,
            )
            return

        # Mostrar janela de progresso e executar a troca de IP
        self._show_ip_change_progress(device, interface, tech_ip)

    def _show_ip_change_progress(
        self,
        device: UbiquitiDevice,
        interface: NetworkInterface,
        tech_ip: str,
    ):
        """Exibe janela de progresso da alteração de IP e executa em background."""
        # Criar janela de progresso
        progress_win = ctk.CTkToplevel(self)
        progress_win.title("Configurando rede...")
        progress_win.geometry("420x220")
        progress_win.configure(fg_color=COLORS["bg_main"])
        progress_win.transient(self.winfo_toplevel())
        progress_win.resizable(False, False)
        progress_win.grab_set()

        inner = ctk.CTkFrame(progress_win, fg_color="transparent")
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

        def _verify_ip_applied(expected_ip: str) -> bool:
            """Verifica via ipconfig se o IP foi realmente aplicado."""
            try:
                output = subprocess.check_output(
                    "ipconfig",
                    encoding="cp850",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5,
                )
                return expected_ip in output
            except Exception:
                return False

        def _wait_for_ip(expected_ip: str, max_attempts: int = 10, interval: float = 0.5) -> bool:
            """Aguarda o Windows concluir a atualização da pilha de rede."""
            for attempt in range(max_attempts):
                if _verify_ip_applied(expected_ip):
                    return True
                if attempt < max_attempts - 1:
                    time.sleep(interval)
            return False

        def _worker():
            mask = "255.255.255.0"
            success, error_msg = _set_static_ip(interface.name, tech_ip, mask)

            if success:
                # Aguardar tempo inicial para o Windows iniciar a aplicação
                time.sleep(1.5)

                # Aguardar a pilha de rede atualizar (até 10 tentativas x 500ms)
                if not _wait_for_ip(tech_ip, max_attempts=10, interval=0.5):
                    progress_win.after(0, lambda: _on_error(
                        "Não foi possível configurar automaticamente\n"
                        "o endereço IP da interface.\n"
                        f"O IP {tech_ip} não foi detectado após a alteração."
                    ))
                    return

                # Abrir o navegador
                webbrowser.open(f"http://{device.ip}")

                # Atualizar UI no thread principal
                progress_win.after(0, _on_success)
            else:
                progress_win.after(0, lambda: _on_error(error_msg))

        def _on_success():
            progress.stop()
            status_label.configure(
                text=f"✅  IP alterado para {tech_ip}\nAbrindo http://{device.ip} no navegador...",
                text_color=COLORS["status_ok"],
            )
            # Fechar janela automaticamente após 2 segundos
            progress_win.after(2000, progress_win.destroy)

        def _on_error(error_msg: str):
            progress.stop()
            progress.pack_forget()
            status_label.configure(
                text=f"❌  {error_msg}",
                text_color=COLORS["status_error"],
            )
            ctk.CTkButton(
                inner, text="Fechar", width=100,
                fg_color=COLORS["bg_card_alt"], hover_color=COLORS["bg_card_hover"],
                command=progress_win.destroy,
            ).pack(pady=(8, 0))

        threading.Thread(target=_worker, daemon=True).start()

    # ================================================================
    # Toast / Mensagem de status rápida
    # ================================================================

    def _show_toast(self, message: str, is_error: bool = False):
        """Exibe uma mensagem temporária na barra de status."""
        color = COLORS["status_error"] if is_error else COLORS["status_ok"]
        original = self.time_label.cget("text")
        self.time_label.configure(text=message, text_color=color)
        self.after(4000, lambda: self.time_label.configure(text=original, text_color=COLORS["text_secondary"]))

    def stop_monitoring(self):
        self.auto_var.set(False)
        if self._auto_id:
            self.after_cancel(self._auto_id)
            self._auto_id = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self.discovery.stop()
