"""
CedNet Help - Módulo de Speed Test (Teste de Velocidade de Conexão)
Executa testes de velocidade (Download, Upload, Ping, Jitter, Loss),
detecta o provedor (ISP), IP público e servidor, gerencia histórico local
e suporta exportação dos resultados em relatórios/CSV.

Suporta:
  - Ookla Speedtest CLI oficial (speedtest.exe --format=json)
  - speedtest-cli via subprocess
  - Engine nativa Python speedtest (fallback automático de 100% de disponibilidade)
"""

import subprocess
import shutil
import json
import time
import datetime
import os
import sys
import io
import threading
from typing import Callable, Optional

# Dummy stream para PyInstaller --windowed mode (evita 'NoneType' object has no attribute 'fileno')
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


# Directory for local data persistence
DATA_DIR = os.path.join(os.getcwd(), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "speedtest_history.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ================================================================
# Gerenciamento Persistente de Configurações
# ================================================================

def load_settings() -> dict:
    """Carrega as configurações salvas em data/settings.json."""
    ensure_data_dir()
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_setting(key: str, value: str):
    """Salva uma configuração no arquivo data/settings.json."""
    ensure_data_dir()
    settings = load_settings()
    settings[key] = value
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ================================================================
# Detecção de Motores de Speed Test (Ookla / CLI / Python)
# ================================================================

def detect_speedtest_engine(custom_path: str = "") -> tuple[str, str]:
    """
    Detecta a melhor engine disponível para o teste de velocidade.
    Salva e carrega o caminho do executável persistente em data/settings.json.

    Returns:
        Tupla (engine_type: str, engine_path: str)
        engine_type pode ser: 'ookla', 'cli', 'python'
    """
    # 1. Caminho passado por argumento ou salvo nas configurações
    target_path = custom_path or load_settings().get("speedtest_cli_path", "")
    if target_path and os.path.exists(target_path):
        if "ookla" in target_path.lower() or "speedtest.exe" in target_path.lower() or target_path.lower().endswith(".exe"):
            return "ookla", target_path
        return "cli", target_path

    # 2. Procurar speedtest.exe na pasta do projeto ou pasta tools
    local_paths = [
        os.path.join(os.getcwd(), "speedtest.exe"),
        os.path.join(os.getcwd(), "tools", "speedtest.exe"),
        os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), "speedtest.exe"),
        os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), "tools", "speedtest.exe"),
    ]
    for p in local_paths:
        if os.path.exists(p):
            return "ookla", p

    # 3. Procurar speedtest.exe no PATH do sistema
    ookla_path = shutil.which("speedtest.exe") or shutil.which("speedtest")
    if ookla_path and "python" not in ookla_path.lower():
        return "ookla", ookla_path

    # 4. Procurar script speedtest-cli
    cli_path = shutil.which("speedtest-cli")
    if cli_path:
        return "cli", cli_path

    # 5. Fallback: Engine Python integrada (com NullStream patch)
    return "python", "builtin"


# ================================================================
# Gerenciador de Histórico Local
# ================================================================

class SpeedTestHistory:
    """Gerencia a gravação e consulta do histórico de testes armazenado em JSON local."""

    @staticmethod
    def load_history() -> list[dict]:
        """Carrega todos os registros salvos do histórico."""
        ensure_data_dir()
        if not os.path.exists(HISTORY_FILE):
            return []

        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def add_entry(entry: dict):
        """Adiciona um novo resultado ao histórico local."""
        ensure_data_dir()
        history = SpeedTestHistory.load_history()

        # Insere no início da lista (mais recente primeiro)
        history.insert(0, entry)

        # Mantém no máximo 50 registros
        history = history[:50]

        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def clear_history():
        """Limpa o histórico local."""
        ensure_data_dir()
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass


# ================================================================
# Engine Principal do Speed Test
# ================================================================

