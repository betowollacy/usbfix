import os
import re
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont, messagebox

from . import creds, logo, usb
from .api import Api, ApiError
from .config import API_BASE, DATA_DIR
from .tunnel import Tunnel

BG = "#0f0d15"
PANEL = "#171422"
PANEL2 = "#1d192b"
ACCENT = "#7c5cff"
ACCENT_DARK = "#5e44d6"
TEXT = "#eceaf2"
MUTED = "#8a87a0"
OK = "#38d99a"
ERR = "#ff5c7a"
WARN = "#ffb454"

FONT = "Segoe UI"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("USB FIX")
        self.geometry("460x660")
        self.minsize(460, 620)
        self.configure(bg=BG)
        self.api = Api(self._read_server())
        self.tunnel = Tunnel()
        self.tunnel.on_change(self._on_tunnel_change)
        self.user = None
        self._bg_tasks = queue.Queue()
        self._font_title = tkfont.Font(family=FONT, size=20, weight="bold")
        self._font_h1 = tkfont.Font(family=FONT, size=15, weight="bold")
        self._font_body = tkfont.Font(family=FONT, size=10)
        self._font_small = tkfont.Font(family=FONT, size=9)
        self._font_btn = tkfont.Font(family=FONT, size=10, weight="bold")

        self._logo_img = None
        try:
            self._logo_img = tk.PhotoImage(data=logo.LOGO_B64)
        except Exception:
            self._logo_img = None
        if self._logo_img:
            try:
                self.iconphoto(True, tk.PhotoImage(data=logo.ICON_B64))
            except Exception:
                pass

        self._build_splash()
        self._build_login()
        self._build_register()
        self._build_server_dialog()
        self._build_portal()

        self._show_splash()
        self.poll_queue()
        self.after(1500, self._after_splash)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    @staticmethod
    def _read_server():
        try:
            with open(DATA_DIR / "server.txt", "r", encoding="utf-8") as fh:
                value = fh.read().strip()
            if value:
                return value
        except Exception:
            pass
        return API_BASE

    def _save_server(self, value):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "server.txt", "w", encoding="utf-8") as fh:
            fh.write(value.strip() or API_BASE)

    def poll_queue(self):
        try:
            while True:
                fn = self._bg_tasks.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(80, self.poll_queue)

    def bg(self, fn, on_done, *args):
        def worker():
            try:
                result = fn(*args)
                err = None
            except Exception as exc:
                result = None
                err = exc
            self._bg_tasks.put(lambda: on_done(result, err))

        threading.Thread(target=worker, daemon=True).start()

    def clear(self, *frames):
        for f in frames:
            f.pack_forget()

    def _logo_label(self, parent, pady):
        if self._logo_img:
            return tk.Label(parent, image=self._logo_img, bg=BG)
        return tk.Label(parent, text="⚡", bg=BG, fg=ACCENT, font=("Segoe UI", 30))

    def _show_splash(self):
        self.splash.pack(fill="both", expand=True)
        for s in (self.login, self.register, self.portal):
            s.pack_forget()

    def _after_splash(self):
        saved = creds.load()
        if saved and saved["token"]:
            self.api.set_token(saved["token"])
            self.bg(self.api.me, self._me_done)
        else:
            self._show_login()

    def _me_done(self, result, err):
        if err is None and result:
            self.user = result
            self._show_portal()
        else:
            creds.clear()
            self._show_login()

    def _show_login(self, info=None):
        self.clear(self.splash, self.register, self.portal)
        self.login.pack(fill="both", expand=True)
        if info:
            self.login_info.configure(text=info, fg=OK)
        self.user_entry.focus_set()

    def _show_register(self):
        self.clear(self.splash, self.login, self.portal)
        self.register.pack(fill="both", expand=True)
        self.reg_user.focus_set()

    def _show_portal(self):
        self.clear(self.splash, self.login, self.register)
        self.portal.pack(fill="both", expand=True)
        self._refresh_portal()

    def _build_splash(self):
        self.splash = tk.Frame(self, bg=BG)
        self._logo_label(self.splash, pady=(180, 4)).pack(pady=(180, 4))
        tk.Label(self.splash, text="USB FIX", bg=BG, fg=TEXT, font=self._font_title).pack()
        tk.Label(self.splash, text="USB remoto por assinatura", bg=BG, fg=MUTED, font=self._font_small).pack(pady=(2, 0))
        bar = tk.Frame(self.splash, bg=BG)
        bar.pack(pady=30)
        self._spinner = tk.Canvas(bar, width=18, height=18, bg=BG, highlightthickness=0)
        self._spinner.pack(pady=20)

    def _draw_spinner(self, i=0):
        self._spinner.delete("all")
        for j in range(8):
            color = ACCENT if j == i % 8 else PANEL2
            self._spinner.create_oval(2 + j * 2, 0, 6 + j * 2, 4, fill=color, outline="")
        self.after(90, lambda: self._draw_spinner(i + 1))

    def _build_login(self):
        self.login = tk.Frame(self, bg=BG)
        pad = tk.Frame(self.login, bg=BG, width=380)
        pad.pack(fill="both", expand=True, padx=40)

        self._logo_label(pad, pady=(44, 0)).pack(pady=(44, 0))
        tk.Label(pad, text="USB FIX", bg=BG, fg=TEXT, font=self._font_title).pack(pady=(4, 2))
        tk.Label(pad, text="Entre com sua conta", bg=BG, fg=MUTED, font=self._font_small).pack(pady=(0, 16))

        self.login_err = tk.Label(pad, text="", bg=BG, fg=ERR, font=self._font_small, wraplength=340, justify="left")
        self.login_err.pack(fill="x", pady=(0, 4))
        self.login_info = tk.Label(pad, text="", bg=BG, fg=OK, font=self._font_small, wraplength=340, justify="left")
        self.login_info.pack(fill="x", pady=(0, 4))

        tk.Label(pad, text="E-mail", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.user_entry = tk.Entry(pad, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                                   font=("Consolas", 13), highlightthickness=1, highlightbackground=PANEL2)
        self.user_entry.pack(fill="x", pady=(2, 6), ipady=7)

        tk.Label(pad, text="Senha", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.pass_entry = tk.Entry(pad, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", show="•",
                                   font=("Consolas", 13), highlightthickness=1, highlightbackground=PANEL2)
        self.pass_entry.pack(fill="x", pady=(2, 10), ipady=7)
        self.pass_entry.bind("<Return>", lambda e: self._do_login())

        self.btn_login = tk.Button(pad, text="Entrar", command=self._do_login,
                                   bg=ACCENT, fg="white", activebackground=ACCENT_DARK,
                                   activeforeground="white", relief="flat", font=self._font_btn, cursor="hand2")
        self.btn_login.pack(fill="x", ipady=10, pady=(4, 8))

        link_register = tk.Label(pad, text="Não tem conta? Criar conta", bg=BG, fg=ACCENT,
                                 font=self._font_small, cursor="hand2")
        link_register.pack(pady=(4, 0))
        link_register.bind("<Button-1>", lambda e: self._show_register())

        self.link_server = tk.Label(pad, text="Servidor", bg=BG, fg=MUTED, font=self._font_small, cursor="hand2")
        self.link_server.pack(side="bottom", pady=(0, 26))
        self.link_server.bind("<Button-1>", lambda e: self._open_server_dialog())

    def _build_register(self):
        self.register = tk.Frame(self, bg=BG)
        pad = tk.Frame(self.register, bg=BG, width=380)
        pad.pack(fill="both", expand=True, padx=40)

        self._logo_label(pad, pady=(44, 0)).pack(pady=(44, 0))
        tk.Label(pad, text="CRIAR CONTA", bg=BG, fg=TEXT, font=self._font_title).pack(pady=(4, 2))
        tk.Label(pad, text="A conta fica ativa após a liberação do vendedor",
                 bg=BG, fg=MUTED, font=self._font_small).pack(pady=(0, 16))

        self.reg_err = tk.Label(pad, text="", bg=BG, fg=ERR, font=self._font_small, wraplength=340, justify="left")
        self.reg_err.pack(fill="x", pady=(0, 4))

        tk.Label(pad, text="E-mail", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_user = tk.Entry(pad, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                                 font=("Consolas", 13), highlightthickness=1, highlightbackground=PANEL2)
        self.reg_user.pack(fill="x", pady=(2, 6), ipady=7)

        tk.Label(pad, text="Senha", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_pass = tk.Entry(pad, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", show="•",
                                 font=("Consolas", 13), highlightthickness=1, highlightbackground=PANEL2)
        self.reg_pass.pack(fill="x", pady=(2, 6), ipady=7)

        tk.Label(pad, text="Confirmar senha", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_pass2 = tk.Entry(pad, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", show="•",
                                  font=("Consolas", 13), highlightthickness=1, highlightbackground=PANEL2)
        self.reg_pass2.pack(fill="x", pady=(2, 10), ipady=7)
        self.reg_pass2.bind("<Return>", lambda e: self._do_register())

        self.btn_register = tk.Button(pad, text="Criar conta", command=self._do_register,
                                      bg=ACCENT, fg="white", activebackground=ACCENT_DARK,
                                      activeforeground="white", relief="flat", font=self._font_btn, cursor="hand2")
        self.btn_register.pack(fill="x", ipady=10, pady=(4, 8))

        back = tk.Label(pad, text="Já tenho conta — voltar ao login", bg=BG, fg=MUTED,
                        font=self._font_small, cursor="hand2")
        back.pack(pady=(4, 0))
        back.bind("<Button-1>", lambda e: self._show_login())

    def _do_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self._login_err("Digite e-mail e senha.")
            return
        self.btn_login.configure(state="disabled", text="Entrando…")
        self.login_err.configure(text="")
        self.login_info.configure(text="")
        self.bg(self.api.login, self._on_login, username, password)

    def _on_login(self, payload, err):
        self.btn_login.configure(state="normal", text="Entrar")
        if err:
            self._login_err(f"⚠ {err}")
            return
        self.api.set_token(payload["token"])
        creds.save(payload["token"], self.user_entry.get().strip())
        self.user = payload["user"]
        self._show_portal()

    def _login_err(self, msg):
        self.login_err.configure(text=f"⚠ {msg}")

    def _do_register(self):
        username = self.reg_user.get().strip()
        password = self.reg_pass.get()
        confirm = self.reg_pass2.get()
        if not username or not password:
            self.reg_err.configure(text="⚠ Preencha todos os campos.")
            return
        if password != confirm:
            self.reg_err.configure(text="⚠ As senhas não conferem.")
            return
        self.reg_user_prev = username
        self.btn_register.configure(state="disabled", text="Criando…")
        self.reg_err.configure(text="")
        self.bg(self.api.register, self._on_register, username, password)

    def _on_register(self, payload, err):
        self.btn_register.configure(state="normal", text="Criar conta")
        if err:
            self.reg_err.configure(text=f"⚠ {err}")
            return
        self.reg_user.set("")
        self.reg_pass.set("")
        self.reg_pass2.set("")
        self.user_entry.delete(0, "end")
        self.user_entry.insert(0, self.reg_user_prev or "")
        self._show_login("✓ " + payload.get("message", "conta criada — aguarde a liberação do vendedor."))

    def _build_server_dialog(self):
        self.server_dialog = tk.Toplevel(self)
        self.server_dialog.withdraw()
        self.server_dialog.title("Servidor")
        self.server_dialog.configure(bg=BG)
        self.server_dialog.resizable(False, False)
        tk.Label(self.server_dialog, text="Endereço do servidor (API)", bg=BG, fg=MUTED,
                 font=self._font_small).pack(padx=16, pady=(14, 2), anchor="w")
        self.server_entry = tk.Entry(self.server_dialog, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                                     relief="flat", font=self._font_body, highlightthickness=1,
                                     highlightbackground=PANEL2, width=40)
        self.server_entry.pack(padx=16, pady=(0, 10))
        row = tk.Frame(self.server_dialog, bg=BG)
        row.pack(padx=16, pady=(0, 14), fill="x")
        tk.Button(row, text="Cancelar", command=self.server_dialog.withdraw, bg=PANEL2, fg=TEXT,
                  relief="flat", font=self._font_small).pack(side="left")
        tk.Button(row, text="Salvar e reconectar", command=self._save_server_dialog, bg=ACCENT, fg="white",
                  relief="flat", font=self._font_small).pack(side="right")
        self.server_dialog.transient(self)

    def _open_server_dialog(self):
        self.server_entry.delete(0, "end")
        self.server_entry.insert(0, self.api.base)
        self.server_dialog.deiconify()
        self.server_dialog.lift()
        self.server_entry.focus_set()

    def _save_server_dialog(self):
        value = self.server_entry.get().strip()
        self._save_server(value)
        self.api = Api(value or API_BASE)
        saved = creds.load()
        if saved:
            self.api.set_token(saved["token"])
        self.server_dialog.withdraw()
        self.login_err.configure(text="")
        self.bg(self.api.me, self._me_done)

    def _build_portal(self):
        self.portal = tk.Frame(self, bg=BG)
        pad = tk.Frame(self.portal, bg=BG)
        pad.pack(fill="both", expand=True, padx=28, pady=18)

        head = tk.Frame(pad, bg=BG)
        head.pack(fill="x")
        self.portal_name = tk.Label(head, text="—", bg=BG, fg=TEXT, font=self._font_h1)
        self.portal_name.pack(side="left")
        self.pill = tk.Label(head, text="offline", bg=WARN, fg="#201500", font=self._font_small, padx=10, pady=3)
        self.pill.pack(side="right")

        self.key_lbl = tk.Label(pad, text="", bg=BG, fg=MUTED, font=self._font_small, anchor="w")
        self.key_lbl.pack(fill="x", pady=(4, 0))
        self.trial_lbl = tk.Label(pad, text="", bg=BG, fg=OK, font=self._font_small, anchor="w")
        self.trial_lbl.pack(fill="x", pady=(0, 6))

        tk.Label(pad, text="Endereço do seu túnel", bg=BG, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x", pady=(6, 2))
        endpoint = tk.Frame(pad, bg=PANEL)
        endpoint.pack(fill="x", pady=(0, 10))
        self.endpoint_lbl = tk.Label(endpoint, text="—", bg=PANEL, fg=TEXT, font=self._font_body,
                                     padx=12, pady=9, anchor="w")
        self.endpoint_lbl.pack(side="left", fill="x", expand=True)
        self.copy_btn = tk.Button(endpoint, text="Copiar", command=self._copy_endpoint, bg=PANEL2, fg=TEXT,
                                  activebackground="#2a2440", activeforeground=TEXT, relief="flat",
                                  font=self._font_small, cursor="hand2", padx=12)
        self.copy_btn.pack(side="right", ipady=8)

        cfg = tk.Frame(pad, bg=PANEL)
        cfg.pack(fill="x", pady=(0, 10))
        tk.Label(cfg, text="Escolha o nome do seu DNS", bg=PANEL, fg=MUTED, font=self._font_small, anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        subrow = tk.Frame(cfg, bg=PANEL)
        subrow.pack(fill="x", padx=12, pady=(0, 10))
        self.sub_inp = tk.Entry(subrow, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                                font=self._font_small, highlightthickness=0)
        self.sub_inp.pack(side="left", fill="x", expand=True, ipady=5)
        self.sub_suffix = tk.Label(subrow, text="", bg=PANEL, fg=MUTED, font=self._font_small)
        self.sub_suffix.pack(side="left", padx=6)
        self.sub_save = tk.Button(subrow, text="Salvar", command=self._save_subdomain, bg=ACCENT, fg="white",
                                  activebackground=ACCENT_DARK, activeforeground="white", relief="flat",
                                  font=self._font_small, cursor="hand2", padx=10)
        self.sub_save.pack(side="right")
        self.sub_msg = tk.Label(cfg, text="", bg=PANEL, fg=TEXT, font=self._font_small, anchor="w")
        self.sub_msg.pack(fill="x", padx=12, pady=(0, 10))

        cards = tk.Frame(pad, bg=BG)
        cards.pack(fill="x", pady=(0, 10))
        self.card_port = self._mini_card(cards, "PORTA PÚBLICA")
        self.card_usb = self._mini_card(cards, "USB LOCAL")
        self.card_sub = self._mini_card(cards, "VALIDADE")

        usbrow = tk.Frame(pad, bg=BG)
        usbrow.pack(fill="x", pady=(0, 10))
        tk.Label(usbrow, text="Porta local do USB Redirector", bg=BG, fg=MUTED, font=self._font_small).pack(side="left")
        self.local_port_var = tk.StringVar(value=os.getenv("TUNNEL_LOCAL_PORT", "32038"))
        self.local_port_entry = tk.Entry(usbrow, textvariable=self.local_port_var, bg=PANEL2, fg=TEXT,
                                         insertbackground=TEXT, relief="flat", justify="center",
                                         font=("Consolas", 10), highlightthickness=0, width=8)
        self.local_port_entry.pack(side="right", ipady=4)

        self.btn_conn = tk.Button(pad, text="Conectar", command=self._toggle_connect, bg=ACCENT, fg="white",
                                  activebackground=ACCENT_DARK, activeforeground="white", relief="flat",
                                  font=self._font_btn, cursor="hand2")
        self.btn_conn.pack(fill="x", ipady=10, pady=(0, 4))
        self.conn_err = tk.Label(pad, text="", bg=BG, fg=ERR, font=self._font_small, wraplength=380, justify="left")
        self.conn_err.pack(fill="x", pady=(0, 6))

        hist_head = tk.Frame(pad, bg=BG)
        hist_head.pack(fill="x")
        tk.Label(hist_head, text="Histórico de conexões", bg=BG, fg=MUTED, font=self._font_small).pack(side="left")
        self.hist_lbl = tk.Label(hist_head, text="", bg=BG, fg=MUTED, font=self._font_small)
        self.hist_lbl.pack(side="right")

        self.hist_box = tk.Frame(pad, bg=BG)
        self.hist_box.pack(fill="both", expand=True, pady=(4, 8))

        foot = tk.Frame(pad, bg=BG)
        foot.pack(fill="x")
        change_lbl = tk.Label(foot, text="Trocar conta", bg=BG, fg=ERR, font=self._font_small, cursor="hand2")
        change_lbl.pack(side="left")
        change_lbl.bind("<Button-1>", lambda e: self._change_user())
        self.change_btn = tk.Button(foot, text="Atualizar", bg=PANEL2, fg=TEXT, activebackground="#2a2440",
                                    relief="flat", font=self._font_small, command=self._renew)
        self.change_btn.pack(side="right")

    def _mini_card(self, parent, title):
        card = tk.Frame(parent, bg=PANEL, width=110)
        card.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=10)
        tk.Label(card, text=title, bg=PANEL, fg=MUTED, font=self._font_small).pack(pady=(8, 2))
        value = tk.Label(card, text="—", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold"))
        value.pack(padx=8)
        return value

    def _com_number(self, value):
        digits = "".join(c for c in value if c.isdigit())
        return int(digits) if digits else 32038

    def _refresh_portal(self):
        self.bg(self._fetch_state, self._render_state)

    def _fetch_state(self):
        me = self.api.me()
        return {"user": me, "sessions": self.api.sessions()}

    def _render_state(self, data, err):
        if err:
            self.conn_err.configure(text=f"⚠ {err}")
            return
        self.user = data["user"]
        u = self.user
        domain = u["endpoint"].split(".", 1)[-1] if u.get("endpoint") else ""
        self.portal_name.configure(text="Meu túnel")
        self.endpoint_lbl.configure(text=f"{u['endpoint']}:{u['port']}" if u.get("endpoint") else "—:—")
        self.key_lbl.configure(text=f"Conta: {u.get('email') or u['username']}")
        self.sub_inp.delete(0, "end")
        self.sub_inp.insert(0, u["subdomain"] or "")
        self.sub_suffix.configure(text=f".{domain}" if domain else "")
        self.card_port.configure(text=str(u["port"]) if u.get("port") else "—")
        self.card_usb.configure(text=self.local_port_var.get() or "—")
        self.card_sub.configure(text=self._format_valid(u))
        self._render_valid(u)
        self._render_history(data["sessions"])
        self._update_pill()

    def _format_valid(self, u):
        valid = u.get("validUntil") or ""
        return valid.replace("T", " ")[:10] if valid else "—"

    def _render_valid(self, u):
        status = u["status"]
        if status == "active":
            self.trial_lbl.configure(text=f"Ativo até {self._format_valid(u)} · trocas de nome: {u['changesLeft']}")
        elif status == "pending":
            self.trial_lbl.configure(text="⏳ Conta criada — aguardando liberação do vendedor.", fg=WARN)
        elif status in ("blocked", "expired"):
            self.trial_lbl.configure(text="⚠ Conta suspensa — regularize com o fornecedor.", fg=ERR)
        else:
            self.trial_lbl.configure(text=status)

    def _render_history(self, sessions):
        for child in self.hist_box.winfo_children():
            child.destroy()
        if not sessions:
            tk.Label(self.hist_box, text="Sem conexões ainda.", bg=BG, fg=MUTED, font=self._font_small).pack(anchor="w")
            self.hist_lbl.configure(text="")
            return
        self.hist_lbl.configure(text=f"{len(sessions)} conexões")
        for s in sessions[:8]:
            when = s["started_at"].replace("T", " ")[:16]
            ip = s.get("client_ip") or "—"
            tk.Label(self.hist_box, text=f"{when}  ·  {ip}  ·  {s['status']}",
                     bg=BG, fg=TEXT, font=self._font_small, anchor="w").pack(fill="x", pady=1)

    def _copy_endpoint(self):
        self.clipboard_clear()
        self.clipboard_append(self.endpoint_lbl.cget("text"))
        self.copy_btn.configure(text="✓ Copiado")
        self.after(1200, lambda: self.copy_btn.configure(text="Copiar"))

    def _save_subdomain(self):
        value = self.sub_inp.get().strip()
        if not value:
            return
        self.sub_save.configure(state="disabled")
        self.bg(self.api.set_subdomain, self._on_subdomain, value)

    def _on_subdomain(self, user, err):
        self.sub_save.configure(state="normal")
        if err:
            self.sub_msg.configure(text=f"⚠ {err}", fg=ERR)
            return
        self.sub_msg.configure(text="Nome atualizado!", fg=OK)
        self.user = user
        self._refresh_portal()

    def _toggle_connect(self):
        if self.tunnel.is_running():
            self.conn_err.configure(text="")
            self.tunnel.stop()
            self.bg(self.api.tunnel_event, lambda r, e: None, "disconnect")
            return
        com = self.local_port_var.get()
        local_port = self._com_number(com)
        if not local_port:
            self.conn_err.configure(text="⚠ Informe uma porta local válida.")
            return
        if not self.user:
            return
        if self.user.get("status") != "active":
            self.conn_err.configure(text="⚠ Sua conta está pendente, suspensa ou expirada.")
            return
        try:
            self.tunnel.start(self.user, local_port)
            self.conn_err.configure(text="")
            self.bg(self.api.tunnel_event, lambda r, e: None, "connect")
        except Exception as exc:
            self.conn_err.configure(text=f"⚠ {exc}")

    def _on_tunnel_change(self, running):
        self.after(0, self._update_pill)

    def _update_pill(self):
        running = self.tunnel.is_running()
        self.btn_conn.configure(text="Desconectar" if running else "Conectar",
                                bg=ACCENT_DARK if running else ACCENT,
                                activebackground=ACCENT if running else ACCENT_DARK)
        if running:
            self.pill.configure(text="online", bg=OK, fg="#00241a")
        elif self.user and self.user.get("status") in ("blocked", "expired", "unused", "pending"):
            self.pill.configure(text="suspensa", bg=ERR, fg="white")
        else:
            self.pill.configure(text="offline", bg=WARN, fg="#201500")

    def _change_user(self):
        self.tunnel.stop()
        creds.clear()
        self.user_entry.delete(0, "end")
        self.pass_entry.delete(0, "end")
        self._show_login()

    def _renew(self):
        saved = creds.load()
        if not saved:
            self._show_login()
            return
        self.bg(self.api.me, self._me_done)

    def _on_close(self):
        self.tunnel.stop()
        self.destroy()


def main():
    app = App()
    app._draw_spinner()
    app.mainloop()


if __name__ == "__main__":
    main()