"""
CedNet Help - Painel de Automação (UX/UI Redesenhado)
Central de ferramentas automatizadas para suporte técnico e atendimento de campo.

Layout Dashboard Split-Panel:
  - Painel Lateral (Esquerda): Lista e chaveamento de automações (Encontrar Credencial, Configuração, Diagnóstico)
  - Área Principal (Direita): Formulário limpo, Card de Progresso Dinâmico, Card de Resultado e Logs Colapsáveis
"""

import customtkinter as ctk
import time
import os
import subprocess
import webbrowser
import queue
from typing import Optional
from modules.automation.password_finder import RadioPasswordFinder
from modules.utils import COLORS, FONTS


class AutomationPanel(ctk.CTkFrame):
    """Painel principal da central de automações com layout Split-Panel moderno."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.finder = RadioPasswordFinder()

        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None
        self._found_result: Optional[dict] = None
        self._logs_expanded: bool = False

        self._create_ui()
        self._start_queue_polling()

    # ================================================================
    # Construção da Interface (Split-Panel)
    # ================================================================

    def _create_ui(self):
        """Monta o layout Split-Panel: Sub-Sidebar (col 0) + Área Principal (col 1)."""
        self.grid_columnconfigure(0, weight=0, minsize=210)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- Coluna 0: Sub-sidebar de Automações ----
        self._create_left_subsidebar()

        # ---- Coluna 1: Área de Conteúdo da Automação Selecionada ----
        self._create_right_content_area()

    def _create_left_subsidebar(self):
        """Cria o painel lateral com a lista de automações disponíveis."""
        subsidebar = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        subsidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(subsidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=15)

        # Cabeçalho da sub-sidebar
        ctk.CTkLabel(
            inner,
            text="⚙️ Automações",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            inner,
            text="FERRAMENTAS",
            font=FONTS["small_bold"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        # Item 1: Encontrar Credencial (Ativo)
        self.btn_nav_finder = ctk.CTkButton(
            inner,
            text="🔑  Encontrar Credencial",
            font=FONTS["body_bold"],
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            hover_color=COLORS["accent_hover"],
            command=lambda: self._switch_automation("finder"),
        )
        self.btn_nav_finder.pack(fill="x", pady=(0, 8))

        # Item 2: Configurar Roteador (Em breve)
        btn_nav_router = ctk.CTkButton(
            inner,
            text="📡  Configurar Roteador\n     [Em breve]",
            font=FONTS["small"],
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover=False,
            state="disabled",
        )
        btn_nav_router.pack(fill="x", pady=(0, 8))

        # Item 3: Diagnóstico Automático (Em breve)
        btn_nav_diag = ctk.CTkButton(
            inner,
            text="🔍  Diagnóstico Auto\n     [Em breve]",
            font=FONTS["small"],
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover=False,
            state="disabled",
        )
        btn_nav_diag.pack(fill="x")

    def _create_right_content_area(self):
        """Cria a área principal de conteúdo e formulários da automação."""
        main_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        main_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # ---- Cabeçalho da Ferramenta ----
        header_card = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=12)
        header_card.pack(fill="x", pady=(0, 12))

        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=18, pady=14)

        ctk.CTkLabel(
            header_inner,
            text="🔑  Encontrar Senha do Rádio / Roteador",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        # ---- Card de Formulário (Configurações do Teste) ----

        form_card = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=12)
        form_card.pack(fill="x", pady=(0, 12))

        form_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        form_inner.pack(fill="x", padx=18, pady=16)

        form_grid = ctk.CTkFrame(form_inner, fg_color="transparent")
        form_grid.pack(fill="x", pady=(0, 14))
        form_grid.columnconfigure(0, weight=2)
        form_grid.columnconfigure(1, weight=1)
        form_grid.columnconfigure(2, weight=1)

        # Campo 1: IP do Equipamento
        ip_box = ctk.CTkFrame(form_grid, fg_color="transparent")
        ip_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(
            ip_box, text="Endereço IP do Equipamento *", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.ip_entry = ctk.CTkEntry(
            ip_box, font=("Consolas", 14), height=40, corner_radius=8,
            fg_color=COLORS["entry_bg"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], placeholder_text="Ex: 10.4.24.5 ou 192.168.1.1",
        )
        self.ip_entry.pack(fill="x")

        # Campo 2: Tipo de Dispositivo
        type_box = ctk.CTkFrame(form_grid, fg_color="transparent")
        type_box.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(
            type_box, text="Tipo de Dispositivo", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.type_combo = ctk.CTkComboBox(
            type_box, values=["ZTE", "Datacom", "TP-Link", "Rádio", "Geral"],
            font=FONTS["body"], dropdown_font=FONTS["body"], height=40, corner_radius=8,
            fg_color=COLORS["entry_bg"], border_color=COLORS["border"],
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_sidebar"], dropdown_hover_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"], dropdown_text_color=COLORS["text_primary"],
        )
        self.type_combo.set("ZTE")
        self.type_combo.pack(fill="x")

        # Campo 3: Usuário Customizado
        user_box = ctk.CTkFrame(form_grid, fg_color="transparent")
        user_box.grid(row=0, column=2, sticky="ew")

        ctk.CTkLabel(
            user_box, text="Usuário Customizado", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.user_combo = ctk.CTkComboBox(
            user_box, values=["(Auto / Padrão)", "admin", "cednet", "user", "multipro", "ubnt", "root"],
            font=FONTS["body"], dropdown_font=FONTS["body"], height=40, corner_radius=8,
            fg_color=COLORS["entry_bg"], border_color=COLORS["border"],
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_sidebar"], dropdown_hover_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"], dropdown_text_color=COLORS["text_primary"],
        )
        self.user_combo.set("(Auto / Padrão)")
        self.user_combo.pack(fill="x")

        # Botão Iniciar Teste
        self.btn_start = ctk.CTkButton(
            form_inner, text="Iniciar Teste de Senhas", font=FONTS["body_bold"],
            height=44, corner_radius=8, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], command=self._toggle_finder,
        )
        self.btn_start.pack(fill="x")

        # ---- Card de Progresso Dinâmico (Exibido apenas durante execução) ----
        self.progress_card = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=12)
        # Inicialmente oculto

        # ---- Card de Resultado (Exibido após término) ----
        self.result_card = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=12)
        # Inicialmente oculto

        # ---- Accordion / Card Colapsável de Logs ----
        self.logs_card = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=12)
        self.logs_card.pack(fill="x", pady=(0, 10))

        # Cabeçalho do Accordion (Botão de Alternar)
        self.btn_toggle_logs = ctk.CTkButton(
            self.logs_card, text="▶  Logs de Execução (Clique para expandir)",
            font=FONTS["body_bold"], height=36, corner_radius=8,
            fg_color="transparent", hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"], anchor="w",
            command=self._toggle_logs,
        )
        self.btn_toggle_logs.pack(fill="x", padx=10, pady=6)

        # Conteúdo do Accordion (Inicialmente oculto)
        self.logs_body = ctk.CTkFrame(self.logs_card, fg_color="transparent")
        
        self.log_textbox = ctk.CTkTextbox(
            self.logs_body, font=FONTS["mono"], fg_color=COLORS["entry_bg"],
            text_color=COLORS["text_secondary"], corner_radius=8, height=130,
            state="disabled", wrap="word",
        )
        self.log_textbox.pack(fill="x", padx=12, pady=(0, 8))

        btn_history = ctk.CTkButton(
            self.logs_body, text="Abrir Histórico em Arquivo", font=FONTS["small_bold"],
            height=28, width=180, corner_radius=6, fg_color=COLORS["bg_sidebar"],
            hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_secondary"],
            command=self._open_history_file,
        )
        btn_history.pack(anchor="e", padx=12, pady=(0, 10))

    # ================================================================
    # Construtores de Sub-Componentes Visualmente Limpos
    # ================================================================

    def _render_progress_card(self):
        """Monta o card dinâmico de progresso da execução."""
        for w in self.progress_card.winfo_children():
            w.destroy()

        inner = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            top_row, text="⚡ Executando Automação...", font=FONTS["heading"],
            text_color=COLORS["text_primary"], anchor="w",
        ).pack(side="left")

        self.lbl_percent_top = ctk.CTkLabel(
            top_row, text="0%", font=FONTS["heading"],
            text_color=COLORS["accent_cyan"], anchor="e",
        )
        self.lbl_percent_top.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            inner, height=10, corner_radius=5,
            progress_color=COLORS["accent"], fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0.0)

        # Métrica Grid
        metrics_grid = ctk.CTkFrame(inner, fg_color="transparent")
        metrics_grid.pack(fill="x", pady=(0, 10))
        metrics_grid.columnconfigure((0, 1), weight=1)

        self._lbl_eq = self._create_metric_item(metrics_grid, "Equipamento:", "Detectando...", 0, 0)
        self._lbl_url = self._create_metric_item(metrics_grid, "URL:", "Conectando...", 0, 1)
        self._lbl_user = self._create_metric_item(metrics_grid, "Usuário:", "(Auto)", 1, 0)
        self._lbl_pass = self._create_metric_item(metrics_grid, "Tentando Senha:", "—", 1, 1)
        self._lbl_prog = self._create_metric_item(metrics_grid, "Etapa:", "0 / 0", 2, 0)
        self._lbl_time = self._create_metric_item(metrics_grid, "Tempo:", "00:00:00", 2, 1)

    def _create_metric_item(self, parent, label: str, default_val: str, row: int, col: int) -> ctk.CTkLabel:
        box = ctk.CTkFrame(parent, fg_color=COLORS["entry_bg"], corner_radius=6)
        box.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(inner, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")
        val_lbl = ctk.CTkLabel(inner, text=default_val, font=FONTS["mono"], text_color=COLORS["accent_cyan"], anchor="w")
        val_lbl.pack(anchor="w")
        return val_lbl

    # ================================================================
    # Interações & Chaveamento
    # ================================================================

    def _switch_automation(self, key: str):
        """Chaveia visualmente a automação selecionada na sub-sidebar."""
        if key == "finder":
            self.btn_nav_finder.configure(fg_color=COLORS["accent"], text_color=COLORS["text_primary"])

    def _toggle_logs(self):
        """Expande ou recolhe o accordion de logs de execução."""
        self._logs_expanded = not self._logs_expanded

        if self._logs_expanded:
            self.btn_toggle_logs.configure(text="▼  Logs de Execução (Clique para recolher)", text_color=COLORS["text_primary"])
            self.logs_body.pack(fill="x", expand=True)
        else:
            self.btn_toggle_logs.configure(text="▶  Logs de Execução (Clique para expandir)", text_color=COLORS["text_secondary"])
            self.logs_body.pack_forget()

    # ================================================================
    # Polling Thread-Safe
    # ================================================================

    def _start_queue_polling(self):
        self._process_queue()

    def _process_queue(self):
        try:
            while True:
                msg_type, payload = self._ui_queue.get_nowait()
                if msg_type == "progress":
                    self._update_progress_ui(payload)
                elif msg_type == "success":
                    self._on_success_ui(payload)
                elif msg_type == "failure":
                    self._on_failure_ui(payload)
        except queue.Empty:
            pass

        self._poll_after_id = self.after(100, self._process_queue)

    # ================================================================
    # Controle de Automação
    # ================================================================

    def _toggle_finder(self):
        """Alterna entre Iniciar e Parar a automação."""
        if self.finder.is_running():
            self.finder.stop_finder()
            self.btn_start.configure(text="Iniciar Teste de Senhas", fg_color=COLORS["accent"])
            self._append_log("Teste interrompido pelo usuário.")
        else:
            self._start_finder()

    def _start_finder(self):
        """Inicia o teste de senhas."""
        target_ip = self.ip_entry.get().strip()
        device_type = self.type_combo.get().strip()
        user_input = self.user_combo.get().strip()
        username = "" if user_input == "(Auto / Padrão)" else user_input

        if not target_ip:
            self._append_log("❌ Informe o endereço IP do equipamento.")
            return

        # Esconde resultado anterior e mostra card de progresso
        self.result_card.pack_forget()
        self._render_progress_card()
        self.progress_card.pack(fill="x", pady=(0, 12))

        # Atualiza botão
        self.btn_start.configure(
            text="Parar Teste", fg_color=COLORS["status_error"], hover_color="#c62828"
        )

        self._append_log(f"\n{'='*45}\n🚀 Iniciando teste: IP {target_ip} | Perfil: {device_type} | User: {username or '(Auto)'}")

        self.finder.start_finder(
            target_ip=target_ip, username=username, device_type=device_type,
            on_progress=lambda d: self._ui_queue.put(("progress", d)),
            on_success=lambda d: self._ui_queue.put(("success", d)),
            on_failure=lambda msg: self._ui_queue.put(("failure", msg)),
        )

    def _update_progress_ui(self, data: dict):
        """Atualiza os indicadores do card de progresso."""
        curr = data["current_index"]
        total = data["total"]
        pct = (curr / total) if total > 0 else 0.0

        self.progress_bar.set(pct)
        pct_text = f"{int(pct * 100)}%"
        self.lbl_percent_top.configure(text=pct_text)

        self._lbl_eq.configure(text=data["equipment"])
        self._lbl_url.configure(text=data["url"])
        self._lbl_user.configure(text=data["username"])

        raw_pass = data["current_password"]
        masked_pass = raw_pass[0] + "*" * (len(raw_pass) - 2) + raw_pass[-1] if len(raw_pass) > 2 else "***"
        self._lbl_pass.configure(text=masked_pass)

        self._lbl_prog.configure(text=f"{curr} / {total}")

        secs = int(data["elapsed_seconds"])
        self._lbl_time.configure(text=f"{secs // 60:02d}:{secs % 60:02d}")

        self._append_log(f"  [{curr}/{total}] Testando: {masked_pass}...")

    def _on_success_ui(self, data: dict):
        """Exibe resultado de sucesso."""
        self.btn_start.configure(text="Iniciar Teste de Senhas", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])
        self.progress_card.pack_forget()

        self._append_log(f"\n✅ SENHA ENCONTRADA!\n   Usuário: {data['username']} | Senha: {data['password']}\n")
        self._render_result_card(data, success=True)

    def _on_failure_ui(self, message: str):
        """Exibe resultado de falha."""
        self.btn_start.configure(text="Iniciar Teste de Senhas", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])
        self.progress_card.pack_forget()

        self._append_log(f"\n{message}\n")
        self._render_result_card({"message": message}, success=False)

    # ================================================================
    # Renderização do Card de Resultado
    # ================================================================

    def _render_result_card(self, data: dict, success: bool):
        """Exibe o card final com o resultado limpo da operação."""
        for w in self.result_card.winfo_children():
            w.destroy()

        border_color = COLORS["status_ok"] if success else COLORS["status_error"]
        bg_color = "#1b3323" if success else "#3d1a1a"

        self.result_card.configure(fg_color=bg_color, border_width=2, border_color=border_color)

        inner = ctk.CTkFrame(self.result_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

        if success:
            ctk.CTkLabel(
                inner, text="🎉  Senha Encontrada com Sucesso!",
                font=FONTS["heading"], text_color=COLORS["status_ok"], anchor="w",
            ).pack(anchor="w", pady=(0, 6))

            info_str = (
                f"• Equipamento: {data['equipment']}\n"
                f"• URL:         {data['url']}\n"
                f"• Usuário:     {data['username']}\n"
                f"• Senha:       {data['password']}"
            )

            ctk.CTkLabel(
                inner, text=info_str, font=FONTS["mono_large"],
                text_color=COLORS["text_primary"], anchor="w", justify="left",
            ).pack(anchor="w", pady=(0, 10))

            btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
            btn_frame.pack(fill="x")

            ctk.CTkButton(
                btn_frame, text="Copiar Usuário", font=FONTS["small_bold"], height=34,
                fg_color=COLORS["bg_card"], hover_color=COLORS["bg_card_hover"],
                command=lambda: self._copy_to_clipboard(data["username"], "Usuário"),
            ).pack(side="left", padx=(0, 5))

            ctk.CTkButton(
                btn_frame, text="Copiar Senha", font=FONTS["small_bold"], height=34,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda: self._copy_to_clipboard(data["password"], "Senha"),
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                btn_frame, text="Abrir Interface Web", font=FONTS["small_bold"], height=34,
                fg_color="#1b5e20", hover_color="#2e7d32",
                command=lambda: webbrowser.open(data["url"]),
            ).pack(side="left", padx=5)

        else:
            ctk.CTkLabel(
                inner, text="❌  Falha na Automação",
                font=FONTS["heading"], text_color=COLORS["status_error"], anchor="w",
            ).pack(anchor="w", pady=(0, 4))

            ctk.CTkLabel(
                inner, text=data.get("message", "Nenhuma senha foi aceita pelo equipamento."),
                font=FONTS["body"], text_color=COLORS["text_secondary"], anchor="w",
            ).pack(anchor="w")

        self.result_card.pack(fill="x", pady=(0, 12))

    # ================================================================
    # Funções Utilitárias de Suporte
    # ================================================================

    def _copy_to_clipboard(self, text: str, label: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._append_log(f"📋 {label} '{text}' copiado para a área de transferência.")

    def _open_history_file(self):
        log_file = os.path.join(os.getcwd(), "logs", "automation_history.log")
        if os.path.exists(log_file):
            try:
                os.startfile(log_file)
            except Exception:
                subprocess.Popen(f'notepad.exe "{log_file}"', shell=True)
        else:
            self._append_log("ℹ️ Nenhum histórico registrado até o momento.")

    def _append_log(self, text: str):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def stop_monitoring(self):
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None

        if self.finder.is_running():
            self.finder.stop_finder()
