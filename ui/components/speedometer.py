"""
CedNet Help - Componente de Velocímetro Animado (Canvas)
Velocímetro circular moderno em Tkinter Canvas com ponteiro animado por interpolação (Lerp),
leitura numérica em tempo real e alternância de tema entre Download (Cyan/Azul) e Upload (Verde).
"""

import tkinter as tk
import math
from typing import Optional
from modules.utils import COLORS, FONTS


class SpeedometerCanvas(tk.Canvas):
    """
    Widget de Velocímetro Circular com Animação Suave.
    """

    def __init__(self, parent, width: int = 240, height: int = 220, bg_color: str = COLORS["bg_card"], **kwargs):
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

        # Centro do arco e raio
        self.cx = width / 2
        self.cy = height / 2 + 10
        self.radius = min(width, height) / 2 - 25

        # Ângulos do arco (135° a 45°, percorrendo 270° no sentido horário)
        self.start_angle = 135  # Em graus (lado esquerdo inferior)
        self.total_sweep = 270  # Varredura até o lado direito inferior

        # Intervalo de velocidade
        self.max_speed = 1000.0  # Mbps máximo na escala log/não-linear
        self.current_value = 0.0
        self.target_value = 0.0

        # Modo: "idle", "download", "upload"
        self.mode = "idle"
        self.primary_color = COLORS["accent_cyan"]

        # Loop de animação
        self._anim_running = False
        self._after_id: Optional[str] = None

        self._draw_static_dial()
        self._draw_needle_and_text(0.0)
        self._start_animation_loop()

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
    # Matematica de Escala e Graus
    # ================================================================

    def _val_to_angle(self, val: float) -> float:
        """
        Converte uma velocidade em Mbps (0 a max_speed) no ângulo correspondente.
        Usa escala não-linear (raiz quadrada) para destacar velocidades baixas e altas.
        """
        if val <= 0:
            pct = 0.0
        else:
            # Escala suave com curva de resposta mais natural
            pct = math.pow(val / self.max_speed, 0.65)
            pct = min(1.0, max(0.0, pct))

        # Ângulo em graus do Tkinter (0 = 3 horas, 90 = 12 horas, 180 = 9 horas, 270 = 6 horas)
        # Nosso arco começa em 225° (sudoeste) e vai no sentido horário até -45° (sudeste)
        angle_deg = 225 - (pct * 270)
        return angle_deg

    # ================================================================
    # Desenho no Canvas
    # ================================================================

    def _draw_static_dial(self):
        """Desenha o mostrador de fundo, arcos e graduações."""
        self.delete("all")

        # 1. Arco de Fundo (Pista escura)
        box = (
            self.cx - self.radius,
            self.cy - self.radius,
            self.cx + self.radius,
            self.cy + self.radius,
        )
        self.create_arc(
            box,
            start=-45,
            extent=270,
            style=tk.ARC,
            outline=COLORS["border"],
            width=14,
        )

        # 2. Arco Ativo com a Cor Primária (baseado na velocidade atual)
        pct = min(1.0, max(0.0, math.pow(self.current_value / self.max_speed, 0.65)))
        if pct > 0.001:
            extent_deg = -pct * 270
            self.create_arc(
                box,
                start=225,
                extent=extent_deg,
                style=tk.ARC,
                outline=self.primary_color,
                width=14,
            )

        # 3. Marcadores de Graduação (Ticks)
        tick_speeds = [0, 10, 50, 100, 250, 500, 1000]
        for spd in tick_speeds:
            if spd > self.max_speed:
                continue
            ang_deg = self._val_to_angle(spd)
            ang_rad = math.radians(ang_deg)

            # Ponto interno e externo da marcação
            r_in = self.radius - 18
            r_out = self.radius - 8

            x1 = self.cx + r_in * math.cos(ang_rad)
            y1 = self.cy - r_in * math.sin(ang_rad)
            x2 = self.cx + r_out * math.cos(ang_rad)
            y2 = self.cy - r_out * math.sin(ang_rad)

            self.create_line(x1, y1, x2, y2, fill=COLORS["text_secondary"], width=2)

            # Rótulos das marcas principais
            r_txt = self.radius - 30
            tx = self.cx + r_txt * math.cos(ang_rad)
            ty = self.cy - r_txt * math.sin(ang_rad)
            lbl = str(spd) if spd < 1000 else "1G"
            self.create_text(
                tx, ty, text=lbl, fill=COLORS["text_secondary"], font=("Segoe UI", 9)
            )

    def _draw_needle_and_text(self, val: float):
        """Desenha o ponteiro central e o texto numérico em tempo real."""
        # 1. Ângulo do Ponteiro
        ang_deg = self._val_to_angle(val)
        ang_rad = math.radians(ang_deg)

        # Comprimento do ponteiro
        needle_len = self.radius - 22
        nx = self.cx + needle_len * math.cos(ang_rad)
        ny = self.cy - needle_len * math.sin(ang_rad)

        # Linha do Ponteiro principal
        self.create_line(
            self.cx, self.cy, nx, ny,
            fill=self.primary_color,
            width=4,
            capstyle=tk.ROUND,
        )

        # Centro do mostrador (Círculo de pivô)
        r_hub = 8
        self.create_oval(
            self.cx - r_hub, self.cy - r_hub,
            self.cx + r_hub, self.cy + r_hub,
            fill=COLORS["bg_main"], outline=self.primary_color, width=3
        )

        # 2. Exibição Numérica Central
        # Formata o número (ex: 277.5 Mbps ou 0.0)
        if val >= 100:
            val_str = f"{val:.1f}"
        elif val >= 10:
            val_str = f"{val:.1f}"
        else:
            val_str = f"{val:.2f}" if val > 0 else "0.0"

        # Valor gigante
        self.create_text(
            self.cx, self.cy + 30,
            text=val_str,
            fill=COLORS["text_primary"],
            font=("Segoe UI", 26, "bold"),
        )

        # Unidade "Mbps"
        self.create_text(
            self.cx, self.cy + 52,
            text="Mbps",
            fill=COLORS["text_secondary"],
            font=("Segoe UI", 10, "bold"),
        )

        # Rótulo de Modo (DOWNLOAD / UPLOAD)
        mode_text = self.mode.upper() if self.mode != "idle" else "SPEED TEST"
        self.create_text(
            self.cx, self.cy + 68,
            text=mode_text,
            fill=self.primary_color,
            font=("Segoe UI", 10, "bold"),
        )

    def redraw(self):
        """Redesenha todo o mostrador."""
        self._draw_static_dial()
        self._draw_needle_and_text(self.current_value)

    # ================================================================
    # Loop de Animação (Suavização Lerp)
    # ================================================================

    def _start_animation_loop(self):
        self._anim_running = True
        self._animate()

    def _animate(self):
        if not self._anim_running:
            return

        # Interpolação Linear (Lerp) para aproximação suave
        diff = self.target_value - self.current_value
        if abs(diff) > 0.01:
            # 20% do caminho a cada frame (suave e ágil)
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
