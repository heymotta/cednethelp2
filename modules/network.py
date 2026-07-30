"""
CedNet Help - Módulo de Rede
Coleta informações de rede: IPv4, Gateway, Máscara, DNS, Interface, Status.

Utiliza múltiplos métodos de detecção em cadeia (fallback):
  1. route print  — mais confiável no Windows
  2. netsh        — resultado detalhado por interface
  3. ipconfig     — método clássico
  4. psutil       — via tabela de rotas do sistema
  5. wmic         — legacy, ainda presente em muitos Windows

Se um método falha, tenta automaticamente o próximo.
"""

import psutil
import socket
import subprocess
import re
import ipaddress
from typing import Optional


# Flag para criação de processo sem janela (Windows)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


class GatewayDetectionLog:
    """Acumula logs de diagnóstico durante a detecção do gateway."""

    def __init__(self):
        self.entries: list[str] = []
        self.gateway: str = ""
        self.method: str = ""
        self.interface: str = ""
        self.ipv4: str = ""

    def log(self, message: str):
        """Adiciona uma entrada ao log."""
        self.entries.append(message)

    def success(self, method: str, gateway: str, interface: str = "", ipv4: str = ""):
        """Registra uma detecção bem-sucedida."""
        self.method = method
        self.gateway = gateway
        self.interface = interface
        self.ipv4 = ipv4
        self.log(f"✅ Método: {method}")
        self.log(f"   Gateway: {gateway}")
        if interface:
            self.log(f"   Interface: {interface}")
        if ipv4:
            self.log(f"   IPv4: {ipv4}")
        self.log("   Gateway encontrado com sucesso.")

    def fail(self, method: str, reason: str):
        """Registra uma falha em um método."""
        self.log(f"❌ Método {method}: Falhou")
        self.log(f"   Motivo: {reason}")
        self.log("   Tentando próximo método...")

    def get_full_log(self) -> str:
        """Retorna o log completo como texto."""
        return "\n".join(self.entries)


