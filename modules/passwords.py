"""
CedNet Help - Módulo de Senhas Padrão
Banco de dados local de senhas padrão de roteadores e equipamentos de rede.
Preparado para futura migração a banco de dados SQLite.
"""


# ============================================================
# Base de Dados de Senhas Padrão
# ============================================================
DEFAULT_PASSWORDS: list[dict[str, str]] = [
    {"marca": "Intelbras",   "usuario": "admin",    "senha": "admin"},
    {"marca": "TP-Link",     "usuario": "admin",    "senha": "admin"},
    {"marca": "Huawei",      "usuario": "admin",    "senha": "admin"},
    {"marca": "ZTE",         "usuario": "admin",    "senha": "admin"},
    {"marca": "Mikrotik",    "usuario": "admin",    "senha": "(vazio)"},
    {"marca": "FiberHome",   "usuario": "admin",    "senha": "admin"},
    {"marca": "D-Link",      "usuario": "admin",    "senha": "admin"},
    {"marca": "Cisco",       "usuario": "admin",    "senha": "admin"},
    {"marca": "Ubiquiti",    "usuario": "ubnt",     "senha": "ubnt"},
    {"marca": "Multilaser",  "usuario": "admin",    "senha": "admin"},
    {"marca": "Greatek",     "usuario": "admin",    "senha": "admin"},
    {"marca": "Elsys",       "usuario": "admin",    "senha": "admin"},
    {"marca": "Nokia",       "usuario": "admin",    "senha": "admin"},
    {"marca": "Mercusys",    "usuario": "admin",    "senha": "admin"},
    {"marca": "Tenda",       "usuario": "admin",    "senha": "admin"},
]


def get_all_passwords() -> list[dict[str, str]]:
    """
    Retorna todas as senhas padrão cadastradas.

    Returns:
        Cópia da lista de dicionários com marca, usuario e senha.
    """
    return DEFAULT_PASSWORDS.copy()


def search_passwords(query: str) -> list[dict[str, str]]:
    """
    Filtra senhas por marca (case-insensitive, busca parcial).

    Args:
        query: Texto para buscar no nome da marca.

    Returns:
        Lista de dicionários com as senhas que correspondem à busca.
    """
    if not query or not query.strip():
        return get_all_passwords()

    query_lower = query.strip().lower()
    return [
        pw for pw in DEFAULT_PASSWORDS
        if query_lower in pw["marca"].lower()
    ]
