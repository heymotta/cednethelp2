"""
CedNet Help - Módulo de Roteador
Utiliza a informação centralizada do NetworkManager para abrir a interface web do roteador.
Inclui verificação de conectividade HTTP/HTTPS antes de abrir.
"""

import webbrowser
import socket
from modules.network_manager import network_manager


def check_router_reachable(ip: str, timeout: float = 2.0) -> tuple[str, bool]:
    """
    Verifica se o roteador é acessível via HTTP ou HTTPS.

    Args:
        ip: Endereço IP do gateway.
        timeout: Timeout em segundos para a tentativa de conexão.

    Returns:
        Tupla (url: str, reachable: bool).
        url será http:// ou https:// dependendo de qual respondeu.
    """
    # Tenta HTTP primeiro (porta 80) — mais comum em roteadores
    for scheme, port in [("http", 80), ("https", 443)]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex((ip, port))
                if result == 0:
                    return f"{scheme}://{ip}", True
        except (socket.timeout, socket.error, OSError):
            continue

    # Se nenhum respondeu, retorna HTTP por padrão
    return f"http://{ip}", False


def open_router_page(gateway_ip: str = "") -> tuple[bool, str, str]:
    """
    Abre a interface web do roteador no navegador padrão.

    Args:
        gateway_ip: Endereço IP do gateway (opcional, usa network_manager por padrão).

    Returns:
        Tupla (sucesso: bool, mensagem: str, log: str).
    """
    state = network_manager.get_state()
    status = state.get("status", {})
    target_gateway = state.get("gateway", "")
    log_text = state.get("log_text", "")

    # O endereço informado pela UI pode ter ficado obsoleto desde o último
    # polling. O serviço central é a fonte atual e deve validar a conexão.
    if (not status.get("connected", False)
            or state.get("ipv4") in ("", "Não disponível")
            or not target_gateway
            or target_gateway == "Não disponível"):
        return (
            False,
            "Não foi possível detectar o Gateway Padrão.\n"
            "Verifique se você está conectado à rede.",
            log_text,
        )

    # Verifica se o roteador é acessível
    url, reachable = check_router_reachable(target_gateway)

    try:
        webbrowser.open(url)
        if reachable:
            return True, f"Abrindo {url} no navegador...", log_text
        else:
            return (
                True,
                f"Abrindo {url} no navegador...\n"
                f"(Nota: a porta pode estar bloqueada, mas tentando mesmo assim)",
                log_text,
            )
    except Exception as e:
        return False, f"Erro ao abrir o navegador:\n{str(e)}", log_text


def find_optimal_mtu(target: str = "1.1.1.1", callback=None) -> dict:
    """
    Descobre o MTU ideal da conexão testando pacotes ICMP com a flag Dont Fragment (-f).
    Utiliza busca binária rápida para encontrar o payload máximo sem fragmentação.

    Args:
        target: IP destino confiável (padrão Cloudflare 1.1.1.1).
        callback: Função opcional callback(step_text, current_payload) para reportar progresso.

    Returns:
        dict com:
            - 'success': bool
            - 'mtu': int | None (payload + 28 bytes de cabeçalho IP/ICMP)
            - 'payload': int | None
            - 'log': list[str]
            - 'classification': str ('Padrão Ethernet (1500)', 'Padrão PPPoE (1492)', etc.)
            - 'message': str
    """
    import subprocess
    import re

    # Criação de flags seguras para Windows sem abrir janela CMD
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    def _ping_size(size: int) -> bool:
        cmd = f"ping -n 1 -w 1000 -f -l {size} {target}"
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="replace",
                creationflags=creationflags,
                timeout=3,
            )
            out = r.stdout.lower()
            # Detecta mensagens de fragmentação em português ou inglês
            if "fragment" in out:
                return False
            # Confirma que recebeu resposta válida do host de destino
            if f"bytes={size}" in out and any(k in out for k in ("tempo=", "tempo<", "time=", "time<")):
                return True
            return False
        except Exception:
            return False

    log: list[str] = []

    # 1. Testa se a conexão geral com o destino responde
    if callback:
        callback("Verificando conectividade com destino...", 1472)
    
    # Testa primeiro o tamanho padrão de Ethernet (payload 1472 -> MTU 1500)
    if _ping_size(1472):
        log.append("Payload 1472 bytes respondeu sem fragmentar.")
        return {
            "success": True,
            "mtu": 1500,
            "payload": 1472,
            "log": log,
            "classification": "Padrão Ethernet / IPoE (1500)",
            "message": "MTU Máxima padrão (1500) operando normalmente sem restrições.",
        }

    log.append("Payload 1472 bytes fragmentou (MTU < 1500). Iniciando busca binária...")

    low = 1200
    high = 1472
    best_payload = None

    while low <= high:
        mid = (low + high) // 2
        if callback:
            callback(f"Testando pacote de {mid} bytes sem fragmentação...", mid)
        ok = _ping_size(mid)
        if ok:
            best_payload = mid
            log.append(f"Pacote {mid} bytes: Passou (OK)")
            low = mid + 1
        else:
            log.append(f"Pacote {mid} bytes: Fragmentou")
            high = mid - 1

    if best_payload is None:
        return {
            "success": False,
            "mtu": None,
            "payload": None,
            "log": log,
            "classification": "Indeterminado",
            "message": "Não foi possível determinar a MTU. Verifique se o destino está acessível.",
        }

    optimal_mtu = best_payload + 28

    if optimal_mtu == 1500:
        classification = "Padrão Ethernet / IPoE (1500)"
    elif optimal_mtu == 1492:
        classification = "Padrão PPPoE (1492)"
    elif optimal_mtu == 1480:
        classification = "Padrão PPPoE / VLAN / Túnel (1480)"
    elif optimal_mtu < 1480:
        classification = f"MTU Reduzida ({optimal_mtu}) - Provável VPN/Túnel"
    else:
        classification = f"MTU Customizada ({optimal_mtu})"

    return {
        "success": True,
        "mtu": optimal_mtu,
        "payload": best_payload,
        "log": log,
        "classification": classification,
        "message": f"MTU ideal calculada: {optimal_mtu} (Payload {best_payload} + 28 bytes de cabeçalho).",
    }