class NetworkInfo:
    """Classe responsável por coletar informações da interface de rede."""

    def __init__(self):
        self._cached_interface: Optional[str] = None
        self.last_detection_log: Optional[GatewayDetectionLog] = None

    # ================================================================
    # Método Público Principal
    # ================================================================

    def get_all_info(self) -> dict:
        """
        Retorna um dicionário completo com todas as informações de rede.

        Returns:
            dict com chaves: ipv4, gateway, mask, dns, interface, status, speed
        """
        return {
            "ipv4": self._get_ipv4(),
            "gateway": self.detect_gateway_with_fallback(),
            "mask": self._get_subnet_mask(),
            "dns": self._get_dns(),
            "interface": self._get_interface_name(),
            "status": self._get_connection_status(),
            "speed": self._get_speed(),
        }

    # ================================================================
    # Detecção de Interface Ativa
    # ================================================================

    def _get_active_interface(self) -> Optional[str]:
        """
        Detecta a interface de rede ativa (não loopback, com IPv4).
        Prioriza interfaces UP com endereço IPv4 válido.
        Ignora interfaces de VPN/virtuais como Tailscale.
        """
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()

            # Nomes de interfaces virtuais/VPN comuns a ignorar
            virtual_prefixes = (
                "tailscale", "zerotier", "vmware", "virtualbox",
                "vethernet", "docker", "wsl", "loopback", "lo",
                "isatap", "teredo",
            )

            # Primeira passagem: interface física UP com IPv4 válido
            for iface, stat in stats.items():
                if iface.lower().startswith(virtual_prefixes):
                    continue
                if stat.isup and iface in addrs:
                    for addr in addrs[iface]:
                        if (addr.family == socket.AF_INET
                                and not addr.address.startswith("127.")
                                and not addr.address.startswith("100.")):  # Tailscale CGNAT
                            self._cached_interface = iface
                            return iface

            # Segunda passagem: qualquer interface UP não-virtual
            for iface, stat in stats.items():
                if not iface.lower().startswith(virtual_prefixes) and stat.isup:
                    self._cached_interface = iface
                    return iface

        except Exception:
            pass

        return self._cached_interface

    # ================================================================
    # Detecção de Gateway com Fallback em Cadeia
    # ================================================================

    def detect_gateway_with_fallback(self) -> str:
        """
        Detecta o gateway padrão utilizando múltiplos métodos em sequência.
        Ordem de prioridade:
          1. route print     — lê diretamente a tabela de rotas
          2. netsh            — informações detalhadas por interface
          3. ipconfig /all    — método clássico
          4. psutil (socket)  — heurística via conexão UDP
          5. wmic             — legado Windows

        Returns:
            Endereço IPv4 do gateway ou "Não disponível".
        """
        log = GatewayDetectionLog()
        self.last_detection_log = log

        # Lista de métodos a tentar, em ordem de confiabilidade
        methods = [
            ("route print", self._gateway_via_route_print),
            ("netsh", self._gateway_via_netsh),
            ("ipconfig", self._gateway_via_ipconfig),
            ("psutil/socket", self._gateway_via_psutil),
            ("wmic", self._gateway_via_wmic),
        ]

        for method_name, method_func in methods:
            try:
                gateway = method_func()
                if gateway and self._is_valid_ipv4(gateway):
                    # Sucesso — registra no log e retorna
                    iface = self._get_interface_name()
                    ipv4 = self._get_ipv4()
                    log.success(method_name, gateway, iface, ipv4)
                    return gateway
                else:
                    log.fail(method_name, "Gateway não retornado ou inválido.")
            except Exception as e:
                log.fail(method_name, str(e))

        log.log("\n⚠️ Nenhum método conseguiu detectar o gateway.")
        return "Não disponível"

    # ---- Método 1: route print ----

    def _gateway_via_route_print(self) -> str:
        """
        Obtém o gateway padrão via 'route print 0.0.0.0'.
        Este é o método mais confiável no Windows pois lê a tabela de rotas diretamente.
        Busca a rota padrão (destino 0.0.0.0) e extrai o gateway.
        """
        output = subprocess.check_output(
            "route print 0.0.0.0",
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=5,
        )

        # Formato: "0.0.0.0   0.0.0.0   192.168.1.1   192.168.1.8   25"
        # O gateway é o terceiro campo de IPv4 na linha com destino 0.0.0.0
        for line in output.splitlines():
            line = line.strip()
            if not line or not line.startswith("0.0.0.0"):
                continue

            # Extrai todos os IPs da linha
            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", line)
            # ips[0] = destino (0.0.0.0), ips[1] = máscara (0.0.0.0),
            # ips[2] = gateway, ips[3] = IP local
            if len(ips) >= 3:
                candidate = ips[2]
                # Ignora se o gateway é 0.0.0.0 (rota local)
                if candidate != "0.0.0.0":
                    return candidate

        return ""

    # ---- Método 2: netsh ----

    def _gateway_via_netsh(self) -> str:
        """
        Obtém o gateway via 'netsh interface ip show config'.
        Funciona bem em PT-BR e EN-US do Windows.
        """
        output = subprocess.check_output(
            "netsh interface ip show config",
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=5,
        )

        # Padrões para "Gateway Padrão" (PT-BR) e "Default Gateway" (EN-US)
        patterns = [
            r"Gateway\s+Padr[ãa�]o[:\s]+(\d+\.\d+\.\d+\.\d+)",
            r"Default\s+Gateway[:\s]+(\d+\.\d+\.\d+\.\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    # ---- Método 3: ipconfig ----

    def _gateway_via_ipconfig(self) -> str:
        """
        Obtém o gateway via 'ipconfig /all'.
        Nota: usa /all para obter informações mais detalhadas.
        """
        output = subprocess.check_output(
            "ipconfig /all",
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=5,
        )

        # Busca gateway IPv4 (padrão PT-BR e EN-US)
        patterns = [
            r"Gateway\s+Padr[ãa�]o[\s.]*:\s*(\d+\.\d+\.\d+\.\d+)",
            r"Default\s+Gateway[\s.]*:\s*(\d+\.\d+\.\d+\.\d+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for gw in matches:
                # Ignora endereços inválidos
                if gw != "0.0.0.0" and self._is_valid_ipv4(gw):
                    return gw

        return ""

    # ---- Método 4: psutil / socket ----

    def _gateway_via_psutil(self) -> str:
        """
        Heurística: conecta um socket UDP a 8.8.8.8 para descobrir o IP local,
        depois tenta inferir o gateway como .1 da sub-rede.
        Menos confiável, mas funciona como último recurso.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]

            # Infere o gateway como primeiro IP da sub-rede
            parts = local_ip.rsplit(".", 1)
            if len(parts) == 2:
                candidate = f"{parts[0]}.1"
                return candidate
        except Exception:
            pass

        return ""

    # ---- Método 5: wmic (legado) ----

    def _gateway_via_wmic(self) -> str:
        """
        Obtém o gateway via WMIC (Windows Management Instrumentation).
        Disponível na maioria dos Windows, mas sendo descontinuado.
        """
        output = subprocess.check_output(
            "wmic nicconfig where IPEnabled=TRUE get DefaultIPGateway /format:list",
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=5,
        )

        # Formato: DefaultIPGateway={"192.168.1.1"}
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
        if match:
            return match.group(1)

        return ""

    # ================================================================
    # Validação de IP
    # ================================================================

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        """Valida se uma string é um endereço IPv4 válido."""
        try:
            addr = ipaddress.IPv4Address(ip)
            # Rejeita endereços especiais
            return not (addr.is_loopback or addr.is_unspecified)
        except (ipaddress.AddressValueError, ValueError):
            return False

    # ================================================================
    # Coleta de Informações Individuais
    # ================================================================

    def _get_ipv4(self) -> str:
        """Obtém o endereço IPv4 da interface ativa."""
        try:
            iface = self._get_active_interface()
            if iface:
                addrs = psutil.net_if_addrs()
                if iface in addrs:
                    for addr in addrs[iface]:
                        if addr.family == socket.AF_INET:
                            return addr.address

            # Fallback: socket UDP para descobrir IP local
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]

        except Exception:
            return "Não disponível"

    def _get_gateway(self) -> str:
        """Wrapper simples — usa o método com fallback."""
        return self.detect_gateway_with_fallback()

    def _get_subnet_mask(self) -> str:
        """Obtém a máscara de sub-rede da interface ativa via psutil."""
        try:
            iface = self._get_active_interface()
            if iface:
                addrs = psutil.net_if_addrs()
                if iface in addrs:
                    for addr in addrs[iface]:
                        if addr.family == socket.AF_INET:
                            return addr.netmask or "Não disponível"
        except Exception:
            pass
        return "Não disponível"

    def _get_dns(self) -> str:
        """
        Obtém os servidores DNS configurados via ipconfig /all.
        Retorna até 2 endereços DNS separados por vírgula.
        """
        try:
            output = subprocess.check_output(
                "ipconfig /all",
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=5,
            )

            # Busca servidores DNS (PT-BR e EN-US)
            patterns = [
                r"(?:Servidores\s+DNS|DNS\s+Servers)[\s.]*:\s*(\d+\.\d+\.\d+\.\d+)",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, output, re.IGNORECASE)
                if matches:
                    unique_dns = list(dict.fromkeys(matches))
                    return ", ".join(unique_dns[:2])

        except (subprocess.SubprocessError, OSError):
            pass

        return "Não disponível"

    def _get_interface_name(self) -> str:
        """Retorna o nome da interface de rede ativa."""
        try:
            iface = self._get_active_interface()
            return iface if iface else "Não detectada"
        except Exception:
            return "Não detectada"

    def _get_connection_status(self) -> dict:
        """
        Verifica o status de conexão do cabo de rede.

        Returns:
            dict com: connected (bool), label (str), emoji (str)
        """
        try:
            iface = self._get_active_interface()
            if iface:
                stats = psutil.net_if_stats()
                if iface in stats:
                    is_up = stats[iface].isup
                    return {
                        "connected": is_up,
                        "label": "Cabo Conectado" if is_up else "Cabo Desconectado",
                        "emoji": "🟢" if is_up else "🔴",
                    }
        except Exception:
            pass

        return {
            "connected": False,
            "label": "Status Desconhecido",
            "emoji": "⚪",
        }

    def _get_speed(self) -> str:
        """Retorna a velocidade da interface de rede em Mbps."""
        try:
            iface = self._get_active_interface()
            if iface:
                stats = psutil.net_if_stats()
                if iface in stats:
                    speed = stats[iface].speed
                    if speed > 0:
                        return f"{speed} Mbps"
        except Exception:
            pass
        return "N/A"
