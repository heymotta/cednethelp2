"""
CedNet Help - Painel de Análise de Canais Wi-Fi
Interface profissional (estilo UniFi / Omada / Meraki) para análise de canais Wi-Fi.

Funcionalidades:
  - Cards de Recomendação Reestruturados (Título, Número em destaque de 28px, Status com ícone, Bullets informativos)
  - Padding generoso (20px lateral, 18px vertical) e tipografia hierárquica clara
  - Tabela responsiva de 5 colunas com alinhamento impecável e 100% de altura vertical
  - Busca em tempo real e varredura sob demanda com resiliência total
"""

import customtkinter as ctk
import threading
from typing import Optional
from modules.wifi_scanner import WiFiScanner
from modules.utils import COLORS, FONTS


# Especificações de alinhamento e peso das 5 colunas essenciais
COL_SPECS = [
    # (Título, Peso, Anchor, Sticky)
    ("SSID (Nome da Rede)", 40, "w", "w"),
    ("BSSID (MAC AP)", 24, "center", "ew"),
    ("Banda", 12, "center", "ew"),
    ("Canal", 10, "center", "ew"),
    ("Sinal (RSSI)", 18, "center", "ew"),
]


class WiFiPanel(ctk.CTkFrame):
    """Painel de Análise de Canais Wi-Fi com Design Corporativo de Alta Fidelidade Visual."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.wifi_scanner = WiFiScanner()

        self._networks: list[dict] = []
        self._analysis: dict = {}
        self._is_scanning: bool = False
        self._cancel_requested: bool = False
        self._watchdog_after_id: Optional[str] = None

        self._create_ui()

    # ================================================================
    # Construção da UI Responsiva
    # ================================================================

    def _create_ui(self):
        """Monta a interface com excelente hierarquia tipográfica e aproveitamento de tela."""
        
        # ---- 1. Seção Superior (Cabeçalho + Alertas + Recomendações + Busca) ----
        top_container = ctk.CTkFrame(self, fg_color="transparent")
        top_container.pack(fill="x", padx=6, pady=(6, 0))

        # Cabeçalho da Página (22px Bold) + Botão Escanear Modernizado (40px)
        header = ctk.CTkFrame(top_container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            header,
            text="📡  Análise de Canais Wi-Fi",
            font=("Segoe UI", 22, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            header,
            text="🚀  Escanear Redes Wi-Fi",
            font=("Segoe UI", 13, "bold"),
            width=220,
            height=40,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._on_btn_click,
        )
        self.btn_refresh.pack(side="right")

        # Card de Erro / Aviso (Escondido por padrão)
        self.error_card = ctk.CTkFrame(
            top_container,
            fg_color="#3d1a1a",
            corner_radius=12,
            border_width=1,
            border_color=COLORS["status_error"],
        )

        err_inner = ctk.CTkFrame(self.error_card, fg_color="transparent")
        err_inner.pack(fill="x", padx=20, pady=16)

        self.lbl_error_icon = ctk.CTkLabel(
            err_inner, text="⚠️", font=("Segoe UI", 22)
        )
        self.lbl_error_icon.pack(side="left", padx=(0, 10))

        self.lbl_error_msg = ctk.CTkLabel(
            err_inner,
            text="",
            font=("Segoe UI", 13),
            text_color=COLORS["status_error"],
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.lbl_error_msg.pack(side="left", fill="x", expand=True)

        # ---- Cards de Recomendação Reestruturados (UniFi / Omada Style) ----
        rec_card = ctk.CTkFrame(
            top_container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        rec_card.pack(fill="x", pady=(0, 12))

        rec_inner = ctk.CTkFrame(rec_card, fg_color="transparent")
        rec_inner.pack(fill="x", padx=20, pady=18)

        ctk.CTkLabel(
            rec_inner,
            text="💡  Recomendação de Canais",
            font=("Segoe UI", 18, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        rec_grid = ctk.CTkFrame(rec_inner, fg_color="transparent")
        rec_grid.pack(fill="x")
        rec_grid.columnconfigure((0, 1), weight=1)

        # Card 2.4 GHz
        self.card_24 = ctk.CTkFrame(rec_grid, fg_color=COLORS["entry_bg"], corner_radius=10)
        self.card_24.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        c24_inner = ctk.CTkFrame(self.card_24, fg_color="transparent")
        c24_inner.pack(fill="x", padx=20, pady=18)

        # Título da Categoria
        ctk.CTkLabel(
            c24_inner,
            text="CANAL RECOMENDADO (2.4 GHz)",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

        # Destaque Principal (28px Bold)
        self.lbl_channel_num_24 = ctk.CTkLabel(
            c24_inner,
            text="Canal —",
            font=("Segoe UI", 28, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
            justify="left",
        )
        self.lbl_channel_num_24.pack(anchor="w", pady=(0, 4))

        # Status
        self.lbl_status_24 = ctk.CTkLabel(
            c24_inner,
            text="Aguardando varredura",
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_status_24.pack(anchor="w", pady=(0, 8))

        # Bullets Informativos
        self.lbl_reasons_24 = ctk.CTkLabel(
            c24_inner,
            text="• Clique em 'Escanear Redes Wi-Fi' para iniciar a análise.",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_reasons_24.pack(anchor="w")

        # Card 5 GHz
        self.card_5g = ctk.CTkFrame(rec_grid, fg_color=COLORS["entry_bg"], corner_radius=10)
        self.card_5g.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        c5g_inner = ctk.CTkFrame(self.card_5g, fg_color="transparent")
        c5g_inner.pack(fill="x", padx=20, pady=18)

        # Título da Categoria
        ctk.CTkLabel(
            c5g_inner,
            text="CANAL RECOMENDADO (5 GHz)",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

        # Destaque Principal (28px Bold)
        self.lbl_channel_num_5g = ctk.CTkLabel(
            c5g_inner,
            text="Canal —",
            font=("Segoe UI", 28, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
            justify="left",
        )
        self.lbl_channel_num_5g.pack(anchor="w", pady=(0, 4))

        # Status
        self.lbl_status_5g = ctk.CTkLabel(
            c5g_inner,
            text="Aguardando varredura",
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_status_5g.pack(anchor="w", pady=(0, 8))

        # Bullets Informativos
        self.lbl_reasons_5g = ctk.CTkLabel(
            c5g_inner,
            text="• Clique em 'Escanear Redes Wi-Fi' para iniciar a análise.",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_reasons_5g.pack(anchor="w")

        # Barra de Pesquisa Modernizada (Altura 40px)
        search_bar = ctk.CTkFrame(top_container, fg_color="transparent")
        search_bar.pack(fill="x", pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="🔍  Pesquisar por SSID, BSSID, Canal ou Banda...",
            font=("Segoe UI", 13),
            height=40,
            corner_radius=10,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ---- 2. Seção Inferior: Tabela Responsiva (100% de preenchimento vertical) ----
        table_container = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        table_container.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Cabeçalho Fixo da Tabela
        table_header = ctk.CTkFrame(
            table_container,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=8,
            height=38,
        )
        table_header.pack(fill="x", padx=10, pady=(10, 4))
        table_header.pack_propagate(False)

        th_inner = ctk.CTkFrame(table_header, fg_color="transparent")
        th_inner.pack(fill="x", padx=12, pady=6)

        for idx, (title, weight, anchor_pos, sticky_pos) in enumerate(COL_SPECS):
            th_inner.columnconfigure(idx, weight=weight)
            ctk.CTkLabel(
                th_inner,
                text=title,
                font=("Segoe UI", 13, "bold"),
                text_color=COLORS["text_secondary"],
                anchor=anchor_pos,
            ).grid(row=0, column=idx, sticky=sticky_pos, padx=4)

        # Corpo Scrollável Responsivo que Expande até o Fim da Tela
        self.scroll_table = ctk.CTkScrollableFrame(
            table_container,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_sidebar"],
        )
        self.scroll_table.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self._row_widgets: list[ctk.CTkFrame] = []
        self._render_networks_table([], initial_idle=True)

    # ================================================================
    # Gerenciamento de Estado & Execução sob Demanda (100% Preservado)
    # ================================================================

    def _on_btn_click(self):
        """Disparado ao clicar no botão de escaneamento."""
        if self._is_scanning:
            self._cancel_requested = True
            self.btn_refresh.configure(text="Cancelando...", state="disabled")
        else:
            self._start_scan()

    def _start_scan(self):
        """Inicia o escaneamento das redes sem fio."""
        self._is_scanning = True
        self._cancel_requested = False

        self.btn_refresh.configure(
            text="🛑 Cancelar Scan",
            fg_color=COLORS["status_error"],
            hover_color="#c62828",
            state="normal",
        )
        self.error_card.pack_forget()

        self.lbl_channel_num_24.configure(text="Canal ...")
        self.lbl_status_24.configure(text="🔍 Escaneando...", text_color=COLORS["accent_cyan"])
        self.lbl_reasons_24.configure(text="• Analisando sinal RSSI e sobreposição...")

        self.lbl_channel_num_5g.configure(text="Canal ...")
        self.lbl_status_5g.configure(text="🔍 Escaneando...", text_color=COLORS["accent_cyan"])
        self.lbl_reasons_5g.configure(text="• Analisando ocupação dos canais 5 GHz...")

        if self._watchdog_after_id:
            self.after_cancel(self._watchdog_after_id)
        self._watchdog_after_id = self.after(10000, self._check_scan_watchdog)

        thread = threading.Thread(target=self._scan_thread_worker, daemon=True)
        thread.start()

    def _check_scan_watchdog(self):
        """Watchdog de resiliência caso a thread externa demore."""
        if self._is_scanning:
            self._on_scan_complete(False, "Tempo limite do escaneamento esgotado.", [], {})

    def _scan_thread_worker(self):
        """Worker em segundo plano."""
        success = False
        message = "Não foi possível concluir a varredura Wi-Fi."
        networks: list[dict] = []
        analysis: dict = {}

        try:
            def is_cancelled():
                return self._cancel_requested

            success, message, networks = WiFiScanner.scan_networks(cancel_checker=is_cancelled)
            if success and networks and not self._cancel_requested:
                analysis = WiFiScanner.analyze_spectrum(networks)
        except Exception as exc:
            message = f"Erro ao processar varredura Wi-Fi: {exc}"
        finally:
            try:
                self.after(0, lambda: self._on_scan_complete(success, message, networks, analysis))
            except RuntimeError:
                self._is_scanning = False

    def _on_scan_complete(self, success: bool, message: str, networks: list[dict], analysis: dict):
        """Callback acionado ao finalizar a busca."""
        if self._watchdog_after_id:
            self.after_cancel(self._watchdog_after_id)
            self._watchdog_after_id = None

        self._is_scanning = False
        self._cancel_requested = False

        self.btn_refresh.configure(
            state="normal",
            text="🚀  Escanear Redes Wi-Fi",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )

        self._networks = networks
        self._analysis = analysis

        if not success or not networks:
            error_msg = message if not success else "Nenhuma rede Wi-Fi foi encontrada."
            self.lbl_error_msg.configure(text=error_msg)
            self.error_card.pack(fill="x", pady=(0, 10))
            self._display_recommendations(None)
            self._render_networks_table([])
            return

        self.error_card.pack_forget()
        self._display_recommendations(analysis)
        self._render_networks_table(networks)

    # ================================================================
    # Renderização das Recomendações
    # ================================================================

    def _display_recommendations(self, analysis: dict | None):
        """Atualiza os cards de recomendação com hierarquia limpa."""
        if not analysis:
            self.lbl_channel_num_24.configure(text="Canal —")
            self.lbl_status_24.configure(text="⚠️ Nenhuma rede detectada", text_color=COLORS["text_secondary"])
            self.lbl_reasons_24.configure(text="• Nenhuma rede sem fio ao alcance.")

            self.lbl_channel_num_5g.configure(text="Canal —")
            self.lbl_status_5g.configure(text="⚠️ Nenhuma rede detectada", text_color=COLORS["text_secondary"])
            self.lbl_reasons_5g.configure(text="• Nenhuma rede sem fio ao alcance.")
            return

        rec24 = analysis.get("recommendation_24", {})
        best24 = rec24.get("best_channel", 1)
        reasons24 = "\n".join([f"• {r.lstrip('• ')}" for r in rec24.get("reasons", [])])

        self.lbl_channel_num_24.configure(text=f"Canal {best24}")
        self.lbl_status_24.configure(text="✔ Menor interferência encontrada", text_color=COLORS["status_ok"])
        self.lbl_reasons_24.configure(text=reasons24)

        rec5g = analysis.get("recommendation_5g", {})
        best5g = rec5g.get("best_channel", 36)
        reasons5g = "\n".join([f"• {r.lstrip('• ')}" for r in rec5g.get("reasons", [])])

        self.lbl_channel_num_5g.configure(text=f"Canal {best5g}")
        self.lbl_status_5g.configure(text="✔ Menor interferência encontrada", text_color=COLORS["status_ok"])
        self.lbl_reasons_5g.configure(text=reasons5g)

    # ================================================================
    # Renderização da Tabela Responsiva de Redes
    # ================================================================

    def _render_networks_table(self, networks: list[dict], initial_idle: bool = False):
        """Limpa e desenha a lista de redes com 5 colunas simétricas."""
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        if initial_idle:
            no_row = ctk.CTkFrame(self.scroll_table, fg_color="transparent")
            no_row.pack(fill="x", pady=25)
            ctk.CTkLabel(
                no_row,
                text="Clique em 'Escanear Redes Wi-Fi' para iniciar a busca das redes disponíveis ao alcance.",
                font=("Segoe UI", 13),
                text_color=COLORS["text_secondary"],
            ).pack()
            self._row_widgets.append(no_row)
            return

        if not networks:
            no_row = ctk.CTkFrame(self.scroll_table, fg_color="transparent")
            no_row.pack(fill="x", pady=20)
            ctk.CTkLabel(
                no_row,
                text="Nenhuma rede Wi-Fi disponível para exibição.",
                font=("Segoe UI", 13),
                text_color=COLORS["text_secondary"],
            ).pack()
            self._row_widgets.append(no_row)
            return

        query = self.search_entry.get().strip().lower()

        filtered = [
            n for n in networks
            if not query or self._match_network_query(n, query)
        ]

        filtered.sort(key=lambda x: x["signal_pct"], reverse=True)

        for index, net in enumerate(filtered):
            self._create_network_row(net, index)

    def _create_network_row(self, net: dict, index: int):
        """Cria uma linha simétrica na tabela com pesos e alinhamento sincronizados."""
        bg = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_card_alt"]

        row = ctk.CTkFrame(
            self.scroll_table,
            fg_color=bg,
            corner_radius=6,
            height=40,
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=6)

        for idx, (_, weight, _, _) in enumerate(COL_SPECS):
            inner.columnconfigure(idx, weight=weight)

        # 0. SSID (Alinhado à esquerda)
        ctk.CTkLabel(
            inner, text=f"📶  {net['ssid']}",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=4)

        # 1. BSSID (Centralizado com fonte monoespaçada)
        ctk.CTkLabel(
            inner, text=net["bssid"],
            font=FONTS["mono"],
            text_color=COLORS["text_secondary"],
            anchor="center",
        ).grid(row=0, column=1, sticky="ew", padx=4)

        # 2. Banda (Centralizada)
        ctk.CTkLabel(
            inner, text=net["band"],
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["accent_cyan"],
            anchor="center",
        ).grid(row=0, column=2, sticky="ew", padx=4)

        # 3. Canal (Centralizado)
        ctk.CTkLabel(
  inner, text=str(net["channel"]),
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
            anchor="center",
        ).grid(row=0, column=3, sticky="ew", padx=4)

        # 4. Sinal RSSI (Centralizado e Colorido)
        rssi = net["rssi_dbm"]
        pct = net["signal_pct"]
        signal_color = COLORS["status_ok"] if rssi >= -65 else (COLORS["status_warning"] if rssi >= -78 else COLORS["status_error"])

        ctk.CTkLabel(
            inner, text=f"{rssi} dBm ({pct}%)",
            font=("Segoe UI", 12, "bold"),
            text_color=signal_color,
            anchor="center",
        ).grid(row=0, column=4, sticky="ew", padx=4)

        self._row_widgets.append(row)

    # ================================================================
    # Pesquisa em Tempo Real
    # ================================================================

    def _on_search(self, event=None):
        """Filtra a tabela de redes em tempo real."""
        self._render_networks_table(self._networks)

    @staticmethod
    def _match_network_query(net: dict, query: str) -> bool:
        """Verifica se a query coincide com qualquer um dos 5 campos da rede."""
        return (
            query in net["ssid"].lower()
            or query in net["bssid"].lower()
            or query in str(net["channel"])
            or query in net["band"].lower()
        )

    def stop_monitoring(self):
        """Cancela timers pendentes ao fechar."""
        if self._watchdog_after_id:
            self.after_cancel(self._watchdog_after_id)
            self._watchdog_after_id = None
        self._cancel_requested = True
