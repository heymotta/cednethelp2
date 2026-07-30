"""
CedNet Help - Painel de Speed Test (Teste de Velocidade)
Interface moderna para medição de velocidade (Download, Upload, Ping, Jitter, Perda),
detecção de ISP/IP, histórico local armazenado e exportação de relatórios.
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
from modules.utils import COLORS, FONTS


class SpeedTestPanel(ctk.CTkFrame):
    """Painel principal do Speed Test."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.runner = SpeedTestRunner()

        self._custom_engine_path: str = load_settings().get("speedtest_cli_path", "")
        self._latest_result: Optional[dict] = None

        # Fila thread-safe para comunicação entre a thread de teste e a GUI
        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None

        self._create_ui()
        self._load_history_table()
        self._start_queue_polling()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface completa do Speed Test."""
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 1. Cabeçalho + Controles ----
        header_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        header_card.pack(fill="x", pady=(0, 12))

        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=20, pady=15)

        # Título + Subtítulo
        title_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            title_frame,
            text="⚡  Speed Test",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        # Engine badge (Ookla / Speedtest Engine)
        engine_type, _ = detect_speedtest_engine()
        engine_label = "Ookla Speedtest CLI" if engine_type == "ookla" else "Speedtest Engine"
        self.lbl_engine_badge = ctk.CTkLabel(
            title_frame,
            text=f"⚙️ {engine_label}",
            font=FONTS["small_bold"],
            text_color=COLORS["accent_cyan"],
            anchor="e",
        )
        self.lbl_engine_badge.pack(side="right")

        # Botões de Iniciar / Cancelar
        ctrl_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        ctrl_frame.pack(fill="x")

        self.btn_start = ctk.CTkButton(
            ctrl_frame,
            text="Iniciar Teste",
            font=FONTS["body_bold"],
            height=44,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._start_test,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_cancel = ctk.CTkButton(
            ctrl_frame,
            text="Cancelar",
            font=FONTS["body_bold"],
            width=140,
            height=44,
            corner_radius=10,
            fg_color=COLORS["bg_sidebar"],
            hover_color=COLORS["bg_card_hover"],
            command=self._cancel_test,
            state="disabled",
        )
        self.btn_cancel.pack(side="right", padx=(5, 0))

        # ---- 2. Progresso & Status do Teste ----
        self.progress_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
        )
        self.progress_card.pack(fill="x", pady=(0, 12))

        p_inner = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        p_inner.pack(fill="x", padx=15, pady=10)

        self.progress_bar = ctk.CTkProgressBar(
            p_inner,
            height=10,
            corner_radius=5,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0.0)

        self.lbl_status = ctk.CTkLabel(
            p_inner,
            text="Pronto para iniciar o teste de velocidade",
            font=FONTS["body_bold"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.lbl_status.pack(anchor="w")

        # ---- 3. Cards de Métricas Principais (Download, Upload, Ping, Jitter) ----
        metrics_grid = ctk.CTkFrame(container, fg_color="transparent")
        metrics_grid.pack(fill="x", pady=(0, 12))
        metrics_grid.columnconfigure((0, 1, 2, 3), weight=1)

        # Card Download
        card_dl = ctk.CTkFrame(metrics_grid, fg_color=COLORS["bg_card"], corner_radius=12)
        card_dl.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")
        inner_dl = ctk.CTkFrame(card_dl, fg_color="transparent")
        inner_dl.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(inner_dl, text="🚀  DOWNLOAD", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_download = ctk.CTkLabel(inner_dl, text="— Mbps", font=("Consolas", 22, "bold"), text_color=COLORS["accent_cyan"], anchor="w")
        self.lbl_download.pack(anchor="w", pady=(4, 0))

        # Card Upload
        card_ul = ctk.CTkFrame(metrics_grid, fg_color=COLORS["bg_card"], corner_radius=12)
        card_ul.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")
        inner_ul = ctk.CTkFrame(card_ul, fg_color="transparent")
        inner_ul.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(inner_ul, text="📤  UPLOAD", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_upload = ctk.CTkLabel(inner_ul, text="— Mbps", font=("Consolas", 22, "bold"), text_color=COLORS["status_ok"], anchor="w")
        self.lbl_upload.pack(anchor="w", pady=(4, 0))

        # Card Ping
        card_ping = ctk.CTkFrame(metrics_grid, fg_color="transparent")
        card_ping.grid(row=0, column=2, padx=3, pady=3, sticky="nsew")
        card_ping_frame = ctk.CTkFrame(card_ping, fg_color=COLORS["bg_card"], corner_radius=12)
        card_ping_frame.pack(fill="both", expand=True)
        inner_ping = ctk.CTkFrame(card_ping_frame, fg_color="transparent")
        inner_ping.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(inner_ping, text="⏱️  PING (Latência)", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_ping = ctk.CTkLabel(inner_ping, text="— ms", font=("Consolas", 22, "bold"), text_color=COLORS["accent_cyan"], anchor="w")
        self.lbl_ping.pack(anchor="w", pady=(4, 0))

        # Card Jitter / Loss
        card_jit = ctk.CTkFrame(metrics_grid, fg_color="transparent")
        card_jit.grid(row=0, column=3, padx=3, pady=3, sticky="nsew")
        card_jit_frame = ctk.CTkFrame(card_jit, fg_color=COLORS["bg_card"], corner_radius=12)
        card_jit_frame.pack(fill="both", expand=True)
        inner_jit = ctk.CTkFrame(card_jit_frame, fg_color="transparent")
        inner_jit.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(inner_jit, text="📉  JITTER / PERDA", font=FONTS["small_bold"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        self.lbl_jitter = ctk.CTkLabel(inner_jit, text="— ms", font=("Consolas", 22, "bold"), text_color=COLORS["text_primary"], anchor="w")
        self.lbl_jitter.pack(anchor="w", pady=(4, 0))

        # ---- 4. Card de Detalhes da Conexão (ISP, IP, Servidor) ----
        details_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        details_card.pack(fill="x", pady=(0, 12))

        det_inner = ctk.CTkFrame(details_card, fg_color="transparent")
        det_inner.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            det_inner, text="🌐  Informações da Conexão e Servidor",
            font=FONTS["heading"], text_color=COLORS["text_primary"], anchor="w"
        ).pack(anchor="w", pady=(0, 10))

        det_grid = ctk.CTkFrame(det_inner, fg_color="transparent")
        det_grid.pack(fill="x")
        det_grid.columnconfigure((0, 1, 2), weight=1)

        self._info_labels: dict[str, ctk.CTkLabel] = {}
        fields = [
            ("isp",             "Provedor (ISP)",        0, 0),
            ("public_ip",       "IP Público",            0, 1),
            ("server_name",     "Servidor de Teste",     0, 2),
            ("server_location", "Localização / Cidade",  1, 0),
            ("date_time",       "Data e Hora",           1, 1),
            ("elapsed",         "Tempo do Teste",        1, 2),
        ]

        for key, label, row, col in fields:
            cell = ctk.CTkFrame(det_grid, fg_color=COLORS["entry_bg"], corner_radius=8)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

            cell_inner = ctk.CTkFrame(cell, fg_color="transparent")
            cell_inner.pack(fill="x", padx=10, pady=8)

            ctk.CTkLabel(cell_inner, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
            val_lbl = ctk.CTkLabel(cell_inner, text="—", font=FONTS["mono"], text_color=COLORS["text_primary"], anchor="w")
            val_lbl.pack(anchor="w", pady=(2, 0))
            self._info_labels[key] = val_lbl

        # ---- 5. Barra de Ações & Exportação ----
        export_bar = ctk.CTkFrame(container, fg_color="transparent")
        export_bar.pack(fill="x", pady=(0, 12))

        self.btn_copy = ctk.CTkButton(
            export_bar,
            text="Copiar Resultado",
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
            text="Exportar CSV",
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
            text="Configurar Speedtest CLI",
            font=FONTS["small_bold"],
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=self._open_config_modal,
        )
        self.btn_config.pack(side="right")

        # Toast notification
        self.toast_label = ctk.CTkLabel(
            container, text="", font=FONTS["body"], text_color=COLORS["accent_cyan"]
        )
        self.toast_label.pack(pady=(0, 6))

        # ---- 6. Tabela de Histórico Local ----
        history_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        history_card.pack(fill="x")

        hist_header = ctk.CTkFrame(history_card, fg_color="transparent")
        hist_header.pack(fill="x", padx=20, pady=(15, 8))

        ctk.CTkLabel(
            hist_header, text="📜  Histórico Local de Testes",
            font=FONTS["heading"], text_color=COLORS["text_primary"], anchor="w"
        ).pack(side="left")

        ctk.CTkButton(
            hist_header,
            text="Limpar Histórico",
            font=FONTS["small"],
            width=110, height=28, corner_radius=6,
            fg_color=COLORS["bg_sidebar"],
            hover_color=COLORS["status_error"],
            command=self._clear_history,
        ).pack(side="right")

        # Header da tabela
        th = ctk.CTkFrame(history_card, fg_color=COLORS["bg_sidebar"], corner_radius=6, height=36)
        th.pack(fill="x", padx=15, pady=(0, 4))
        th.pack_propagate(False)

        th_inner = ctk.CTkFrame(th, fg_color="transparent")
        th_inner.pack(fill="x", padx=12, pady=6)
        th_inner.columnconfigure(0, weight=2)
        th_inner.columnconfigure(1, weight=1)
        th_inner.columnconfigure(2, weight=2)
        th_inner.columnconfigure(3, weight=2)
        th_inner.columnconfigure(4, weight=1)
        th_inner.columnconfigure(5, weight=2)

        cols = [("Data/Hora", 0), ("Engine", 1), ("Download", 2), ("Upload", 3), ("Ping", 4), ("Provedor / Servidor", 5)]
        for name, idx in cols:
            ctk.CTkLabel(th_inner, text=name, font=FONTS["body_bold"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=idx, sticky="w", padx=3)

        # Corpo scrollável
        self.scroll_history = ctk.CTkScrollableFrame(
            history_card,
            fg_color="transparent",
            height=180,
            scrollbar_button_color=COLORS["bg_card"],
        )
        self.scroll_history.pack(fill="x", padx=15, pady=(0, 15))

        self._history_rows: list[ctk.CTkFrame] = []

    # ================================================================
    # Communication Polling Loop
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

        self._poll_after_id = self.after(100, self._process_queue)

    # ================================================================
    # Execução do Teste
    # ================================================================

    def _start_test(self):
        """Inicia a medição de velocidade."""
        if self.runner.is_running():
            return

        # UI Estado Rodando
        self.btn_start.configure(state="disabled", text="⏳  Escaneando...")
        self.btn_cancel.configure(state="normal", fg_color=COLORS["status_error"], hover_color="#c62828")
        self.btn_copy.configure(state="disabled")
        self.btn_csv.configure(state="disabled")

        self.progress_bar.set(0.05)
        self.lbl_status.configure(text="Iniciando teste de velocidade...", text_color=COLORS["accent_cyan"])

        # Reset campos
        self.lbl_download.configure(text="— Mbps")
        self.lbl_upload.configure(text="— Mbps")
        self.lbl_ping.configure(text="— ms")
        self.lbl_jitter.configure(text="— ms")

        self.runner.run_test(
            custom_path=self._custom_engine_path,
            on_progress=lambda pct, msg, p: self._ui_queue.put(("progress", (pct, msg, p))),
            on_complete=lambda res: self._ui_queue.put(("complete", res)),
            on_error=lambda err: self._ui_queue.put(("error", err)),
        )

    def _cancel_test(self):
        """Cancela o teste."""
        self.runner.cancel_test()
        self._reset_ui_idle()
        self.lbl_status.configure(text="⏹️ Teste cancelado.", text_color=COLORS["status_error"])

    def _update_progress_ui(self, percent: int, message: str, partial: dict):
        """Atualiza barra e rótulos de progresso."""
        self.progress_bar.set(percent / 100.0)
        self.lbl_status.configure(text=message, text_color=COLORS["accent_cyan"])

        if "download_mbps" in partial:
            self.lbl_download.configure(text=f"{partial['download_mbps']} Mbps")
        if "upload_mbps" in partial:
            self.lbl_upload.configure(text=f"{partial['upload_mbps']} Mbps")
        if "ping_ms" in partial:
            self.lbl_ping.configure(text=f"{partial['ping_ms']} ms")
        if "isp" in partial:
            self._info_labels["isp"].configure(text=partial["isp"])
        if "public_ip" in partial:
            self._info_labels["public_ip"].configure(text=partial["public_ip"])
        if "server_name" in partial:
            self._info_labels["server_name"].configure(text=partial["server_name"])

    def _on_test_complete(self, result: dict):
        """Callback acionado ao finalizar o teste."""
        self._reset_ui_idle()
        self._latest_result = result

        self.progress_bar.set(1.0)
        self.lbl_status.configure(
            text=f"✅ Teste concluído em {result.get('elapsed_seconds', 0)}s! (Engine: {result.get('engine', '')})",
            text_color=COLORS["status_ok"],
        )

        # Atualiza métricas
        self.lbl_download.configure(text=f"{result.get('download_mbps', 0)} Mbps")
        self.lbl_upload.configure(text=f"{result.get('upload_mbps', 0)} Mbps")
        self.lbl_ping.configure(text=f"{result.get('ping_ms', 0)} ms")

        jit = result.get("jitter_ms", 0)
        loss = result.get("packet_loss_pct", 0)
        self.lbl_jitter.configure(text=f"{jit} ms / {loss}% loss")

        # Atualiza detalhes
        self._info_labels["isp"].configure(text=result.get("isp", "—"))
        self._info_labels["public_ip"].configure(text=result.get("public_ip", "—"))
        self._info_labels["server_name"].configure(text=result.get("server_name", "—"))
        self._info_labels["server_location"].configure(text=result.get("server_location", "—"))

        dt = f"{result.get('date_str', '')} {result.get('time_str', '')}"
        self._info_labels["date_time"].configure(text=dt)
        self._info_labels["elapsed"].configure(text=f"{result.get('elapsed_seconds', 0)}s")

        # Habilita botões de exportação
        self.btn_copy.configure(state="normal")
        self.btn_csv.configure(state="normal")

        # Recarrega a tabela de histórico
        self._load_history_table()

    def _on_test_error(self, err_msg: str):
        """Callback acionado em caso de falha."""
        self._reset_ui_idle()
        self.lbl_status.configure(text=err_msg, text_color=COLORS["status_error"])

    def _reset_ui_idle(self):
        """Restaura a UI para estado ocioso."""
        self.btn_start.configure(state="normal", text="Iniciar Teste")
        self.btn_cancel.configure(state="disabled", fg_color=COLORS["bg_sidebar"])

    # ================================================================
    # Histórico Local
    # ================================================================

    def _load_history_table(self):
        """Carrega e renderiza o histórico local."""
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
                height=34,
            )
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            r_inner = ctk.CTkFrame(row, fg_color="transparent")
            r_inner.pack(fill="x", padx=12, pady=5)
            r_inner.columnconfigure(0, weight=2)
            r_inner.columnconfigure(1, weight=1)
            r_inner.columnconfigure(2, weight=2)
            r_inner.columnconfigure(3, weight=2)
            r_inner.columnconfigure(4, weight=1)
            r_inner.columnconfigure(5, weight=2)

            dt_str = f"{entry.get('date_str', '')} {entry.get('time_str', '')}"
            ctk.CTkLabel(r_inner, text=dt_str, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=0, sticky="w", padx=3)
            ctk.CTkLabel(r_inner, text=entry.get("engine", "CLI")[:8], font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=1, sticky="w", padx=3)
            ctk.CTkLabel(r_inner, text=f"{entry.get('download_mbps', 0)} Mbps", font=FONTS["small_bold"], text_color=COLORS["accent_cyan"], anchor="w").grid(row=0, column=2, sticky="w", padx=3)
            ctk.CTkLabel(r_inner, text=f"{entry.get('upload_mbps', 0)} Mbps", font=FONTS["small_bold"], text_color=COLORS["status_ok"], anchor="w").grid(row=0, column=3, sticky="w", padx=3)
            ctk.CTkLabel(r_inner, text=f"{entry.get('ping_ms', 0)} ms", font=FONTS["small"], text_color=COLORS["text_primary"], anchor="w").grid(row=0, column=4, sticky="w", padx=3)

            prov_srv = f"{entry.get('isp', '')} / {entry.get('server_name', '')}"
            ctk.CTkLabel(r_inner, text=prov_srv[:30], font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").grid(row=0, column=5, sticky="w", padx=3)

            self._history_rows.append(row)

    def _clear_history(self):
        """Limpa o histórico."""
        SpeedTestHistory.clear_history()
        self._load_history_table()
        self._show_toast("🗑️ Histórico local limpo com sucesso.")

    # ================================================================
    # Ações e Exportação
    # ================================================================

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
        """Abre modal para configurar o caminho do Speedtest CLI."""
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
            new_engine, _ = detect_speedtest_engine(self._custom_engine_path)
            engine_label = "Ookla Speedtest CLI" if new_engine == "ookla" else "Speedtest Engine"
            self.lbl_engine_badge.configure(text=f"⚙️ {engine_label}")
            modal.destroy()
            self._show_toast("✅ Configuração do Speedtest salva permanentemente!")

        ctk.CTkButton(
            modal, text="Salvar Configurações", font=FONTS["body_bold"],
            height=42, corner_radius=8, fg_color=COLORS["accent"], command=save_config
        ).pack(fill="x", padx=30)

    def _show_toast(self, message: str):
        self.toast_label.configure(text=message)
        self.after(5000, lambda: self.toast_label.configure(text=""))

    def stop_monitoring(self):
        """Cancela polling ao fechar."""
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None

        if self.runner.is_running():
            self.runner.cancel_test()
