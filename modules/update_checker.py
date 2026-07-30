"""
CedNet Help - Módulo de Verificação de Atualizações
Consulta o version.json remoto no GitHub, compara com a versão instalada
e oferece ao usuário a possibilidade de atualizar via CedNet Updater.

Responsabilidades:
  - Consultar version.json remoto (GitHub raw)
  - Comparar versões semânticas (major.minor.patch)
  - Exibir janela de atualização disponível (changelog, versões)
  - Fechar o CedNet Help e iniciar o CedNet Updater
"""

import json
import os
import sys
import subprocess
import threading
import urllib.request
import urllib.error
import ssl
from typing import Optional, Callable

from modules.utils import APP_VERSION

# URL do version.json hospedado no GitHub (raw content)
VERSION_URL = "https://raw.githubusercontent.com/heymotta/cednethelp2/main/version.json"

# Diretórios preservados durante atualização (nunca sobrescritos)
PRESERVED_DIRS = ["data", "logs"]
PRESERVED_FILES = ["passwords.json", "data/settings.json", "data/speedtest_history.json"]


def get_app_dir() -> str:
    """Retorna o diretório raiz da aplicação (funciona tanto em dev quanto empacotado)."""
    if getattr(sys, "frozen", False):
        # Executando como .exe empacotado pelo PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Executando em modo desenvolvimento
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def compare_versions(local: str, remote: str) -> int:
    """
    Compara duas versões semânticas (ex: '1.2.3').
    Retorna:
        -1 se local < remote (atualização disponível)
         0 se local == remote
         1 se local > remote
    """
    try:
        local_parts = [int(x) for x in local.strip().split(".")]
        remote_parts = [int(x) for x in remote.strip().split(".")]

        # Normaliza para 3 partes
        while len(local_parts) < 3:
            local_parts.append(0)
        while len(remote_parts) < 3:
            remote_parts.append(0)

        for l_part, r_part in zip(local_parts, remote_parts):
            if l_part < r_part:
                return -1
            elif l_part > r_part:
                return 1
        return 0
    except (ValueError, AttributeError):
        return 0


def fetch_remote_version(timeout: float = 5.0) -> Optional[dict]:
    """
    Consulta o version.json remoto e retorna os dados como dicionário.
    Retorna None em caso de falha (sem internet, timeout, URL inválida).
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            VERSION_URL,
            headers={"User-Agent": "CedNet-Help-Updater/1.0", "Cache-Control": "no-cache"},
        )

        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            TimeoutError, OSError, Exception):
        return None


def check_for_update() -> Optional[dict]:
    """
    Verifica se existe uma atualização disponível.

    Returns:
        Dicionário com informações da atualização ou None se não houver.
        Campos: version, download_url, changelog, sha256, current_version
    """
    remote = fetch_remote_version()
    if not remote:
        return None

    remote_version = remote.get("version", "0.0.0")
    if compare_versions(APP_VERSION, remote_version) < 0:
        return {
            "version": remote_version,
            "current_version": APP_VERSION,
            "download_url": remote.get("download_url", ""),
            "changelog": remote.get("changelog", []),
            "sha256": remote.get("sha256", ""),
            "minimum_version": remote.get("minimum_version", "1.0.0"),
        }

    return None


def check_for_update_async(callback: Callable[[Optional[dict]], None]):
    """
    Verifica atualizações em background thread e chama o callback com o resultado.
    """
    def _worker():
        result = check_for_update()
        callback(result)

    thread = threading.Thread(target=_worker, daemon=True, name="UpdateChecker")
    thread.start()


def launch_updater(update_info: dict, app_dir: str = "") -> bool:
    """
    Inicia o CedNet Updater passando os parâmetros necessários.

    Args:
        update_info: Dicionário com version, download_url, sha256
        app_dir: Caminho da instalação do CedNet Help

    Returns:
        True se o updater foi iniciado com sucesso
    """
    if not app_dir:
        app_dir = get_app_dir()

    # Procura o CedNet_Updater.exe na mesma pasta ou pasta pai
    updater_paths = [
        os.path.join(app_dir, "CedNet_Updater.exe"),
        os.path.join(app_dir, "..", "CedNet_Updater", "CedNet_Updater.exe"),
        os.path.join(app_dir, "updater", "CedNet_Updater.exe"),
    ]

    updater_exe = None
    for path in updater_paths:
        if os.path.exists(path):
            updater_exe = os.path.abspath(path)
            break

    if not updater_exe:
        return False

    # Prepara os argumentos para o Updater
    args = [
        updater_exe,
        "--install-dir", app_dir,
        "--download-url", update_info.get("download_url", ""),
        "--version", update_info.get("version", ""),
    ]

    sha256 = update_info.get("sha256", "")
    if sha256:
        args.extend(["--sha256", sha256])

    try:
        subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return True
    except Exception:
        return False
