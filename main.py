"""
CedNet Help — Ponto de Entrada
Aplicação desktop para suporte técnico de rede.

Desenvolvido com Python 3.13+ e CustomTkinter.
Módulos: Rede | Roteador | Senhas
"""

import sys
import os
import io

# Dummy stream para evitar exceção 'NoneType' object has no attribute 'fileno'
# quando executado via PyInstaller em modo --windowed (sem console)
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

# Garante que o diretório raiz do projeto está no path
# para que os imports de módulos funcionem corretamente
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import CedNetApp


def main():
    """Inicializa e executa a aplicação CedNet Help."""
    app = CedNetApp()
    app.mainloop()


if __name__ == "__main__":
    main()
