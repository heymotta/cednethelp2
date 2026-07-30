"""
CedNet Help - Painel Scanner de Rede (Avançado)
Ferramenta profissional para descoberta e diagnóstico de dispositivos na sub-rede local.

Funcionalidades:
  - Detecção de portas web acessíveis (80, 443, 8080, 8443)
  - Inspeção de cabeçalho Server e tag <title> HTML unescaped
  - Classificação inteligente de equipamento (Roteador, ONU, Câmera, Impressora, PC)
  - Resolução de fabricante estrita (OUI + Banner HTTP) sem falsos positivos (exibe 'Desconhecido')
  - Coluna "Acesso Web" (🌐 Sim / ❌ Não)
  - Duplo clique para abrir a interface web (HTTPS priorizado)
  - Menu de contexto (clique direito) e Modal "Ver Detalhes"
  - Barra de progresso + métricas + cronômetro + pesquisa em tempo real
"""

import customtkinter as ctk
import time
import subprocess
import webbrowser
import queue
import tkinter as tk
from typing import Optional
from modules.network_scanner import NetworkScanner
from modules.utils import COLORS, FONTS


class ScannerPanel(ctk.CTkFrame):
    """Painel do Scanner de Rede avançado."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.scanner = NetworkScanner()

        self._devices: list[dict] = []
        self._selected_device: Optional[dict] = None
        self._selected_row_widget: Optional[ctk.CTkFrame] = None

        # Fila thread-safe para atualização da UI
        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None

        # Estado do scanner
        self._start_time: float = 0.0
        self._is_monitoring: bool = False
        self._monitor_after_id: Optional[str] = None

        self._create_ui()
        self._auto_detect_subnet()
        self._start_queue_polling()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta toda a interface do Scanner de Rede."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 1. Cabeçalho + Controles ----
        header_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        header_card.pack(fill="x", pady=(0, 10))

        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=20, pady=15)

        # Título + Switch Monitoramento
        title_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            title_frame,
            text="🔍  Scanner de Rede",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.switch_monitor = ctk.CTkSwitch(
            title_frame,
            text="🔄  Monitoramento Contínuo",
            font=FONTS["small_bold"],
            text_color=COLORS["text_secondary"],
            progress_color=COLORS["accent"],
            command=self._toggle_monitoring,
        )
        self.switch_monitor.pack(side="right")

        # Entrada de faixa + Botão Scan
        controls_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        controls_frame.pack(fill="x")
        controls_frame.columnconfigure(0, weight=1)

        target_box = ctk.CTkFrame(controls_frame, fg_color="transparent")
        target_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(
            target_box,
            text="Faixa da Rede (CIDR ou IP-IP):",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 2))

        self.target_entry = ctk.CTkEntry(
            target_box,
            font=FONTS["mono"],
            height=38,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="Ex: 192.168.1.0/24 ou 192.168.1.1-192.168.1.254",
        )
        self.target_entry.pack(fill="x")

        self.btn_scan = ctk.CTkButton(
            controls_frame,
            text="Iniciar Scan",
            font=FONTS["body_bold"],
            width=160,
            height=38,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_scan,
        )
        self.btn_scan.grid(row=0, column=1, sticky="e", pady=(18, 0))

        # ---- 2. Card de Progresso & Métricas ----
        progress_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
        )
        progress_card.pack(fill="x", pady=(0, 10))

        p_inner = ctk.CTkFrame(progress_card, fg_color="transparent")
        p_inner.pack(fill="x", padx=15, pady=10)

        self.progress_bar = ctk.CTkProgressBar(
            p_inner,
            height=10,
            corner_radius=5,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(0, 8))
        self.progress_bar.set(0.0)

        metrics_frame = ctk.CTkFrame(p_inner, fg_color="transparent")
        metrics_frame.pack(fill="x")

        self.lbl_count = ctk.CTkLabel(
            metrics_frame,
            text="Dispositivos: 0",
            font=FONTS["body_bold"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        )
        self.lbl_count.pack(side="left")

        self.lbl_progress = ctk.CTkLabel(
            metrics_frame,
            text="Progresso: 0/0 (0%)",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        )
        self.lbl_progress.pack(side="left", padx=30)

        self.lbl_time = ctk.CTkLabel(
            metrics_frame,
            text="Tempo: 0.0s",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="e",
        )
        self.lbl_time.pack(side="right")

        # ---- 3. Barra de Pesquisa + Ações Rápidas ----
        search_bar = ctk.CTkFrame(container, fg_color="transparent")
        search_bar.pack(fill="x", pady=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="🔍  Pesquisar por IP, MAC, Hostname, Fabricante ou Tipo...",
            font=FONTS["body"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.actions_frame = ctk.CTkFrame(search_bar, fg_color="transparent")
        self.actions_frame.pack(side="right")

        action_buttons = [
            ("Abrir Web",   self._open_web,     "Abrir Web"),
            ("Detalhes",    self._show_details, "Ver Detalhes"),
            ("IP",          self._copy_ip,      "Copiar IP"),
            ("MAC",         self._copy_mac,     "Copiar MAC"),
            ("Ping",        self._ping_t,       "Ping Contínuo"),
            ("CMD",         self._open_cmd,     "Prompt CMD"),
        ]

        for text, cmd, tooltip in action_buttons:
            btn = ctk.CTkButton(
                self.actions_frame,
                text=text,
                font=FONTS["small_bold"],
                width=85,
                height=34,
                corner_radius=6,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"],
                command=cmd,
                state="disabled",
            )
            btn.pack(side="left", padx=2)

        # ---- 4. Tabela de Resultados (Header + Scroll) ----
        table_header = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=8,
            height=40,
        )
        table_header.pack(fill="x", pady=(0, 4))
        table_header.pack_propagate(False)

        th_inner = ctk.CTkFrame(table_header, fg_color="transparent")
        th_inner.pack(fill="x", padx=15, pady=8)
        th_inner.columnconfigure(0, weight=2)  # IP
        th_inner.columnconfigure(1, weight=2)  # MAC
        th_inner.columnconfigure(2, weight=2)  # Hostname
        th_inner.columnconfigure(3, weight=2)  # Fabricante
        th_inner.columnconfigure(4, weight=3)  # Tipo de Equipamento
        th_inner.columnconfigure(5, weight=1)  # Acesso Web
        th_inner.columnconfigure(6, weight=1)  # Ping
        th_inner.columnconfigure(7, weight=1)  # Status

        cols = [
            ("IP", 0), ("MAC Address", 1), ("Hostname", 2),
            ("Fabricante", 3), ("Tipo de Equipamento", 4),
            ("Acesso Web", 5), ("Ping", 6), ("Status", 7)
        ]
        for col_name, col_idx in cols:
            ctk.CTkLabel(
                th_inner,
                text=col_name,
                font=FONTS["body_bold"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=0, column=col_idx, sticky="w", padx=4)

        # Corpo Scrollável da Tabela
        self.scroll_table = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        self.scroll_table.pack(fill="both", expand=True)

        self._row_widgets: list[ctk.CTkFrame] = []

        # Toast notification label no rodapé
        self.toast_label = ctk.CTkLabel(
            container,
            text="",
            font=FONTS["body"],
            text_color=COLORS["accent_cyan"],
        )
        self.toast_label.pack(pady=(4, 0))

    # ================================================================
    # Detecção Inicial e Polling da Fila
    # ================================================================

    def _auto_detect_subnet(self):
        """Preenche automaticamente a sub-rede detectada."""
        default_subnet = NetworkScanner.detect_default_subnet()
        self.target_entry.delete(0, "end")
        self.target_entry.insert(0, default_subnet)

    def _start_queue_polling(self):
        """Inicia o polling da fila thread-safe para a GUI."""
        self._process_ui_queue()

    def _process_ui_queue(self):
        """Processa eventos enviados da thread do scanner."""
        try:
            while True:
                msg_type, payload = self._ui_queue.get_nowait()

                if msg_type == "device":
                    self._add_device_to_table(payload)
                elif msg_type == "progress":
                    scanned, total, elapsed = payload
                    self._update_progress_ui(scanned, total, elapsed)
                elif msg_type == "complete":
                    self._on_scan_complete(payload)

        except queue.Empty:
            pass

        self._poll_after_id = self.after(100, self._process_ui_queue)

    # ================================================================
    # Controle do Scan
    # ================================================================

    def _toggle_scan(self):
        """Alterna entre Iniciar e Parar o scan."""
        if self.scanner.is_scanning():
            self._stop_scan()
        else:
            self._start_scan()

    def _start_scan(self):
        """Inicia a varredura multithreaded."""
        target_range = self.target_entry.get().strip()
        if not target_range:
            return

        self._devices.clear()
        self._selected_device = None
        self._selected_row_widget = None

        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        self._disable_action_buttons()

        self.btn_scan.configure(
            text="Parar Scan",
            fg_color=COLORS["status_error"],
            hover_color="#c62828",
        )
        self.progress_bar.set(0.0)
        self.lbl_count.configure(text="Dispositivos: 0")
        self.lbl_progress.configure(text="Iniciando varredura...")
        self.lbl_time.configure(text="Tempo: 0.0s")

        self._start_time = time.time()

        self.scanner.start_scan(
            target_range,
            on_device_found=lambda dev: self._ui_queue.put(("device", dev)),
            on_progress=lambda s, t, e: self._ui_queue.put(("progress", (s, t, e))),
            on_complete=lambda devs: self._ui_queue.put(("complete", devs)),
            max_workers=64,
        )

    def _stop_scan(self):
        """Para o scan."""
        self.scanner.stop_scan()
        self.btn_scan.configure(text="Iniciar Scan", fg_color=COLORS["accent"])
        self.lbl_progress.configure(text="Varredura interrompida pelo usuário")

    def _on_scan_complete(self, devices: list[dict]):
        """Callback executado ao finalizar."""
        self.btn_scan.configure(
            text="Iniciar Scan",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        self.progress_bar.set(1.0)
        elapsed = time.time() - self._start_time
        self.lbl_time.configure(text=f"Tempo: {elapsed:.1f}s")
        self.lbl_progress.configure(text=f"Concluído: {len(devices)} dispositivos encontrados em {elapsed:.1f}s")

    def _update_progress_ui(self, scanned: int, total: int, elapsed: float):
        """Atualiza a barra de progresso."""
        if total > 0:
            fraction = min(1.0, scanned / total)
            self.progress_bar.set(fraction)
            pct = int(fraction * 100)
            self.lbl_progress.configure(text=f"Progresso: {scanned}/{total} ({pct}%)")

        self.lbl_time.configure(text=f"Tempo: {elapsed:.1f}s")

    # ================================================================
    # Tabela de Resultados
    # ================================================================

    def _add_device_to_table(self, device: dict):
        """Adiciona um dispositivo à tabela em tempo real."""
        for existing in self._devices:
            if existing["ip"] == device["ip"]:
                return

        self._devices.append(device)
        self.lbl_count.configure(text=f"Dispositivos: {len(self._devices)}")

        query = self.search_entry.get().strip().lower()
        if query and not self._match_device_query(device, query):
            return

        self._create_device_row(device, len(self._row_widgets))

    def _create_device_row(self, device: dict, index: int):
        """Cria uma linha na tabela."""
        bg = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_card_alt"]

        row = ctk.CTkFrame(
            self.scroll_table,
            fg_color=bg,
            corner_radius=6,
            height=44,
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=8)
        inner.columnconfigure(0, weight=2)
        inner.columnconfigure(1, weight=2)
        inner.columnconfigure(2, weight=2)
        inner.columnconfigure(3, weight=2)
        inner.columnconfigure(4, weight=3)
        inner.columnconfigure(5, weight=1)
        inner.columnconfigure(6, weight=1)
        inner.columnconfigure(7, weight=1)

        # IP
        lbl_ip = ctk.CTkLabel(
            inner, text=device["ip"],
            font=FONTS["mono_large"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        )
        lbl_ip.grid(row=0, column=0, sticky="w", padx=4)

        # MAC
        lbl_mac = ctk.CTkLabel(
            inner, text=device["mac"],
            font=FONTS["mono"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        lbl_mac.grid(row=0, column=1, sticky="w", padx=4)

        # Hostname
        lbl_host = ctk.CTkLabel(
            inner, text=device["hostname"],
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        lbl_host.grid(row=0, column=2, sticky="w", padx=4)

        # Fabricante
        lbl_vendor = ctk.CTkLabel(
            inner, text=device["vendor"],
            font=FONTS["body_bold"],
            text_color=COLORS["text_secondary"] if device["vendor"] == "Desconhecido" else COLORS["text_primary"],
            anchor="w",
        )
        lbl_vendor.grid(row=0, column=3, sticky="w", padx=4)

        # Tipo de Equipamento (com Ícone)
        type_str = f"{device['icon']}  {device['device_type']}"
        lbl_type = ctk.CTkLabel(
            inner, text=type_str,
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        lbl_type.grid(row=0, column=4, sticky="w", padx=4)

        # Acesso Web (🌐 Sim / ❌ Não)
        web_str = "🌐  Sim" if device["has_web"] else "❌  Não"
        lbl_web = ctk.CTkLabel(
            inner, text=web_str,
            font=FONTS["body_bold"],
            text_color=COLORS["status_ok"] if device["has_web"] else COLORS["text_secondary"],
            anchor="w",
        )
        lbl_web.grid(row=0, column=5, sticky="w", padx=4)

        # Latência (Ping)
        ping_str = f"{device['ping_ms']} ms" if device['is_online'] else "—"
        lbl_ping = ctk.CTkLabel(
            inner, text=ping_str,
            font=FONTS["small"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        )
        lbl_ping.grid(row=0, column=6, sticky="w", padx=4)

        # Status
        status_str = "🟢 Online" if device['is_online'] else "🔴 Offline"
        lbl_status = ctk.CTkLabel(
            inner, text=status_str,
            font=FONTS["small_bold"],
            text_color=COLORS["status_ok"] if device['is_online'] else COLORS["status_error"],
            anchor="w",
        )
        lbl_status.grid(row=0, column=7, sticky="w", padx=4)

        # Eventos: Clique simples para selecionar, Duplo clique para abrir Web
        for w in [row, inner, lbl_ip, lbl_mac, lbl_host, lbl_vendor, lbl_type, lbl_web, lbl_ping, lbl_status]:
            w.bind("<Button-1>", lambda e, d=device, r=row: self._select_device(d, r))
            w.bind("<Double-Button-1>", lambda e, d=device: self._on_double_click_device(d))
            w.bind("<Button-3>", lambda e, d=device, r=row: self._on_right_click_device(e, d, r))

        self._row_widgets.append(row)

    # ================================================================
    # Seleção e Eventos de Clique
    # ================================================================

    def _select_device(self, device: dict, row_widget: ctk.CTkFrame):
        """Seleciona o dispositivo na tabela."""
        if self._selected_row_widget and self._selected_row_widget.winfo_exists():
            try:
                idx = self._row_widgets.index(self._selected_row_widget)
                bg = COLORS["bg_card"] if idx % 2 == 0 else COLORS["bg_card_alt"]
                self._selected_row_widget.configure(fg_color=bg)
            except ValueError:
                pass

        self._selected_device = device
        self._selected_row_widget = row_widget
        row_widget.configure(fg_color=COLORS["bg_card_hover"])
        self._enable_action_buttons()

    def _on_double_click_device(self, device: dict):
        """Ao dar duplo clique: abre a interface web ou exibe aviso."""
        if device.get("has_web") and device.get("web_url"):
            webbrowser.open(device["web_url"])
            self._show_toast(f"🌐 Abrindo {device['web_url']} no navegador...")
        else:
            self._show_toast(f"ℹ️ O dispositivo {device['ip']} não possui interface web disponível.")

    def _on_right_click_device(self, event, device: dict, row_widget: ctk.CTkFrame):
        """Clique direito: seleciona o dispositivo e abre o menu contextual nativo."""
        self._select_device(device, row_widget)
        self._show_context_menu(event, device)

    def _show_context_menu(self, event, device: dict):
        """Exibe o menu de contexto no ponto do clique."""
        menu = tk.Menu(self, tearoff=0, bg="#16213e", fg="#ffffff", activebackground="#1a73e8", activeforeground="#ffffff")

        if device.get("has_web"):
            menu.add_command(label=f"🌐 Abrir Web ({device.get('web_url')})", command=self._open_web)
        else:
            menu.add_command(label="🌐 Sem Interface Web", state="disabled")

        menu.add_separator()
        menu.add_command(label=f"📋 Copiar IP ({device['ip']})", command=self._copy_ip)
        menu.add_command(label=f"📋 Copiar MAC ({device['mac']})", command=self._copy_mac)
        menu.add_separator()
        menu.add_command(label="⚡ Executar Ping Contínuo", command=self._ping_t)
        menu.add_command(label="💻 Abrir Prompt CMD", command=self._open_cmd)
        menu.add_separator()
        menu.add_command(label="ℹ️ Ver Detalhes", command=self._show_details)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ================================================================
    # Ações Rápidas & Modal de Detalhes
    # ================================================================

    def _enable_action_buttons(self):
        """Habilita/desabilita botões conforme o dispositivo selecionado."""
        for child in self.actions_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state="normal")

    def _disable_action_buttons(self):
        """Desabilita a barra de ações."""
        for child in self.actions_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state="disabled")

    def _copy_ip(self):
        if self._selected_device:
            self.clipboard_clear()
            self.clipboard_append(self._selected_device["ip"])
            self._show_toast(f"📋 IP {self._selected_device['ip']} copiado!")

    def _copy_mac(self):
        if self._selected_device:
            self.clipboard_clear()
            self.clipboard_append(self._selected_device["mac"])
            self._show_toast(f"📋 MAC {self._selected_device['mac']} copiado!")

    def _open_web(self):
        if self._selected_device:
            if self._selected_device.get("has_web"):
                webbrowser.open(self._selected_device["web_url"])
                self._show_toast(f"🌐 Abrindo {self._selected_device['web_url']}...")
            else:
                self._show_toast("ℹ️ Dispositivo sem interface web acessível.")

    def _ping_t(self):
        if self._selected_device:
            ip = self._selected_device["ip"]
            subprocess.Popen(f'start cmd /k "title Ping {ip} && ping -t {ip}"', shell=True)

    def _open_cmd(self):
        if self._selected_device:
            ip = self._selected_device["ip"]
            subprocess.Popen(f'start cmd /k "title CMD {ip} && ping {ip}"', shell=True)

    def _show_details(self):
        """Exibe modal com todos os detalhes técnicos do dispositivo selecionado."""
        if not self._selected_device:
            return

        dev = self._selected_device

        modal = ctk.CTkToplevel(self)
        modal.title(f"Detalhes do Dispositivo — {dev['ip']}")
        modal.geometry("520x460")
        modal.resizable(False, False)
        modal.configure(fg_color=COLORS["bg_main"])
        modal.attributes("-topmost", True)
        modal.grab_set()

        # Cabeçalho do modal
        header = ctk.CTkFrame(modal, fg_color=COLORS["bg_card"], corner_radius=10)
        header.pack(fill="x", padx=15, pady=15)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="x", padx=15, pady=12)

        ctk.CTkLabel(
            h_inner,
            text=f"{dev['icon']}  {dev['device_type']}",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            h_inner,
            text=f"IP: {dev['ip']}  |  MAC: {dev['mac']}",
            font=FONTS["mono"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        # Tabela de especificações
        specs_frame = ctk.CTkScrollableFrame(modal, fg_color=COLORS["bg_card"], corner_radius=10)
        specs_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        details_list = [
            ("Endereço IPv4", dev["ip"]),
            ("Endereço MAC", dev["mac"]),
            ("Hostname DNS", dev["hostname"]),
            ("Fabricante", dev["vendor"]),
            ("Tipo de Equipamento", dev["device_type"]),
            ("Interface Web", "🌐 Disponível" if dev["has_web"] else "❌ Indisponível"),
            ("URL Web", dev.get("web_url") or "—"),
            ("Porta Web", str(dev.get("web_port")) if dev.get("has_web") else "—"),
            ("Título HTML (<title>)", dev.get("http_title") or "—"),
            ("Servidor HTTP (Header)", dev.get("http_server") or "—"),
            ("Latência Ping", f"{dev['ping_ms']} ms" if dev['is_online'] else "—"),
            ("Status", "🟢 Online" if dev['is_online'] else "🔴 Offline"),
        ]

        for label, val in details_list:
            row = ctk.CTkFrame(specs_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row, text=f"{label}:",
                font=FONTS["body_bold"],
                text_color=COLORS["text_secondary"],
                width=170,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=str(val),
                font=FONTS["mono"],
                text_color=COLORS["text_primary"],
                anchor="w",
                wraplength=280,
            ).pack(side="left", fill="x", expand=True)

        # Botão Fechar
        ctk.CTkButton(
            modal,
            text="Fechar",
            font=FONTS["body_bold"],
            height=38,
            corner_radius=8,
            fg_color=COLORS["accent"],
            command=modal.destroy,
        ).pack(fill="x", padx=15, pady=(0, 15))

    def _show_toast(self, message: str):
        """Exibe um aviso temporário no rodapé da tabela."""
        self.toast_label.configure(text=message)
        self.after(5000, lambda: self.toast_label.configure(text=""))

    # ================================================================
    # Pesquisa / Filtragem em Tempo Real
    # ================================================================

    def _on_search(self, event=None):
        """Filtra a tabela em tempo real."""
        query = self.search_entry.get().strip().lower()

        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        self._disable_action_buttons()

        if not query:
            for i, dev in enumerate(self._devices):
                self._create_device_row(dev, i)
        else:
            count = 0
            for dev in self._devices:
                if self._match_device_query(dev, query):
                    self._create_device_row(dev, count)
                    count += 1

    @staticmethod
    def _match_device_query(dev: dict, query: str) -> bool:
        """Verifica se o dispositivo corresponde à busca."""
        web_keyword = "sim" if dev.get("has_web") else "nao"
        return (
            query in dev["ip"].lower()
            or query in dev["mac"].lower()
            or query in dev["hostname"].lower()
            or query in dev["vendor"].lower()
            or query in dev["device_type"].lower()
            or query in web_keyword
        )

    # ================================================================
    # Monitoramento Contínuo e Encerramento
    # ================================================================

    def _toggle_monitoring(self):
        """Liga/desliga monitoramento automático."""
        self._is_monitoring = bool(self.switch_monitor.get())

        if self._is_monitoring:
            self._run_monitoring_cycle()
        else:
            if self._monitor_after_id:
                self.after_cancel(self._monitor_after_id)
                self._monitor_after_id = None

    def _run_monitoring_cycle(self):
        """Ciclo periódico de re-varredura."""
        if not self._is_monitoring:
            return

        if not self.scanner.is_scanning():
            target_range = self.target_entry.get().strip()
            if target_range:
                self.scanner.start_scan(
                    target_range,
                    on_device_found=lambda dev: self._ui_queue.put(("device", dev)),
                    on_progress=lambda s, t, e: self._ui_queue.put(("progress", (s, t, e))),
                    on_complete=lambda devs: self._ui_queue.put(("complete", devs)),
                    max_workers=64,
                )

        self._monitor_after_id = self.after(15000, self._run_monitoring_cycle)

    def stop_monitoring(self):
        """Encerra loops ao fechar a janela."""
        self._is_monitoring = False
        if self._monitor_after_id:
            self.after_cancel(self._monitor_after_id)
            self._monitor_after_id = None

        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None

        if self.scanner.is_scanning():
            self.scanner.stop_scan()
