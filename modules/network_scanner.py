"""
CedNet Help - Módulo Scanner de Rede (Avançado)
Descoberta rápida e inteligente de dispositivos na sub-rede local.

Funcionalidades Avançadas:
  - Detecção de portas web acessíveis (80, 443, 8080, 8443)
  - Inspeção de cabeçalho HTTP Server e tag <title> HTML
  - Identificação inteligente de tipo (Roteador, ONU, Câmera, Impressora, Computador)
  - Resolução de fabricante por OUI estrita + inspeção de banner HTTP (sem falsos positivos)
  - Obtenção nativa de MAC Address via Windows SendARP
  - Varredura paralela multithreaded (64 a 128 workers)
"""

import ctypes
import struct
import socket
import subprocess
import ipaddress
import time
import re
import html
import urllib.request
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
from modules.network_manager import network_manager


# ================================================================
# Tabela Estrita de Fabricantes por OUI (MAC Prefix)
# Nota: Apenas OUIs oficiais e verificados. Se incerto, retorna "Desconhecido".
# ================================================================
MAC_OUI_DATABASE: dict[str, str] = {
    # ZTE
    "00:15:EB": "ZTE",
    "10:5B:AD": "ZTE",
    "D0:5B:A8": "ZTE",
    "70:9F:2D": "ZTE",
    "CC:7B:35": "ZTE",

    # Intelbras
    "00:1E:58": "Intelbras",
    "1C:B5:6C": "Intelbras",
    "F4:CA:E5": "Intelbras",

    # TP-Link
    "50:C7:BF": "TP-Link",
    "E8:48:B8": "TP-Link",
    "98:DA:C4": "TP-Link",
    "00:31:92": "TP-Link",
    "C0:25:E9": "TP-Link",
    "18:A6:F7": "TP-Link",
    "A0:F3:C1": "TP-Link",

    # Huawei
    "00:E0:FC": "Huawei",
    "04:25:C4": "Huawei",
    "20:F4:1B": "Huawei",
    "70:7B:E8": "Huawei",
    "CC:CC:81": "Huawei",
    "48:46:FB": "Huawei",

    # Mikrotik
    "6C:3B:6B": "Mikrotik",
    "48:8E:42": "Mikrotik",
    "B8:69:F4": "Mikrotik",
    "D4:CA:6D": "Mikrotik",
    "E8:94:F6": "Mikrotik",
    "00:0C:42": "Mikrotik",

    # FiberHome
    "00:25:9E": "FiberHome",
    "04:B2:95": "FiberHome",
    "80:89:17": "FiberHome",
    "78:6B:4A": "FiberHome",

    # Ubiquiti
    "00:15:6D": "Ubiquiti",
    "04:18:D6": "Ubiquiti",
    "24:A4:3C": "Ubiquiti",
    "78:8A:20": "Ubiquiti",
    "B4:FB:E4": "Ubiquiti",
    "F0:9F:C2": "Ubiquiti",

    # Cisco
    "00:0F:66": "Cisco",
    "00:1A:A1": "Cisco",
    "00:1D:A2": "Cisco",

    # D-Link
    "00:18:01": "D-Link",
    "14:D6:4D": "D-Link",

    # Hikvision / Câmeras IP
    "44:47:CC": "Hikvision",
    "C0:56:E3": "Hikvision",

    # Multilaser / Mercusys / Tenda
    "00:22:93": "Mercusys",
    "70:4F:57": "Mercusys",
    "00:B0:0C": "Tenda",
    "50:2B:73": "Tenda",

    # Hardware PCs / Servidores
    "00:D8:61": "MSI (Micro-Star)",
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "08:00:27": "VirtualBox",
    "00:15:5D": "Microsoft",
    "00:1A:A0": "Dell",
    "18:66:DA": "Dell",
    "B0:83:FE": "Dell",
    "00:1E:0B": "HP",
    "3C:D9:2B": "HP",
    "00:03:93": "Apple",
    "3C:07:54": "Apple",
    "A4:5E:60": "Apple",
    "00:12:FB": "Samsung",
    "50:85:69": "Samsung",
    "00:1B:21": "Intel",
    "3C:97:0E": "Intel",
    "00:E0:4C": "Realtek",
}


def lookup_vendor_by_oui(mac: str) -> str:
    """
    Identifica o fabricante via OUI estrito.
    Se não houver correspondência exata de confiança, retorna 'Desconhecido'.
    """
    if not mac or mac == "—" or len(mac) < 8:
        return "Desconhecido"

    clean_mac = mac.upper().replace("-", ":")
    prefix = clean_mac[:8]

    return MAC_OUI_DATABASE.get(prefix, "Desconhecido")


