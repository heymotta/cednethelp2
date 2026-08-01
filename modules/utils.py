"""
CedNet Help - Módulo de Utilitários
Constantes compartilhadas: cores, fontes, dimensões e funções auxiliares.
"""


# ============================================================
# Paleta de Cores — Tema Escuro Profissional
# ============================================================
COLORS = {
    # Backgrounds
    "bg_main": "#1a1a2e",           # Fundo principal (azul escuro profundo)
    "bg_sidebar": "#16213e",         # Fundo da sidebar
    "bg_card": "#0f3460",            # Cards / Frames
    "bg_card_alt": "#132a4a",        # Cards alternados
    "bg_card_hover": "#1a4a7a",      # Cards hover
    "entry_bg": "#0d2137",           # Campo de entrada

    # Acentos
    "accent": "#1a73e8",             # Botão ativo / Acento principal
    "accent_hover": "#2196f3",       # Botão hover
    "accent_cyan": "#00bcd4",        # Destaque ciano (valores)

    # Texto
    "text_primary": "#ffffff",       # Texto principal (branco)
    "text_secondary": "#94a3b8",     # Texto secundário (cinza azulado)

    # Status
    "status_ok": "#4caf50",          # Verde (conectado)
    "status_error": "#f44336",       # Vermelho (desconectado)
    "status_warning": "#ff9800",     # Laranja (alerta)

    # Bordas
    "border": "#1e3a5f",             # Bordas sutis
}


# ============================================================
# Fontes — Segoe UI (nativa Windows) + Consolas (mono)
# ============================================================
FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "subtitle": ("Segoe UI", 16, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "small_bold": ("Segoe UI", 11, "bold"),
    "mono": ("Consolas", 13),
    "mono_bold": ("Consolas", 13, "bold"),
    "mono_large": ("Consolas", 15, "bold"),
    "sidebar_btn": ("Segoe UI", 14),

    "sidebar_title": ("Segoe UI", 18, "bold"),
}


# ============================================================
# Dimensões
# ============================================================
SIDEBAR_WIDTH = 220
WINDOW_SIZE = "1050x680"
WINDOW_MIN_SIZE = (900, 600)


# ============================================================
# Informações do App
# ============================================================
APP_VERSION = "1.8.0"
APP_NAME = "CedNet Help"



# ============================================================
# Funções Utilitárias
# ============================================================
def format_error_message(error: Exception) -> str:
    """Formata uma exceção em mensagem amigável para o usuário."""
    error_map = {
        "ConnectionError": "Erro de conexão. Verifique sua rede.",
        "TimeoutError": "Tempo de espera esgotado.",
        "PermissionError": "Permissão negada. Execute como administrador.",
        "FileNotFoundError": "Recurso não encontrado.",
    }
    error_type = type(error).__name__
    return error_map.get(error_type, f"Erro inesperado: {str(error)}")
