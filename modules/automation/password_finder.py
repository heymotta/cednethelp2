"""
CedNet Help - Automação: Localizador de Senhas de Rádio/Roteador
Automação para testes de credenciais padrão em equipamentos autorizados.

Suporta:
  - Detecção automática de interface HTTP/HTTPS
  - Inspeção de formulários de login HTML (Ubiquiti, TP-Link, Intelbras, Huawei, ZTE, Geral)
  - Suporte a HTTP Basic/Digest Authentication
  - Gerenciamento de sessão e cookies (http.cookiejar)
  - Parada imediata ao encontrar o login correto
  - Log detalhado em tempo real e em arquivo de histórico local
"""

import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import ssl
import re
import html
import socket
import subprocess
import time
import os
import datetime
import threading
from typing import Callable, Optional
from modules.passwords import DEFAULT_PASSWORDS


# ================================================================
# Lista Específica de Senhas de Rádio & Provedor
# ================================================================
RADIO_PASSWORDS: list[str] = [
    "%W2sajuB",
    "DitCD34a9",
    "0D03BD7",
    "%cednet.734",
    "Fcd24cli",
    "dITcd34A9",
    "%DitCD34a9",
    "%DitCD34a10",
    "rogatech061",
    "98103855",
    "m2u0n7h8o3z+",
    "h748159263h*",
    "L0i2n0k4+",
    "base",
    "%Ph8rehu",
    "Erebro2h",
    "5SNRAv06",
    "Xbd74BN2",
    "%Ph8rehuGC@734",
    "%Ph8rehu@734",
]


def get_combined_passwords() -> list[str]:
    """
    Retorna a lista combinada e desduplicada de senhas de rádios e senhas padrão do sistema.
    """
    combined = list(RADIO_PASSWORDS)

    # Adiciona senhas do módulo passwords.py que não estejam na lista
    try:
        for p_entry in DEFAULT_PASSWORDS:
            pwd = p_entry.get("password", "").strip()
            if pwd and pwd not in combined:
                combined.append(pwd)
    except Exception:
        pass

    return combined


# ================================================================
# Engine de Automação de Login HTTP / Form / Basic Auth
# ================================================================