# ================================================================
# Obtenção Nativa de MAC Address (Windows SendARP)
# ================================================================

def get_mac_address_sendarp(ip_str: str) -> str:
    """Obtém o endereço MAC nativamente via Windows SendARP."""
    try:
        inetaddr = struct.unpack("<I", socket.inet_aton(ip_str))[0]
        macaddr = (ctypes.c_byte * 6)()
        maclen = ctypes.c_ulong(6)

        result = ctypes.windll.iphlpapi.SendARP(
            inetaddr, 0, ctypes.byref(macaddr), ctypes.byref(maclen)
        )

        if result == 0:
            bytes_mac = bytes(macaddr)
            return ":".join(f"{b:02X}" for b in bytes_mac)
    except Exception:
        pass
    return "—"


# ================================================================
# Ping e Latência
# ================================================================

def ping_host(ip_str: str, timeout_ms: int = 350) -> tuple[bool, int]:
    """Envia um ping rápido via comando nativo do Windows."""
    try:
        output = subprocess.check_output(
            f"ping -n 1 -w {timeout_ms} {ip_str}",
            encoding="cp850",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=1.2,
        )

        match = re.search(r"(?:tempo|time)[=<](\d+)\s*ms", output, re.IGNORECASE)
        if match:
            return True, int(match.group(1))

        if "TTL=" in output or "ttl=" in output:
            return True, 1

    except (subprocess.SubprocessError, OSError):
        pass

    return False, 0


def resolve_hostname(ip_str: str) -> str:
    """Resolve o hostname reverso via DNS."""
    try:
        socket.setdefaulttimeout(0.35)
        hostname, _, _ = socket.gethostbyaddr(ip_str)
        return hostname if hostname else "—"
    except Exception:
        return "—"


# ================================================================
# Inspeção de Portas Web & Banner HTTP/HTTPS
# ================================================================

def inspect_web_interface(ip_str: str) -> dict:
    """
    Testa portas web (80, 443, 8080, 8443) e inspeciona o título HTML e Server header.

    Returns:
        Dict com: has_web (bool), web_url (str), web_port (int),
                  web_protocol (str), http_title (str), http_server (str)
    """
    result = {
        "has_web": False,
        "web_url": "",
        "web_port": 0,
        "web_protocol": "http",
        "http_title": "",
        "http_server": "",
    }

    # Contexto SSL para ignorar certificados autoassinados comuns em roteadores/ONUs
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # Ordem de teste: 80, 443, 8080, 8443
    web_ports = [
        ("http", 80),
        ("https", 443),
        ("http", 8080),
        ("https", 8443),
    ]

    for protocol, port in web_ports:
        try:
            # Testa abertura rápida de socket TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                if s.connect_ex((ip_str, port)) != 0:
                    continue

            # Se a porta está aberta, marca como web disponível
            url = f"{protocol}://{ip_str}" if port in (80, 443) else f"{protocol}://{ip_str}:{port}"
            result["has_web"] = True
            result["web_url"] = url
            result["web_port"] = port
            result["web_protocol"] = protocol

            # Tenta ler o título HTML e cabeçalho Server
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )

            with urllib.request.urlopen(req, timeout=1.0, context=ssl_ctx) as resp:
                result["http_server"] = resp.headers.get("Server", "").strip()
                body = resp.read(3072).decode("utf-8", errors="ignore")

                # Extrai a tag <title>
                title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
                if title_match:
                    raw_title = title_match.group(1).strip()
                    # Decodifica entidades HTML como &#70;&#54;&#55;&#48;&#76; -> F670L
                    clean_title = html.unescape(raw_title)
                    # Limpa quebras de linha
                    clean_title = " ".join(clean_title.split())
                    result["http_title"] = clean_title[:60]

            # Se encontrou porta e title/server, interrompe a busca de portas
            if result["http_title"] or result["http_server"]:
                break

        except Exception:
            # Mesmo se falhar o GET (ex: auth HTTP 401), se a porta abriu, é Web
            pass

    return result


# ================================================================
# Classificador Inteligente de Equipamento
# ================================================================

