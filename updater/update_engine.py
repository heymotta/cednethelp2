"""
CedNet Updater - Engine de Download & Instalação
Módulo responsável por:
  - Baixar o pacote .zip com progresso e velocidade
  - Verificar integridade via SHA-256
  - Encerrar processos do CedNet Help
  - Extrair e substituir arquivos preservando dados do usuário
  - Reiniciar o CedNet Help após conclusão
"""

import os
import sys
import time
import hashlib
import shutil
import zipfile
import subprocess
import urllib.request
import urllib.error
import ssl
import threading
import tempfile
import datetime
from typing import Callable, Optional


# Diretórios e arquivos que NUNCA são sobrescritos durante a atualização
PRESERVED_PATTERNS = [
    "data",
    "logs",
    "passwords.json",
]


def get_log_path() -> str:
    """Retorna o caminho do arquivo de log do updater."""
    log_dir = os.path.join(tempfile.gettempdir(), "CedNet_Updater_Logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "updater.log")


def write_log(message: str):
    """Escreve uma entrada no log do updater."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(get_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


class UpdateEngine:
    """
    Engine principal do CedNet Updater.
    Gerencia download, verificação, extração e instalação.
    """

    def __init__(
        self,
        install_dir: str,
        download_url: str,
        target_version: str,
        expected_sha256: str = "",
    ):
        self.install_dir = os.path.abspath(install_dir)
        self.download_url = download_url
        self.target_version = target_version
        self.expected_sha256 = expected_sha256.strip().lower()

        self._cancel_requested = False
        self._is_running = False

        # Caminhos temporários
        self._temp_dir = tempfile.mkdtemp(prefix="cednet_update_")
        self._zip_path = os.path.join(self._temp_dir, "update.zip")
        self._extract_dir = os.path.join(self._temp_dir, "extracted")

        write_log(f"UpdateEngine inicializado: install_dir={self.install_dir}, url={self.download_url}, version={self.target_version}")

    def cancel(self):
        """Solicita cancelamento da operação."""
        self._cancel_requested = True
        write_log("Cancelamento solicitado pelo usuário.")

    def is_running(self) -> bool:
        return self._is_running

    def run_update(
        self,
        on_progress: Callable[[int, str, str], None],
        on_complete: Callable[[bool, str], None],
    ):
        """
        Executa a atualização completa em background thread.

        Args:
            on_progress: callback(percent, status_text, detail_text)
            on_complete: callback(success: bool, message: str)
        """
        if self._is_running:
            return

        self._is_running = True
        self._cancel_requested = False

        thread = threading.Thread(
            target=self._run_worker,
            args=(on_progress, on_complete),
            daemon=True,
            name="UpdateEngineWorker",
        )
        thread.start()

    def _run_worker(self, on_progress, on_complete):
        """Worker thread executando todas as etapas da atualização."""
        try:
            # Etapa 1: Download
            on_progress(5, "Baixando atualização...", f"Conectando a {self.download_url[:60]}...")
            write_log(f"Iniciando download: {self.download_url}")

            success = self._download_file(on_progress)
            if not success:
                if self._cancel_requested:
                    on_complete(False, "Download cancelado pelo usuário.")
                else:
                    on_complete(False, "Falha ao baixar o pacote de atualização.\nVerifique sua conexão com a internet.")
                self._cleanup()
                return

            # Etapa 2: Verificação de integridade
            if self._cancel_requested:
                on_complete(False, "Atualização cancelada.")
                self._cleanup()
                return

            on_progress(70, "Verificando integridade...", "Calculando hash SHA-256...")
            write_log("Verificando integridade do download.")

            if self.expected_sha256:
                file_hash = self._calculate_sha256(self._zip_path)
                if file_hash != self.expected_sha256:
                    write_log(f"FALHA de integridade! Esperado: {self.expected_sha256}, Obtido: {file_hash}")
                    on_complete(False, "Falha na verificação de integridade do arquivo.\nO download pode estar corrompido. Tente novamente.")
                    self._cleanup()
                    return
                write_log(f"Hash SHA-256 verificado com sucesso: {file_hash}")

            # Etapa 3: Extrair o pacote
            if self._cancel_requested:
                on_complete(False, "Atualização cancelada.")
                self._cleanup()
                return

            on_progress(75, "Extraindo arquivos...", "Descompactando pacote de atualização...")
            write_log("Extraindo arquivos do pacote .zip")

            extract_ok = self._extract_zip()
            if not extract_ok:
                on_complete(False, "Falha ao extrair o pacote de atualização.\nO arquivo pode estar corrompido.")
                self._cleanup()
                return

            # Etapa 4: Encerrar processos do CedNet Help
            on_progress(82, "Encerrando CedNet Help...", "Finalizando processos em execução...")
            write_log("Encerrando processos do CedNet Help.")
            self._kill_cednet_processes()

            time.sleep(1.0)  # Aguarda processos encerrarem

            # Etapa 5: Substituir arquivos
            if self._cancel_requested:
                on_complete(False, "Atualização cancelada.")
                self._cleanup()
                return

            on_progress(88, "Instalando atualização...", "Substituindo arquivos do programa...")
            write_log(f"Substituindo arquivos em: {self.install_dir}")

            install_ok = self._install_files()
            if not install_ok:
                on_complete(False, "Falha ao instalar os novos arquivos.\nVerifique as permissões da pasta de instalação.")
                self._cleanup()
                return

            # Etapa 6: Limpeza
            on_progress(95, "Finalizando...", "Limpando arquivos temporários...")
            self._cleanup()

            on_progress(100, "Atualização concluída!", f"CedNet Help atualizado para v{self.target_version}")
            write_log(f"Atualização para v{self.target_version} concluída com sucesso!")

            self._is_running = False
            on_complete(True, f"Atualização para v{self.target_version} concluída com sucesso!")

        except Exception as e:
            write_log(f"ERRO CRÍTICO: {str(e)}")
            self._is_running = False
            on_complete(False, f"Erro inesperado durante a atualização:\n{str(e)}")
            self._cleanup()

    # ================================================================
    # Download com Progresso
    # ================================================================

    def _download_file(self, on_progress) -> bool:
        """Baixa o arquivo ZIP com progresso em tempo real."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "CedNet-Updater/1.0"},
            )

            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192
                start_time = time.time()

                with open(self._zip_path, "wb") as f:
                    while True:
                        if self._cancel_requested:
                            return False

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # Calcula progresso e velocidade
                        elapsed = time.time() - start_time
                        speed_bps = downloaded / max(elapsed, 0.001)

                        if speed_bps >= 1_048_576:
                            speed_str = f"{speed_bps / 1_048_576:.1f} MB/s"
                        else:
                            speed_str = f"{speed_bps / 1024:.0f} KB/s"

                        if total_size > 0:
                            pct = int((downloaded / total_size) * 65) + 5  # 5% a 70%
                            size_str = f"{downloaded / 1_048_576:.1f} / {total_size / 1_048_576:.1f} MB"
                        else:
                            pct = min(65, int(downloaded / 10_000))
                            size_str = f"{downloaded / 1_048_576:.1f} MB"

                        on_progress(pct, "Baixando atualização...", f"{size_str}  •  {speed_str}")

            write_log(f"Download concluído: {downloaded} bytes em {time.time() - start_time:.1f}s")
            return True

        except Exception as e:
            write_log(f"Erro no download: {str(e)}")
            return False

    # ================================================================
    # Verificação de Integridade
    # ================================================================

    @staticmethod
    def _calculate_sha256(filepath: str) -> str:
        """Calcula o hash SHA-256 de um arquivo."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest().lower()

    # ================================================================
    # Extração do Pacote ZIP
    # ================================================================

    def _extract_zip(self) -> bool:
        """Extrai o conteúdo do ZIP baixado."""
        try:
            os.makedirs(self._extract_dir, exist_ok=True)
            with zipfile.ZipFile(self._zip_path, "r") as zf:
                zf.extractall(self._extract_dir)
            write_log(f"Extração concluída em: {self._extract_dir}")
            return True
        except (zipfile.BadZipFile, Exception) as e:
            write_log(f"Erro na extração: {str(e)}")
            return False

    # ================================================================
    # Encerrar Processos do CedNet Help
    # ================================================================

    @staticmethod
    def _kill_cednet_processes():
        """Encerra todos os processos CedNet_Help.exe em execução."""
        try:
            subprocess.run(
                'taskkill /F /IM "CedNet_Help.exe"',
                shell=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except Exception:
            pass

    # ================================================================
    # Instalação dos Novos Arquivos
    # ================================================================

    def _install_files(self) -> bool:
        """
        Copia os novos arquivos para o diretório de instalação,
        preservando dados do usuário (data/, logs/, passwords.json).
        """
        try:
            # Identifica o diretório raiz dentro do ZIP extraído
            source_dir = self._find_source_root(self._extract_dir)
            if not source_dir:
                write_log("Não foi possível identificar a raiz dos arquivos no pacote.")
                return False

            write_log(f"Diretório fonte identificado: {source_dir}")

            # Itera sobre os arquivos do pacote e copia para o install_dir
            for root, dirs, files in os.walk(source_dir):
                # Caminho relativo dentro do pacote
                rel_root = os.path.relpath(root, source_dir)

                # Verifica se esse diretório deve ser preservado
                if self._should_preserve(rel_root):
                    write_log(f"  PRESERVADO (dir): {rel_root}")
                    continue

                # Cria o diretório de destino
                dest_dir = os.path.join(self.install_dir, rel_root) if rel_root != "." else self.install_dir
                os.makedirs(dest_dir, exist_ok=True)

                for filename in files:
                    rel_path = os.path.join(rel_root, filename) if rel_root != "." else filename

                    # Verifica se esse arquivo deve ser preservado
                    if self._should_preserve(rel_path):
                        write_log(f"  PRESERVADO: {rel_path}")
                        continue

                    src_file = os.path.join(root, filename)
                    dst_file = os.path.join(self.install_dir, rel_path)

                    try:
                        shutil.copy2(src_file, dst_file)
                    except Exception as e:
                        write_log(f"  ERRO ao copiar {rel_path}: {str(e)}")

            write_log("Instalação dos novos arquivos concluída.")
            return True

        except Exception as e:
            write_log(f"Erro na instalação: {str(e)}")
            return False

    def _find_source_root(self, extract_dir: str) -> Optional[str]:
        """
        Identifica o diretório raiz dentro do ZIP extraído.
        O ZIP pode conter uma pasta raiz (CedNet_Help/) ou os arquivos diretamente.
        """
        entries = os.listdir(extract_dir)

        # Se o ZIP contém uma única pasta, essa é a raiz
        if len(entries) == 1:
            single = os.path.join(extract_dir, entries[0])
            if os.path.isdir(single):
                # Verifica se parece com a raiz do projeto (contém main.py ou CedNet_Help.exe)
                inner = os.listdir(single)
                if "CedNet_Help.exe" in inner or "main.py" in inner:
                    return single

        # Se contém diretamente os arquivos do projeto
        if "CedNet_Help.exe" in entries or "main.py" in entries:
            return extract_dir

        # Busca recursiva de 1 nível
        for entry in entries:
            path = os.path.join(extract_dir, entry)
            if os.path.isdir(path):
                inner = os.listdir(path)
                if "CedNet_Help.exe" in inner or "main.py" in inner:
                    return path

        return extract_dir

    @staticmethod
    def _should_preserve(rel_path: str) -> bool:
        """Verifica se um caminho deve ser preservado durante a atualização."""
        rel_path_normalized = rel_path.replace("\\", "/").strip("/")
        for pattern in PRESERVED_PATTERNS:
            if rel_path_normalized == pattern or rel_path_normalized.startswith(pattern + "/"):
                return True
        return False

    # ================================================================
    # Limpeza
    # ================================================================

    def _cleanup(self):
        """Remove arquivos temporários do download e extração."""
        self._is_running = False
        try:
            if os.path.exists(self._temp_dir):
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            write_log("Limpeza de temporários concluída.")
        except Exception:
            pass

    # ================================================================
    # Reiniciar CedNet Help
    # ================================================================

    def restart_cednet_help(self) -> bool:
        """Inicia o CedNet Help após a atualização."""
        exe_path = os.path.join(self.install_dir, "CedNet_Help.exe")

        if not os.path.exists(exe_path):
            write_log(f"CedNet_Help.exe não encontrado em: {exe_path}")
            return False

        try:
            subprocess.Popen(
                [exe_path],
                cwd=self.install_dir,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            write_log(f"CedNet Help reiniciado: {exe_path}")
            return True
        except Exception as e:
            write_log(f"Erro ao reiniciar: {str(e)}")
            return False
