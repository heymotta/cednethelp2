"""
CedNet Help - Componente de Velocímetro Animado (Canvas Responsivo)
Velocímetro circular moderno em Tkinter Canvas com ponteiro animado por interpolação (Lerp),
leitura numérica em tempo real e layout responsivo sem sobreposição de texto.
"""

import tkinter as tk
import math
from typing import Optional
from modules.utils import COLORS, FONTS


class SpeedometerCanvas(tk.Canvas):
    """
    Widget de Velocímetro Circular Responsivo com Animação Suave.
    """

    def __init__(
        self,
        parent,
        width: int = 260,
        height: int = 240,
        bg_color: str = COLORS["bg_card"],
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )

        self.w = width
        self.h = height
        self.bg_color = bg_color

        # Intervalo de velocidade
        self.max_speed = 1000.0
        self.current_value = 0.0
        self.target_value = 0.0

        # Modo: "idle", "download", "upload"
        self.mode = "idle"
        self.primary_color = COLORS["accent_cyan"]

        # Loop de animação
        self._anim_running = False
        self._after_id: Optional[str] = None

        # Evento de redimensionamento responsivo
        self.bind("<Configure>", self._on_configure)

        self.redraw()
        self._start_animation_loop()

    def _on_configure(self, event):
        """Atualiza dimensões dinamicamente se a janela for redimensionada."""
        if event.width > 10 and event.height > 10:
            if event.width != self.w or event.height != self.h:
                self.w = event.width
                self.h = event.height
                self.redraw()

    def set_mode(self, mode: str):
        """Define o modo visual: 'idle', 'download', 'upload'."""
        self.mode = mode
        if mode == "upload":
            self.primary_color = COLORS["status_ok"]
        elif mode == "download":
            self.primary_color = COLORS["accent_cyan"]
        else:
            self.primary_color = COLORS["accent_cyan"]
        self.redraw()

    def set_value(self, val: float, max_scale: float = 1000.0):
        """Atualiza a velocidade alvo (o ponteiro deslizará até ela)."""
        self.target_value = max(0.0, float(val))
        if max_scale > 0:
            self.max_speed = max_scale

    def set_value_instant(self, val: float):
        """Define a velocidade instantaneamente sem interpolação."""
        self.target_value = max(0.0, float(val))
        self.current_value = self.target_value
        self.redraw()

    def reset(self):
        """Reseta o velocímetro para zero."""
        self.target_value = 0.0
        self.current_value = 0.0
        self.mode = "idle"
        self.primary_color = COLORS["accent_cyan"]
        self.redraw()

    # ================================================================
    # Matemática de Escala e Graus
    # ================================================================

    def _val_to_angle(self, val: float) -> float:
        """
        Converte velocidade em Mbps no ângulo do ponteiro.
        Arco inicia em 215° (inferior esquerdo) e varre 250° no sentido horário até -35°.
        """
        if val <= 0:
            pct = 0.0
        else:
            pct = math.pow(val / self.max_speed, 0.65)
            pct = min(1.0, max(0.0, pct))

        angle_deg = 215 - (pct * 250)
        return angle_deg

    # ================================================================
    # Desenho Responsivo no Canvas
    # ================================================================

    def redraw(self):
        """Redesenha todo o mostrador garantindo zero sobreposição."""
        self.delete("all")

        w = self.w
        h = self.h

        # Centro do arco posicionado no terço superior do card (38% da altura)
        cx = w / 2.0
        cy = h * 0.38

        # Raio proporcional
        radius = min(w, h) * 0.34
        if radius < 30:
            return

        # 1. Arco de Fundo (Pista Escura)
        box = (
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
        )
        arc_width = max(8, int(radius * 0.14))
        self.create_arc(
            box,
            start=-35,
            extent=250,
            style=tk.ARC,
            outline=COLORS["border"],
            width=arc_width,
        )

        # 2. Arco Ativo com a Cor Primária
        pct = min(1.0, max(0.0, math.pow(self.current_value / self.max_speed, 0.65)))
        if pct > 0.001:
            extent_deg = -pct * 250
            self.create_arc(
                box,
                start=215,
                extent=extent_deg,
                style=tk.ARC,
                outline=self.primary_color,
                width=arc_width,
            )

        # 3. Marcadores de Graduação (Ticks)
        tick_speeds = [0, 50, 100, 250, 500, 1000]
        for spd in tick_speeds:
            if spd > self.max_speed:
                continue
            ang_deg = self._val_to_angle(spd)
            ang_rad = math.radians(ang_deg)

            r_in = radius - arc_width * 1.1
            r_out = radius - arc_width * 0.4

            x1 = cx + r_in * math.cos(ang_rad)
            y1 = cy - r_in * math.sin(ang_rad)
            x2 = cx + r_out * math.cos(ang_rad)
            y2 = cy - r_out * math.sin(ang_rad)

            self.create_line(x1, y1, x2, y2, fill=COLORS["text_secondary"], width=2)

            # Rótulos dos números do mostrador (fora do arco)
            r_txt = radius + arc_width * 0.9
            tx = cx + r_txt * math.cos(ang_rad)
            ty = cy - r_txt * math.sin(ang_rad)
            lbl = str(spd) if spd < 1000 else "1G"
            font_size = max(7, int(radius * 0.11))
            self.create_text(
                tx, ty, text=lbl, fill=COLORS["text_secondary"], font=("Segoe UI", font_size)
            )

        # 4. Ponteiro Central
        ang_deg = self._val_to_angle(self.current_value)
        ang_rad = math.radians(ang_deg)

        needle_len = radius - arc_width * 0.2
        nx = cx + needle_len * math.cos(ang_rad)
        ny = cy - needle_len * math.sin(ang_rad)

        needle_w = max(3, int(radius * 0.05))
        self.create_line(
            cx, cy, nx, ny,
            fill=self.primary_color,
            width=needle_w,
            capstyle=tk.ROUND,
        )

        # Pivô Central
        r_hub = max(4, int(radius * 0.08))
        self.create_oval(
            cx - r_hub, cy - r_hub,
            cx + r_hub, cy + r_hub,
            fill=COLORS["bg_main"], outline=self.primary_color, width=2
        )

        # 5. HIERAQUIA DE TEXTO (Posicionada estritamente ABAIXO do pivô sem sobreposição)
        # Linha 1: Valor Numérico Gigante (ex: 287.8)
        y_val = cy + radius * 0.45
        if self.current_value >= 100:
            val_str = f"{self.current_value:.1f}"
        elif self.current_value >= 10:
            val_str = f"{self.current_value:.1f}"
        else:
            val_str = f"{self.current_value:.2f}" if self.current_value > 0 else "0.0"

        val_font_size = max(16, int(radius * 0.30))
        self.create_text(
            cx, y_val,
            text=val_str,
            fill=COLORS["text_primary"],
            font=("Segoe UI", val_font_size, "bold"),
        )

        # Linha 2: Unidade "Mbps"
        y_unit = y_val + radius * 0.32
        unit_font_size = max(9, int(radius * 0.13))
        self.create_text(
            cx, y_unit,
            text="Mbps",
            fill=COLORS["text_secondary"],
            font=("Segoe UI", unit_font_size, "bold"),
        )

        # Linha 3: Modo ("DOWNLOAD" / "UPLOAD" / "SPEED TEST")
        y_mode = y_unit + radius * 0.26
        mode_text = self.mode.upper() if self.mode != "idle" else "SPEED TEST"
        mode_font_size = max(9, int(radius * 0.13))
        self.create_text(
            cx, y_mode,
            text=mode_text,
            fill=self.primary_color,
            font=("Segoe UI", mode_font_size, "bold"),
        )

    # ================================================================
    # Loop de Animação (Suavização Lerp)
    # ================================================================

    def _start_animation_loop(self):
        self._anim_running = True
        self._animate()

    def _animate(self):
        if not self._anim_running:
            return

        diff = self.target_value - self.current_value
        if abs(diff) > 0.01:
            self.current_value += diff * 0.22
            self.redraw()
        elif self.current_value != self.target_value:
            self.current_value = self.target_value
            self.redraw()

        self._after_id = self.after(25, self._animate)

    def destroy(self):
        self._anim_running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        super().destroy()
