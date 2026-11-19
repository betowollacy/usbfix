"""Tema visual do USB FIX (dark tech reforçado).

Centraliza cores, fontes e pequenos helpers para manter a interface
consistente entre login, portal, splash e atualização.

Paleta: preto profundo + ciano elétrico + violeta + toque magenta.
"""

import customtkinter as ctk

# Superfícies — preto profundo com camadas azuis
BG = "#02050C"
BG_ELEV = "#060C18"
PANEL = "#091320"
PANEL2 = "#0F1D31"
HEADER_BG = "#050A14"
LINE = "#1C3B5E"
LINE_SOFT = "#122640"

# Bordas com brilho (usadas nos cards e campos)
BORDER = "#1D5A86"
BORDER_SOFT = "#143A5C"

# Acentos
ACCENT = "#8358FF"       # violeta elétrico — botões e checkboxes (texto branco)
ACCENT_DARK = "#6D3FE0"
ACCENT2 = "#00E5FF"      # ciano elétrico — texto, ícones, barras e destaques
GLOW = "#FF4FD8"         # magenta — fecha o gradiente

# Texto e estados
TEXT = "#F0F9FF"
MUTED = "#93A9C4"
SUBTLE = "#607899"
OK = "#34D399"
ERR = "#FB7185"
WARN = "#FBBF24"

# Tipografia
FONT = "Segoe UI"
MONO = "Cascadia Mono"


def fonts():
    """Fonte usada pela aplicação (criada aqui para evitar duplicação)."""
    return {
        "title": ctk.CTkFont(family=FONT, size=24, weight="bold"),
        "h1": ctk.CTkFont(family=FONT, size=20, weight="bold"),
        "h2": ctk.CTkFont(family=FONT, size=14, weight="bold"),
        "body": ctk.CTkFont(family=FONT, size=12),
        "small": ctk.CTkFont(family=FONT, size=10),
        "tiny": ctk.CTkFont(family=FONT, size=9, weight="bold"),
        "btn": ctk.CTkFont(family=FONT, size=12, weight="bold"),
        "mono": ctk.CTkFont(family=MONO, size=12),
        "percent": ctk.CTkFont(family=FONT, size=22, weight="bold"),
    }


def gradient_strip(parent, height=5, colors=(ACCENT2, ACCENT, GLOW)):
    """Faixa horizontal com gradiente ciano -> violeta -> magenta."""
    import tkinter as tk

    canvas = tk.Canvas(parent, height=height, highlightthickness=0, bd=0)
    canvas.pack(fill="x", side="top")

    def redraw(event=None):
        canvas.delete("grad")
        w = canvas.winfo_width()
        if w < 2:
            return
        for x in range(w):
            pos = x / max(1, w - 1) * (len(colors) - 1)
            i = min(int(pos), len(colors) - 2)
            t = pos - i
            a = tuple(int(colors[i][j:j + 2], 16) for j in (1, 3, 5))
            b = tuple(int(colors[i + 1][j:j + 2], 16) for j in (1, 3, 5))
            color = "#" + "".join(f"{round(a[k] + (b[k] - a[k]) * t):02x}" for k in range(3))
            canvas.create_line(x, 0, x, height, fill=color, tags="grad")

    canvas.bind("<Configure>", redraw)
    return canvas
