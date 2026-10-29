"""
CedNet Help - Gerador e Cache de Ícones e Indicadores Visuais (UI Icons)
Gera ícones vetoriais/rasterizados nítidos via Pillow e CTkImage para
substituir o uso de emojis de fontes do sistema, conforme regras Hallmark.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw
from typing import Optional, Tuple
from modules.utils import COLORS


_INDICATOR_CACHE: dict[str, ctk.CTkImage] = {}


def get_status_indicator_image(status_type: str, size: Tuple[int, int] = (20, 20)) -> ctk.CTkImage:
    """
    Retorna uma imagem CTkImage vetorial nítida de indicador de status circular (ponto de status com borda suave).

    Args:
        status_type: 'ok' (verde), 'error' (vermelho), 'warning' (amarelo), 'idle' (cinza).
        size: Dimensão (largura, altura) em pixels lógicos.
    """
    cache_key = f"{status_type}_{size[0]}x{size[1]}"
    if cache_key in _INDICATOR_CACHE:
        return _INDICATOR_CACHE[cache_key]

    w, h = size
    # Renderiza em 2x (supersampling) para anti-aliasing perfeito no Tkinter
    scale = 2
    sw, sh = w * scale, h * scale

    colors_map = {
        "ok": {
            "light": ((22, 163, 74), (74, 222, 128)),
            "dark": ((74, 222, 128), (34, 197, 94)),
        },
        "error": {
            "light": ((220, 38, 38), (248, 113, 113)),
            "dark": ((248, 113, 113), (239, 68, 68)),
        },
        "warning": {
            "light": ((217, 119, 6), (255, 152, 0)),
            "dark": ((255, 152, 0), (245, 158, 11)),
        },
        "idle": {
            "light": ((156, 163, 175), (209, 213, 219)),
            "dark": ((100, 116, 139), (71, 85, 105)),
        },
    }

    palette = colors_map.get(status_type, colors_map["idle"])

    def _draw_circle(fill_rgb: Tuple[int, int, int]) -> Image.Image:
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = scale * 2
        # Círculo central com preenchimento sólido e nítido
        draw.ellipse((pad, pad, sw - pad, sh - pad), fill=(*fill_rgb, 255))
        return img.resize((w, h), Image.Resampling.LANCZOS)

    img_light = _draw_circle(palette["light"][0])
    img_dark = _draw_circle(palette["dark"][0])

    ctk_img = ctk.CTkImage(light_image=img_light, dark_image=img_dark, size=size)
    _INDICATOR_CACHE[cache_key] = ctk_img
    return ctk_img

