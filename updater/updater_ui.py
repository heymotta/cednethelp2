"""
CedNet Updater - Interface Gráfica (CustomTkinter)
Janela moderna de atualização com:
  - Progresso em tempo real com barra visual
  - Velocidade de download e status detalhado
  - Botões Cancelar e Reiniciar
  - Tratamento completo de erros
"""

import customtkinter as ctk
import queue
import sys
import os
from update_engine import UpdateEngine


# ============================================================
# Paleta de Cores (Consistente com CedNet Help)
# ============================================================
COLORS = {
    "bg_main": "#1a1a2e",
    "bg_card": "#0f3460",
    "bg_card_alt": "#132a4a",
    "entry_bg": "#0d2137",
    "accent": "#1a73e8",
    "accent_hover": "#2196f3",
    "accent_cyan": "#00bcd4",
    "text_primary": "#ffffff",
    "text_secondary": "#94a3b8",
    "status_ok": "#4caf50",
    "status_error": "#f44336",
    "border": "#1e3a5f",
}

FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "subtitle": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "small_bold": ("Segoe UI", 11, "bold"),
    "mono": ("Consolas", 12),
}


class UpdaterApp(ctk.CTk):
    """Janela principal do CedNet Updater."""

    def __init__(self, install_dir: str, download_url: str, target_version: str, expected_sha256: str = ""):
        super().__init__()

        self.title("CedNet Updater")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_main"])

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._engine = UpdateEngine(
            install_dir=install_dir,
            download_url=download_url,
            target_version=target_version,
            expected_sha256=expected_sha256,
        )

        self._target_version = target_version
        self._ui_queue = queue.Queue()
        self._update_finished = False

        self._create_ui()
        self._start_queue_polling()

        # Inicia a atualização automaticamente
        self.after(500, self._start_update)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================
    # Construção da UI
    # ================================================================

    def _create_ui(self):
        # ---- Card Principal ----
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=25, pady=25)

        # Título
        ctk.CTkLabel(
            inner,
            text="CedNet Updater",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(
            inner,
            text=f"Atualizando para v{self._target_version}",
            font=FONTS["subtitle"],
            text_color=COLORS["accent_cyan"],
        ).pack(anchor="w", pady=(0, 20))

        # Status
        status_frame = ctk.CTkFrame(inner, fg_color=COLORS["entry_bg"], corner_radius=10)
        status_frame.pack(fill="x", pady=(0, 15))

        status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_inner.pack(fill="x", padx=15, pady=12)

        self.lbl_status = ctk.CTkLabel(
            status_inner,
            text="Preparando atualização...",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.lbl_status.pack(anchor="w")

        self.lbl_detail = ctk.CTkLabel(
            status_inner,
            text="Aguarde...",
            font=FONTS["mono"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.lbl_detail.pack(anchor="w", pady=(4, 0))

        # Barra de Progresso
        self.progress_bar = ctk.CTkProgressBar(
            inner,
            height=14,
            corner_radius=7,
            progress_color=COLORS["accent"],
            fg_color=COLORS["entry_bg"],
        )
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0.0)

        # Porcentagem
        self.lbl_percent = ctk.CTkLabel(
            inner,
            text="0%",
            font=FONTS["body_bold"],
            text_color=COLORS["accent_cyan"],
        )
        self.lbl_percent.pack(anchor="e", pady=(0, 20))

        # Botões
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            font=FONTS["body_bold"],
            height=42,
            corner_radius=10,
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["status_error"],
            command=self._cancel_update,
        )
        self.btn_cancel.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_restart = ctk.CTkButton(
            btn_frame,
            text="Abrir CedNet Help",
            font=FONTS["body_bold"],
            height=42,
            corner_radius=10,
            fg_color=COLORS["status_ok"],
            hover_color="#388e3c",
            command=self._restart_and_close,
            state="disabled",
        )
        self.btn_restart.pack(side="right", fill="x", expand=True, padx=(5, 0))

    # ================================================================
    # Queue Polling (Thread-safe GUI updates)
    # ================================================================

    def _start_queue_polling(self):
        self._process_queue()

    def _process_queue(self):
        try:
            while True:
                msg_type, payload = self._ui_queue.get_nowait()
                if msg_type == "progress":
                    pct, status, detail = payload
                    self._update_progress(pct, status, detail)
                elif msg_type == "complete":
                    success, message = payload
                    self._on_complete(success, message)
        except queue.Empty:
            pass

        self.after(80, self._process_queue)

    # ================================================================
    # Controle da Atualização
    # ================================================================

    def _start_update(self):
        """Inicia o processo de atualização."""
        self._engine.run_update(
            on_progress=lambda pct, s, d: self._ui_queue.put(("progress", (pct, s, d))),
            on_complete=lambda ok, msg: self._ui_queue.put(("complete", (ok, msg))),
        )

    def _cancel_update(self):
        """Cancela a atualização."""
        if self._update_finished:
            self._on_close()
            return

        self._engine.cancel()
        self.lbl_status.configure(text="Cancelando...", text_color=COLORS["status_error"])

    def _update_progress(self, percent: int, status: str, detail: str):
        """Atualiza a UI de progresso."""
        self.progress_bar.set(percent / 100.0)
        self.lbl_percent.configure(text=f"{percent}%")
        self.lbl_status.configure(text=status, text_color=COLORS["text_primary"])
        self.lbl_detail.configure(text=detail)

    def _on_complete(self, success: bool, message: str):
        """Callback ao finalizar a atualização."""
        self._update_finished = True

        if success:
            self.progress_bar.set(1.0)
            self.lbl_percent.configure(text="100%")
            self.lbl_status.configure(text="Atualização concluída!", text_color=COLORS["status_ok"])
            self.lbl_detail.configure(text=message)
            self.btn_cancel.configure(text="Fechar", fg_color=COLORS["bg_card_alt"])
            self.btn_restart.configure(state="normal")
        else:
            self.progress_bar.configure(progress_color=COLORS["status_error"])
            self.lbl_status.configure(text="Falha na atualização", text_color=COLORS["status_error"])
            self.lbl_detail.configure(text=message)
            self.btn_cancel.configure(text="Fechar")

    def _restart_and_close(self):
        """Reinicia o CedNet Help e fecha o Updater."""
        self._engine.restart_cednet_help()
        self.after(500, self.destroy)

    def _on_close(self):
        """Fecha o Updater."""
        if self._engine.is_running():
            self._engine.cancel()
        self.destroy()
