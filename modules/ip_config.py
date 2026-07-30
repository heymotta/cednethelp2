"""
CedNet Help - Módulo de Configuração de IP
Permite visualizar, alterar (IP estático) e restaurar (DHCP) as
configurações IPv4 de interfaces de rede no Windows.

Utiliza netsh para aplicar configurações — requer privilégios de administrador.
"""

import ctypes
import ipaddress
import subprocess
import re
import psutil
import socket
from typing import Optional


# Flag para ocultar janela do processo
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


# ================================================================
# Verificação de Privilégios
# ================================================================

def is_admin() -> bool:
    """Verifica se o programa está sendo executado como Administrador."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ================================================================
# Listagem de Interfaces
# ================================================================

def get_all_interfaces() -> list[dict]:
    """
    Retorna uma lista de todas as interfaces de rede disponíveis.

    Returns:
        Lista de dicts com: name, is_up, has_ipv4, type_hint
    """
    interfaces = []
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for iface_name, stat in stats.items():
            # Ignora loopback
            if iface_name.lower().startswith(("loopback", "lo")):
                continue

            # Verifica se tem IPv4
            has_ipv4 = False
            ipv4_addr = ""
            if iface_name in addrs:
                for addr in addrs[iface_name]:
                    if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                        has_ipv4 = True
                        ipv4_addr = addr.address
                        break

            # Tenta inferir o tipo de interface pelo nome
            type_hint = _guess_interface_type(iface_name)

            interfaces.append({
                "name": iface_name,
                "is_up": stat.isup,
                "has_ipv4": has_ipv4,
                "ipv4": ipv4_addr,
                "speed": stat.speed,
                "type_hint": type_hint,
            })

    except Exception:
        pass

    # Ordena: interfaces ativas primeiro, depois por nome
    interfaces.sort(key=lambda x: (not x["is_up"], x["name"]))
    return interfaces


def _guess_interface_type(name: str) -> str:
    """Infere o tipo da interface pelo nome."""
    name_lower = name.lower()
    if "wi-fi" in name_lower or "wifi" in name_lower or "wireless" in name_lower:
        return "Wi-Fi"
    elif "ethernet" in name_lower or "eth" in name_lower:
        return "Ethernet"
    elif "usb" in name_lower:
        return "USB"
    elif "tailscale" in name_lower or "zerotier" in name_lower:
        return "VPN"
    elif "vmware" in name_lower or "virtualbox" in name_lower or "vethernet" in name_lower:
        return "Virtual"
    elif "bluetooth" in name_lower:
        return "Bluetooth"
    return "Outro"


def get_default_interface_name() -> str:
    """Retorna o nome da interface ativa padrão (com IPv4)."""
    interfaces = get_all_interfaces()
    # Prioriza: ativa + com IPv4 + não-virtual
    virtual_types = ("VPN", "Virtual", "Bluetooth")
    for iface in interfaces:
        if iface["is_up"] and iface["has_ipv4"] and iface["type_hint"] not in virtual_types:
            return iface["name"]
    # Fallback: qualquer ativa
    for iface in interfaces:
        if iface["is_up"]:
            return iface["name"]
    return interfaces[0]["name"] if interfaces else ""


# ================================================================
# Informações da Interface Selecionada
# ================================================================

def get_interface_config(iface_name: str) -> dict:
    """
    Obtém a configuração completa de uma interface via netsh.

    Args:
        iface_name: Nome da interface (ex: "Ethernet").

    Returns:
        Dict com: ipv4, mask, gateway, dns_primary, dns_secondary,
                  is_dhcp, status, raw_output
    """
    config = {
        "ipv4": "",
        "mask": "",
        "gateway": "",
        "dns_primary": "",
        "dns_secondary": "",
        "is_dhcp": True,
        "status": "Desconhecida",
        "raw_output": "",
    }

    try:
        output = subprocess.check_output(
            f'netsh interface ip show config name="{iface_name}"',
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=5,
        )
        config["raw_output"] = output

        # ---- Status ----
        stats = psutil.net_if_stats()
        if iface_name in stats:
            config["status"] = "Conectada" if stats[iface_name].isup else "Desconectada"

        # ---- DHCP ----
        dhcp_match = re.search(r"DHCP\s+(?:habilitado|enabled)[:\s]+([SNsn]|[YNyn])", output, re.IGNORECASE)
        if dhcp_match:
            val = dhcp_match.group(1).upper()
            config["is_dhcp"] = val in ("S", "Y")

        # ---- IPv4 ----
        ip_match = re.search(
            r"(?:Endere[çc]o\s+IP|IP\s+Address|Endere.o\s+IP)[:\s]+(\d+\.\d+\.\d+\.\d+)",
            output, re.IGNORECASE
        )
        if ip_match:
            config["ipv4"] = ip_match.group(1)

        # ---- Máscara ----
        mask_match = re.search(
            r"(?:m[áa]scara|mask)[:\s)]+(\d+\.\d+\.\d+\.\d+)",
            output, re.IGNORECASE
        )
        if mask_match:
            config["mask"] = mask_match.group(1)

        # ---- Gateway ----
        gw_match = re.search(
            r"Gateway\s+(?:Padr[ãa]o|Default|Padr.o)[:\s]+(\d+\.\d+\.\d+\.\d+)",
            output, re.IGNORECASE
        )
        if gw_match:
            config["gateway"] = gw_match.group(1)

        # ---- DNS ----
        dns_matches = re.findall(
            r"(?:DNS|Servidores\s+DNS)[\s\w.]*?:\s*(\d+\.\d+\.\d+\.\d+)",
            output, re.IGNORECASE
        )
        # Também captura linhas de DNS adicionais (linhas com apenas IP indentado)
        dns_extra = re.findall(r"^\s+(\d+\.\d+\.\d+\.\d+)\s*$", output, re.MULTILINE)
        all_dns = list(dict.fromkeys(dns_matches + dns_extra))  # Remove duplicatas

        if len(all_dns) >= 1:
            config["dns_primary"] = all_dns[0]
        if len(all_dns) >= 2:
            config["dns_secondary"] = all_dns[1]

    except subprocess.TimeoutExpired:
        config["status"] = "Timeout"
    except subprocess.CalledProcessError:
        config["status"] = "Erro"
    except Exception as e:
        config["status"] = f"Erro: {str(e)}"

    return config


# ================================================================
# Validação de Configuração IP
# ================================================================

def validate_ip_config(
    ip: str, mask: str, gateway: str = "",
    dns1: str = "", dns2: str = ""
) -> tuple[bool, str]:
    """
    Valida uma configuração de IP estático.

    Args:
        ip: Endereço IPv4.
        mask: Máscara de sub-rede.
        gateway: Gateway padrão (opcional).
        dns1: DNS primário (opcional).
        dns2: DNS secundário (opcional).

    Returns:
        Tupla (válido: bool, mensagem_erro: str).
    """
    # Validar IP
    if not ip or not ip.strip():
        return False, "O endereço IP é obrigatório."
    try:
        ip_obj = ipaddress.IPv4Address(ip.strip())
        if ip_obj.is_loopback:
            return False, "O endereço de loopback (127.x) não pode ser usado."
        if ip_obj.is_unspecified:
            return False, "O endereço 0.0.0.0 não pode ser usado."
    except ipaddress.AddressValueError:
        return False, f"Endereço IP inválido: {ip}"

    # Validar máscara
    if not mask or not mask.strip():
        return False, "A máscara de sub-rede é obrigatória."
    try:
        # Verifica se é uma máscara válida (contígua)
        mask_int = int(ipaddress.IPv4Address(mask.strip()))
        # Máscara deve ser contígua (1s seguidos de 0s)
        if mask_int == 0:
            return False, "Máscara de sub-rede não pode ser 0.0.0.0."
        # Verifica bits contíguos
        inverted = mask_int ^ 0xFFFFFFFF
        if (inverted + 1) & inverted != 0:
            return False, f"Máscara de sub-rede inválida: {mask}"
    except (ipaddress.AddressValueError, ValueError):
        return False, f"Máscara de sub-rede inválida: {mask}"

    # Validar gateway (se fornecido)
    if gateway and gateway.strip():
        try:
            gw_obj = ipaddress.IPv4Address(gateway.strip())
            # Verifica se o gateway está na mesma sub-rede
            network = ipaddress.IPv4Network(f"{ip.strip()}/{mask.strip()}", strict=False)
            if gw_obj not in network:
                return False, (
                    f"O gateway {gateway} não pertence à mesma rede "
                    f"({network.network_address}/{network.prefixlen})."
                )
        except ipaddress.AddressValueError:
            return False, f"Gateway inválido: {gateway}"

    # Validar DNS (se fornecidos)
    for label, dns in [("DNS Primário", dns1), ("DNS Secundário", dns2)]:
        if dns and dns.strip():
            try:
                ipaddress.IPv4Address(dns.strip())
            except ipaddress.AddressValueError:
                return False, f"{label} inválido: {dns}"

    return True, ""


# ================================================================
# Aplicar Configurações
# ================================================================

def set_static_ip(
    iface_name: str, ip: str, mask: str,
    gateway: str = "", dns1: str = "", dns2: str = ""
) -> tuple[bool, str]:
    """
    Configura IP estático em uma interface via netsh.
    Requer privilégios de administrador.

    Args:
        iface_name: Nome da interface (ex: "Ethernet").
        ip, mask, gateway: Configuração IPv4.
        dns1, dns2: Servidores DNS.

    Returns:
        Tupla (sucesso: bool, log_mensagem: str).
    """
    if not is_admin():
        return False, (
            "❌ Privilégios de administrador necessários.\n"
            "Feche o programa e execute novamente como Administrador\n"
            "(clique com botão direito → Executar como administrador)."
        )

    log_lines = []

    try:
        # ---- Configurar IP e máscara ----
        cmd_ip = f'netsh interface ip set address name="{iface_name}" static {ip} {mask}'
        if gateway and gateway.strip():
            cmd_ip += f" {gateway}"

        log_lines.append(f"Executando: {cmd_ip}")
        result = subprocess.run(
            cmd_ip,
            capture_output=True,
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=15,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
            log_lines.append(f"❌ Erro ao configurar IP: {error_msg}")
            return False, "\n".join(log_lines)

        log_lines.append("✅ IP e máscara configurados com sucesso.")

        # ---- Configurar DNS primário ----
        if dns1 and dns1.strip():
            cmd_dns1 = f'netsh interface ip set dns name="{iface_name}" static {dns1.strip()}'
            log_lines.append(f"Executando: {cmd_dns1}")
            result = subprocess.run(
                cmd_dns1,
                capture_output=True,
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=10,
            )
            if result.returncode == 0:
                log_lines.append(f"✅ DNS primário configurado: {dns1.strip()}")
            else:
                log_lines.append(f"⚠️ Falha ao configurar DNS primário: {result.stderr.strip()}")

        # ---- Configurar DNS secundário ----
        if dns2 and dns2.strip():
            cmd_dns2 = f'netsh interface ip add dns name="{iface_name}" {dns2.strip()} index=2'
            log_lines.append(f"Executando: {cmd_dns2}")
            result = subprocess.run(
                cmd_dns2,
                capture_output=True,
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=10,
            )
            if result.returncode == 0:
                log_lines.append(f"✅ DNS secundário configurado: {dns2.strip()}")
            else:
                log_lines.append(f"⚠️ Falha ao configurar DNS secundário: {result.stderr.strip()}")

        log_lines.append("\n✅ Configuração de IP estático aplicada com sucesso!")
        return True, "\n".join(log_lines)

    except subprocess.TimeoutExpired:
        log_lines.append("❌ Timeout: o comando demorou mais que o esperado.")
        return False, "\n".join(log_lines)
    except Exception as e:
        log_lines.append(f"❌ Erro inesperado: {str(e)}")
        return False, "\n".join(log_lines)


def restore_dhcp(iface_name: str) -> tuple[bool, str]:
    """
    Restaura a interface para obter IP automaticamente via DHCP.
    Também restaura DNS automático e renova o endereço.
    Requer privilégios de administrador.

    Args:
        iface_name: Nome da interface (ex: "Ethernet").

    Returns:
        Tupla (sucesso: bool, log_mensagem: str).
    """
    if not is_admin():
        return False, (
            "❌ Privilégios de administrador necessários.\n"
            "Feche o programa e execute novamente como Administrador\n"
            "(clique com botão direito → Executar como administrador)."
        )

    log_lines = []

    try:
        # ---- Restaurar IP para DHCP ----
        cmd_ip = f'netsh interface ip set address name="{iface_name}" dhcp'
        log_lines.append(f"Executando: {cmd_ip}")
        result = subprocess.run(
            cmd_ip,
            capture_output=True,
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=15,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
            log_lines.append(f"❌ Erro ao restaurar DHCP: {error_msg}")
            return False, "\n".join(log_lines)

        log_lines.append("✅ IP configurado para DHCP.")

        # ---- Restaurar DNS para automático ----
        cmd_dns = f'netsh interface ip set dns name="{iface_name}" dhcp'
        log_lines.append(f"Executando: {cmd_dns}")
        result = subprocess.run(
            cmd_dns,
            capture_output=True,
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=10,
        )

        if result.returncode == 0:
            log_lines.append("✅ DNS configurado para automático.")
        else:
            log_lines.append(f"⚠️ Falha ao restaurar DNS: {result.stderr.strip()}")

        # ---- Renovar endereço IP ----
        cmd_renew = f'ipconfig /renew "{iface_name}"'
        log_lines.append(f"Executando: {cmd_renew}")
        result = subprocess.run(
            cmd_renew,
            capture_output=True,
            encoding="cp850",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=20,
        )

        if result.returncode == 0:
            log_lines.append("✅ Endereço IP renovado com sucesso.")
        else:
            log_lines.append("⚠️ Falha ao renovar IP (pode normalizar em alguns segundos).")

        log_lines.append("\n✅ Configuração automática (DHCP) restaurada com sucesso!")
        return True, "\n".join(log_lines)

    except subprocess.TimeoutExpired:
        log_lines.append("❌ Timeout: o comando demorou mais que o esperado.")
        return False, "\n".join(log_lines)
    except Exception as e:
        log_lines.append(f"❌ Erro inesperado: {str(e)}")
        return False, "\n".join(log_lines)
