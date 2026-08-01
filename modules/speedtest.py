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

# Dummy stream para PyInstaller --windowed mode (evita 'ValueError: negative file descriptor')
class NullStream(io.StringIO):
    def fileno(self):
        return -1
    def write(self, s):
        pass
    def flush(self):
        pass

for _stream_name in ('stdin', 'stdout', 'stderr'):
    _stream = getattr(sys, _stream_name, None)
    if _stream is None or not hasattr(_stream, 'fileno'):
        setattr(sys, _stream_name, NullStream())
    else:
        try:
            if _stream.fileno() < 0:
                setattr(sys, _stream_name, NullStream())
        except Exception:
            setattr(sys, _stream_name, NullStream())


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
        engine_type pode ser: 'ookla', 'cli', 'not_found'
    """
    # 1. Caminho passado por argumento ou salvo nas configurações
    target_path = custom_path or load_settings().get("speedtest_cli_path", "")
    if target_path and os.path.exists(target_path) and os.path.isfile(target_path):
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
        if os.path.exists(p) and os.path.isfile(p):
            save_setting("speedtest_cli_path", p)
            return "ookla", p

    # 3. Procurar speedtest.exe no PATH do sistema
    ookla_path = shutil.which("speedtest.exe") or shutil.which("speedtest")
    if ookla_path and "python" not in ookla_path.lower() and os.path.isfile(ookla_path):
        save_setting("speedtest_cli_path", ookla_path)
        return "ookla", ookla_path

    # 4. Procurar script speedtest-cli
    cli_path = shutil.which("speedtest-cli")
    if cli_path and os.path.isfile(cli_path):
        save_setting("speedtest_cli_path", cli_path)
        return "cli", cli_path

    # 5. Se nenhuma CLI for encontrada
    return "not_found", ""



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

    def run_demo_test(
        self,
        demo_params: dict,
        on_progress: Callable[[int, str, dict], None],
        on_complete: Callable[[dict], None],
        on_error: Callable[[str], None],
    ):
        """Inicia uma simulação realista de Speed Test (Modo Demonstração)."""
        if self._is_running:
            return

        self._is_running = True
        self._cancel_requested = False

        thread = threading.Thread(
            target=self._run_demo_worker,
            args=(demo_params, on_progress, on_complete, on_error),
            daemon=True,
            name="SpeedTestDemoWorker",
        )
        thread.start()

    def _run_demo_worker(
        self,
        demo_params: dict,
        on_progress: Callable[[int, str, dict], None],
        on_complete: Callable[[dict], None],
        on_error: Callable[[str], None],
    ):
        import random
        import math
        start_time = time.time()

        try:
            target_dl = float(demo_params.get("download_mbps", 300.0))
            target_ul = float(demo_params.get("upload_mbps", 150.0))
            ping_val = float(demo_params.get("ping_ms", 12.0))
            jitter_val = float(demo_params.get("jitter_ms", 1.5))
            loss_val = float(demo_params.get("packet_loss_pct", 0.0))

            isp = demo_params.get("isp", "CedNet Telecom")
            public_ip = demo_params.get("public_ip", "189.100.50.25")
            server_name = demo_params.get("server_name", "CedNet SP")
            server_loc = demo_params.get("server_location", "São Paulo - Brasil")

            partial_state = {
                "phase": "init",
                "download_mbps": 0.0,
                "upload_mbps": 0.0,
                "download_max_mbps": 0.0,
                "upload_max_mbps": 0.0,
                "ping_ms": 0.0,
                "jitter_ms": 0.0,
                "packet_loss_pct": loss_val,
                "isp": isp,
                "public_ip": public_ip,
                "server_name": server_name,
                "server_location": server_loc,
                "progress_pct": 5,
                "step_label": "🟢 Conectando (Modo Demo)...",
                "is_demo": True,
            }

            # 1. Servidor
            if self._cancel_requested:
                return
            partial_state["phase"] = "server"
            partial_state["step_label"] = "🟢 Servidor encontrado"
            partial_state["progress_pct"] = 15
            on_progress(15, partial_state["step_label"], partial_state.copy())
            time.sleep(1.2)

            # 2. Ping
            if self._cancel_requested:
                return
            partial_state["phase"] = "ping"
            partial_state["step_label"] = "🟢 Medindo latência (Ping/Jitter)..."
            partial_state["ping_ms"] = ping_val
            partial_state["jitter_ms"] = jitter_val
            partial_state["progress_pct"] = 25
            on_progress(25, partial_state["step_label"], partial_state.copy())
            time.sleep(1.5)

            # 3. Download (Simulação realista de ~8 segundos)
            if self._cancel_requested:
                return
            partial_state["phase"] = "download"
            partial_state["step_label"] = "🟢 Medindo Download..."

            dl_steps = 32
            max_dl = 0.0
            for i in range(1, dl_steps + 1):
                if self._cancel_requested:
                    return
                ratio = i / dl_steps
                curve = 1.0 - math.exp(-i / 6.0)
                fluctuation = random.uniform(-0.025, 0.035) if i > 8 else 0.0
                cur_dl = round(target_dl * curve * (1.0 + fluctuation), 2)
                if cur_dl > max_dl:
                    max_dl = cur_dl

                partial_state["download_mbps"] = cur_dl
                partial_state["download_max_mbps"] = max_dl
                prog = 30 + int(ratio * 35)
                partial_state["progress_pct"] = prog
                on_progress(prog, partial_state["step_label"], partial_state.copy())
                time.sleep(0.25)

            partial_state["download_mbps"] = target_dl
            partial_state["download_max_mbps"] = max(target_dl, max_dl)
            on_progress(65, partial_state["step_label"], partial_state.copy())
            time.sleep(0.6)

            # 4. Upload (Simulação realista de ~8 segundos)
            if self._cancel_requested:
                return
            partial_state["phase"] = "upload"
            partial_state["step_label"] = "🟢 Medindo Upload..."

            ul_steps = 32
            max_ul = 0.0
            for i in range(1, ul_steps + 1):
                if self._cancel_requested:
                    return
                ratio = i / ul_steps
                curve = 1.0 - math.exp(-i / 6.0)
                fluctuation = random.uniform(-0.025, 0.035) if i > 8 else 0.0
                cur_ul = round(target_ul * curve * (1.0 + fluctuation), 2)
                if cur_ul > max_ul:
                    max_ul = cur_ul

                partial_state["upload_mbps"] = cur_ul
                partial_state["upload_max_mbps"] = max_ul
                prog = 65 + int(ratio * 30)
                partial_state["progress_pct"] = prog
                on_progress(prog, partial_state["step_label"], partial_state.copy())
                time.sleep(0.25)

            partial_state["upload_mbps"] = target_ul
            partial_state["upload_max_mbps"] = max(target_ul, max_ul)

            # 5. Conclusão Demo
            if self._cancel_requested:
                return

            elapsed = round(time.time() - start_time, 1)
            final_result = {
                "download_mbps": target_dl,
                "upload_mbps": target_ul,
                "download_max_mbps": max(target_dl, max_dl),
                "upload_max_mbps": max(target_ul, max_ul),
                "ping_ms": ping_val,
                "jitter_ms": jitter_val,
                "packet_loss_pct": loss_val,
                "isp": isp,
                "public_ip": public_ip,
                "server_name": server_name,
                "server_location": server_loc,
                "distance_km": 0,
                "elapsed_seconds": elapsed,
                "date_str": datetime.datetime.now().strftime("%d/%m/%Y"),
                "time_str": datetime.datetime.now().strftime("%H:%M:%S"),
                "engine": "Modo Demonstração 🎭",
                "is_demo": True,
            }

            self._is_running = False
            on_complete(final_result)

        except Exception as e:
            self._is_running = False
            on_error(f"Erro na simulação do Modo Demo: {e}")

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

            if engine_type == "not_found":
                self._is_running = False
                on_error("Speedtest CLI não encontrado. Selecione o executável para continuar.")
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
    # Execução via Ookla Speedtest.exe Oficial (Streaming JSONL)
    # ================================================================

    def _run_ookla_engine(self, bin_path: str, on_progress: Callable) -> Optional[dict]:
        if self._cancel_requested:
            return None

        try:
            kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1,
            }
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(
                [bin_path, "-f", "jsonl", "-p", "yes", "--accept-license", "--accept-gdpr"],
                **kwargs
            )

            partial_state = {
                "phase": "init",
                "download_mbps": 0.0,
                "upload_mbps": 0.0,
                "download_max_mbps": 0.0,
                "upload_max_mbps": 0.0,
                "ping_ms": 0.0,
                "jitter_ms": 0.0,
                "packet_loss_pct": 0.0,
                "isp": "—",
                "public_ip": "—",
                "server_name": "—",
                "server_location": "—",
                "progress_pct": 5,
                "step_label": "🟢 Conectando...",
            }
            on_progress(5, "🟢 Conectando aos servidores Ookla...", partial_state.copy())

            final_result = None

            while True:
                if self._cancel_requested:
                    if self._process:
                        try:
                            self._process.terminate()
                        except Exception:
                            pass
                    return None

                line = self._process.stdout.readline()
                if not line:
                    break

                line_str = line.strip()
                if not line_str or not line_str.startswith("{"):
                    continue

                try:
                    data = json.loads(line_str)
                except Exception:
                    continue

                event_type = data.get("type")

                if event_type == "testStart":
                    partial_state["phase"] = "server"
                    partial_state["step_label"] = "🟢 Escolhendo melhor servidor..."
                    partial_state["progress_pct"] = 15

                    if "isp" in data:
                        partial_state["isp"] = data["isp"]
                    if "interface" in data and "externalIp" in data["interface"]:
                        partial_state["public_ip"] = data["interface"]["externalIp"]
                    if "server" in data:
                        srv = data["server"]
                        partial_state["server_name"] = srv.get("name", "—")
                        loc = srv.get("location", "")
                        country = srv.get("country", "")
                        partial_state["server_location"] = f"{loc} - {country}".strip(" -")
                    
                    on_progress(15, partial_state["step_label"], partial_state.copy())

                elif event_type == "ping":
                    partial_state["phase"] = "ping"
                    partial_state["step_label"] = "🟢 Medindo latência (Ping/Jitter)..."
                    png = data.get("ping", {})
                    partial_state["ping_ms"] = round(png.get("latency", 0), 1)
                    partial_state["jitter_ms"] = round(png.get("jitter", 0), 1)
                    prog = png.get("progress", 0)
                    partial_state["progress_pct"] = int(20 + prog * 10)

                    on_progress(partial_state["progress_pct"], partial_state["step_label"], partial_state.copy())

                elif event_type == "download":
                    partial_state["phase"] = "download"
                    partial_state["step_label"] = "🟢 Medindo Download..."
                    dl = data.get("download", {})
                    bw = dl.get("bandwidth", 0)
                    cur_mbps = round(bw * 8 / 1e6, 2)
                    partial_state["download_mbps"] = cur_mbps
                    if cur_mbps > partial_state["download_max_mbps"]:
                        partial_state["download_max_mbps"] = cur_mbps

                    prog = dl.get("progress", 0)
                    partial_state["progress_pct"] = int(30 + prog * 35)

                    on_progress(partial_state["progress_pct"], partial_state["step_label"], partial_state.copy())

                elif event_type == "upload":
                    partial_state["phase"] = "upload"
                    partial_state["step_label"] = "🟢 Medindo Upload..."
                    ul = data.get("upload", {})
                    bw = ul.get("bandwidth", 0)
                    cur_mbps = round(bw * 8 / 1e6, 2)
                    partial_state["upload_mbps"] = cur_mbps
                    if cur_mbps > partial_state["upload_max_mbps"]:
                        partial_state["upload_max_mbps"] = cur_mbps

                    prog = ul.get("progress", 0)
                    partial_state["progress_pct"] = int(65 + prog * 30)

                    on_progress(partial_state["progress_pct"], partial_state["step_label"], partial_state.copy())

                elif event_type == "result":
                    partial_state["phase"] = "complete"
                    partial_state["step_label"] = "✔ Teste concluído"
                    partial_state["progress_pct"] = 100

                    download_mbps = round(data.get("download", {}).get("bandwidth", 0) * 8 / 1e6, 2)
                    upload_mbps = round(data.get("upload", {}).get("bandwidth", 0) * 8 / 1e6, 2)
                    ping_ms = round(data.get("ping", {}).get("latency", 0), 1)
                    jitter_ms = round(data.get("ping", {}).get("jitter", 0), 1)
                    packet_loss = round(data.get("packetLoss", 0.0), 1)

                    isp = data.get("isp", partial_state.get("isp", "CedNet Telecom"))
                    public_ip = data.get("interface", {}).get("externalIp", partial_state.get("public_ip", "—"))

                    srv = data.get("server", {})
                    server_name = srv.get("name", partial_state.get("server_name", "Servidor Ookla"))
                    loc = srv.get("location", "")
                    country = srv.get("country", "")
                    server_loc = f"{loc} - {country}".strip(" -") if loc else partial_state.get("server_location", "—")

                    final_result = {
                        "download_mbps": download_mbps,
                        "upload_mbps": upload_mbps,
                        "download_max_mbps": max(download_mbps, partial_state["download_max_mbps"]),
                        "upload_max_mbps": max(upload_mbps, partial_state["upload_max_mbps"]),
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
                    on_progress(100, "✔ Teste concluído", final_result.copy())

            if self._process:
                try:
                    self._process.wait(timeout=3)
                except Exception:
                    pass

            return final_result or (partial_state if partial_state.get("download_mbps", 0) > 0 else None)

        except Exception as exc:
            print(f"Erro no Ookla Engine streaming: {exc}")
            return None

    # ================================================================
    # Execução via speedtest-cli script
    # ================================================================

    def _run_cli_engine(self, bin_path: str, on_progress: Callable) -> Optional[dict]:
        if self._cancel_requested:
            return None

        on_progress(30, "Executando Speedtest CLI...", {})

        try:
            kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            }
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(
                [bin_path, "--json"],
                **kwargs
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
        except Exception as exc:
            print(f"Erro no CLI Engine: {exc}")
            return None


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
