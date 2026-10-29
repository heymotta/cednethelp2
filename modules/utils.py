"""
CedNet Help - Módulo de Utilitários
Constantes compartilhadas: cores, fontes, dimensões e funções auxiliares.
"""

# Paleta de Cores e Tokens Visuais
COLORS = {
    # Backgrounds
    "bg_main": "#1a1a2e",
    "bg_sidebar": "#16213e",
    "bg_card": "#0f3460",
    "bg_card_alt": "#132a4a",
    "bg_card_hover": "#1a4a7a",
    "entry_bg": "#0d2137",

    # Acentos
    "accent": "#1a73e8",
    "accent_hover": "#2196f3",
    "accent_cyan": "#00bcd4",

    # Texto
    "text_primary": "#ffffff",
    "text_secondary": "#94a3b8",

    # Status (Acessíveis segundo WCAG AA sobre fundos escuros)
    "status_ok": "#4ade80",
    "status_error": "#f87171",
    "status_warning": "#ff9800",

    # Ações e Alertas
    "btn_success": "#15803d",
    "btn_success_hover": "#166534",
    "bg_error_banner": "#3d1a1a",
    "border_error_banner": "#dc2626",
    "text_error_banner": "#fca5a5",

    # Bordas
    "border": "#1e3a5f",
}

# Fontes tipográficas
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

# Dimensões da janela
SIDEBAR_WIDTH = 220
WINDOW_SIZE = "1050x680"
WINDOW_MIN_SIZE = (900, 600)

APP_VERSION = "1.9.9"
APP_NAME = "CedNet Help"

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
