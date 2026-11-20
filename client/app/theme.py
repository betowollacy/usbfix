"""Tema visual premium do USB FIX.

Paleta: azul-marinho profundo, azul tecnológico e detalhes ciano/âmbar.
Mantém os mesmos nomes de constantes para não alterar a lógica dos componentes.
"""

import customtkinter as ctk

# Superfícies — azul-marinho profundo
BG = "#070D18"
BG_ELEV = "#0B1422"
PANEL = "#101B2C"
PANEL2 = "#17263A"
HEADER_BG = "#0A1321"
LINE = "#29415E"
LINE_SOFT = "#1B3049"

# Bordas discretas
BORDER = "#294966"
BORDER_SOFT = "#203A55"

# Acentos — azul como cor principal, ciano para informação e âmbar em detalhes
ACCENT = "#2478E8"
ACCENT_DARK = "#185DBB"
ACCENT2 = "#42C7E8"
GLOW = "#F2A84B"

# Texto e estados
TEXT = "#F4F7FB"
MUTED = "#A8B8CC"
SUBTLE = "#71849D"
OK = "#35C995"
ERR = "#F07178"
WARN = "#F2B85B"

# Tipografia
FONT = "Segoe UI"
MONO = "Cascadia Mono"


def fonts():
    """Fonte usada pela aplicação (criada aqui para evitar duplicação)."""
    return {
        "title": ctk.CTkFont(family=FONT, size=25, weight="bold"),
        "h1": ctk.CTkFont(family=FONT, size=21, weight="bold"),
        "h2": ctk.CTkFont(family=FONT, size=14, weight="bold"),
        "body": ctk.CTkFont(family=FONT, size=12),
        "small": ctk.CTkFont(family=FONT, size=11),
        "tiny": ctk.CTkFont(family=FONT, size=9, weight="bold"),
        "btn": ctk.CTkFont(family=FONT, size=12, weight="bold"),
        "mono": ctk.CTkFont(family=MONO, size=12),
        "percent": ctk.CTkFont(family=FONT, size=23, weight="bold"),
    }


def gradient_strip(parent, height=4, colors=(ACCENT, ACCENT2, GLOW)):
    """Faixa de destaque azul → ciano → âmbar, sem brilho excessivo."""
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
            color = "#" + "".join(
                f"{round(a[k] + (b[k] - a[k]) * t):02x}" for k in range(3)
            )
            canvas.create_line(x, 0, x, height, fill=color, tags="grad")

    canvas.bind("<Configure>", redraw)
    return canvas