def classify_device(
    ip_str: str,
    mac: str,
    hostname: str,
    oui_vendor: str,
    web_info: dict,
) -> tuple[str, str, str]:
    """
    Classifica o tipo do equipamento e fabricante com base em múltiplas fontes:
    HTTP Title, HTTP Server header, Hostname, MAC OUI e IP (gateway).

    Returns:
        Tupla (vendor: str, device_type: str, icon: str)
    """
    title = web_info.get("http_title", "").upper()
    server = web_info.get("http_server", "").upper()
    host = hostname.upper()
    oui = oui_vendor.upper()

    combined = f"{title} {server} {host} {oui}"

    vendor = oui_vendor
    device_type = "Dispositivo de Rede"
    icon = "🌐"

    # ---- 1. Regras para ZTE ----
    if "ZTE" in combined or "ZXHN" in combined or "F670" in combined or "F660" in combined or "F609" in combined:
        vendor = "ZTE"
        model = ""
        model_match = re.search(r"(F670\w*|F660\w*|F609\w*|ZXHN\s*\w*)", combined)
        if model_match:
            model = f" ({model_match.group(1)})"
        device_type = f"Roteador / ONU ZTE{model}"
        icon = "📡"

    # ---- 2. Regras para MikroTik ----
    elif "MIKROTIK" in combined or "ROUTEROS" in combined:
        vendor = "MikroTik"
        device_type = "Roteador MikroTik (RouterOS)"
        icon = "📡"

    # ---- 3. Regras para Huawei ----
    elif "HUAWEI" in combined or "HG8145" in combined or "HG8245" in combined or "EG8145" in combined:
        vendor = "Huawei"
        model_match = re.search(r"(HG8\d+\w*|EG8\d+\w*)", combined)
        model = f" ({model_match.group(1)})" if model_match else ""
        device_type = f"ONU / Roteador Huawei{model}"
        icon = "🔌"

    # ---- 4. Regras para FiberHome ----
    elif "FIBERHOME" in combined or "HG6245" in combined or "AN5506" in combined:
        vendor = "FiberHome"
        device_type = "ONU FiberHome"
        icon = "🔌"

    # ---- 5. Regras para Intelbras ----
    elif "INTELBRAS" in combined or "WI-FORCE" in combined or "ACTION" in combined:
        vendor = "Intelbras"
        device_type = "Roteador / Equip. Intelbras"
        icon = "📡"

    # ---- 6. Regras para TP-Link ----
    elif "TP-LINK" in combined or "TPLINK" in combined or "ARCHER" in combined:
        vendor = "TP-Link"
        device_type = "Roteador TP-Link"
        icon = "📡"

    # ---- 7. Regras para Ubiquiti ----
    elif "UBIQUITI" in combined or "UNIFI" in combined or "AIRMAX" in combined:
        vendor = "Ubiquiti"
        device_type = "Equipamento Ubiquiti"
        icon = "📡"

    # ---- 8. Câmeras IP / DVR / NVR ----
    elif "HIKVISION" in combined or "DAHUA" in combined or "IP CAMERA" in combined or "DVR" in combined or "NVR" in combined:
        if "HIKVISION" in combined:
            vendor = "Hikvision"
        elif "DAHUA" in combined:
            vendor = "Dahua"
        device_type = "Câmera IP / DVR"
        icon = "📹"

    # ---- 9. Impressoras ----
    elif "PRINTER" in combined or "LASERJET" in combined or "EPSON" in combined or "CANON" in combined or "BROTHER" in combined:
        device_type = "Impressora de Rede"
        icon = "🖨️"

    # ---- 10. Computadores (Windows / Linux / Apple) ----
    elif "DESKTOP" in host or "LAPTOP" in host or "WIN" in host or "PC" in host or "MSI" in oui or "DELL" in oui or "HP" in oui or "LENOVO" in oui:
        device_type = "Computador / PC"
        icon = "💻"

    # ---- Fallback: Gateway geralmente é Roteador ----
    else:
        state = network_manager.get_state()
        if ip_str == state.get("gateway"):
            device_type = "Roteador Principal"
            icon = "📡"

    # Se o fabricante continua desconhecido mas o título deu uma pista
    if vendor == "Desconhecido" and web_info.get("http_title"):
        title_text = web_info["http_title"]
        vendor = title_text[:20]

    return vendor, device_type, icon


# ================================================================
# Classe Principal NetworkScanner
# ================================================================

