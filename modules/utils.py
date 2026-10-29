"""
CedNet Help - Módulo de Utilitários
Constantes compartilhadas: cores, fontes, dimensões e funções auxiliares.
"""

# Paleta de Cores e Tokens Visuais (Light Mode, Dark Mode)
# Suporte nativo a temas do CustomTkinter (o tema escuro é o padrão da aplicação)
COLORS = {
    # Backgrounds
    "bg_main": ("#f7f8fa", "#1a1a2e"),
    "bg_sidebar": ("#f0f1f3", "#16213e"),
    "bg_card": ("#ffffff", "#0f3460"),
    "bg_card_alt": ("#f5f6f8", "#132a4a"),
    "bg_card_hover": ("#eaecef", "#1a4a7a"),
    "entry_bg": ("#f3f4f6", "#0d2137"),

    # Acentos
    "accent": ("#1a73e8", "#1a73e8"),
    "accent_hover": ("#1557b0", "#2196f3"),
    "accent_cyan": ("#2563a8", "#00bcd4"),

    # Texto
    "text_primary": ("#1a1f2e", "#ffffff"),
    "text_secondary": ("#6b7280", "#94a3b8"),

    # Status (Acessíveis segundo WCAG AA sobre fundos claros e escuros)
    "status_ok": ("#16a34a", "#4ade80"),
    "status_error": ("#dc2626", "#f87171"),
    "status_warning": ("#d97706", "#ff9800"),

    # Ações e Alertas
    "btn_success": ("#16a34a", "#15803d"),
    "btn_success_hover": ("#15803d", "#166534"),
    "bg_error_banner": ("#fef2f2", "#3d1a1a"),
    "border_error_banner": ("#f87171", "#dc2626"),
    "text_error_banner": ("#991b1b", "#fca5a5"),

    # Bordas
    "border": ("#d4d7dd", "#1e3a5f"),

    # Tokens Semânticos Adicionais (Hallmark / Anti-Slop Audit)
    "gold_trophy": ("#d97706", "#ffd700"),
    "btn_danger": ("#dc2626", "#dc2626"),
    "btn_danger_hover": ("#b91c1c", "#c62828"),
    "badge_success_bg": ("#e4f5ea", "#1b5e20"),
    "badge_success_text": ("#166534", "#81c784"),
}

# Escala Padronizada de Raios de Canto (Hallmark Tokens)
RADIUS = {
    "none": 0,
    "sm": 6,      # Badges, tags, pequenos botões e células
    "md": 8,      # Botões primários, campos de entrada (entry)
    "lg": 12,     # Cards de conteúdo e caixas modais
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

APP_VERSION = "1.10.6"
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
