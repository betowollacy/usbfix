import base64
import io
import os
import queue
import threading
import tkinter as tk
import uuid

import customtkinter as ctk
from PIL import Image
from tkinter import messagebox

from . import creds, logo, usb
from .api import Api, ApiError
from .config import API_BASE, APP_NAME, DATA_DIR, VERSION
from .tunnel import Tunnel
from . import updater

BG = "#0f0d15"
PANEL = "#171422"
PANEL2 = "#1e192e"
HEADER_BG = "#151229"
LINE = "#2a2440"
ACCENT = "#7c5cff"
ACCENT_DARK = "#5e44d6"
TEXT = "#eceaf2"
MUTED = "#8a87a0"
OK = "#38d99a"
ERR = "#ff5c7a"
WARN = "#ffb454"

FONT = "Segoe UI"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("USB FIX")
        w, h = 380, 560
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2 - 20}")
        self.minsize(355, 500)
        self.withdraw()
        self.configure(fg_color=BG)
        self.api = Api(self._read_server())
        self.tunnel = Tunnel()
        self.tunnel.on_change(self._on_tunnel_change)
        self.user = None
        self._hb_on = False
        self._update_checked = False
        self._updating = False
        self._update_data = None
        self.instance = self._load_instance()
        self._bg_tasks = queue.Queue()
        self._font_title = ctk.CTkFont(family=FONT, size=19, weight="bold")
        self._font_h1 = ctk.CTkFont(family=FONT, size=16, weight="bold")
        self._font_h2 = ctk.CTkFont(family=FONT, size=13, weight="bold")
        self._font_body = ctk.CTkFont(family=FONT, size=10)
        self._font_small = ctk.CTkFont(family=FONT, size=9)
        self._font_btn = ctk.CTkFont(family=FONT, size=10, weight="bold")
        self._font_mono = ctk.CTkFont(family="Consolas", size=12)

        self._logo_img = None
        try:
            raw = base64.b64decode(logo.LOGO_B64)
            img = Image.open(io.BytesIO(raw))
            w, h = img.size
            ch = 26
            self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(int(w * ch / h), ch))
        except Exception:
            self._logo_img = None
        try:
            raw = base64.b64decode(logo.LOGO_B64)
            img = Image.open(io.BytesIO(raw))
            w, h = img.size
            ch = 46
            self._splash_logo = ctk.CTkImage(light_image=img, dark_image=img, size=(int(w * ch / h), ch))
        except Exception:
            self._splash_logo = None
        try:
            self.iconphoto(True, tk.PhotoImage(data=logo.ICON_B64))
            self._icon16 = tk.PhotoImage(data=logo.ICON_B64)
            self.iconphoto(False, self._icon16)
        except Exception:
            pass

        self._build_splash_win()
        self._build_login()
        self._build_register()
        self._build_server_dialog()
        self._build_portal()

        self._open_splash()
        self.poll_queue()
        self.after(1500, self._after_splash)
        self.after(3000, self._check_update)
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

    def _load_instance(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            p = DATA_DIR / "instance.txt"
            value = p.read_text(encoding="utf-8").strip()
            if value:
                return value
        except Exception:
            pass
        value = uuid.uuid4().hex
        try:
            (DATA_DIR / "instance.txt").write_text(value, encoding="utf-8")
        except Exception:
            pass
        return value

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

    def _logo_pack(self, parent):
        if self._logo_img:
            return ctk.CTkLabel(parent, text="", image=self._logo_img, fg_color="transparent")
        return ctk.CTkLabel(parent, text="⚡", text_color=ACCENT, font=("Segoe UI", 24))

    def _head_bar(self, parent, right_builder=None):
        bar = ctk.CTkFrame(parent, fg_color=HEADER_BG, corner_radius=0)
        bar.pack(fill="x", side="top")
        row = ctk.CTkFrame(bar, fg_color=HEADER_BG, corner_radius=0)
        row.pack(fill="x", padx=24, pady=(13, 13))
        self._logo_pack(row).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row, text="USB FIX", text_color=TEXT, font=self._font_h2).pack(side="left")
        ctk.CTkLabel(row, text="acesso remoto USB", text_color=MUTED,
                     font=self._font_small).pack(side="left", padx=(12, 0), pady=(5, 0))
        if right_builder:
            right_builder(row)
        ctk.CTkFrame(parent, height=3, fg_color=ACCENT, corner_radius=0).pack(fill="x", side="top")

    def _add_update_label(self, parent):
        lbl = ctk.CTkLabel(parent, text="", text_color=ACCENT,
                           font=self._font_small, cursor="hand2")
        lbl.pack(side="bottom", pady=(0, 6))
        lbl.bind("<Button-1>", lambda e: self._do_update(lbl))
        return lbl

    def _set_update_text(self, text):
        for w in (self.update_login, self.update_portal):
            if w and w.winfo_exists():
                w.configure(text=text)

    def _check_update(self):
        if self._update_checked or self._updating:
            return
        self._update_checked = True
        self.bg(self.api.downloads, self._on_check_update)

    def _on_check_update(self, data, err):
        if err or not data:
            return
        app = data.get("app") or {}
        version = (app.get("version") or "").strip()
        url = (app.get("url") or "").strip()
        if not version or not url or not updater.newer(version):
            return
        self._update_data = {"version": version, "url": url}
        self._set_update_text(f"★ Nova versão v{version} disponível — atualizar")

    def _do_update(self, lbl=None):
        if self._updating or not self._update_data:
            return
        self._updating = True
        self._set_update_text("Baixando atualização…")
        self.bg(self._download_update, self._on_update_done)

    def _download_update(self):
        url = self._update_data["url"].strip()
        if url.startswith("/"):
            url = self.api.base.rstrip("/") + url
        dest = updater.new_binary_path()
        return updater.download(url, dest)

    def _on_update_done(self, dest, err):
        if err:
            self._updating = False
            self._set_update_text(f"⚠ Falha ao baixar atualização: {err}")
            return
        self._updating = False
        if not self._confirm_update():
            self._set_update_text(f"★ Atualização v{self._update_data['version']} disponível")
            return
        if updater.prepare_relaunch(dest):
            self.after(200, self._on_close)
        else:
            self._set_update_text("Atualização baixada — reabra o app para concluir.")

    def _confirm_update(self):
        if not updater.is_frozen():
            return True
        from tkinter import messagebox
        return messagebox.askyesno(
            "USB FIX",
            f"Nova versão v{self._update_data['version']} baixada.\n\n"
            "O app será fechado e reaberto automaticamente. Continuar?",
            parent=self,
        )

    def _open_splash(self):
        self.withdraw()
        for s in (self.login, self.register, self.portal):
            s.pack_forget()
        self.splash_win.deiconify()
        self.splash_win.lift()
        self._draw_spinner()
        self.after(2600, self._after_splash)

    def _close_splash_win(self):
        if getattr(self, "splash_win", None) and self.splash_win.winfo_exists():
            try:
                self.splash_win.destroy()
            except Exception:
                pass
        self.splash_win = None
        self.deiconify()

    def _after_splash(self):
        saved = creds.load()
        if saved and saved["token"]:
            self.api.set_token(saved["token"])
            self.bg(self.api.me, self._me_done, self.instance)
        else:
            self._close_splash_win()
            self._show_login()

    def _me_done(self, result, err):
        self._close_splash_win()
        if err is None and result:
            self.user = result
            self._show_portal()
        else:
            creds.clear()
            self._show_login()

    def _show_login(self, info=None):
        self.clear(self.register, self.portal)
        self.login.pack(fill="both", expand=True)
        if info:
            self.login_info.configure(text=info, text_color=OK)
        self.user_entry.focus_set()

    def _show_register(self):
        self.clear(self.login, self.portal)
        self.register.pack(fill="both", expand=True)
        self.reg_user.focus_set()

    def _show_portal(self):
        self.clear(self.login, self.register)
        self.portal.pack(fill="both", expand=True)
        self._refresh_portal()

    def _build_splash_win(self):
        self.splash_win = ctk.CTkToplevel(self)
        self.splash_win.withdraw()
        self.splash_win.configure(fg_color=BG)
        self.splash_win.resizable(False, False)
        self.splash_win.overrideredirect(True)
        w, h = 390, 250
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.splash_win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2 - 30}")
        body = ctk.CTkFrame(self.splash_win, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        ctk.CTkFrame(self.splash_win, height=4, fg_color=ACCENT, corner_radius=0).pack(fill="x", side="top")
        ctk.CTkFrame(body, height=52, fg_color=HEADER_BG, corner_radius=0).pack(fill="x", side="top")
        if self._splash_logo:
            ctk.CTkLabel(body, text="", image=self._splash_logo, fg_color="transparent").pack(pady=(6, 0))
        else:
            ctk.CTkLabel(body, text="⚡", text_color=ACCENT, font=("Segoe UI", 26)).pack(pady=(8, 0))
        ctk.CTkLabel(body, text=APP_NAME, text_color=TEXT, font=ctk.CTkFont(family=FONT, size=26, weight="bold")).pack(pady=(6, 0))
        ctk.CTkLabel(body, text="USB remoto por assinatura", text_color=MUTED,
                     font=self._font_small).pack(pady=(2, 14))
        self.spinner = ctk.CTkProgressBar(body, mode="indeterminate", width=150, height=6,
                                          fg_color=PANEL2, progress_color=ACCENT, corner_radius=3)
        self.spinner.pack()
        ctk.CTkLabel(body, text=f"v{VERSION}", text_color="#5a5670",
                     font=self._font_small).pack(side="bottom", pady=(0, 12))
        self.splash_win.protocol("WM_DELETE_WINDOW", lambda: None)

    def _draw_spinner(self):
        bar = getattr(self, "spinner", None)
        if bar and bar.winfo_exists():
            try:
                bar.start()
            except Exception:
                pass

    def _label(self, parent, text, **kw):
        defaults = dict(text_color=TEXT, font=self._font_small, anchor="w")
        defaults.update(kw)
        return ctk.CTkLabel(parent, text=text, **defaults)

    def _entry(self, parent, show=None, **kw):
        defaults = dict(fg_color=PANEL2, border_color=LINE, border_width=1,
                        text_color=TEXT, font=self._font_body, corner_radius=8)
        defaults.update(kw)
        if show:
            defaults["show"] = show
        return ctk.CTkEntry(parent, **defaults)

    def _build_login(self):
        self.login = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._head_bar(self.login)
        pad = ctk.CTkFrame(self.login, fg_color=BG, corner_radius=0)
        pad.pack(fill="both", expand=True, padx=28)
        ctk.CTkFrame(pad, fg_color=BG, corner_radius=0).pack(fill="both", expand=True)
        wrap = ctk.CTkFrame(pad, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", pady=(8, 8))
        ctk.CTkFrame(pad, fg_color=BG, corner_radius=0).pack(fill="both", expand=True)
        card = ctk.CTkFrame(wrap, fg_color=PANEL, corner_radius=14, border_width=1, border_color=LINE)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color=PANEL, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(inner, text="Entrar", text_color=TEXT, font=self._font_h1,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text="Acesse sua conta para conectar seus dispositivos", text_color=MUTED,
                     font=self._font_small, anchor="w").pack(fill="x", pady=(2, 16))

        self.login_err = ctk.CTkLabel(inner, text="", text_color=ERR, font=self._font_small,
                                      wraplength=300, justify="left")
        self.login_err.pack(fill="x", pady=(0, 4))
        self.login_info = ctk.CTkLabel(inner, text="", text_color=OK, font=self._font_small,
                                       wraplength=300, justify="left")
        self.login_info.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(inner, text="Usuário", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.user_entry = self._entry(inner, font=self._font_mono)
        self.user_entry.pack(fill="x", pady=(4, 10), ipady=2)

        ctk.CTkLabel(inner, text="Senha", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.pass_entry = self._entry(inner, show="•", font=self._font_mono)
        self.pass_entry.pack(fill="x", pady=(4, 12), ipady=2)
        self.pass_entry.bind("<Return>", lambda e: self._do_login())

        self.save_login_var = tk.BooleanVar(value=True)
        self.chk_save = ctk.CTkCheckBox(inner, text="Salvar login neste computador", variable=self.save_login_var,
                                        onvalue=True, offvalue=False, fg_color=ACCENT, hover_color=ACCENT_DARK,
                                        checkmark_color="white", border_color=MUTED, text_color=MUTED,
                                        font=self._font_small, corner_radius=6)
        self.chk_save.pack(fill="x", pady=(0, 14))

        self.btn_login = ctk.CTkButton(inner, text="Entrar", command=self._do_login, height=42,
                                       fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                                       font=self._font_btn, corner_radius=10, cursor="hand2")
        self.btn_login.pack(fill="x", pady=(0, 6))

        link_register = ctk.CTkLabel(inner, text="Não tem conta? Criar conta", text_color=ACCENT,
                                     font=self._font_small, cursor="hand2")
        link_register.pack(pady=(10, 0))
        link_register.bind("<Button-1>", lambda e: self._show_register())

        self.link_server = ctk.CTkLabel(self.login, text="Servidor", text_color=MUTED,
                                        font=self._font_small, cursor="hand2")
        self.link_server.pack(side="bottom", pady=(0, 24))
        self.link_server.bind("<Button-1>", lambda e: self._open_server_dialog())
        self.update_login = self._add_update_label(self.login)
        ctk.CTkLabel(self.login, text=f"USB FIX v{VERSION}", text_color="#5a5670",
                     font=self._font_small).pack(side="bottom", pady=(0, 8))

    def _build_register(self):
        self.register = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._head_bar(self.register)
        pad = ctk.CTkFrame(self.register, fg_color=BG, corner_radius=0)
        pad.pack(fill="both", expand=True, padx=28)
        ctk.CTkFrame(pad, fg_color=BG, corner_radius=0).pack(fill="both", expand=True)
        wrap = ctk.CTkFrame(pad, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", pady=(8, 8))
        ctk.CTkFrame(pad, fg_color=BG, corner_radius=0).pack(fill="both", expand=True)
        card = ctk.CTkFrame(wrap, fg_color=PANEL, corner_radius=14, border_width=1, border_color=LINE)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color=PANEL, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=24, pady=22)

        ctk.CTkLabel(inner, text="Criar conta", text_color=TEXT, font=self._font_h1,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text="A conta fica ativa após a liberação do vendedor", text_color=MUTED,
                     font=self._font_small, anchor="w").pack(fill="x", pady=(2, 16))

        self.reg_err = ctk.CTkLabel(inner, text="", text_color=ERR, font=self._font_small,
                                    wraplength=300, justify="left")
        self.reg_err.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(inner, text="Usuário", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_user = self._entry(inner, font=self._font_mono)
        self.reg_user.pack(fill="x", pady=(4, 8), ipady=2)

        ctk.CTkLabel(inner, text="E-mail", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_mail = self._entry(inner, font=self._font_mono)
        self.reg_mail.pack(fill="x", pady=(4, 8), ipady=2)

        ctk.CTkLabel(inner, text="Senha", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x")
        self.reg_pass = self._entry(inner, show="•", font=self._font_mono)
        self.reg_pass.pack(fill="x", pady=(4, 12), ipady=2)
        self.reg_pass.bind("<Return>", lambda e: self._do_register())

        self.btn_register = ctk.CTkButton(inner, text="Criar conta", command=self._do_register, height=42,
                                          fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                                          font=self._font_btn, corner_radius=10, cursor="hand2")
        self.btn_register.pack(fill="x", pady=(2, 6))

        back = ctk.CTkLabel(inner, text="Já tenho conta — voltar ao login", text_color=ACCENT,
                            font=self._font_small, cursor="hand2")
        back.pack(pady=(10, 0))
        back.bind("<Button-1>", lambda e: self._show_login())
        ctk.CTkLabel(self.register, text=f"USB FIX v{VERSION}", text_color="#5a5670",
                     font=self._font_small).pack(side="bottom", pady=(0, 8))

    def _do_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self._login_err("Digite usuário e senha.")
            return
        self.btn_login.configure(state="disabled", text="Entrando…")
        self.login_err.configure(text="")
        self.login_info.configure(text="")
        self.bg(self.api.login, self._on_login, username, password, self.instance)

    def _on_login(self, payload, err):
        self.btn_login.configure(state="normal", text="Entrar")
        if err:
            self._login_err(f"⚠ {err}")
            return
        self.api.set_token(payload["token"])
        creds.save(payload["token"], self.user_entry.get().strip(), remember=self.save_login_var.get())
        self.user = payload["user"]
        self._show_portal()

    def _login_err(self, msg):
        self.login_err.configure(text=f"⚠ {msg}")

    def _do_register(self):
        username = self.reg_user.get().strip()
        email = self.reg_mail.get().strip()
        password = self.reg_pass.get()
        if not username or not email or not password:
            self.reg_err.configure(text="⚠ Preencha usuário, e-mail e senha.")
            return
        self.reg_user_prev = username
        self.btn_register.configure(state="disabled", text="Criando…")
        self.reg_err.configure(text="")
        self.bg(self.api.register, self._on_register, username, password, email)

    def _on_register(self, payload, err):
        self.btn_register.configure(state="normal", text="Criar conta")
        if err:
            self.reg_err.configure(text=f"⚠ {err}")
            return
        self.reg_user.set("")
        self.reg_mail.set("")
        self.reg_pass.set("")
        self.user_entry.delete(0, "end")
        self.user_entry.insert(0, self.reg_user_prev or "")
        self._show_login("✓ " + payload.get("message", "conta criada — aguarde a liberação do vendedor."))

    def _build_server_dialog(self):
        self.server_dialog = ctk.CTkToplevel(self)
        self.server_dialog.withdraw()
        self.server_dialog.title("Servidor")
        self.server_dialog.configure(fg_color=BG)
        self.server_dialog.resizable(False, False)
        ctk.CTkLabel(self.server_dialog, text="Endereço do servidor (API)", text_color=MUTED,
                     font=self._font_small).pack(padx=16, pady=(14, 2), anchor="w")
        self.server_entry = self._entry(self.server_dialog, width=360)
        self.server_entry.pack(padx=16, pady=(0, 12))
        row = ctk.CTkFrame(self.server_dialog, fg_color=BG, corner_radius=0)
        row.pack(padx=16, pady=(0, 14), fill="x")
        ctk.CTkButton(row, text="Cancelar", command=self.server_dialog.withdraw, width=110,
                      fg_color=PANEL2, hover_color="#2a2440", text_color=TEXT,
                      font=self._font_small, corner_radius=8).pack(side="left")
        ctk.CTkButton(row, text="Salvar e reconectar", command=self._save_server_dialog, width=160,
                      fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                      font=self._font_small, corner_radius=8).pack(side="right")
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
        self.bg(self.api.me, self._me_done, self.instance)

    def _box(self, parent, **kw):
        defaults = dict(fg_color=PANEL2, border_color=LINE, border_width=1, corner_radius=10)
        defaults.update(kw)
        return ctk.CTkFrame(parent, **defaults)

    def _build_portal(self):
        self.portal = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._head_bar(self.portal, right_builder=self._pill_builder)

        card = ctk.CTkFrame(self.portal, fg_color=PANEL, corner_radius=14, border_width=1, border_color=LINE)
        card.pack(fill="both", expand=True, padx=22, pady=(18, 10))
        inner = ctk.CTkFrame(card, fg_color=PANEL, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=18, pady=18)

        self.key_lbl = ctk.CTkLabel(inner, text="", text_color=MUTED, font=self._font_small, anchor="w")
        self.key_lbl.pack(fill="x", pady=(0, 2))
        self.trial_lbl = ctk.CTkLabel(inner, text="", text_color=OK, font=self._font_small, anchor="w")
        self.trial_lbl.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(inner, text="Seu endereço", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x", pady=(0, 4))
        endpoint = self._box(inner)
        endpoint.pack(fill="x", pady=(0, 12))
        self.endpoint_lbl = ctk.CTkLabel(endpoint, text="—:—", text_color=TEXT, font=self._font_mono,
                                         anchor="w", padx=14, pady=10)
        self.endpoint_lbl.pack(side="left", fill="x", expand=True)
        self.copy_btn = ctk.CTkButton(endpoint, text="Copiar", command=self._copy_endpoint,
                                      fg_color="transparent", hover_color="#262043", text_color=ACCENT,
                                      font=self._font_small, corner_radius=8, cursor="hand2", anchor="e", width=72)
        self.copy_btn.pack(side="right", padx=(0, 6), pady=6)

        ctk.CTkLabel(inner, text="Escolha seu nome", text_color=MUTED, font=self._font_small, anchor="w").pack(fill="x", pady=(0, 4))
        cfg = self._box(inner)
        cfg.pack(fill="x", pady=(0, 12))
        subrow = ctk.CTkFrame(cfg, fg_color="transparent", corner_radius=0)
        subrow.pack(fill="x", padx=12, pady=8)
        self.sub_inp = ctk.CTkEntry(subrow, fg_color=PANEL, border_width=0, text_color=TEXT,
                                    font=self._font_small, corner_radius=6)
        self.sub_inp.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 8))
        self.sub_suffix = ctk.CTkLabel(subrow, text="", text_color=MUTED, font=self._font_small)
        self.sub_suffix.pack(side="left", padx=(0, 8))
        self.sub_save = ctk.CTkButton(subrow, text="Salvar", command=self._save_subdomain, width=74,
                                      fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                                      font=self._font_small, corner_radius=8, cursor="hand2")
        self.sub_save.pack(side="right")
        self.sub_msg = ctk.CTkLabel(cfg, text="", text_color=TEXT, font=self._font_small, anchor="w")
        self.sub_msg.pack(fill="x", padx=12, pady=(0, 8))

        self.user_sec = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        self.user_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(self.user_sec, text="Usuário de login", text_color=MUTED, font=self._font_small,
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 4))
        userbox = self._box(self.user_sec)
        brows = ctk.CTkFrame(userbox, fg_color="transparent", corner_radius=0)
        brows.pack(fill="x", padx=12, pady=8)
        self.user_inp = ctk.CTkEntry(brows, fg_color=PANEL, border_width=0, text_color=TEXT,
                                     font=self._font_small, corner_radius=6)
        self.user_inp.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 8))
        self.user_save = ctk.CTkButton(brows, text="Definir", command=self._save_my_username, width=74,
                                       fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                                       font=self._font_small, corner_radius=8, cursor="hand2")
        self.user_save.pack(side="right")
        self.user_msg = ctk.CTkLabel(userbox, text="", text_color=MUTED, font=self._font_small, anchor="w")
        self.user_msg.pack(fill="x", padx=12, pady=(0, 8))
        self.userbox = userbox
        self.username_plain = ctk.CTkLabel(self.user_sec, text="", text_color=TEXT,
                                           font=self._font_mono, anchor="w")

        usbrow = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        usbrow.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(usbrow, text="Porta local do USB Redirector", text_color=MUTED,
                     font=self._font_small).pack(side="left")
        self.local_port_var = tk.StringVar(value=os.getenv("TUNNEL_LOCAL_PORT", "32038"))
        self.local_port_entry = ctk.CTkEntry(usbrow, textvariable=self.local_port_var, fg_color=PANEL2,
                                             border_width=0, text_color=TEXT, justify="center",
                                             font=self._font_small, corner_radius=8, width=92)
        self.local_port_entry.pack(side="right", ipady=2)

        self.btn_conn = ctk.CTkButton(inner, text="Conectar", command=self._toggle_connect, height=42,
                                      fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white",
                                      font=self._font_btn, corner_radius=10, cursor="hand2")
        self.btn_conn.pack(fill="x", pady=(0, 4))
        self.conn_err = ctk.CTkLabel(inner, text="", text_color=ERR, font=self._font_small,
                                     wraplength=330, justify="left")
        self.conn_err.pack(fill="x")

        foot = ctk.CTkFrame(self.portal, fg_color="transparent", corner_radius=0)
        foot.pack(fill="x", padx=22)
        self.btn_logout = ctk.CTkButton(foot, text="Sair", command=self._logout, width=88, height=34,
                                        fg_color="#3a1520", hover_color="#4a1f2e", text_color=ERR,
                                        font=self._font_small, corner_radius=8, cursor="hand2")
        self.btn_logout.pack(side="left")
        self.change_btn = ctk.CTkButton(foot, text="Atualizar", command=self._renew, width=110, height=34,
                                        fg_color=PANEL2, hover_color="#2a2440", text_color=TEXT,
                                        font=self._font_small, corner_radius=8, cursor="hand2")
        self.change_btn.pack(side="right")
        self.update_portal = self._add_update_label(self.portal)
        ctk.CTkLabel(self.portal, text=f"USB FIX v{VERSION}", text_color="#5a5670",
                     font=self._font_small).pack(side="bottom", pady=(0, 8))

    def _pill_builder(self, row):
        self.pill = ctk.CTkLabel(row, text="offline", text_color="#201500", fg_color=WARN,
                                 font=self._font_small, corner_radius=999, padx=12, height=26)
        self.pill.pack(side="right")

    def _com_number(self, value):
        digits = "".join(c for c in value if c.isdigit())
        return int(digits) if digits else 32038

    def _refresh_portal(self):
        self.bg(self._fetch_state, self._render_state)

    def _fetch_state(self):
        return {"user": self.api.me(self.instance)}

    def _render_state(self, data, err):
        if err:
            self.conn_err.configure(text=f"⚠ {err}")
            return
        self.user = data["user"]
        u = self.user
        domain = u["endpoint"].split(".", 1)[-1] if u.get("endpoint") else ""
        self.endpoint_lbl.configure(text=f"{u['endpoint']}:{u['port']}" if u.get("endpoint") else "—:—")
        self.key_lbl.configure(text=f"Conta: {u.get('email') or u['username']}")
        self.sub_inp.delete(0, "end")
        self.sub_inp.insert(0, u["subdomain"] or "")
        self.sub_suffix.configure(text=f".{domain}" if domain else "")
        email = (u.get("email") or "").strip().lower()
        if email and u["username"].strip().lower() == email:
            self.username_plain.grid_forget()
            self.user_inp.delete(0, "end")
            self.user_inp.insert(0, u["username"].split("@")[0])
            self.user_msg.configure(text="Entre no app com esse nome após definir.", text_color=MUTED)
            self.userbox.grid(row=1, column=0, sticky="ew")
        else:
            self.userbox.grid_forget()
            self.username_plain.configure(text=f"Usuário de login: {u['username']}")
            self.username_plain.grid(row=1, column=0, sticky="w")
        self._render_valid(u)
        self._update_pill()

    def _format_valid(self, u):
        valid = u.get("validUntil") or ""
        return valid.replace("T", " ")[:10] if valid else "—"

    def _render_valid(self, u):
        status = u["status"]
        if status == "active":
            self.trial_lbl.configure(text=f"Ativo até {self._format_valid(u)} · trocas de nome: {u['changesLeft']}",
                                     text_color=OK)
        elif status == "pending":
            self.trial_lbl.configure(text="⏳ Conta criada — aguardando liberação do vendedor.", text_color=WARN)
        elif status in ("blocked", "expired"):
            self.trial_lbl.configure(text="⚠ Conta suspensa — regularize com o fornecedor.", text_color=ERR)
        else:
            self.trial_lbl.configure(text=status)

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
            self.sub_msg.configure(text=f"⚠ {err}", text_color=ERR)
            return
        self.sub_msg.configure(text="Nome atualizado!", text_color=OK)
        self.user = user
        self._refresh_portal()

    def _save_my_username(self):
        value = self.user_inp.get().strip()
        if not value:
            self.user_msg.configure(text="Digite o nome de usuário desejado.", text_color=ERR)
            return
        self.user_save.configure(state="disabled")
        self.bg(self.api.set_my_username, self._on_my_username, value, self.instance)

    def _on_my_username(self, user, err):
        self.user_save.configure(state="normal")
        if err:
            self.user_msg.configure(text=f"⚠ {err}", text_color=ERR)
            return
        self.user_msg.configure(text="Usuário de login definido!", text_color=OK)
        self.user = user
        self._refresh_portal()

    def _toggle_connect(self):
        if self.tunnel.is_running():
            self.conn_err.configure(text="")
            self._hb_on = False
            self.tunnel.stop()
            self.bg(self.api.tunnel_event, lambda r, e: None, "disconnect", self.instance)
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
            self.bg(self.api.tunnel_event, self._on_tunnel_event, "connect", self.instance)
        except Exception as exc:
            self.conn_err.configure(text=f"⚠ {exc}")

    def _on_tunnel_event(self, result, err):
        if err:
            if self.tunnel.is_running():
                self.tunnel.stop()
            self.conn_err.configure(text=f"⚠ {err}")
            return
        if not self._hb_on:
            self._hb_on = True
            self._heartbeat()

    def _heartbeat(self):
        if not self._hb_on or not self.tunnel.is_running():
            return
        self.bg(self.api.tunnel_event, lambda r, e: None, "connect", self.instance)
        self.after(30000, self._heartbeat)

    def _on_tunnel_change(self, running):
        self.after(0, self._update_pill)

    def _update_pill(self):
        running = self.tunnel.is_running()
        self.btn_conn.configure(text="Desconectar" if running else "Conectar",
                                fg_color=ACCENT_DARK if running else ACCENT,
                                hover_color=ACCENT if running else ACCENT_DARK)
        if running:
            self.pill.configure(text="conectado", text_color="#00241a", fg_color=OK)
            if self.user and self.user.get("endpoint"):
                self.endpoint_lbl.configure(text=f"✓ {self.user['endpoint']}:{self.user.get('port')}",
                                            text_color=OK)
        elif self.user and self.user.get("status") in ("blocked", "expired", "unused", "pending"):
            self.pill.configure(text="suspensa", text_color="white", fg_color=ERR)
        else:
            self.pill.configure(text="offline", text_color="#201500", fg_color=WARN)
            if self.user and self.user.get("endpoint"):
                self.endpoint_lbl.configure(text=f"{self.user['endpoint']}:{self.user.get('port')}",
                                            text_color=TEXT)

    def _logout(self):
        self._hb_on = False
        self.tunnel.stop()
        try:
            threading.Thread(
                target=self.api.tunnel_event, args=("disconnect", self.instance), daemon=True
            ).start()
        except Exception:
            pass
        creds.clear()
        self.user = None
        self.user_entry.delete(0, "end")
        self.pass_entry.delete(0, "end")
        self._show_login()

    def _renew(self):
        saved = creds.load()
        if not saved:
            self._show_login()
            return
        self.bg(self.api.me, self._me_done, self.instance)

    def _on_close(self):
        self._hb_on = False
        self.tunnel.stop()
        try:
            threading.Thread(
                target=self.api.tunnel_event, args=("disconnect", self.instance), daemon=True
            ).start()
        except Exception:
            pass
        self.destroy()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    app = App()
    app._draw_spinner()
    app.mainloop()


if __name__ == "__main__":
    main()