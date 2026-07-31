"""Página do scanner nativo de descoberta Ubiquiti."""

import ipaddress
import queue
import time
import webbrowser
from tkinter import ttk

import customtkinter as ctk

from modules.utils import COLORS, FONTS
from scanner.discovery import UbiquitiDiscovery
from scanner.models import NetworkInterface, UbiquitiDevice


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

    def _show_details(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        device = self.devices.get(selected[0])
        if not device:
            return
        modal = ctk.CTkToplevel(self)
        modal.title(f"Detalhes Ubiquiti - {device.ip}")
        modal.geometry("510x430")
        modal.configure(fg_color=COLORS["bg_main"])
        modal.transient(self.winfo_toplevel())
        ctk.CTkLabel(modal, text=f"{device.model or 'Dispositivo Ubiquiti'}", font=FONTS["title"], text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(20, 14))
        details = [("Modelo", device.model), ("IP", device.ip), ("MAC", device.mac), ("Hardware Address", device.hardware_address), ("Hostname", device.system_name), ("Firmware", device.firmware), ("Plataforma", device.platform), ("Versão do protocolo", device.protocol_version), ("Tempo de resposta", f"{device.response_ms:.1f} ms" if device.response_ms is not None else "-"), ("Última descoberta", device.discovered_at.strftime("%d/%m/%Y %H:%M:%S"))]
        box = ctk.CTkScrollableFrame(modal, fg_color=COLORS["bg_card"])
        box.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        for label, value in details:
            ctk.CTkLabel(box, text=f"{label}:", width=165, anchor="w", font=FONTS["body_bold"], text_color=COLORS["text_secondary"]).pack(side="left", padx=8, pady=5)
            ctk.CTkLabel(box, text=value or "-", anchor="w", font=FONTS["mono"], text_color=COLORS["text_primary"]).pack(fill="x", padx=8, pady=5)
        ctk.CTkButton(modal, text="Abrir Interface Web", command=lambda: webbrowser.open(f"http://{device.ip}"), width=190).pack(side="left", padx=(20, 5), pady=(0, 18))
        ctk.CTkButton(modal, text="Fechar", fg_color=COLORS["bg_card_alt"], command=modal.destroy, width=100).pack(side="right", padx=(5, 20), pady=(0, 18))

    def stop_monitoring(self):
        self.auto_var.set(False)
        if self._auto_id:
            self.after_cancel(self._auto_id)
            self._auto_id = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self.discovery.stop()
