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
    target_gateway = gateway_ip or state.get("gateway", "")
    log_text = state.get("log_text", "")

    if not target_gateway or target_gateway == "Não disponível":
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
