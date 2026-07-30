"""
CedNet Updater — Ponto de Entrada
Executável separado responsável por baixar, verificar e instalar
atualizações do CedNet Help de forma segura e com feedback visual.

Uso pelo CedNet Help (automático):
    CedNet_Updater.exe --install-dir "C:/path/to/CedNetHelp"
                       --download-url "https://..."
                       --version "1.1.0"
                       [--sha256 "abc123..."]

Uso direto (duplo-clique):
    Exibe tela informativa orientando o usuário.
"""

import sys
import os
import io

# NullStream para PyInstaller --windowed mode
class NullStream(io.StringIO):
    def fileno(self):
        return -1
    def write(self, s):
        pass
    def flush(self):
        pass

if sys.stdout is None or not hasattr(sys.stdout, 'fileno'):
    sys.stdout = NullStream()
if sys.stderr is None or not hasattr(sys.stderr, 'fileno'):
    sys.stderr = NullStream()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    """
    Parseia argumentos de linha de comando.
    Retorna None se nenhum argumento relevante foi fornecido (duplo-clique).
    """
    # Verifica se foi executado sem argumentos (duplo-clique)
    # sys.argv[0] é o nome do programa, então se len == 1, sem args
    if len(sys.argv) <= 1:
        return None

    import argparse
    parser = argparse.ArgumentParser(description="CedNet Updater")
    parser.add_argument("--install-dir", required=True, help="Diretório de instalação do CedNet Help")
    parser.add_argument("--download-url", required=True, help="URL de download do pacote .zip")
    parser.add_argument("--version", required=True, help="Versão a ser instalada")
    parser.add_argument("--sha256", default="", help="Hash SHA-256 esperado do download (opcional)")

    try:
        return parser.parse_args()
    except SystemExit:
        # argparse chama sys.exit em caso de erro. Capturamos para mostrar a tela informativa.
        return None


def show_info_screen():
    """Exibe uma tela informativa quando o updater é aberto diretamente (sem argumentos)."""
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("CedNet Updater")
    app.geometry("480x320")
    app.resizable(False, False)
    app.configure(fg_color="#1a1a2e")

    card = ctk.CTkFrame(app, fg_color="#0f3460", corner_radius=16)
    card.pack(fill="both", expand=True, padx=20, pady=20)

    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=25, pady=25)

    ctk.CTkLabel(
        inner,
        text="CedNet Updater",
        font=("Segoe UI", 22, "bold"),
        text_color="#ffffff",
    ).pack(anchor="w", pady=(0, 8))

    ctk.CTkLabel(
        inner,
        text="Módulo de Atualização Automática",
        font=("Segoe UI", 14, "bold"),
        text_color="#00bcd4",
    ).pack(anchor="w", pady=(0, 20))

    # Mensagem informativa
    info_frame = ctk.CTkFrame(inner, fg_color="#0d2137", corner_radius=10)
    info_frame.pack(fill="x", pady=(0, 15))

    info_inner = ctk.CTkFrame(info_frame, fg_color="transparent")
    info_inner.pack(fill="x", padx=15, pady=12)

    ctk.CTkLabel(
        info_inner,
        text="Este programa é executado automaticamente\n"
             "pelo CedNet Help quando uma atualização\n"
             "está disponível.",
        font=("Segoe UI", 13),
        text_color="#94a3b8",
        justify="left",
        anchor="w",
    ).pack(anchor="w")

    ctk.CTkLabel(
        info_inner,
        text="Para verificar atualizações, abra o\n"
             "CedNet Help normalmente.",
        font=("Segoe UI", 13, "bold"),
        text_color="#ffffff",
        justify="left",
        anchor="w",
    ).pack(anchor="w", pady=(10, 0))

    # Botão fechar
    ctk.CTkButton(
        inner,
        text="Fechar",
        font=("Segoe UI", 14, "bold"),
        height=42,
        corner_radius=10,
        fg_color="#1a73e8",
        hover_color="#2196f3",
        command=app.destroy,
    ).pack(fill="x")

    app.mainloop()


def main():
    args = parse_args()

    if args is None:
        # Executado sem argumentos → tela informativa
        show_info_screen()
        return

    from updater_ui import UpdaterApp

    app = UpdaterApp(
        install_dir=args.install_dir,
        download_url=args.download_url,
        target_version=args.version,
        expected_sha256=args.sha256,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