class NetworkScanner:
    """
    Gerenciador do Scanner de Rede Avançado.
    """

    def __init__(self):
        self._is_scanning: bool = False
        self._cancel_requested: bool = False
        self._executor: Optional[ThreadPoolExecutor] = None

    @staticmethod
    def detect_default_subnet() -> str:
        """Calcula a faixa da sub-rede atual com base no NetworkManager."""
        try:
            state = network_manager.get_state()
            ipv4 = state.get("ipv4", "")
            mask = state.get("mask", "")

            if ipv4 and mask and ipv4 != "Não disponível" and mask != "Não disponível":
                network = ipaddress.IPv4Network(f"{ipv4}/{mask}", strict=False)
                return str(network)
        except Exception:
            pass

        return "192.168.1.0/24"

    @staticmethod
    def parse_ip_targets(target_str: str) -> list[str]:
        """Converte CIDR ou faixa em lista de IPs."""
        target_str = target_str.strip()

        if "/" in target_str:
            try:
                network = ipaddress.IPv4Network(target_str, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ValueError:
                pass

        if "-" in target_str:
            try:
                parts = target_str.split("-")
                start_ip = parts[0].strip()
                end_suffix = parts[1].strip()

                start_obj = ipaddress.IPv4Address(start_ip)
                if "." in end_suffix:
                    end_obj = ipaddress.IPv4Address(end_suffix)
                else:
                    base_parts = start_ip.rsplit(".", 1)[0]
                    end_obj = ipaddress.IPv4Address(f"{base_parts}.{end_suffix}")

                start_int = int(start_obj)
                end_int = int(end_obj)

                if start_int <= end_int and (end_int - start_int) <= 1024:
                    return [str(ipaddress.IPv4Address(i)) for i in range(start_int, end_int + 1)]
            except Exception:
                pass

        try:
            ipaddress.IPv4Address(target_str)
            return [target_str]
        except ValueError:
            pass

        return []

    def scan_single_device(self, ip_str: str) -> Optional[dict]:
        """
        Varre um único endereço IP de forma completa:
          1. MAC via SendARP
          2. Ping e Latência
          3. Resolução Hostname
          4. Teste de Portas Web & Título HTML
          5. Classificação Inteligente do Equipamento e Fabricante
        """
        if self._cancel_requested:
            return None

        # 1. MAC via SendARP
        mac = get_mac_address_sendarp(ip_str)

        # 2. Ping
        is_online, ping_ms = ping_host(ip_str, timeout_ms=300)

        # Se não respondeu ping E não respondeu ARP, considera offline
        if not is_online and mac == "—":
            return None

        if not is_online and mac != "—":
            is_online = True
            ping_ms = 1

        # 3. Hostname
        hostname = resolve_hostname(ip_str)

        # 4. Fabricante via OUI
        oui_vendor = lookup_vendor_by_oui(mac)

        # 5. Inspeção Web (Portas 80, 443, 8080, 8443 e Título HTML)
        web_info = inspect_web_interface(ip_str)

        # 6. Classificação Inteligente
        vendor, device_type, icon = classify_device(
            ip_str, mac, hostname, oui_vendor, web_info
        )

        return {
            "ip": ip_str,
            "mac": mac,
            "hostname": hostname,
            "vendor": vendor,
            "device_type": device_type,
            "icon": icon,
            "has_web": web_info["has_web"],
            "web_url": web_info["web_url"],
            "web_port": web_info["web_port"],
            "web_protocol": web_info["web_protocol"],
            "http_title": web_info["http_title"],
            "http_server": web_info["http_server"],
            "ping_ms": ping_ms,
            "status": "Online" if is_online else "Offline",
            "is_online": is_online,
        }

    def start_scan(
        self,
        target_range: str,
        on_device_found: Callable[[dict], None],
        on_progress: Callable[[int, int, float], None],
        on_complete: Callable[[list[dict]], None],
        max_workers: int = 64,
    ):
        """Inicia a varredura em background thread."""
        if self._is_scanning:
            return

        self._is_scanning = True
        self._cancel_requested = False

        targets = self.parse_ip_targets(target_range)
        if not targets:
            on_complete([])
            self._is_scanning = False
            return

        thread = threading.Thread(
            target=self._run_scan_thread,
            args=(targets, on_device_found, on_progress, on_complete, max_workers),
            daemon=True,
            name="NetworkScannerWorker",
        )
        thread.start()

    def stop_scan(self):
        """Solicita a interrupção imediata da varredura."""
        self._cancel_requested = True
        self._is_scanning = False

    def is_scanning(self) -> bool:
        """Retorna True se houver varredura em andamento."""
        return self._is_scanning

    def _run_scan_thread(
        self,
        targets: list[str],
        on_device_found: Callable[[dict], None],
        on_progress: Callable[[int, int, float], None],
        on_complete: Callable[[list[dict]], None],
        max_workers: int,
    ):
        """Executa a varredura paralela usando ThreadPoolExecutor."""
        start_time = time.time()
        total_targets = len(targets)
        scanned_count = 0
        discovered_devices: list[dict] = []

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Scanner")

        try:
            future_to_ip = {
                self._executor.submit(self.scan_single_device, ip): ip
                for ip in targets
            }

            for future in as_completed(future_to_ip):
                if self._cancel_requested:
                    break

                scanned_count += 1
                elapsed = time.time() - start_time

                try:
                    device = future.result()
                    if device:
                        discovered_devices.append(device)
                        on_device_found(device)
                except Exception:
                    pass

                on_progress(scanned_count, total_targets, elapsed)

        finally:
            self._executor.shutdown(wait=False)
            self._executor = None
            self._is_scanning = False
            on_complete(discovered_devices)
