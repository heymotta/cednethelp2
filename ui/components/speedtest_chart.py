"""
CedNet Help - Componente de Gráfico em Tempo Real (Canvas)
Gráfico de linha fluido e dinâmico desenhado em Canvas para acompanhar
a velocidade de Download e Upload amostra a amostra.
"""

import tkinter as tk
from typing import Optional
from modules.utils import COLORS, FONTS


class RealtimeChartCanvas(tk.Canvas):
    """
    Gráfico em Tempo Real com Curva Suave e Auto-escalonamento de Banda.
    """

    def __init__(self, parent, width: int = 480, height: int = 140, bg_color: str = COLORS["bg_card"], **kwargs):
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

        # Margens internas para eixos e rótulos
        self.pad_top = 20
        self.pad_bottom = 25
        self.pad_left = 55
        self.pad_right = 15

        # Dados da série
        self.download_points: list[float] = []
        self.upload_points: list[float] = []

        self.max_val = 100.0  # Teto inicial de Mbps do eixo Y
        self.active_mode = "download"  # "download", "upload", "complete"

        self.redraw()

    def reset(self):
        """Limpa o gráfico."""
        self.download_points.clear()
        self.upload_points.clear()
        self.max_val = 100.0
        self.active_mode = "download"
        self.redraw()

    def add_point(self, value: float, mode: str = "download"):
        """Adiciona um novo ponto de medição de velocidade no gráfico."""
        self.active_mode = mode
        val = max(0.0, float(value))

        if mode == "download":
            self.download_points.append(val)
        else:
            self.upload_points.append(val)

        # Ajusta dinamicamente a escala máxima do eixo Y com folga de 20%
        highest = max([val] + self.download_points + self.upload_points)
        if highest > self.max_val:
            # Arredonda para o próximo patamar amigável (100, 200, 300, 500, 1000)
            if highest <= 100:
                self.max_val = 100.0
            elif highest <= 300:
                self.max_val = 300.0
            elif highest <= 600:
                self.max_val = 600.0
            else:
                self.max_val = max(1000.0, highest * 1.15)

        self.redraw()

    # ================================================================
    # Desenho do Gráfico
    # ================================================================

    def redraw(self):
        """Redesenha a grade e as linhas de velocidade."""
        self.delete("all")

        plot_w = self.w - self.pad_left - self.pad_right
        plot_h = self.h - self.pad_top - self.pad_bottom

        # 1. Linhas de Grade Horizontais e Rótulos do Eixo Y
        y_steps = 3
        for i in range(y_steps + 1):
            fraction = i / y_steps
            y = self.pad_top + plot_h * (1 - fraction)
            val_label = self.max_val * fraction

            # Linha tracejada horizontal
            self.create_line(
                self.pad_left, y, self.w - self.pad_right, y,
                fill=COLORS["border"], dash=(2, 4), width=1
            )

            # Rótulo de velocidade
            lbl_str = f"{int(val_label)} M" if val_label >= 1 else "0"
            self.create_text(
                self.pad_left - 8, y,
                text=lbl_str,
                fill=COLORS["text_secondary"],
                font=("Consolas", 8),
                anchor="e"
            )

        # 2. Desenho das Séries de Download e Upload
        self._draw_series(self.download_points, COLORS["accent_cyan"], plot_w, plot_h)
        self._draw_series(self.upload_points, COLORS["status_ok"], plot_w, plot_h)

        # 3. Legenda no Topo Direitos
        self.create_rectangle(
            self.w - 140, 5, self.w - 130, 13,
            fill=COLORS["accent_cyan"], outline=""
        )
        self.create_text(
            self.w - 95, 9, text="Download", fill=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")
        )

        self.create_rectangle(
            self.w - 60, 5, self.w - 50, 13,
            fill=COLORS["status_ok"], outline=""
        )
        self.create_text(
            self.w - 20, 9, text="Upload", fill=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")
        )

    def _draw_series(self, points: list[float], color: str, plot_w: float, plot_h: float):
        if not points:
            return

        num_pts = len(points)
        coords = []

        # Calcula coordenadas (x, y) de cada ponto
        for idx, val in enumerate(points):
            if num_pts == 1:
                x = self.pad_left + plot_w / 2
            else:
                x = self.pad_left + (idx / (max(num_pts - 1, 1))) * plot_w

            norm_val = min(1.0, max(0.0, val / self.max_val))
            y = self.pad_top + plot_h * (1.0 - norm_val)
            coords.extend([x, y])

        # Se houver pelo menos 2 pontos (4 valores de coordenadas)
        if len(coords) >= 4:
            # Polygon para preenchimento de sombra abaixo da linha
            poly_coords = [self.pad_left, self.pad_top + plot_h] + coords + [coords[-2], self.pad_top + plot_h]
            try:
                self.create_polygon(
                    poly_coords,
                    fill=self._get_translucent_color(color),
                    outline="",
                )
            except Exception:
                pass

            # Linha principal contínua
            self.create_line(
                coords,
                fill=color,
                width=3,
                smooth=True,  # Linha suavizada/spline
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )

        # Destaca o último ponto com um pequeno círculo
        if coords:
            lx, ly = coords[-2], coords[-1]
            self.create_oval(
                lx - 4, ly - 4, lx + 4, ly + 4,
                fill=COLORS["text_primary"], outline=color, width=2
            )

    def _get_translucent_color(self, hex_color: str) -> str:
        """Retorna uma cor escura combinada com o fundo para simular transparência."""
        if hex_color == COLORS["accent_cyan"]:
            return "#093848"
        elif hex_color == COLORS["status_ok"]:
            return "#0a3818"
        return "#132a4a"
