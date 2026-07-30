"""
CedNet Updater — Ponto de Entrada
Executável separado responsável por baixar, verificar e instalar
atualizações do CedNet Help de forma segura e com feedback visual.

Uso:
    CedNet_Updater.exe --install-dir "C:/path/to/CedNetHelp"
                       --download-url "https://..."
                       --version "1.1.0"
                       [--sha256 "abc123..."]
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

import argparse
from updater_ui import UpdaterApp


def parse_args():
    """Parseia os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description="CedNet Updater")
    parser.add_argument("--install-dir", required=True, help="Diretório de instalação do CedNet Help")
    parser.add_argument("--download-url", required=True, help="URL de download do pacote .zip")
    parser.add_argument("--version", required=True, help="Versão a ser instalada")
    parser.add_argument("--sha256", default="", help="Hash SHA-256 esperado do download (opcional)")
    return parser.parse_args()


def main():
    args = parse_args()

    app = UpdaterApp(
        install_dir=args.install_dir,
        download_url=args.download_url,
        target_version=args.version,
        expected_sha256=args.sha256,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
