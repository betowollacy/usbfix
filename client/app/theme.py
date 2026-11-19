"""Tema visual do USB FIX (dark tech).

Centraliza cores, fontes e pequenos helpers para manter a interface
consistente entre login, portal, splash e atualização.
"""

import customtkinter as ctk

# Superfícies
BG = "#070B14"
BG_ELEV = "#0B1120"
PANEL = "#0F192C"
PANEL2 = "#16233B"
HEADER_BG = "#0A1020"
LINE = "#23314C"
LINE_SOFT = "#1A2740"

# Acentos
ACCENT = "#6C7BFF"
ACCENT_DARK = "#5364E8"
ACCENT2 = "#22D3EE"
GLOW = "#7C3AED"

# Texto e estados
TEXT = "#F8FAFC"
MUTED = "#9AA8C2"
SUBTLE = "#64748B"
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


def gradient_strip(parent, height=3, colors=(ACCENT2, ACCENT, GLOW)):
    """Faixa horizontal com gradiente suave (substitui a linha sólida)."""
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
