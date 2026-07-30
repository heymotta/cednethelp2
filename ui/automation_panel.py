"""
CedNet Help - Painel de Automação
Central de ferramentas automatizadas para suporte técnico e atendimento de campo.

Ferramentas:
  - 🔑 Encontrar Senha do Rádio / Roteador (Automação de testes de credenciais)
  - ⚙️ Configuração Automática (Próxima expansão)
  - 🔍 Diagnóstico Automático (Próxima expansão)
"""

import customtkinter as ctk
import time
import os
import subprocess
import webbrowser
import queue
from typing import Optional
from modules.automation.password_finder import RadioPasswordFinder, RADIO_PASSWORDS
from modules.utils import COLORS, FONTS


class AutomationPanel(ctk.CTkFrame):
    """Painel principal da central de automações."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.finder = RadioPasswordFinder()

        self._ui_queue = queue.Queue()
        self._poll_after_id: Optional[str] = None
        self._found_result: Optional[dict] = None

        self._create_ui()
        self._start_queue_polling()

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        """Monta a interface completa da Central de Automação."""
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_card"],
        )
        container.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- Cabeçalho ----
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            header,
            text="🤖  Central de Automação",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Ferramentas e bots inteligentes para suporte técnico e configurações rápidas",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # ---- Card da Ferramenta: Encontrar Senha do Rádio ----
        tool_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        tool_card.pack(fill="x", pady=(0, 15))

        tool_inner = ctk.CTkFrame(tool_card, fg_color="transparent")
        tool_inner.pack(fill="x", padx=20, pady=20)

        # Título da Ferramenta
        tool_title_frame = ctk.CTkFrame(tool_inner, fg_color="transparent")
        tool_title_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            tool_title_frame,
            text="🔑  Encontrar Senha do Rádio / Roteador",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            tool_title_frame,
            text="Testa a lista de credenciais da empresa",
            font=FONTS["small"],
            text_color=COLORS["accent_cyan"],
            anchor="e",
        ).pack(side="right")

        # Formulário de Entradas (2 colunas: IP e Usuário)
        form_grid = ctk.CTkFrame(tool_inner, fg_color="transparent")
        form_grid.pack(fill="x", pady=(0, 15))
        form_grid.columnconfigure(0, weight=2)
        form_grid.columnconfigure(1, weight=1)

        # Campo IP
        ip_box = ctk.CTkFrame(form_grid, fg_color="transparent")
        ip_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(
            ip_box,
            text="Endereço IP do Equipamento *",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.ip_entry = ctk.CTkEntry(
            ip_box,
            font=("Consolas", 15),
            height=42,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="Ex: 10.4.24.5 ou 192.168.1.1",
        )
        self.ip_entry.pack(fill="x")

        # Campo Usuário (ComboBox)
        user_box = ctk.CTkFrame(form_grid, fg_color="transparent")
        user_box.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            user_box,
            text="Usuário",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        self.user_combo = ctk.CTkComboBox(
            user_box,
            values=["admin", "ubnt", "root", "user", "cednet"],
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            height=42,
            corner_radius=8,
            fg_color=COLORS["entry_bg"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_sidebar"],
            dropdown_hover_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
        )
        self.user_combo.set("admin")
        self.user_combo.pack(fill="x")

        # Botão Iniciar Teste
        self.btn_start = ctk.CTkButton(
            tool_inner,
            text="Iniciar Teste de Senhas",
            font=FONTS["body_bold"],
            height=46,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_finder,
        )
        self.btn_start.pack(fill="x")

        # ---- Card de Métricas & Progresso do Teste ----
        self.metrics_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        self.metrics_card.pack(fill="x", pady=(0, 15))

        m_inner = ctk.CTkFrame(self.metrics_card, fg_color="transparent")
        m_inner.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            m_inner,
            text="📊  Status da Execução em Tempo Real",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        # Barra de Progresso
        self.progress_bar = ctk.CTkProgressBar(
            m_inner,
            height=10,
            corner_radius=5,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0.0)

        # Metrics grid (2 colunas x 3 linhas)
        metrics_grid = ctk.CTkFrame(m_inner, fg_color="transparent")
        metrics_grid.pack(fill="x")
        metrics_grid.columnconfigure((0, 1), weight=1)

        self._lbl_eq = self._create_metric_item(metrics_grid, "Equipamento:", "—", 0, 0)
        self._lbl_url = self._create_metric_item(metrics_grid, "URL Acessada:", "—", 0, 1)
        self._lbl_user = self._create_metric_item(metrics_grid, "Usuário:", "admin", 1, 0)
        self._lbl_pass = self._create_metric_item(metrics_grid, "Tentando Senha:", "—", 1, 1)
        self._lbl_prog = self._create_metric_item(metrics_grid, "Progresso:", "0 / 0", 2, 0)
        self._lbl_time = self._create_metric_item(metrics_grid, "Tempo Decorrido:", "00:00:00", 2, 1)

        # ---- Card de Resultado (Exibido após término) ----
        self.result_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        # Oculto por padrão

        # ---- Card de Log ----
        log_card = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        log_card.pack(fill="x")

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            log_header,
            text="📝  Log de Execução",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        btn_open_history = ctk.CTkButton(
            log_header,
            text="Abrir Histórico",
            font=FONTS["small_bold"],
            width=130,
            height=28,
            corner_radius=6,
            fg_color=COLORS["bg_sidebar"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"],
            command=self._open_history_file,
        )
        btn_open_history.pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            log_card,
            font=FONTS["mono"],
            fg_color=COLORS["entry_bg"],
            text_color=COLORS["text_secondary"],
            corner_radius=8,
            height=130,
            state="disabled",
            wrap="word",
        )
        self.log_textbox.pack(fill="x", padx=20, pady=(0, 15))

    def _create_metric_item(self, parent, label: str, default_val: str, row: int, col: int) -> ctk.CTkLabel:
        """Cria um item de métrica (Rótulo + Valor)."""
        box = ctk.CTkFrame(parent, fg_color=COLORS["entry_bg"], corner_radius=6)
        box.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            inner, text=label, font=FONTS["small"],
            text_color=COLORS["text_secondary"], anchor="w"
        ).pack(anchor="w")

        val_lbl = ctk.CTkLabel(
            inner, text=default_val, font=FONTS["mono"],
            text_color=COLORS["accent_cyan"], anchor="w"
        )
        val_lbl.pack(anchor="w", pady=(1, 0))
        return val_lbl

    # ================================================================
    # Queue Polling Thread-Safe
    # ================================================================

    def _start_queue_polling(self):
        """Inicia polling da fila de comunicação com a thread de automação."""
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
        """Alterna entre Iniciar e Parar o bot de senhas."""
        if self.finder.is_running():
            self.finder.stop_finder()
            self.btn_start.configure(text="Iniciar Teste de Senhas", fg_color=COLORS["accent"])
            self._append_log("Teste interrompido pelo usuário.")
        else:
            self._start_finder()

    def _start_finder(self):
        """Inicia a busca por senha."""
        target_ip = self.ip_entry.get().strip()
        username = self.user_combo.get().strip() or "admin"

        if not target_ip:
            self._append_log("❌ Informe o endereço IP do equipamento.")
            return

        # Oculta resultado anterior
        self.result_card.pack_forget()

        # UI: estado rodando
        self.btn_start.configure(
            text="Parar Teste",
            fg_color=COLORS["status_error"],
            hover_color="#c62828",
        )
        self.progress_bar.set(0.0)
        self._lbl_eq.configure(text="Detectando...")
        self._lbl_url.configure(text="Conectando...")
        self._lbl_user.configure(text=username)
        self._lbl_pass.configure(text="—")
        self._lbl_prog.configure(text="0 / 0")
        self._lbl_time.configure(text="00:00:00")

        self._append_log(f"\n{'='*50}\n🚀 Iniciando teste de senhas no IP: {target_ip} (User: {username})")

        self.finder.start_finder(
            target_ip=target_ip,
            username=username,
            on_progress=lambda d: self._ui_queue.put(("progress", d)),
            on_success=lambda d: self._ui_queue.put(("success", d)),
            on_failure=lambda msg: self._ui_queue.put(("failure", msg)),
        )

    def _update_progress_ui(self, data: dict):
        """Atualiza a UI durante os testes."""
        curr = data["current_index"]
        total = data["total"]
        pct = (curr / total) if total > 0 else 0.0
        self.progress_bar.set(pct)

        self._lbl_eq.configure(text=data["equipment"])
        self._lbl_url.configure(text=data["url"])
        self._lbl_user.configure(text=data["username"])

        # Mascara a senha para privacidade no log
        raw_pass = data["current_password"]
        masked_pass = raw_pass[0] + "*" * (len(raw_pass) - 2) + raw_pass[-1] if len(raw_pass) > 2 else "***"
        self._lbl_pass.configure(text=masked_pass)

        self._lbl_prog.configure(text=f"{curr} / {total} ({int(pct*100)}%)")

        secs = int(data["elapsed_seconds"])
        mins = secs // 60
        secs_rem = secs % 60
        self._lbl_time.configure(text=f"{mins:02d}:{secs_rem:02d}")

        self._append_log(f"  [{curr}/{total}] Testando: {masked_pass}...")

    def _on_success_ui(self, data: dict):
        """Callback acionado ao encontrar a senha correta."""
        self.btn_start.configure(
            text="Iniciar Teste de Senhas",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        self.progress_bar.set(1.0)
        self._found_result = data

        self._append_log(
            f"\n✅ SENHA ENCONTRADA!\n"
            f"   Usuário: {data['username']}\n"
            f"   Senha:   {data['password']}\n"
            f"   URL:     {data['url']}\n"
            f"   Tempo:   {data['elapsed_seconds']:.1f}s\n"
        )

        self._render_result_card(data, success=True)

    def _on_failure_ui(self, message: str):
        """Callback acionado se nenhuma senha funcionar."""
        self.btn_start.configure(
            text="Iniciar Teste de Senhas",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        self._append_log(f"\n{message}\n")
        self._render_result_card({"message": message}, success=False)

    # ================================================================
    # Renderização do Card de Resultado
    # ================================================================

    def _render_result_card(self, data: dict, success: bool):
        """Exibe o card final de resultado com botões de ação."""
        for w in self.result_card.winfo_children():
            w.destroy()

        border_color = COLORS["status_ok"] if success else COLORS["status_error"]
        bg_color = "#1b3323" if success else "#3d1a1a"

        self.result_card.configure(
            fg_color=bg_color,
            border_width=2,
            border_color=border_color,
        )

        inner = ctk.CTkFrame(self.result_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)

        if success:
            ctk.CTkLabel(
                inner,
                text="🎉  Senha Encontrada com Sucesso!",
                font=FONTS["title"],
                text_color=COLORS["status_ok"],
                anchor="w",
            ).pack(anchor="w", pady=(0, 8))

            info_str = (
                f"• Equipamento: {data['equipment']}\n"
                f"• URL:         {data['url']}\n"
                f"• Usuário:     {data['username']}\n"
                f"• Senha:       {data['password']}"
            )

            ctk.CTkLabel(
                inner,
                text=info_str,
                font=FONTS["mono_large"],
                text_color=COLORS["text_primary"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=(0, 12))

            # Botões de Ação
            btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
            btn_frame.pack(fill="x")

            ctk.CTkButton(
                btn_frame,
                text="Copiar Usuário",
                font=FONTS["small_bold"],
                height=36,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_card_hover"],
                command=lambda: self._copy_to_clipboard(data["username"], "Usuário"),
            ).pack(side="left", padx=(0, 5))

            ctk.CTkButton(
                btn_frame,
                text="Copiar Senha",
                font=FONTS["small_bold"],
                height=36,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                command=lambda: self._copy_to_clipboard(data["password"], "Senha"),
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                btn_frame,
                text="Abrir Interface Web",
                font=FONTS["small_bold"],
                height=36,
                fg_color="#1b5e20",
                hover_color="#2e7d32",
                command=lambda: webbrowser.open(data["url"]),
            ).pack(side="left", padx=5)

        else:
            ctk.CTkLabel(
                inner,
                text="❌  Falha na Automação",
                font=FONTS["title"],
                text_color=COLORS["status_error"],
                anchor="w",
            ).pack(anchor="w", pady=(0, 5))

            ctk.CTkLabel(
                inner,
                text=data.get("message", "Nenhuma senha foi aceita pelo equipamento."),
                font=FONTS["body"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w")

        # Exibe o card de resultado no container
        self.result_card.pack(fill="x", pady=(0, 15))

    # ================================================================
    # Utilidades
    # ================================================================

    def _copy_to_clipboard(self, text: str, label: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._append_log(f"📋 {label} '{text}' copiado para a área de transferência.")

    def _open_history_file(self):
        """Abre o arquivo de histórico local no editor padrão do Windows."""
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
        """Cancela polling ao fechar a janela."""
        if self._poll_after_id:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None

        if self.finder.is_running():
            self.finder.stop_finder()
