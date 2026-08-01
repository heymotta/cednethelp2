"""
CedNet Help - Painel de Speed Test (Redesign Interativo em Tempo Real)
Interface inspirada no Speedtest.net com velocímetro animado em Canvas,
gráfico em tempo real, cronômetro, rastreador de etapas e integração com streaming do Ookla CLI.
"""

import customtkinter as ctk
import time
import os
import queue
from tkinter import filedialog
from typing import Optional

from modules.speedtest import (
    SpeedTestRunner,
    SpeedTestHistory,
    export_result_to_csv,
    copy_formatted_summary,
    detect_speedtest_engine,
    load_settings,
    save_setting,
)
from modules.network_manager import network_manager
from modules.utils import COLORS, FONTS
from ui.components.speedometer import SpeedometerCanvas
from ui.components.speedtest_chart import RealtimeChartCanvas


class SpeedTestPanel(ctk.CTkFrame):
    """Painel principal do Speed Test com UI animada em tempo real."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.runner = SpeedTestRunner()

        self._custom_engine_path: str = load_settings().get("speedtest_cli_path", "")
        self._latest_result: Optional[dict] = None

        # Fila thread-safe para comunicação entre worker e GUI
        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None

        # Cronômetro do teste
        self._test_start_time: Optional[float] = None
        self._timer_after_id: Optional[str] = None

        # Estado da fase atual
        self._current_phase = "idle"  # idle, server, ping, download, upload, complete

        self._create_ui()
        self._load_history_table()
        self._start_queue_polling()
        self._update_engine_badge()
        self._update_network_banner()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface interativa completa."""
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 1. Cabeçalho + Informações de Rede Pré-Teste ----
        header_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        header_card.pack(fill="x", pady=(0, 10))

        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=18, pady=12)

        # Título + Engine Badge
        title_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            title_frame,
            text="⚡  Speed Test Interativo",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.lbl_engine_badge = ctk.CTkLabel(
            title_frame,
            text="⚙️ Detectando...",
            font=FONTS["small_bold"],
            text_color=COLORS["accent_cyan"],
            anchor="e",
        )
        self.lbl_engine_badge.pack(side="right")

        # Banner de Conexão Pré-Teste (IP Local, Gateway, Interface)
        self.net_banner = ctk.CTkFrame(header_inner, fg_color=COLORS["entry_bg"], corner_radius=8)
        self.net_banner.pack(fill="x")

        net_inner = ctk.CTkFrame(self.net_banner, fg_color="transparent")
        net_inner.pack(fill="x", padx=12, pady=6)

        self.lbl_net_info = ctk.CTkLabel(
            net_inner,
            text="🌐 Conexão: IPv4: Carregando... | Gateway: Carregando... | Interface: Carregando...",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.lbl_net_info.pack(side="left")

        self.lbl_timer = ctk.CTkLabel(
            net_inner,
            text="⏱️ 00:00",
            font=FONTS["mono_bold"],
            text_color=COLORS["accent_cyan"],
            anchor="e",
        )
        self.lbl_timer.pack(side="right")

        # ---- 2. Barra de Progresso + Etapas do Teste ----
        steps_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=10)
        steps_card.pack(fill="x", pady=(0, 10))

        s_inner = ctk.CTkFrame(steps_card, fg_color="transparent")
        s_inner.pack(fill="x", padx=15, pady=10)

        # Rótulos dos Passos/Etapas
        self.step_frames: dict[str, ctk.CTkLabel] = {}
        steps_grid = ctk.CTkFrame(s_inner, fg_color="transparent")
        steps_grid.pack(fill="x", pady=(0, 6))
        steps_grid.columnconfigure((0, 1, 2, 3, 4), weight=1)

        steps_def = [
            ("server", "1. 🟢 Servidor"),
            ("ping", "2. ⏱️ Latência"),
            ("download", "3. 🚀 Download"),
            ("upload", "4. 📤 Upload"),
            ("complete", "5. ✔ Concluído"),
        ]

        for key, text in steps_def:
            lbl = ctk.CTkLabel(
                steps_grid,
                text=text,
                font=FONTS["small_bold"],
                text_color=COLORS["text_secondary"],
                anchor="center",
            )
            col_idx = len(self.step_frames)
            lbl.grid(row=0, column=col_idx, sticky="ew")
            self.step_frames[key] = lbl

        # Barra de progresso linear
        self.progress_bar = ctk.CTkProgressBar(
            s_inner,
            height=8,
            corner_radius=4,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(4, 4))
        self.progress_bar.set(0.0)

        self.lbl_status = ctk.CTkLabel(
            s_inner,
            text="Pronto para iniciar o teste de velocidade",
            font=FONTS["body_bold"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.lbl_status.pack(anchor="w")

        # ---- 3. Área Central: Velocímetro + Métricas em Tempo Real ----
        center_row = ctk.CTkFrame(container, fg_color="transparent")
        center_row.pack(fill="x", pady=(0, 10))
        center_row.columnconfigure(0, weight=0)  # Velocímetro
        center_row.columnconfigure(1, weight=1)  # Cards de Métricas

        # Card do Velocímetro Canvas
        gauge_card = ctk.CTkFrame(center_row, fg_color=COLORS["bg_card"], corner_radius=12)
        gauge_card.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        gauge_inner = ctk.CTkFrame(gauge_card, fg_color="transparent")
        gauge_inner.pack(padx=10, pady=10)

        self.speedometer = SpeedometerCanvas(
            gauge_inner, width=230, height=210, bg_color=COLORS["bg_card"]
        )
        self.speedometer.pack()

        # Botão Principal Ação (Iniciar / Cancelar / Novo Teste)
        self.btn_action = ctk.CTkButton(
            gauge_inner,
            text="🚀  Iniciar Teste",
            font=FONTS["body_bold"],
            height=40,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._on_action_click,
        )
        self.btn_action.pack(fill="x", pady=(4, 0))

        # Cards de Métricas em Tempo Real (Direita)
        metrics_card = ctk.CTkFrame(center_row, fg_color=COLORS["bg_card"], corner_radius=12)
        metrics_card.grid(row=0, column=1, padx=(5, 0), sticky="nsew")

        m_inner = ctk.CTkFrame(metrics_card, fg_color="transparent")
        m_inner.pack(fill="both", expand=True, padx=15, pady=12)

        m_grid = ctk.CTkFrame(m_inner, fg_color="transparent")
        m_grid.pack(fill="both", expand=True)
        m_grid.columnconfigure((0, 1), weight=1)
        m_grid.rowconfigure((0, 1), weight=1)

        # Download Metric Card
        c_dl = ctk.CTkFrame(m_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
        c_dl.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")
        cdl_i = ctk.CTkFrame(c_dl, fg_color="transparent")
        cdl_i.pack(fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(cdl_i, text="🚀  DOWNLOAD", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_dl_val = ctk.CTkLabel(cdl_i, text="0.0 Mbps", font=("Consolas", 20, "bold"), text_color=COLORS["accent_cyan"], anchor="w")
        self.lbl_dl_val.pack(anchor="w")
        self.lbl_dl_peak = ctk.CTkLabel(cdl_i, text="Pico: 0.0 Mbps", font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_dl_peak.pack(anchor="w")

        # Upload Metric Card
        c_ul = ctk.CTkFrame(m_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
        c_ul.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")
        cul_i = ctk.CTkFrame(c_ul, fg_color="transparent")
        cul_i.pack(fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(cul_i, text="📤  UPLOAD", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_ul_val = ctk.CTkLabel(cul_i, text="0.0 Mbps", font=("Consolas", 20, "bold"), text_color=COLORS["status_ok"], anchor="w")
        self.lbl_ul_val.pack(anchor="w")
        self.lbl_ul_peak = ctk.CTkLabel(cul_i, text="Pico: 0.0 Mbps", font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_ul_peak.pack(anchor="w")

        # Ping / Latência Card
        c_png = ctk.CTkFrame(m_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
        c_png.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")
        cpng_i = ctk.CTkFrame(c_png, fg_color="transparent")
        cpng_i.pack(fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(cpng_i, text="⏱️  PING (LATÊNCIA)", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_ping_val = ctk.CTkLabel(cpng_i, text="— ms", font=("Consolas", 20, "bold"), text_color=COLORS["accent_cyan"], anchor="w")
        self.lbl_ping_val.pack(anchor="w")
        self.lbl_jitter_val = ctk.CTkLabel(cpng_i, text="Jitter: — ms", font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_jitter_val.pack(anchor="w")

        # Perda de Pacotes / Qualidade Card
        c_loss = ctk.CTkFrame(m_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
        c_loss.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")
        closs_i = ctk.CTkFrame(c_loss, fg_color="transparent")
        closs_i.pack(fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(closs_i, text="📉  PERDA DE PACOTES", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_loss_val = ctk.CTkLabel(closs_i, text="0.0 %", font=("Consolas", 20, "bold"), text_color=COLORS["text_primary"], anchor="w")
        self.lbl_loss_val.pack(anchor="w")
        self.lbl_quality = ctk.CTkLabel(closs_i, text="Qualidade: Excelente", font=FONTS["small"], text_color=COLORS["status_ok"], anchor="w")
        self.lbl_quality.pack(anchor="w")

        # ---- 4. Gráfico Dinâmico em Tempo Real (Canvas) ----
        chart_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        chart_card.pack(fill="x", pady=(0, 10))

        chart_inner = ctk.CTkFrame(chart_card, fg_color="transparent")
        chart_inner.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            chart_inner,
            text="📊  Gráfico de Banda em Tempo Real",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        self.chart = RealtimeChartCanvas(
            chart_inner, width=760, height=130, bg_color=COLORS["bg_card"]
        )
        self.chart.pack(fill="x")

        # ---- 5. Card de Detalhes da Conexão ----
        details_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        details_card.pack(fill="x", pady=(0, 10))

        det_inner = ctk.CTkFrame(details_card, fg_color="transparent")
        det_inner.pack(fill="x", padx=15, pady=12)

        ctk.CTkLabel(
            det_inner,
            text="🌐  Servidor & Provedor Identificados",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        det_grid = ctk.CTkFrame(det_inner, fg_color="transparent")
        det_grid.pack(fill="x")
        det_grid.columnconfigure((0, 1, 2), weight=1)

        self._info_labels: dict[str, ctk.CTkLabel] = {}
        fields = [
            ("isp", "Provedor (ISP)", 0, 0),
            ("public_ip", "IP Público", 0, 1),
            ("server_name", "Servidor de Teste", 0, 2),
            ("server_location", "Localização / Cidade", 1, 0),
            ("date_time", "Data e Hora", 1, 1),
            ("elapsed", "Tempo Decorrido", 1, 2),
        ]

        for key, label, row, col in fields:
            cell = ctk.CTkFrame(det_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

            cell_inner = ctk.CTkFrame(cell, fg_color="transparent")
            cell_inner.pack(fill="x", padx=10, pady=6)

            ctk.CTkLabel(cell_inner, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
            val_lbl = ctk.CTkLabel(cell_inner, text="—", font=FONTS["mono"], text_color=COLORS["text_primary"], anchor="w")
            val_lbl.pack(anchor="w", pady=(2, 0))
            self._info_labels[key] = val_lbl

        # ---- 6. Barra de Ações / Exportação ----
        export_bar = ctk.CTkFrame(container, fg_color="transparent")
        export_bar.pack(fill="x", pady=(0, 10))

        self.btn_copy = ctk.CTkButton(
            export_bar,
            text="📋 Copiar Resultado",
            font=FONTS["small_bold"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=self._copy_results,
            state="disabled",
        )
        self.btn_copy.pack(side="left", padx=(0, 5))

        self.btn_csv = ctk.CTkButton(
            export_bar,
            text="📊 Exportar CSV",
            font=FONTS["small_bold"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=self._export_csv,
            state="disabled",
        )
        self.btn_csv.pack(side="left", padx=5)

        self.btn_config = ctk.CTkButton(
            export_bar,
            text="⚙️ Configurar Speedtest CLI",
            font=FONTS["small_bold"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=self._open_config_modal,
        )
        self.btn_config.pack(side="right")

        self.toast_label = ctk.CTkLabel(
            container, text="", font=FONTS["body"], text_color=COLORS["accent_cyan"]
        )
        self.toast_label.pack(pady=(0, 4))

        # ---- 7. Histórico Local de Testes ----
        history_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        history_card.pack(fill="x")

        hist_header = ctk.CTkFrame(history_card, fg_color="transparent")
        hist_header.pack(fill="x", padx=18, pady=(12, 6))

        ctk.CTkLabel(
            hist_header, text="📜  Histórico Local de Testes",
            font=FONTS["heading"], text_color=COLORS["text_primary"], anchor="w"
        ).pack(side="left")

        ctk.CTkButton(
            hist_header, text="Limpar Histórico", font=FONTS["small"],
            width=110, height=28, corner_radius=6,
            fg_color=COLORS["bg_sidebar"], hover_color=COLORS["status_error"],
            command=self._clear_history,
        ).pack(side="right")

        # Tabela Header
        th = ctk.CTkFrame(history_card, fg_color=COLORS["bg_sidebar"], corner_radius=6, height=32)
        th.pack(fill="x", padx=15, pady=(0, 4))
        th.pack_propagate(False)

        th_inner = ctk.CTkFrame(th, fg_color="transparent")
        th_inner.pack(fill="x", padx=10, pady=4)
        th_inner.columnconfigure(0, weight=2)
        th_inner.columnconfigure(1, weight=1)
        th_inner.columnconfigure(2, weight=2)
        th_inner.columnconfigure(3, weight=2)
        th_inner.columnconfigure(4, weight=1)
        th_inner.columnconfigure(5, weight=2)

        cols = [("Data/Hora", 0), ("Engine", 1), ("Download", 2), ("Upload", 3), ("Ping", 4), ("Provedor / Servidor", 5)]
        for name, idx in cols:
            ctk.CTkLabel(th_inner, text=name, font=FONTS["body_bold"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=idx, sticky="w", padx=2)

        self.scroll_history = ctk.CTkScrollableFrame(
            history_card, fg_color="transparent", height=150, scrollbar_button_color=COLORS["bg_card"]
        )
        self.scroll_history.pack(fill="x", padx=15, pady=(0, 12))
        self._history_rows: list[ctk.CTkFrame] = []

    # ================================================================
    # Atualizações de Rede Pré-Teste
    # ================================================================

    def _update_network_banner(self):
        """Atualiza a faixa de informações de rede local pré-teste."""
        st = network_manager.get_state()
        ip = st.get("ipv4", "Não detectado")
        gw = st.get("gateway", "Não detectado") or "Não disponível"
        iface = st.get("interface", "Não detectada")
        self.lbl_net_info.configure(
            text=f"🌐 Conexão Atual: IPv4: {ip}  |  Gateway: {gw}  |  Interface: {iface}"
        )
        self.after(3000, self._update_network_banner)

    def _update_engine_badge(self):
        engine_type, path = detect_speedtest_engine(self._custom_engine_path)
        if engine_type in ("ookla", "cli"):
            label = "Ookla Speedtest CLI" if engine_type == "ookla" else "Speedtest CLI"
            self.lbl_engine_badge.configure(text=f"⚙️ {label}", text_color=COLORS["accent_cyan"])
        else:
            self.lbl_engine_badge.configure(text="⚠️ CLI não encontrado", text_color=COLORS["status_warning"])

    # ================================================================
    # Loop de Comunicação Thread-Safe (Polling Queue)
    # ================================================================

    def _start_queue_polling(self):
        self._process_queue()

    def _process_queue(self):
        try:
            while True:
                msg_type, payload = self._ui_queue.get_nowait()
                if msg_type == "progress":
                    pct, msg, partial = payload
                    self._update_progress_ui(pct, msg, partial)
                elif msg_type == "complete":
                    self._on_test_complete(payload)
                elif msg_type == "error":
                    self._on_test_error(payload)
        except queue.Empty:
            pass

        self._poll_after_id = self.after(50, self._process_queue)

    # ================================================================
    # Controle do Teste & Cronômetro
    # ================================================================

    def _on_action_click(self):
        if self.runner.is_running():
            self._cancel_test()
        else:
            self._start_test()

    def _start_test(self):
        if self.runner.is_running():
            return

        # UI Estado Rodando
        self.btn_action.configure(
            text="🛑 Cancelar Teste",
            fg_color=COLORS["status_error"],
            hover_color="#c62828"
        )
        self.btn_copy.configure(state="disabled")
        self.btn_csv.configure(state="disabled")

        # Reset dos componentes gráficos
        self.speedometer.reset()
        self.chart.reset()
        self.progress_bar.set(0.05)
        self._set_active_step("server")

        # Reset dos labels
        self.lbl_dl_val.configure(text="0.0 Mbps")
        self.lbl_dl_peak.configure(text="Pico: 0.0 Mbps")
        self.lbl_ul_val.configure(text="0.0 Mbps")
        self.lbl_ul_peak.configure(text="Pico: 0.0 Mbps")
        self.lbl_ping_val.configure(text="— ms")
        self.lbl_jitter_val.configure(text="Jitter: — ms")
        self.lbl_loss_val.configure(text="0.0 %")
        self.lbl_status.configure(text="🟢 Conectando aos servidores...", text_color=COLORS["accent_cyan"])

        # Inicia Cronômetro
        self._test_start_time = time.time()
        self._start_timer()

        self.runner.run_test(
            custom_path=self._custom_engine_path,
            on_progress=lambda pct, msg, p: self._ui_queue.put(("progress", (pct, msg, p))),
            on_complete=lambda res: self._ui_queue.put(("complete", res)),
            on_error=lambda err: self._ui_queue.put(("error", err)),
        )

    def _cancel_test(self):
        self.runner.cancel_test()
        self._stop_timer()
        self._reset_ui_idle()
        self.lbl_status.configure(text="⏹️ Teste de velocidade cancelado pelo usuário.", text_color=COLORS["status_error"])

    def _start_timer(self):
        if self._test_start_time is None:
            return
        elapsed = int(time.time() - self._test_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        self.lbl_timer.configure(text=f"⏱️ {mins:02d}:{secs:02d}")
        self._timer_after_id = self.after(500, self._start_timer)

    def _stop_timer(self):
        if self._timer_after_id:
            self.after_cancel(self._timer_after_id)
            self._timer_after_id = None

    # ================================================================
    # Atualizações Interativas em Tempo Real
    # ================================================================

    def _set_active_step(self, step_key: str):
        self._current_phase = step_key
        for k, lbl in self.step_frames.items():
            if k == step_key:
                lbl.configure(text_color=COLORS["accent_cyan"])
            else:
                lbl.configure(text_color=COLORS["text_secondary"])

    def _update_progress_ui(self, percent: int, message: str, partial: dict):
        self.progress_bar.set(percent / 100.0)
        self.lbl_status.configure(text=message, text_color=COLORS["accent_cyan"])

        phase = partial.get("phase", "init")

        # Atualiza a etapa ativa
        if phase in self.step_frames:
            self._set_active_step(phase)

        # Servidor / ISP / IP Público
        if "isp" in partial and partial["isp"] != "—":
            self._info_labels["isp"].configure(text=partial["isp"])
        if "public_ip" in partial and partial["public_ip"] != "—":
            self._info_labels["public_ip"].configure(text=partial["public_ip"])
        if "server_name" in partial and partial["server_name"] != "—":
            self._info_labels["server_name"].configure(text=partial["server_name"])
        if "server_location" in partial and partial["server_location"] != "—":
            self._info_labels["server_location"].configure(text=partial["server_location"])

        # Latência e Jitter
        if "ping_ms" in partial and partial["ping_ms"] > 0:
            self.lbl_ping_val.configure(text=f"{partial['ping_ms']} ms")
        if "jitter_ms" in partial and partial["jitter_ms"] > 0:
            self.lbl_jitter_val.configure(text=f"Jitter: {partial['jitter_ms']} ms")

        # Download em tempo real
        if phase == "download" or "download_mbps" in partial:
            dl_val = partial.get("download_mbps", 0.0)
            dl_max = partial.get("download_max_mbps", dl_val)

            if dl_val > 0:
                self.lbl_dl_val.configure(text=f"{dl_val:.1f} Mbps")
                self.lbl_dl_peak.configure(text=f"Pico: {dl_max:.1f} Mbps")

                # Atualiza Velocímetro Canvas e Gráfico
                self.speedometer.set_mode("download")
                self.speedometer.set_value(dl_val)
                self.chart.add_point(dl_val, mode="download")

        # Upload em tempo real
        if phase == "upload" or "upload_mbps" in partial:
            ul_val = partial.get("upload_mbps", 0.0)
            ul_max = partial.get("upload_max_mbps", ul_val)

            if ul_val > 0:
                self.lbl_ul_val.configure(text=f"{ul_val:.1f} Mbps")
                self.lbl_ul_peak.configure(text=f"Pico: {ul_max:.1f} Mbps")

                # Alterna o velocímetro automaticamente para Upload
                self.speedometer.set_mode("upload")
                self.speedometer.set_value(ul_val)
                self.chart.add_point(ul_val, mode="upload")

    def _on_test_complete(self, result: dict):
        self._stop_timer()
        self._reset_ui_idle()
        self._latest_result = result
        self._set_active_step("complete")

        self.progress_bar.set(1.0)
        elapsed = result.get("elapsed_seconds", 0)
        self.lbl_status.configure(
            text=f"✔ Teste concluído com sucesso em {elapsed}s! (Engine: {result.get('engine', '')})",
            text_color=COLORS["status_ok"],
        )

        # Trava velocímetro no valor final do Download
        final_dl = result.get("download_mbps", 0.0)
        self.speedometer.set_mode("download")
        self.speedometer.set_value_instant(final_dl)

        # Atualiza métricas finais
        self.lbl_dl_val.configure(text=f"{final_dl:.2f} Mbps")
        self.lbl_dl_peak.configure(text=f"Pico: {result.get('download_max_mbps', final_dl):.2f} Mbps")

        final_ul = result.get("upload_mbps", 0.0)
        self.lbl_ul_val.configure(text=f"{final_ul:.2f} Mbps")
        self.lbl_ul_peak.configure(text=f"Pico: {result.get('upload_max_mbps', final_ul):.2f} Mbps")

        self.lbl_ping_val.configure(text=f"{result.get('ping_ms', 0)} ms")
        self.lbl_jitter_val.configure(text=f"Jitter: {result.get('jitter_ms', 0)} ms")
        loss = result.get("packet_loss_pct", 0.0)
        self.lbl_loss_val.configure(text=f"{loss:.1f} %")

        # Qualidade
        if loss == 0 and result.get("ping_ms", 99) < 25:
            self.lbl_quality.configure(text="Qualidade: Excelente 🟢", text_color=COLORS["status_ok"])
        elif loss < 2.0 and result.get("ping_ms", 99) < 60:
            self.lbl_quality.configure(text="Qualidade: Boa 🟡", text_color=COLORS["accent_cyan"])
        else:
            self.lbl_quality.configure(text="Qualidade: Instável 🔴", text_color=COLORS["status_error"])

        # Atualiza detalhes finais
        self._info_labels["isp"].configure(text=result.get("isp", "—"))
        self._info_labels["public_ip"].configure(text=result.get("public_ip", "—"))
        self._info_labels["server_name"].configure(text=result.get("server_name", "—"))
        self._info_labels["server_location"].configure(text=result.get("server_location", "—"))

        dt = f"{result.get('date_str', '')} {result.get('time_str', '')}"
        self._info_labels["date_time"].configure(text=dt)
        self._info_labels["elapsed"].configure(text=f"{elapsed}s")

        self.btn_copy.configure(state="normal")
        self.btn_csv.configure(state="normal")
        self._load_history_table()

    def _on_test_error(self, err_msg: str):
        self._stop_timer()
        self._reset_ui_idle()
        self.lbl_status.configure(text=err_msg, text_color=COLORS["status_error"])

    def _reset_ui_idle(self):
        self.btn_action.configure(
            text="🔄  Novo Teste" if self._latest_result else "🚀  Iniciar Teste",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )

    # ================================================================
    # Tabela de Histórico e Ações
    # ================================================================

    def _load_history_table(self):
        for w in self._history_rows:
            w.destroy()
        self._history_rows.clear()

        history = SpeedTestHistory.load_history()
        if not history:
            no_row = ctk.CTkFrame(self.scroll_history, fg_color="transparent")
            no_row.pack(fill="x", pady=10)
            ctk.CTkLabel(no_row, text="Nenhum teste registrado no histórico local.", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack()
            self._history_rows.append(no_row)
            return

        for idx, entry in enumerate(history):
            row = ctk.CTkFrame(
                self.scroll_history,
                fg_color=COLORS["bg_card"] if idx % 2 == 0 else COLORS["bg_card_alt"],
                corner_radius=4,
                height=32,
            )
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            r_inner = ctk.CTkFrame(row, fg_color="transparent")
            r_inner.pack(fill="x", padx=10, pady=4)
            r_inner.columnconfigure(0, weight=2)
            r_inner.columnconfigure(1, weight=1)
            r_inner.columnconfigure(2, weight=2)
            r_inner.columnconfigure(3, weight=2)
            r_inner.columnconfigure(4, weight=1)
            r_inner.columnconfigure(5, weight=2)

            dt_str = f"{entry.get('date_str', '')} {entry.get('time_str', '')}"
            ctk.CTkLabel(r_inner, text=dt_str, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=0, sticky="w", padx=2)
            ctk.CTkLabel(r_inner, text=entry.get("engine", "CLI")[:8], font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=1, sticky="w", padx=2)
            ctk.CTkLabel(r_inner, text=f"{entry.get('download_mbps', 0)} Mbps", font=FONTS["small_bold"], text_color=COLORS["accent_cyan"], anchor="w").grid(row=0, column=2, sticky="w", padx=2)
            ctk.CTkLabel(r_inner, text=f"{entry.get('upload_mbps', 0)} Mbps", font=FONTS["small_bold"], text_color=COLORS["status_ok"], anchor="w").grid(row=0, column=3, sticky="w", padx=2)
            ctk.CTkLabel(r_inner, text=f"{entry.get('ping_ms', 0)} ms", font=FONTS["small"], text_color=COLORS["text_primary"], anchor="w").grid(row=0, column=4, sticky="w", padx=2)

            prov_srv = f"{entry.get('isp', '')} / {entry.get('server_name', '')}"
            ctk.CTkLabel(r_inner, text=prov_srv[:28], font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=5, sticky="w", padx=2)

            self._history_rows.append(row)

    def _clear_history(self):
        SpeedTestHistory.clear_history()
        self._load_history_table()
        self._show_toast("🗑️ Histórico local limpo com sucesso.")

    def _copy_results(self):
        if self._latest_result:
            formatted_text = copy_formatted_summary(self._latest_result)
            self.clipboard_clear()
            self.clipboard_append(formatted_text)
            self._show_toast("📋 Relatório copiado para a área de transferência!")

    def _export_csv(self):
        if not self._latest_result:
            return

        filepath = filedialog.asksaveasfilename(
            title="Salvar Relatório em CSV",
            defaultextension=".csv",
            filetypes=[("Arquivo CSV", "*.csv"), ("Todos os Arquivos", "*.*")],
            initialfile=f"speedtest_{self._latest_result.get('date_str', '').replace('/', '-')}.csv",
        )

        if filepath:
            if export_result_to_csv(self._latest_result, filepath):
                self._show_toast(f"📊 Arquivo CSV salvo em: {filepath}")

    def _open_config_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Configurações do Speedtest CLI")
        modal.geometry("520x280")
        modal.resizable(False, False)
        modal.configure(fg_color=COLORS["bg_main"])
        modal.attributes("-topmost", True)
        modal.grab_set()

        ctk.CTkLabel(
            modal, text="⚙️  Configurar Executável Speedtest CLI",
            font=FONTS["subtitle"], text_color=COLORS["text_primary"]
        ).pack(pady=(20, 10))

        engine_type, current_path = detect_speedtest_engine(self._custom_engine_path)
        status_text = f"Engine Ativa: {engine_type.upper()} ({current_path})"

        ctk.CTkLabel(
            modal, text=status_text,
            font=FONTS["small"], text_color=COLORS["accent_cyan"], wraplength=480
        ).pack(pady=(0, 15))

        entry_frame = ctk.CTkFrame(modal, fg_color="transparent")
        entry_frame.pack(fill="x", padx=30, pady=(0, 15))

        path_entry = ctk.CTkEntry(
            entry_frame, font=FONTS["mono"], height=38,
            fg_color=COLORS["entry_bg"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="Caminho para speedtest.exe oficial da Ookla",
        )
        path_entry.insert(0, self._custom_engine_path)
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_file():
            f = filedialog.askopenfilename(
                title="Selecionar speedtest.exe da Ookla",
                filetypes=[("Executável Windows", "*.exe"), ("Todos os Arquivos", "*.*")],
            )
            if f:
                path_entry.delete(0, "end")
                path_entry.insert(0, f)

        ctk.CTkButton(
            entry_frame, text="Procurar...", font=FONTS["small_bold"],
            width=90, height=38, fg_color=COLORS["accent"], command=browse_file
        ).pack(side="right")

        def save_config():
            self._custom_engine_path = path_entry.get().strip()
            save_setting("speedtest_cli_path", self._custom_engine_path)
            self._update_engine_badge()
            modal.destroy()
            self._show_toast("✅ Configuração salva permanentemente!")

        ctk.CTkButton(
            modal, text="Salvar Configurações", font=FONTS["body_bold"],
            height=42, corner_radius=8, fg_color=COLORS["accent"], command=save_config
        ).pack(fill="x", padx=30)

    def _show_toast(self, message: str):
        self.toast_label.configure(text=message)
        self.after(5000, lambda: self.toast_label.configure(text=""))

    def stop_monitoring(self):
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None
        self._stop_timer()
        if self.runner.is_running():
            self.runner.cancel_test()