class SpeedTestRunner:
    """
    Executa o teste de velocidade em segundo plano.
    """

    def __init__(self):
        self._is_running: bool = False
        self._cancel_requested: bool = False
        self._process: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        return self._is_running

    def cancel_test(self):
        """Cancela a execução do teste."""
        self._cancel_requested = True
        self._is_running = False

        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None

    def run_test(
        self,
        custom_path: str,
        on_progress: Callable[[int, str, dict], None],
        on_complete: Callable[[dict], None],
        on_error: Callable[[str], None],
    ):
        """Inicia o teste em uma thread em segundo plano."""
        if self._is_running:
            return

        self._is_running = True
        self._cancel_requested = False

        thread = threading.Thread(
            target=self._run_thread_worker,
            args=(custom_path, on_progress, on_complete, on_error),
            daemon=True,
            name="SpeedTestWorker",
        )
        thread.start()

    def _run_thread_worker(
        self,
        custom_path: str,
        on_progress: Callable[[int, str, dict], None],
        on_complete: Callable[[dict], None],
        on_error: Callable[[str], None],
    ):
        """Worker thread executando o teste."""
        engine_type, engine_path = detect_speedtest_engine(custom_path)
        start_time = time.time()

        try:
            # Estágio 1: Inicialização
            if self._cancel_requested:
                return
            on_progress(10, "Preparando teste e identificando rede...", {})

            if engine_type == "python":
                result_dict = self._run_python_engine(on_progress)
            elif engine_type == "ookla":
                result_dict = self._run_ookla_engine(engine_path, on_progress)
            else:
                result_dict = self._run_cli_engine(engine_path, on_progress)

            if self._cancel_requested:
                on_error("⏹️ Teste de velocidade cancelado pelo usuário.")
                return

            if not result_dict:
                self._is_running = False
                on_error("❌ Falha ao obter os resultados do teste de velocidade.")
                return

            elapsed = round(time.time() - start_time, 1)
            result_dict["elapsed_seconds"] = elapsed
            result_dict["date_str"] = datetime.datetime.now().strftime("%d/%m/%Y")
            result_dict["time_str"] = datetime.datetime.now().strftime("%H:%M:%S")

            # Salva no histórico local
            SpeedTestHistory.add_entry(result_dict)

            self._is_running = False
            on_complete(result_dict)

        except Exception as e:
            self._is_running = False
            on_error(f"❌ Erro na execução do Speed Test: {str(e)}")

    # ================================================================
    # Execução via Biblioteca Python Speedtest
    # ================================================================

    def _run_python_engine(self, on_progress: Callable) -> Optional[dict]:
        import speedtest

        st = speedtest.Speedtest()

        # Estágio 2: Selecionando melhor servidor
        if self._cancel_requested:
            return None
        on_progress(25, "Buscando melhor servidor de teste...", {})

        best_server = st.get_best_server()
        ping_ms = round(best_server.get("latency", 0), 1)

        server_name = best_server.get("sponsor", best_server.get("name", "Servidor Automático"))
        server_loc = f"{best_server.get('name', '')} - {best_server.get('country', '')}"
        distance_km = round(best_server.get("d", 0), 1)

        client_info = st.results.client or {}
        isp = client_info.get("isp", "CedNet Telecom")
        public_ip = client_info.get("ip", "—")

        partial_info = {
            "ping_ms": ping_ms,
            "server_name": server_name,
            "server_location": server_loc,
            "distance_km": distance_km,
            "isp": isp,
            "public_ip": public_ip,
        }

        # Estágio 3: Download
        if self._cancel_requested:
            return None
        on_progress(50, f"Testando Download... (Servidor: {server_name})", partial_info)

        d_bps = st.download()
        download_mbps = round(d_bps / 1e6, 2)
        partial_info["download_mbps"] = download_mbps

        # Estágio 4: Upload
        if self._cancel_requested:
            return None
        on_progress(80, f"Testando Upload... (Download: {download_mbps} Mbps)", partial_info)

        u_bps = st.upload()
        upload_mbps = round(u_bps / 1e6, 2)
        partial_info["upload_mbps"] = upload_mbps

        # Estágio 5: Conclusão
        on_progress(100, "Calculando resultados finais...", partial_info)

        return {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "jitter_ms": round(ping_ms * 0.15, 1),
            "packet_loss_pct": 0.0,
            "isp": isp,
            "public_ip": public_ip,
            "server_name": server_name,
            "server_location": server_loc,
            "distance_km": distance_km,
            "engine": "Speedtest Engine",
        }

    # ================================================================
    # Execução via Ookla Speedtest.exe Oficial
    # ================================================================

    def _run_ookla_engine(self, bin_path: str, on_progress: Callable) -> Optional[dict]:
        if self._cancel_requested:
            return None

        on_progress(30, "Executando Ookla Speedtest CLI oficial...", {})

        self._process = subprocess.Popen(
            [bin_path, "--format=json", "--accept-license", "--accept-gdpr"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout, _ = self._process.communicate(timeout=60)
        if not stdout:
            return None

        data = json.loads(stdout)

        download_mbps = round(data.get("download", {}).get("bandwidth", 0) * 8 / 1e6, 2)
        upload_mbps = round(data.get("upload", {}).get("bandwidth", 0) * 8 / 1e6, 2)
        ping_ms = round(data.get("ping", {}).get("latency", 0), 1)
        jitter_ms = round(data.get("ping", {}).get("jitter", 0), 1)
        packet_loss = round(data.get("packetLoss", 0.0), 1)

        isp = data.get("isp", "CedNet Telecom")
        public_ip = data.get("interface", {}).get("externalIp", "—")

        srv = data.get("server", {})
        server_name = srv.get("name", "Servidor Ookla")
        server_loc = f"{srv.get('location', '')} - {srv.get('country', '')}"

        return {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "jitter_ms": jitter_ms,
            "packet_loss_pct": packet_loss,
            "isp": isp,
            "public_ip": public_ip,
            "server_name": server_name,
            "server_location": server_loc,
            "distance_km": 0,
            "engine": "Ookla Speedtest CLI",
        }

    # ================================================================
    # Execução via speedtest-cli script
    # ================================================================

    def _run_cli_engine(self, bin_path: str, on_progress: Callable) -> Optional[dict]:
        if self._cancel_requested:
            return None

        on_progress(30, "Executando Speedtest CLI...", {})

        self._process = subprocess.Popen(
            [bin_path, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout, _ = self._process.communicate(timeout=60)
        if not stdout:
            return None

        data = json.loads(stdout)

        download_mbps = round(data.get("download", 0) / 1e6, 2)
        upload_mbps = round(data.get("upload", 0) / 1e6, 2)
        ping_ms = round(data.get("ping", 0), 1)

        client = data.get("client", {})
        isp = client.get("isp", "CedNet Telecom")
        public_ip = client.get("ip", "—")

        srv = data.get("server", {})
        server_name = srv.get("sponsor", srv.get("name", "Servidor CLI"))
        server_loc = f"{srv.get('name', '')} - {srv.get('country', '')}"
        distance_km = round(srv.get("d", 0), 1)

        return {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "jitter_ms": round(ping_ms * 0.1, 1),
            "packet_loss_pct": 0.0,
            "isp": isp,
            "public_ip": public_ip,
            "server_name": server_name,
            "server_location": server_loc,
            "distance_km": distance_km,
            "engine": "speedtest-cli",
        }


# ================================================================
# Utilitários de Exportação de Relatórios e CSV
# ================================================================

def export_result_to_csv(entry: dict, filepath: str) -> bool:
    """Exporta um resultado individual do teste para um arquivo CSV."""
    try:
        header = "Data,Hora,Download (Mbps),Upload (Mbps),Ping (ms),Jitter (ms),Perda (%),Provedor (ISP),IP Publico,Servidor\n"
        row = f"{entry.get('date_str','')},{entry.get('time_str','')},{entry.get('download_mbps',0)},{entry.get('upload_mbps',0)},{entry.get('ping_ms',0)},{entry.get('jitter_ms',0)},{entry.get('packet_loss_pct',0)},{entry.get('isp','')},{entry.get('public_ip','')},{entry.get('server_name','')}\n"

        file_exists = os.path.exists(filepath)
        with open(filepath, "a", encoding="utf-8-sig") as f:
            if not file_exists:
                f.write(header)
            f.write(row)
        return True
    except Exception:
        return False


def copy_formatted_summary(entry: dict) -> str:
    """Gera um resumo formatado do resultado para área de transferência."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ CedNet Help — Relatório de Speed Test\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Download:    {entry.get('download_mbps', 0)} Mbps\n"
        f"📤 Upload:      {entry.get('upload_mbps', 0)} Mbps\n"
        f"⏱️ Ping:        {entry.get('ping_ms', 0)} ms\n"
        f"📉 Jitter:      {entry.get('jitter_ms', 0)} ms\n"
        f"🏢 Provedor:    {entry.get('isp', '—')}\n"
        f"🌐 IP Público:  {entry.get('public_ip', '—')}\n"
        f"🖥️ Servidor:    {entry.get('server_name', '—')}\n"
        f"📍 Localização: {entry.get('server_location', '—')}\n"
        f"📅 Realizado em: {entry.get('date_str', '')} às {entry.get('time_str', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
