"""
CedNet Help - Painel de Análise de Canais Wi-Fi
Ferramenta profissional para análise de espectro Wi-Fi (2.4 GHz e 5 GHz),
visualização gráfica de canais congestionados e recomendação inteligente do melhor canal.

Funcionalidades:
  - Varredura de redes próximas (SSID, BSSID, Banda, Canal, Sinal, Segurança)
  - Card de Recomendação Inteligente com justificativas técnicas (2.4 GHz e 5 GHz)
  - Visualização gráfica da ocupação dos canais (Barras de Densidade)
  - Tabela filtrável em tempo real
  - Tratamento para falta de adaptador Wi-Fi ou serviço wlansvc desligado
"""

import customtkinter as ctk
import threading
from typing import Optional
from modules.wifi_scanner import WiFiScanner
from modules.utils import COLORS, FONTS


class WiFiPanel(ctk.CTkFrame):
    """Painel de Análise de Canais Wi-Fi."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.wifi_scanner = WiFiScanner()

        self._networks: list[dict] = []
        self._analysis: dict = {}
        self._is_scanning: bool = False

        self._create_ui()
        # Executa a varredura inicial ao abrir
        self._run_scan()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta toda a interface do painel Wi-Fi."""
        self.container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        self.container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 1. Cabeçalho + Botão Escanear ----
        header = ctk.CTkFrame(self.container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            header,
            text="📡  Análise de Canais Wi-Fi",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            header,
            text="Escanear Novamente",
            font=FONTS["body_bold"],
            width=180,
            height=38,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._run_scan,
        )
        self.btn_refresh.pack(side="right")

        # ---- Card de Erro / Aviso (Escondido por padrão) ----
        self.error_card = ctk.CTkFrame(
            self.container,
            fg_color="#3d1a1a",
            corner_radius=12,
            border_width=1,
            border_color=COLORS["status_error"],
        )

        err_inner = ctk.CTkFrame(self.error_card, fg_color="transparent")
        err_inner.pack(fill="x", padx=20, pady=15)

        self.lbl_error_icon = ctk.CTkLabel(
            err_inner, text="⚠️", font=("Segoe UI", 24)
        )
        self.lbl_error_icon.pack(side="left", padx=(0, 10))

        self.lbl_error_msg = ctk.CTkLabel(
            err_inner,
            text="",
            font=FONTS["body"],
            text_color=COLORS["status_error"],
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.lbl_error_msg.pack(side="left", fill="x", expand=True)

        # ---- 2. Cards de Recomendação Inteligente ----
        rec_card = ctk.CTkFrame(
            self.container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        rec_card.pack(fill="x", pady=(0, 12))

        rec_inner = ctk.CTkFrame(rec_card, fg_color="transparent")
        rec_inner.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            rec_inner,
            text="💡  Recomendação de Canais",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        # Grid com 2 colunas: 2.4 GHz (esquerda) e 5 GHz (direita)
        rec_grid = ctk.CTkFrame(rec_inner, fg_color="transparent")
        rec_grid.pack(fill="x")
        rec_grid.columnconfigure((0, 1), weight=1)

        # Card 2.4 GHz
        self.card_24 = ctk.CTkFrame(rec_grid, fg_color=COLORS["entry_bg"], corner_radius=10)
        self.card_24.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        c24_inner = ctk.CTkFrame(self.card_24, fg_color="transparent")
        c24_inner.pack(fill="x", padx=15, pady=12)

        self.lbl_best_24 = ctk.CTkLabel(
            c24_inner,
            text="✔ Melhor canal 2.4 GHz: —",
            font=FONTS["subtitle"],
            text_color=COLORS["status_ok"],
            anchor="w",
        )
        self.lbl_best_24.pack(anchor="w", pady=(0, 5))

        self.lbl_reasons_24 = ctk.CTkLabel(
            c24_inner,
            text="Aguardando varredura...",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_reasons_24.pack(anchor="w")

        # Card 5 GHz
        self.card_5g = ctk.CTkFrame(rec_grid, fg_color=COLORS["entry_bg"], corner_radius=10)
        self.card_5g.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        c5g_inner = ctk.CTkFrame(self.card_5g, fg_color="transparent")
        c5g_inner.pack(fill="x", padx=15, pady=12)

        self.lbl_best_5g = ctk.CTkLabel(
            c5g_inner,
            text="✔ Melhor canal 5 GHz: —",
            font=FONTS["subtitle"],
            text_color=COLORS["status_ok"],
            anchor="w",
        )
        self.lbl_best_5g.pack(anchor="w", pady=(0, 5))

        self.lbl_reasons_5g = ctk.CTkLabel(
            c5g_inner,
            text="Aguardando varredura...",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        self.lbl_reasons_5g.pack(anchor="w")

        # ---- 3. Gráfico de Densidade de Espectro ----
        graph_card = ctk.CTkFrame(
            self.container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        graph_card.pack(fill="x", pady=(0, 12))

        graph_inner = ctk.CTkFrame(graph_card, fg_color="transparent")
        graph_inner.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            graph_inner,
            text="📊  Ocupação do Espectro (2.4 GHz)",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        # Container de barras dos canais 1 a 13
        self.bars_frame_24 = ctk.CTkFrame(graph_inner, fg_color="transparent")
        self.bars_frame_24.pack(fill="x")
        self.bars_frame_24.columnconfigure(list(range(13)), weight=1)

        self._channel_bars_24: dict[int, dict] = {}
        for ch in range(1, 14):
            bar_box = ctk.CTkFrame(self.bars_frame_24, fg_color="transparent")
            bar_box.grid(row=0, column=ch-1, padx=2, sticky="ew")

            # Indicador numérico de redes no topo
            count_lbl = ctk.CTkLabel(
                bar_box, text="0", font=FONTS["small_bold"],
                text_color=COLORS["text_secondary"],
            )
            count_lbl.pack()

            # Barra vertical (simulada via progress bar)
            p_bar = ctk.CTkProgressBar(
                bar_box, height=50, orientation="vertical",
                corner_radius=4, fg_color=COLORS["entry_bg"],
                progress_color=COLORS["accent"],
            )
            p_bar.pack(pady=3)
            p_bar.set(0.0)

            # Rótulo do Canal
            ch_color = COLORS["accent_cyan"] if ch in (1, 3, 6) else COLORS["text_secondary"]
            ch_lbl = ctk.CTkLabel(
                bar_box, text=f"Ch {ch}", font=FONTS["small_bold"],
                text_color=ch_color,
            )
            ch_lbl.pack()

            self._channel_bars_24[ch] = {"bar": p_bar, "count": count_lbl}

        # ---- 4. Barra de Pesquisa ----
        search_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        search_bar.pack(fill="x", pady=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="🔍  Pesquisar por SSID, Canal, Banda ou Segurança...",
            font=FONTS["body"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ---- 5. Tabela de Redes Wi-Fi ----
        table_header = ctk.CTkFrame(
            self.container,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=8,
            height=40,
        )
        table_header.pack(fill="x", pady=(0, 4))
        table_header.pack_propagate(False)

        th_inner = ctk.CTkFrame(table_header, fg_color="transparent")
        th_inner.pack(fill="x", padx=15, pady=8)
        th_inner.columnconfigure(0, weight=3)  # SSID
        th_inner.columnconfigure(1, weight=2)  # BSSID
        th_inner.columnconfigure(2, weight=1)  # Banda
        th_inner.columnconfigure(3, weight=1)  # Canal
        th_inner.columnconfigure(4, weight=1)  # Frequência
        th_inner.columnconfigure(5, weight=2)  # Sinal (dBm / %)
        th_inner.columnconfigure(6, weight=2)  # Segurança

        cols = [
            ("SSID (Nome da Rede)", 0), ("BSSID (MAC AP)", 1), ("Banda", 2),
            ("Canal", 3), ("Frequência", 4), ("Sinal (RSSI)", 5), ("Segurança", 6)
        ]
        for col_name, col_idx in cols:
            ctk.CTkLabel(
                th_inner, text=col_name,
                font=FONTS["body_bold"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=0, column=col_idx, sticky="w", padx=4)

        # Corpo Scrollável
        self.scroll_table = ctk.CTkScrollableFrame(
            self.container,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        self.scroll_table.pack(fill="both", expand=True)

        self._row_widgets: list[ctk.CTkFrame] = []

    # ================================================================
    # Execução da Varredura (em Background Thread)
    # ================================================================

    def _run_scan(self):
        """Inicia a varredura das redes Wi-Fi."""
        if self._is_scanning:
            return

        self._is_scanning = True
        self.btn_refresh.configure(state="disabled", text="Escaneando...")
        self.error_card.pack_forget()

        # Reseta barras
        for item in self._channel_bars_24.values():
            item["bar"].set(0.0)
            item["count"].configure(text="0")

        thread = threading.Thread(target=self._scan_thread_worker, daemon=True)
        thread.start()

    def _scan_thread_worker(self):
        """Worker que chama o WiFiScanner."""
        success, message, networks = WiFiScanner.scan_networks()

        analysis = {}
        if success and networks:
            analysis = WiFiScanner.analyze_spectrum(networks)

        # Atualiza a UI na thread principal via after()
        try:
            self.after(0, lambda: self._on_scan_complete(success, message, networks, analysis))
        except RuntimeError:
            pass

    def _on_scan_complete(self, success: bool, message: str, networks: list[dict], analysis: dict):
        """Callback acionado ao concluir a varredura."""
        self._is_scanning = False
        self.btn_refresh.configure(state="normal", text="Escanear Novamente")

        self._networks = networks
        self._analysis = analysis

        if not success:
            # Exibe mensagem de erro
            self.lbl_error_msg.configure(text=message)
            self.error_card.pack(fill="x", pady=(0, 12))
            self._display_recommendations(None)
            self._render_networks_table([])
            return

        # Sucesso: renderiza recomendações, gráfico e tabela
        self._display_recommendations(analysis)
        self._render_spectrum_graph(analysis.get("channels_24", {}))
        self._render_networks_table(networks)

    # ================================================================
    # Renderização das Recomendações
    # ================================================================

    def _display_recommendations(self, analysis: dict | None):
        """Atualiza os cards de recomendação inteligente."""
        if not analysis:
            self.lbl_best_24.configure(text="Canal recomendado: —", text_color=COLORS["text_secondary"])
            self.lbl_reasons_24.configure(text="Nenhuma rede detectada.")
            self.lbl_best_5g.configure(text="Canal recomendado: —", text_color=COLORS["text_secondary"])
            self.lbl_reasons_5g.configure(text="Nenhuma rede detectada.")
            return

        rec24 = analysis.get("recommendation_24", {})
        best24 = rec24.get("best_channel", 1)
        reasons24 = "\n".join(rec24.get("reasons", []))

        self.lbl_best_24.configure(
            text=f"Canal recomendado: {best24} (Menor interferência entre os canais permitidos 1 a 6)",
            text_color=COLORS["status_ok"],
        )
        self.lbl_reasons_24.configure(text=reasons24)

        rec5g = analysis.get("recommendation_5g", {})
        best5g = rec5g.get("best_channel", 36)
        reasons5g = "\n".join(rec5g.get("reasons", []))

        self.lbl_best_5g.configure(
            text=f"Canal recomendado: {best5g} (Melhor opção entre 36, 40 e 44)",
            text_color=COLORS["status_ok"],
        )
        self.lbl_reasons_5g.configure(text=reasons5g)


    # ================================================================
    # Renderização do Gráfico de Espectro
    # ================================================================

    def _render_spectrum_graph(self, channels_24: dict[int, list[dict]]):
        """Atualiza a densidade das barras verticais de cada canal 2.4 GHz."""
        # Encontra o maior número de redes em um único canal para escala
        max_nets = max([len(nets) for nets in channels_24.values()] + [1])

        for ch in range(1, 14):
            if ch in self._channel_bars_24:
                nets = channels_24.get(ch, [])
                count = len(nets)

                bar = self._channel_bars_24[ch]["bar"]
                lbl = self._channel_bars_24[ch]["count"]

                lbl.configure(text=str(count))

                # Fração de altura
                fraction = min(1.0, count / max_nets) if count > 0 else 0.0
                bar.set(fraction)

                # Cor conforme a densidade
                if count == 0:
                    bar.configure(progress_color=COLORS["accent"])
                elif count <= 2:
                    bar.configure(progress_color=COLORS["status_warning"])
                else:
                    bar.configure(progress_color=COLORS["status_error"])

    # ================================================================
    # Renderização da Tabela de Redes
    # ================================================================

    def _render_networks_table(self, networks: list[dict]):
        """Limpa e redesenha a tabela com a lista de redes."""
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        query = self.search_entry.get().strip().lower()

        filtered = [
            n for n in networks
            if not query or self._match_network_query(n, query)
        ]

        # Ordena por intensidade de sinal (mais forte primeiro)
        filtered.sort(key=lambda x: x["signal_pct"], reverse=True)

        for index, net in enumerate(filtered):
            self._create_network_row(net, index)

    def _create_network_row(self, net: dict, index: int):
        """Cria uma linha na tabela para a rede sem fio."""
        bg = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_card_alt"]

        row = ctk.CTkFrame(
            self.scroll_table,
            fg_color=bg,
            corner_radius=6,
            height=42,
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=8)
        inner.columnconfigure(0, weight=3)
        inner.columnconfigure(1, weight=2)
        inner.columnconfigure(2, weight=1)
        inner.columnconfigure(3, weight=1)
        inner.columnconfigure(4, weight=1)
        inner.columnconfigure(5, weight=2)
        inner.columnconfigure(6, weight=2)

        # SSID
        ctk.CTkLabel(
            inner, text=f"📶  {net['ssid']}",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=4)

        # BSSID (MAC)
        ctk.CTkLabel(
            inner, text=net["bssid"],
            font=FONTS["mono"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=4)

        # Banda
        ctk.CTkLabel(
            inner, text=net["band"],
            font=FONTS["body_bold"],
            text_color=COLORS["accent_cyan"],
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=4)

        # Canal
        ctk.CTkLabel(
            inner, text=f"Ch {net['channel']}",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=3, sticky="w", padx=4)

        # Frequência
        ctk.CTkLabel(
            inner, text=f"{net['frequency_mhz']} MHz",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=4, sticky="w", padx=4)

        # Sinal (dBm / %)
        rssi = net["rssi_dbm"]
        pct = net["signal_pct"]
        signal_color = COLORS["status_ok"] if rssi >= -65 else (COLORS["status_warning"] if rssi >= -78 else COLORS["status_error"])

        ctk.CTkLabel(
            inner, text=f"{rssi} dBm ({pct}%)",
            font=FONTS["body_bold"],
            text_color=signal_color,
            anchor="w",
        ).grid(row=0, column=5, sticky="w", padx=4)

        # Segurança
        ctk.CTkLabel(
            inner, text=net["security"],
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=6, sticky="w", padx=4)

        self._row_widgets.append(row)

    # ================================================================
    # Pesquisa em Tempo Real
    # ================================================================

    def _on_search(self, event=None):
        """Filtra a tabela de redes em tempo real."""
        self._render_networks_table(self._networks)

    @staticmethod
    def _match_network_query(net: dict, query: str) -> bool:
        """Verifica correspondência no filtro."""
        return (
            query in net["ssid"].lower()
            or query in net["bssid"].lower()
            or query in str(net["channel"])
            or query in net["band"].lower()
            or query in net["security"].lower()
        )
