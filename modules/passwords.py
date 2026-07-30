"""
CedNet Help - Módulo de Senhas Padrão
Banco de dados local de senhas padrão de roteadores e equipamentos de rede.
Preparado para futura migração a banco de dados SQLite.
"""


# ============================================================
# Credenciais organizadas por modelo/marca de equipamento
# ============================================================
CREDENTIALS_BY_TYPE: dict[str, list[dict[str, str]]] = {
    "zte": [
        {"user": "cednet", "pass": "GCrouter@734"},
        {"user": "multipro", "pass": "multipro"},
        {"user": "user", "pass": "user"},
        {"user": "admin", "pass": "admin"},
    ],
    "datacom": [
        {"user": "user", "pass": "user"},
        {"user": "cednet", "pass": "GCrouter@734"},
        {"user": "admin", "pass": "admin"},
    ],
    "tplink": [
        {"user": "admin", "pass": "admin"},
        {"user": "admin", "pass": "cednetrouter"},
        {"user": "admin", "pass": "GCrouter@734"},
    ],
    "radio": [
        {"user": "admin", "pass": "%W2sajuB"},
        {"user": "admin", "pass": "dITcd34A9"},
        {"user": "admin", "pass": "DitCD34a9"},
        {"user": "admin", "pass": "%Ph8rehu"},
        {"user": "admin", "pass": "Fcd24cli"},
        {"user": "admin", "pass": "%Ph8rehuGC"},
        {"user": "ubnt", "pass": "ubnt"},
        {"user": "admin", "pass": "0D03BD7"},
        {"user": "admin", "pass": "5SNRAv06"},
        {"user": "admin", "pass": "Xbd74BN2"},
        {"user": "admin", "pass": "Erebro2h"},
    ],
}


# ============================================================
# Base de Dados Geral de Senhas Padrão
# ============================================================
DEFAULT_PASSWORDS: list[dict[str, str]] = [
    {"marca": "ZTE (CedNet)", "usuario": "cednet", "senha": "GCrouter@734"},
    {"marca": "ZTE (MultiPro)", "usuario": "multipro", "senha": "multipro"},
    {"marca": "ZTE (User)", "usuario": "user", "senha": "user"},
    {"marca": "Datacom (User)", "usuario": "user", "senha": "user"},
    {"marca": "Datacom (CedNet)", "usuario": "cednet", "senha": "GCrouter@734"},
    {"marca": "TP-Link (CedNet)", "usuario": "admin", "senha": "cednetrouter"},
    {"marca": "TP-Link (GC)", "usuario": "admin", "senha": "GCrouter@734"},
    {"marca": "Intelbras", "usuario": "admin", "senha": "admin"},
    {"marca": "TP-Link", "usuario": "admin", "senha": "admin"},
    {"marca": "Huawei", "usuario": "admin", "senha": "admin"},
    {"marca": "ZTE", "usuario": "admin", "senha": "admin"},
    {"marca": "Mikrotik", "usuario": "admin", "senha": "(vazio)"},
    {"marca": "FiberHome", "usuario": "admin", "senha": "admin"},
    {"marca": "D-Link", "usuario": "admin", "senha": "admin"},
    {"marca": "Cisco", "usuario": "admin", "senha": "admin"},
    {"marca": "Ubiquiti", "usuario": "ubnt", "senha": "ubnt"},
    {"marca": "Rádio Ubiquiti", "usuario": "admin", "senha": "%W2sajuB"},
    {"marca": "Rádio Ubiquiti", "usuario": "admin", "senha": "dITcd34A9"},
    {"marca": "Multilaser", "usuario": "admin", "senha": "admin"},
    {"marca": "Greatek", "usuario": "admin", "senha": "admin"},
    {"marca": "Elsys", "usuario": "admin", "senha": "admin"},
    {"marca": "Nokia", "usuario": "admin", "senha": "admin"},
    {"marca": "Mercusys", "usuario": "admin", "senha": "admin"},
    {"marca": "Tenda", "usuario": "admin", "senha": "admin"},
]


def get_credentials_by_device_type(device_type: str) -> list[dict[str, str]]:
    """
    Retorna a lista de pares {user, pass} para um determinado tipo de equipamento.

    Args:
        device_type: Identificador ('zte', 'datacom', 'tplink', 'radio', etc.)

    Returns:
        Lista de dicionários com chaves 'user' e 'pass'.
    """
    device_lower = (device_type or "").strip().lower().replace("-", "").replace("_", "").replace("á", "a")
    if device_lower in CREDENTIALS_BY_TYPE:
        return CREDENTIALS_BY_TYPE[device_lower].copy()
    
    # Se 'geral' ou não especificado, retorna ZTE por padrão
    return CREDENTIALS_BY_TYPE.get("zte", []).copy()



def get_all_passwords() -> list[dict[str, str]]:
    """
    Retorna todas as senhas padrão cadastradas.

    Returns:
        Cópia da lista de dicionários com marca, usuario e senha.
    """
    return DEFAULT_PASSWORDS.copy()


def search_passwords(query: str) -> list[dict[str, str]]:
    """
    Filtra senhas por marca ou usuário (case-insensitive, busca parcial).

    Args:
        query: Texto para buscar no nome da marca ou usuário.

    Returns:
        Lista de dicionários com as senhas que correspondem à busca.
    """
    if not query or not query.strip():
        return get_all_passwords()

    query_lower = query.strip().lower()
    return [
        pw for pw in DEFAULT_PASSWORDS
        if query_lower in pw["marca"].lower() or query_lower in pw["usuario"].lower()
    ]