class RadioPasswordFinder:
    """
    Executa os testes de credenciais padrão em equipamentos de rádio/roteador.
    """

    def __init__(self):
        self._is_running: bool = False
        self._stop_requested: bool = False

        # SSL unverified context para rádios com certificado autoassinado
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    # ================================================================
    # Detecção de Conectividade e Web
    # ================================================================

    def check_target_web(self, target_ip: str) -> tuple[bool, str, str]:
        """
        Verifica se o IP responde e se possui porta web (80, 443, 8080, 8443) aberta.

        Returns:
            Tupla (is_web_open: bool, url_base: str, equipment_type: str)
        """
        # 1. Teste de ping rápido
        ping_ok = self._ping(target_ip)
        if not ping_ok:
            # Tenta mesmo assim caso o ping esteja bloqueado por firewall
            pass

        # 2. Testa portas web
        for protocol, port in [("http", 80), ("https", 443), ("http", 8080), ("https", 8443)]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex((target_ip, port)) == 0:
                        url = f"{protocol}://{target_ip}" if port in (80, 443) else f"{protocol}://{target_ip}:{port}"
                        eq_type = self._detect_equipment_type(url)
                        return True, url, eq_type
            except Exception:
                continue

        return False, "", "Desconhecido"

    def _ping(self, ip_str: str) -> bool:
        """Ping nativo do Windows."""
        try:
            res = subprocess.run(
                f"ping -n 1 -w 300 {ip_str}",
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1.0,
            )
            return res.returncode == 0
        except Exception:
            return False

    def _detect_equipment_type(self, url: str) -> str:
        """Inspeciona a página de login para identificar o fabricante."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=1.2, context=self._ssl_ctx) as resp:
                body = resp.read(4096).decode("utf-8", errors="ignore").upper()
                server = resp.headers.get("Server", "").upper()

                if "AIROS" in body or "UBIQUITI" in body or "UBNT" in body:
                    return "Ubiquiti airOS"
                if "INTELBRAS" in body or "WI-FORCE" in body:
                    return "Intelbras"
                if "MIKROTIK" in body or "ROUTEROS" in body:
                    return "MikroTik RouterOS"
                if "TP-LINK" in body or "TPLINK" in body:
                    return "TP-Link"
                if "HUAWEI" in body:
                    return "Huawei"
                if "ZTE" in body or "ZXHN" in body or "F670" in body:
                    return "ZTE"
                if "LIGHTTPD" in server:
                    return "Equipamento Web (lighttpd)"
        except Exception:
            pass

        return "Equipamento Web Geral"

    # ================================================================
    # Teste de Login Automatizado
    # ================================================================

    def start_finder(
        self,
        target_ip: str,
        username: str,
        on_progress: Callable[[dict], None],
        on_success: Callable[[dict], None],
        on_failure: Callable[[str], None],
    ):
        """Inicia a automação de testes de senha em thread separada."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_requested = False

        thread = threading.Thread(
            target=self._run_finder_thread,
            args=(target_ip, username, on_progress, on_success, on_failure),
            daemon=True,
            name="PasswordFinderWorker",
        )
        thread.start()

    def stop_finder(self):
        """Solicita a interrupção da automação."""
        self._stop_requested = True
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def _run_finder_thread(
        self,
        target_ip: str,
        username: str,
        on_progress: Callable[[dict], None],
        on_success: Callable[[dict], None],
        on_failure: Callable[[str], None],
    ):
        """Executa a sequência de testes de senha."""
        start_time = time.time()

        # 1. Verifica conectividade web
        is_web, url_base, eq_type = self.check_target_web(target_ip)

        if not is_web:
            self._is_running = False
            self._write_history_log(target_ip, url_base, eq_type, username, "FALHA", "Nenhuma interface web encontrada.")
            on_failure("❌ Equipamento não possui interface web (HTTP/HTTPS) acessível.")
            return

        passwords = get_combined_passwords()
        total_passwords = len(passwords)

        self._write_history_log(target_ip, url_base, eq_type, username, "INICIADO", f"Testando {total_passwords} senhas...")

        found_password = None

        for idx, password in enumerate(passwords, start=1):
            if self._stop_requested:
                self._is_running = False
                on_failure("⏹️ Automação interrompida pelo usuário.")
                return

            elapsed_sec = time.time() - start_time

            # Envia progresso para a UI
            progress_data = {
                "equipment": eq_type,
                "url": url_base,
                "username": username,
                "current_index": idx,
                "total": total_passwords,
                "current_password": password,
                "elapsed_seconds": elapsed_sec,
            }
            on_progress(progress_data)

            # Tenta autenticar
            login_ok = self._try_login(url_base, username, password)

            if login_ok:
                found_password = password
                break

            time.sleep(0.15)  # Pequena pausa entre requisições

        elapsed_sec = time.time() - start_time
        self._is_running = False

        if found_password:
            res_data = {
                "ip": target_ip,
                "url": url_base,
                "equipment": eq_type,
                "username": username,
                "password": found_password,
                "elapsed_seconds": elapsed_sec,
            }
            self._write_history_log(target_ip, url_base, eq_type, username, "SUCESSO", f"Senha encontrada: {found_password}")
            on_success(res_data)
        else:
            self._write_history_log(target_ip, url_base, eq_type, username, "FALHA", "Nenhuma senha aceita.")
            on_failure("❌ Nenhuma das senhas cadastradas foi aceita pelo equipamento.")

    # ================================================================
    # Submissão de Formulário / HTTP Authentication
    # ================================================================

    def _try_login(self, url_base: str, username: str, password: str) -> bool:
        """
        Tenta autenticação via HTTP POST Form submission ou Basic Auth.
        """
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

        # 1. Tenta Form POST com campos comuns de login
        form_payloads = [
            {"username": username, "password": password},
            {"user": username, "pass": password},
            {"user": username, "password": password},
            {"login": username, "password": password},
            {"username": username, "pwd": password},
            {"auth_user": username, "auth_pass": password},
            {"ubnt_username": username, "ubnt_password": password},
        ]

        # URLs de endpoint de login conhecidas
        login_endpoints = [
            "/login",
            "/login.cgi",
            "/cgi-bin/login.cgi",
            "/api/login",
            "/index.cgi",
            "",  # Página raiz
        ]

        for endpoint in login_endpoints:
            full_url = f"{url_base}{endpoint}"
            for payload in form_payloads:
                try:
                    data_encoded = urllib.parse.urlencode(payload).encode("utf-8")
                    req = urllib.request.Request(
                        full_url,
                        data=data_encoded,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )

                    with opener.open(req, timeout=1.5) as resp:
                        final_url = resp.geturl()
                        body = resp.read(3072).decode("utf-8", errors="ignore").lower()

                        # Indicadores de login BEM-SUCEDIDO:
                        # - Redirecionou para página principal (main.cgi, status.cgi, home, dashboard)
                        # - Ou recebeu cookie de sessão e corpo NÃO contém "invalid", "error", "erro", "incorreta"
                        if any(kw in final_url.lower() for kw in ["main", "status", "dashboard", "home", "index"]):
                            return True

                        if "invalid" not in body and "incorrect" not in body and "incorret" not in body and "fail" not in body:
                            # Se definiu um cookie e o HTTP retornou 200 OK sem mensagem de erro de login
                            if len(cj) > 0:
                                return True

                except urllib.error.HTTPError as e:
                    if e.code in (301, 302):
                        loc = e.headers.get("Location", "")
                        if any(kw in loc.lower() for kw in ["main", "status", "dashboard", "home"]):
                            return True
                except Exception:
                    pass

        # 2. Tenta HTTP Basic / Digest Auth
        try:
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, url_base, username, password)
            auth_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            auth_opener = urllib.request.build_opener(
                auth_handler,
                urllib.request.HTTPCookieProcessor(cj),
                urllib.request.HTTPSHandler(context=self._ssl_ctx),
            )

            with auth_opener.open(url_base, timeout=1.5) as resp:
                if resp.status in (200, 302):
                    return True
        except Exception:
            pass

        return False

    # ================================================================
    # Registro de Histórico em Arquivo Local
    # ================================================================

    @staticmethod
    def _write_history_log(ip: str, url: str, equipment: str, username: str, status: str, detail: str):
        """Registra o evento no arquivo de histórico local."""
        try:
            log_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "automation_history.log")

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"[{timestamp}] IP: {ip} | URL: {url} | Equipamento: {equipment} | User: {username} | Status: {status} | {detail}\n"

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
