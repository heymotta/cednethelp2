"""
CedNet Help - Interface da Aba Teste de DNS (ui/dns_panel.py)
Exibe cartões de servidores DNS em tempo real, indicador de melhor servidor (Hero Card) e tabela de ranking.
"""

import customtkinter as ctk
import time
import queue
from typing import Optional, Dict, List
from modules.dns_models import DNSProvider, DNSTestResult, DNSBenchmarkSummary
from modules.dns_repository import DNSRepository
from modules.dns_tester import DNSTester
from modules.utils import COLORS, FONTS


class DNSPanel(ctk.CTkFrame):
    """Painel completo de Teste de Desempenho de DNS."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.repository = DNSRepository()
        self.tester = DNSTester(self.repository)

        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None

        self._provider_cards: Dict[str, ctk.CTkFrame] = {}
        self._provider_latency_labels: Dict[str, ctk.CTkLabel] = {}
        self._provider_status_labels: Dict[str, ctk.CTkLabel] = {}
        self._results_map: Dict[str, DNSTestResult] = {}

        self._create_ui()
        self._start_queue_polling()

    # ================================================================
    # Construção da Interface Gráfica
    # ================================================================

    def _create_ui(self):
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 1. Cabeçalho ----
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="⚡  Teste de Desempenho de DNS",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Mede o tempo real de resolução DNS com múltiplas consultas para identificar o servidor mais rápido",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # ---- 2. Hero Card: Melhor Servidor DNS ----
        self.hero_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.hero_card.pack(fill="x", pady=(0, 12))
        self._render_hero_card_content(None)

        # ---- 3. Painel de Controle e Progresso ----
        ctrl_card = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=12)
        ctrl_card.pack(fill="x", pady=(0, 12))

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=14)

        btn_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 10))

        self.btn_start = ctk.CTkButton(
            btn_row,
            text="Iniciar Teste de DNS",
            font=FONTS["body_bold"],
            height=40,
            width=200,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._on_click_start,
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancelar",
            font=FONTS["body_bold"],
            height=40,
            width=120,
            corner_radius=8,
            fg_color=COLORS["bg_sidebar"],
            hover_color=COLORS["status_error"],
            text_color=COLORS["text_secondary"],
            state="disabled",
            command=self._on_click_cancel,
        )
        self.btn_cancel.pack(side="left")

        self.lbl_progress_status = ctk.CTkLabel(
            btn_row,
            text="Pronto para iniciar os testes.",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            anchor="e",
        )
        self.lbl_progress_status.pack(side="right")

        # Barra de Progresso
        prog_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        prog_row.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            prog_row,
            height=8,
            corner_radius=4,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.progress_bar.set(0.0)

        self.lbl_pct = ctk.CTkLabel(
            prog_row,
            text="0%",
            font=FONTS["mono_bold"],
            text_color=COLORS["accent_cyan"],
            width=45,
        )
        self.lbl_pct.pack(side="right")

        # ---- 4. Seção Dupla: Grid de Cards + Tabela de Ranking ----
        body_split = ctk.CTkFrame(container, fg_color="transparent")
        body_split.pack(fill="x")
        body_split.columnconfigure(0, weight=3)
        body_split.columnconfigure(1, weight=2)

        # Coluna Esquerda: Grid de Cards dos Provedores
        left_box = ctk.CTkFrame(body_split, fg_color="transparent")
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(
            left_box,
            text="📡 Servidores DNS Públicos",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        self.cards_grid_frame = ctk.CTkFrame(left_box, fg_color="transparent")
        self.cards_grid_frame.pack(fill="x")
        self.cards_grid_frame.columnconfigure((0, 1), weight=1)

        self._build_provider_cards()

        # Coluna Direita: Tabela de Ranking
        right_box = ctk.CTkFrame(body_split, fg_color=COLORS["bg_card"], corner_radius=12)
        right_box.grid(row=0, column=1, sticky="nsew")

        right_inner = ctk.CTkFrame(right_box, fg_color="transparent")
        right_inner.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            right_inner,
            text="📊 Ranking de Latência",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        self.ranking_container = ctk.CTkFrame(right_inner, fg_color="transparent")
        self.ranking_container.pack(fill="both", expand=True)

        self._update_ranking_table([])

    # ================================================================
    # Renderização de Sub-componentes
    # ================================================================

    def _render_hero_card_content(self, best_res: Optional[DNSTestResult]):
        """Atualiza a caixa de destaque do melhor servidor DNS encontrado."""
        for child in self.hero_card.winfo_children():
            child.destroy()

        inner = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)

        if best_res and best_res.status == "Concluído" and best_res.latency_ms is not None:
            self.hero_card.configure(border_color=COLORS["accent"], border_width=2)
            
            top_line = ctk.CTkFrame(inner, fg_color="transparent")
            top_line.pack(fill="x", pady=(0, 6))

            ctk.CTkLabel(
                top_line,
                text="🏆  Melhor Servidor DNS Encontrado",
                font=FONTS["heading"],
                text_color=COLORS["accent_cyan"],
                anchor="w",
            ).pack(side="left")

            badge = ctk.CTkFrame(top_line, fg_color="#1b5e20", corner_radius=6)
            badge.pack(side="right")
            ctk.CTkLabel(
                badge,
                text="Recomendado",
                font=FONTS["small_bold"],
                text_color="#81c784",
                padx=8,
                pady=2,
            ).pack()

            # Detalhes do Servidor Campeão
            p = best_res.provider
            details_frame = ctk.CTkFrame(inner, fg_color="transparent")
            details_frame.pack(fill="x")
            details_frame.columnconfigure((0, 1, 2, 3), weight=1)

            self._create_hero_item(details_frame, "Provedor", p.name, 0)
            self._create_hero_item(details_frame, "DNS Primário", p.primary_ip, 1)
            self._create_hero_item(details_frame, "DNS Secundário", p.secondary_ip, 2)
            self._create_hero_item(details_frame, "Latência Média", best_res.formatted_latency, 3, highlight=True)

        else:
            self.hero_card.configure(border_color=COLORS["border"], border_width=1)
            ctk.CTkLabel(
                inner,
                text="🏆  Melhor Servidor DNS: -- (Aguardando início do teste)",
                font=FONTS["body_bold"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w")

    def _create_hero_item(self, parent, label: str, val: str, col: int, highlight: bool = False):
        box = ctk.CTkFrame(parent, fg_color=COLORS["entry_bg"], corner_radius=6)
        box.grid(row=0, column=col, padx=3, pady=2, sticky="nsew")

        box_inner = ctk.CTkFrame(box, fg_color="transparent")
        box_inner.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(box_inner, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        color = COLORS["status_ok"] if highlight else COLORS["text_primary"]
        font = FONTS["heading"] if highlight else FONTS["mono_bold"]
        ctk.CTkLabel(box_inner, text=val, font=font, text_color=color, anchor="w").pack(anchor="w")

    def _build_provider_cards(self):
        """Constrói os 14 cartões de servidores DNS no grid."""
        providers = self.repository.load_providers()

        for idx, p in enumerate(providers):
            row = idx // 2
            col = idx % 2

            card = ctk.CTkFrame(
                self.cards_grid_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=10,
                border_width=1,
                border_color=COLORS["border"],
            )
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=12, pady=10)

            # Cabeçalho do Card (Nome + Categoria)
            top_row = ctk.CTkFrame(card_inner, fg_color="transparent")
            top_row.pack(fill="x", pady=(0, 4))

            ctk.CTkLabel(
                top_row,
                text=p.name,
                font=FONTS["body_bold"],
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                top_row,
                text=p.category,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
                anchor="e",
            ).pack(side="right")

            # IPs Primário e Secundário
            ip_str = f"P: {p.primary_ip}  |  S: {p.secondary_ip}"
            ctk.CTkLabel(
                card_inner,
                text=ip_str,
                font=FONTS["mono"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w", pady=(0, 6))

            # Rodapé do Card (Latência + Status Badge)
            bottom_row = ctk.CTkFrame(card_inner, fg_color="transparent")
            bottom_row.pack(fill="x")

            lbl_lat = ctk.CTkLabel(
                bottom_row,
                text="-- ms",
                font=FONTS["heading"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            )
            lbl_lat.pack(side="left")

            lbl_status = ctk.CTkLabel(
                bottom_row,
                text="Aguardando",
                font=FONTS["small_bold"],
                text_color=COLORS["text_secondary"],
                anchor="e",
            )
            lbl_status.pack(side="right")

            # Armazena referências para atualizações em tempo real
            self._provider_cards[p.id] = card
            self._provider_latency_labels[p.id] = lbl_lat
            self._provider_status_labels[p.id] = lbl_status

    def _update_ranking_table(self, results: List[DNSTestResult]):
        """Atualiza a tabela ordenada de ranking à direita."""
        for child in self.ranking_container.winfo_children():
            child.destroy()

        if not results:
            ctk.CTkLabel(
                self.ranking_container,
                text="Nenhum teste realizado ainda.",
                font=FONTS["body"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(pady=20)
            return

        # Ordena: Concluídos primeiro (menor latência), depois Timeouts/Erros
        completed = [r for r in results if r.status == "Concluído" and r.latency_ms is not None]
        others = [r for r in results if r not in completed]

        completed.sort(key=lambda r: r.latency_ms)
        sorted_results = completed + others

        medals = ["🥇 1º", "🥈 2º", "🥉 3º"]

        for idx, res in enumerate(sorted_results, start=1):
            row_frame = ctk.CTkFrame(
                self.ranking_container,
                fg_color=COLORS["entry_bg"] if idx % 2 == 0 else COLORS["bg_card"],
                corner_radius=6,
            )
            row_frame.pack(fill="x", pady=2)

            row_inner = ctk.CTkFrame(row_frame, fg_color="transparent")
            row_inner.pack(fill="x", padx=10, pady=6)

            pos_text = medals[idx - 1] if idx <= 3 else f"   {idx}º"

            ctk.CTkLabel(
                row_inner,
                text=pos_text,
                font=FONTS["body_bold"],
                text_color=COLORS["accent_cyan"] if idx <= 3 else COLORS["text_secondary"],
                width=55,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row_inner,
                text=res.provider.name,
                font=FONTS["body"],
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            lat_color = COLORS["status_ok"] if res.status == "Concluído" else COLORS["status_error"]
            ctk.CTkLabel(
                row_inner,
                text=res.formatted_latency,
                font=FONTS["mono_bold"],
                text_color=lat_color,
                anchor="e",
                width=80,
            ).pack(side="right")

    # ================================================================
    # Eventos de Botões e Controle de Teste
    # ================================================================

    def _on_click_start(self):
        """Inicia a sequência de testes de DNS."""
        if self.tester.is_running():
            return

        # Restaura a interface
        self._reset_ui_for_test()

        self.btn_start.configure(state="disabled", fg_color=COLORS["bg_sidebar"])
        self.btn_cancel.configure(state="normal", fg_color=COLORS["status_error"], text_color=COLORS["text_primary"])
        self.lbl_progress_status.configure(text="Iniciando teste de latência...")

        self.tester.start_test(
            on_provider_start=lambda p: self._ui_queue.put(("start", p)),
            on_provider_complete=lambda r: self._ui_queue.put(("complete", r)),
            on_progress=lambda pct, curr, tot: self._ui_queue.put(("progress", (pct, curr, tot))),
            on_finish=lambda summary: self._ui_queue.put(("finish", summary)),
            on_error=lambda err: self._ui_queue.put(("error", err)),
        )

    def _on_click_cancel(self):
        """Solicita cancelamento do teste."""
        if self.tester.is_running():
            self.tester.stop_test()
            self.lbl_progress_status.configure(text="Cancelando teste...")
            self.btn_cancel.configure(state="disabled")

    def _reset_ui_for_test(self):
        """Limpa resultados anteriores e redefine os cards."""
        self._results_map.clear()
        self.progress_bar.set(0.0)
        self.lbl_pct.configure(text="0%")
        self._render_hero_card_content(None)
        self._update_ranking_table([])

        for p_id, card in self._provider_cards.items():
            card.configure(border_color=COLORS["border"], border_width=1)
            self._provider_latency_labels[p_id].configure(text="-- ms", text_color=COLORS["text_secondary"])
            self._provider_status_labels[p_id].configure(text="Aguardando", text_color=COLORS["text_secondary"])

    # ================================================================
    # Polling Thread-Safe de Mensagens da UI Queue
    # ================================================================

    def _start_queue_polling(self):
        self._process_queue()

    def _process_queue(self):
        try:
            while True:
                msg_type, payload = self._ui_queue.get_nowait()
                if msg_type == "start":
                    self._on_provider_start_ui(payload)
                elif msg_type == "complete":
                    self._on_provider_complete_ui(payload)
                elif msg_type == "progress":
                    self._on_progress_ui(payload)
                elif msg_type == "finish":
                    self._on_finish_ui(payload)
                elif msg_type == "error":
                    self._on_error_ui(payload)
        except queue.Empty:
            pass

        self._poll_after_id = self.after(50, self._process_queue)

    def _on_provider_start_ui(self, provider: DNSProvider):
        p_id = provider.id
        if p_id in self._provider_status_labels:
            self._provider_status_labels[p_id].configure(text="Testando...", text_color=COLORS["accent_cyan"])
            self._provider_latency_labels[p_id].configure(text="...", text_color=COLORS["accent_cyan"])

    def _on_provider_complete_ui(self, res: DNSTestResult):
        p_id = res.provider.id
        self._results_map[p_id] = res

        if p_id in self._provider_latency_labels:
            self._provider_latency_labels[p_id].configure(
                text=res.formatted_latency,
                text_color=COLORS["status_ok"] if res.status == "Concluído" else COLORS["status_error"],
            )

        if p_id in self._provider_status_labels:
            status_color = COLORS["status_ok"] if res.status == "Concluído" else COLORS["status_error"]
            self._provider_status_labels[p_id].configure(text=res.status, text_color=status_color)

        # Atualiza a tabela de ranking em tempo real com os resultados obtidos até o momento
        self._update_ranking_table(list(self._results_map.values()))

    def _on_progress_ui(self, payload: tuple):
        pct, curr, total = payload
        self.progress_bar.set(pct)
        self.lbl_pct.configure(text=f"{int(pct * 100)}%")
        self.lbl_progress_status.configure(text=f"Testando {curr} de {total} servidores...")

    def _on_finish_ui(self, summary: DNSBenchmarkSummary):
        self.btn_start.configure(state="normal", fg_color=COLORS["accent"])
        self.btn_cancel.configure(state="disabled", fg_color=COLORS["bg_sidebar"], text_color=COLORS["text_secondary"])

        if summary.cancelled:
            self.lbl_progress_status.configure(text="Teste cancelado pelo usuário.")
        else:
            self.lbl_progress_status.configure(text=f"Concluído em {summary.total_time_seconds:.1f}s!")

        # Destaca o servidor campeão
        if summary.best_result:
            self._render_hero_card_content(summary.best_result)
            best_id = summary.best_result.provider.id
            if best_id in self._provider_cards:
                self._provider_cards[best_id].configure(border_color="#FFD700", border_width=2)
                self._provider_status_labels[best_id].configure(text="🥇 O Mais Rápido", text_color="#FFD700")

    def _on_error_ui(self, err_msg: str):
        self.btn_start.configure(state="normal", fg_color=COLORS["accent"])
        self.btn_cancel.configure(state="disabled", fg_color=COLORS["bg_sidebar"])
        self.lbl_progress_status.configure(text=f"Erro: {err_msg}")

    def stop_monitoring(self):
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None
        if self.tester.is_running():
            self.tester.stop_test()
