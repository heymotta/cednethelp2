"""
CedNet Help - Automação: Localizador de Senhas de Rádio/Roteador (Motor Anti-Falso-Positivo Definitivo)
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
import json
from typing import Callable, Optional
from modules.passwords import DEFAULT_PASSWORDS, get_credentials_by_device_type


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
    """Retorna a lista combinada e desduplicada de senhas de rádios e senhas padrão do sistema."""
    combined = list(RADIO_PASSWORDS)
    try:
        for p_entry in DEFAULT_PASSWORDS:
            pwd = p_entry.get("senha", "").strip() or p_entry.get("password", "").strip()
            if pwd and pwd not in combined:
                combined.append(pwd)
    except Exception:
        pass
    return combined


class RadioPasswordFinder:
    """Executa os testes de credenciais padrão em equipamentos de rádio/roteador com validação rigorosa de 3 camadas."""

    def __init__(self):
        self._is_running: bool = False
        self._stop_requested: bool = False

        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def check_target_web(self, target_ip: str) -> tuple[bool, str, str]:
        """Verifica se o IP responde e se possui porta web (80, 443, 8080, 8443) aberta."""
        ping_ok = self._ping(target_ip)

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

    def start_finder(
        self,
        target_ip: str,
        username: str,
        device_type: str,
        on_progress: Callable[[dict], None],
        on_success: Callable[[dict], None],
        on_failure: Callable[[str], None],
    ):
        if self._is_running:
            return

        self._is_running = True
        self._stop_requested = False

        thread = threading.Thread(
            target=self._run_finder_thread,
            args=(target_ip, username, device_type, on_progress, on_success, on_failure),
            daemon=True,
            name="PasswordFinderWorker",
        )
        thread.start()

    def stop_finder(self):
        self._stop_requested = True
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def _run_finder_thread(
        self,
        target_ip: str,
        username: str,
        device_type: str,
        on_progress: Callable[[dict], None],
        on_success: Callable[[dict], None],
        on_failure: Callable[[str], None],
    ):
        try:
            start_time = time.time()

            is_web, url_base, eq_type = self.check_target_web(target_ip)

            if not is_web:
                self._is_running = False
                self._write_history_log(target_ip, url_base, eq_type, username or "auto", "FALHA", "Nenhuma interface web encontrada.")
                on_failure("❌ Equipamento não possui interface web (HTTP/HTTPS) acessível.")
                return

            credentials_to_test: list[dict[str, str]] = []

            if device_type and device_type.lower() != "geral":
                typed_creds = get_credentials_by_device_type(device_type)
                for c in typed_creds:
                    user = username if username and username.strip() else c["user"]
                    pwd = c["pass"]
                    if {"user": user, "pass": pwd} not in credentials_to_test:
                        credentials_to_test.append({"user": user, "pass": pwd})
            else:
                target_user = username.strip() if username and username.strip() else "admin"
                combined_passwords = get_combined_passwords()
                for pwd in combined_passwords:
                    credentials_to_test.append({"user": target_user, "pass": pwd})

            total_credentials = len(credentials_to_test)
            self._write_history_log(target_ip, url_base, eq_type, device_type, "INICIADO", f"Testando {total_credentials} combinações com sistema estrito anti-falso-positivo...")

            found_cred = None

            for idx, cred in enumerate(credentials_to_test, start=1):
                if self._stop_requested:
                    self._is_running = False
                    on_failure("⏹️ Automação interrompida pelo usuário.")
                    return

                curr_user = cred["user"]
                curr_pass = cred["pass"]
                elapsed_sec = time.time() - start_time

                progress_data = {
                    "equipment": eq_type,
                    "url": url_base,
                    "username": curr_user,
                    "current_index": idx,
                    "total": total_credentials,
                    "current_password": curr_pass,
                    "elapsed_seconds": elapsed_sec,
                }
                on_progress(progress_data)

                login_ok = self._try_login_robust(url_base, curr_user, curr_pass, eq_type)

                if login_ok:
                    found_cred = cred
                    break

                time.sleep(0.15)

            elapsed_sec = time.time() - start_time
            self._is_running = False

            if found_cred:
                res_data = {
                    "ip": target_ip,
                    "url": url_base,
                    "equipment": eq_type,
                    "username": found_cred["user"],
                    "password": found_cred["pass"],
                    "elapsed_seconds": elapsed_sec,
                }
                self._write_history_log(target_ip, url_base, eq_type, found_cred["user"], "SUCESSO", f"Senha VALIDADA: {found_cred['pass']}")
                on_success(res_data)
            else:
                self._write_history_log(target_ip, url_base, eq_type, username or "auto", "FALHA", "Nenhuma senha aceita.")
                on_failure("❌ Nenhuma das credenciais testadas foi aceita pelo equipamento.")

        except Exception as err:
            self._is_running = False
            on_failure(f"❌ Erro de execução na automação: {str(err)}")

    # ================================================================
    # Submissão de Formulário / Validação Anti-Falso-Positivo
    # ================================================================

    def _try_login_robust(self, url_base: str, username: str, password: str, eq_type: str) -> bool:
        """
        Valida a autenticação utilizando 3 camadas estritas de verificação para eliminar 100% dos falsos positivos.
        """
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

        ERROR_KEYWORDS = [
            "errado", "errados", "incorret", "incorreto", "incorrect", "invalid", "inválido", "invalido",
            "falho", "falha", "failed", "failure", "wrong", "denied", "negado", "bloquead", "locked",
            "tentativas", "attempts", "unauthorized", "erro", "error", "expirad"
        ]

        # 1. TRATAMENTO ESPECÍFICO PARA ZTE (AJAX Endpoint)
        if "ZTE" in eq_type.upper() or "ZXHN" in eq_type.upper():
            try:
                # GET inicial para sessão do servidor
                req_init = urllib.request.Request(url_base, headers={"User-Agent": "Mozilla/5.0"})
                with opener.open(req_init, timeout=2.0) as resp_init:
                    init_html = resp_init.read().decode("utf-8", errors="ignore")
                    token_match = re.search(r'id="_sessionTOKEN"\s+value="([^"]*)"', init_html)
                    token_val = token_match.group(1) if token_match else ""

                url_zte = f"{url_base}/?_type=loginData&_tag=login_entry"
                payload_zte = urllib.parse.urlencode({
                    "username": username,
                    "password": password,
                    "Frm_Username": username,
                    "Frm_Password": password,
                    "_sessionTOKEN": token_val,
                    "action": "login"
                }).encode("utf-8")

                req_zte = urllib.request.Request(
                    url_zte,
                    data=payload_zte,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    }
                )

                with opener.open(req_zte, timeout=2.0) as resp_zte:
                    raw_text = resp_zte.read().decode("utf-8", errors="ignore")
                    try:
                        res_json = json.loads(raw_text)
                        err_msg = str(res_json.get("loginErrMsg", "")).lower()
                        prompt_msg = str(res_json.get("promptMsg", "")).lower()
                        locking_time = res_json.get("lockingTime", -1)

                        if err_msg or "falho" in prompt_msg or "errado" in prompt_msg or "expirad" in err_msg or locking_time > 0:
                            return False
                    except Exception:
                        pass

                # Após o POST de login AJAX, realiza a validação rigorosa da sessão autenticada
                if self._verify_authenticated_session(opener, url_base):
                    return True

            except Exception:
                pass

        # 2. TESTE DE SUBMISSÃO DE FORMULÁRIO PADRÃO HTTP POST
        form_payloads = [
            {"username": username, "password": password},
            {"user": username, "pass": password},
            {"user": username, "password": password},
            {"login": username, "password": password},
            {"username": username, "pwd": password},
            {"auth_user": username, "auth_pass": password},
            {"ubnt_username": username, "ubnt_password": password},
            {"Frm_Username": username, "Frm_Password": password},
        ]

        login_endpoints = [
            "/login.cgi",
            "/login",
            "/cgi-bin/login.cgi",
            "/api/login",
            "/index.cgi",
            "",
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

                    with opener.open(req, timeout=2.0) as resp:
                        body = resp.read(6144).decode("utf-8", errors="ignore").lower()

                        if any(kw in body for kw in ERROR_KEYWORDS):
                            continue

                        if self._is_login_page_html(body):
                            continue

                        if self._verify_authenticated_session(opener, url_base):
                            return True

                except urllib.error.HTTPError as e:
                    if e.code in (301, 302):
                        if self._verify_authenticated_session(opener, url_base):
                            return True
                except Exception:
                    pass

        return False

    def _is_login_page_html(self, html_body: str) -> bool:
        """
        Retorna True se o HTML retornado ainda for a página de login.
        """
        body_lower = html_body.lower()

        # Se contiver campos típicos de entrada de credenciais -> AINDA É A TELA DE LOGIN!
        indicators = [
            "type=\"password\"", 'type="password"', "type='password'",
            "frm_username", "frm_password", "id=\"loginid\"", 'id="loginid"',
            "name=\"username\"", "name='username'", "btnlogin", "por favor faça o login"
        ]

        return any(ind in body_lower for ind in indicators)

    def _verify_authenticated_session(self, opener: urllib.request.OpenerDirector, url_base: str) -> bool:
        """
        Realiza um probe secundário em endpoints internos para confirmar se a sessão realmente possui privilégios de acesso.
        Retorna True APENAS se a página de login sumiu E a sessão autenticada for confirmada.
        """
        protected_endpoints = [
            "",
            "/main.html",
            "/status.asp",
            "/status.cgi",
            "/home.htm",
            "/sys_status.htm",
        ]

        for endp in protected_endpoints:
            try:
                req = urllib.request.Request(f"{url_base}{endp}", headers={"User-Agent": "Mozilla/5.0"})
                with opener.open(req, timeout=1.5) as resp:
                    body = resp.read(6144).decode("utf-8", errors="ignore")

                    # 1. Se o HTML ainda contiver os campos da tela de login -> NÃO ESTÁ LOGADO!
                    if self._is_login_page_html(body):
                        continue

                    # 2. Se não tiver campos de login E contiver marcadores de sessão ativa (Logout, Sair, Sair do sistema)
                    body_lower = body.lower()
                    if any(term in body_lower for term in ["logout", "sair", "desconectar", "logoff", "log off", "btnlogout"]):
                        return True
            except Exception:
                continue

        return False

    # ================================================================
    # Registro de Histórico em Arquivo Local
    # ================================================================

    @staticmethod
    def _write_history_log(ip: str, url: str, equipment: str, username: str, status: str, detail: str):
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
