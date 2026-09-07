import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, messagebox
from urllib import request, error

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

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


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tunnel Admin — usuários")
        self.geometry("780x520")
        self.configure(bg=BG)
        self._tasks = queue.Queue()
        self._font_small = tkfont.Font(family=FONT, size=9)
        self._font_btn = tkfont.Font(family=FONT, size=10, weight="bold")

        cfg = load_config()
        default_srv = cfg.get("servidor") or os.getenv("TUNNEL_API", "http://127.0.0.1:8000")
        default_tok = cfg.get("token") or os.getenv("TUNNEL_ADMIN_TOKEN", "")

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(top, text="Servidor", bg=BG, fg=MUTED, font=self._font_small).grid(row=0, column=0, sticky="w")
        self.srv = tk.Entry(top, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                            font=self._font_small, highlightthickness=1, highlightbackground=PANEL2, width=34)
        self.srv.insert(0, default_srv)
        self.srv.grid(row=1, column=0, sticky="we", padx=(0, 8), ipady=5)

        tk.Label(top, text="Token admin", bg=BG, fg=MUTED, font=self._font_small).grid(row=0, column=1, sticky="w")
        self.tok = tk.Entry(top, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                            font=self._font_small, highlightthickness=1, highlightbackground=PANEL2, width=30)
        self.tok.insert(0, default_tok)
        self.tok.grid(row=1, column=1, sticky="we", padx=(0, 8), ipady=5)

        self.btn_list = tk.Button(top, text="Listar", command=self.load_users, bg=ACCENT, fg="white",
                                  relief="flat", font=self._font_small, cursor="hand2", padx=12)
        self.btn_list.grid(row=1, column=2, padx=(0, 6), ipady=5)
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)

        self.status = tk.Label(self, text="", bg=BG, fg=MUTED, font=self._font_small, anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 6))

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=16)
        self.listbox = tk.Listbox(mid, bg=PANEL2, fg=TEXT, selectbackground=ACCENT, relief="flat",
                                  font=tkfont.Font(family="Consolas", size=9), highlightthickness=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(mid, command=self.listbox.yview, bg=PANEL)
        scroll.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=16, pady=12)
        tk.Label(actions, text="Dias:", bg=BG, fg=MUTED, font=self._font_small).pack(side="left", padx=(0, 6))
        self.days = tk.Spinbox(actions, from_=1, to=365, width=5, bg=PANEL2, fg=TEXT, relief="flat",
                               buttonbackground=PANEL2, highlightthickness=0)
        self.days.delete(0, "end")
        self.days.insert(0, "30")
        self.days.pack(side="left", padx=(0, 8), ipady=3)
        self.btn_approve = tk.Button(actions, text="Liberar licença", command=self.approve_user,
                                     bg=OK, fg="#00241a", relief="flat", font=self._font_small, cursor="hand2")
        self.btn_approve.pack(side="left", padx=(0, 8))
        self.btn_extend = tk.Button(actions, text="Renovar", command=self.extend_user,
                                    bg=ACCENT, fg="white", relief="flat", font=self._font_small, cursor="hand2")
        self.btn_extend.pack(side="left", padx=(0, 8))
        self.btn_block = tk.Button(actions, text="Bloquear", command=self.block_user,
                                   bg=ERR, fg="white", relief="flat", font=self._font_small, cursor="hand2")
        self.btn_block.pack(side="left")
        self.btn_copy = tk.Button(actions, text="Copiar usuário", command=self.copy_username,
                                  bg=PANEL2, fg=TEXT, relief="flat", font=self._font_small, cursor="hand2")
        self.btn_copy.pack(side="right")

        self.users = []
        self.poll_queue()
        self.after(400, self.load_users)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def poll_queue(self):
        try:
            while True:
                fn = self._tasks.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(80, self.poll_queue)

    def bg_call(self, fn, on_done, *args):
        def worker():
            try:
                result = fn(*args)
                err = None
            except Exception as exc:
                result = None
                err = exc
            self._tasks.put(lambda: on_done(result, err))

        threading.Thread(target=worker, daemon=True).start()

    def _req(self, method, path, body=None):
        srv = self.srv.get().strip().rstrip("/")
        tok = self.tok.get().strip()
        save_config({"servidor": srv or "http://127.0.0.1:8000", "token": tok})
        headers = {"Authorization": f"Bearer {tok}"}
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(srv + path, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except error.HTTPError as exc:
            detail = "erro do servidor"
            try:
                detail = json.loads(exc.read()).get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(f"{exc.code}: {detail}")

    def load_users(self):
        self.status.configure(text="carregando…", fg=MUTED)
        self.bg_call(self._req, self._on_load, "GET", "/api/admin/users")

    def _on_load(self, rows, err):
        if err:
            self.status.configure(text=f"⚠ {err}", fg=ERR)
            return
        self.users = rows or []
        self._fill_list()
        self.status.configure(text=f"{len(self.users)} usuários carregados", fg=OK)

    def _fill_list(self):
        self.listbox.delete(0, "end")
        for k in self.users:
            valid = (k.get("validUntil") or "—").replace("T", " ")[:10]
            sub = k.get("subdomain") or "—"
            port = k.get("port") or "—"
            status = k["statusRaw"]
            marker = {"pending": "⏳", "active": "✓", "blocked": "⛔", "expired": "!?"}.get(status, "?")
            line = (f"{marker} {k['username']:<22} {status:<8}  "
                    f"{sub}.{self._domain(k)}  :{port}   até {valid}")
            self.listbox.insert("end", line)

    def _domain(self, k):
        ep = k.get("endpoint") or ""
        return ep.split(".", 1)[-1] if "." in ep else ""

    def approve_user(self):
        self._selected_action(lambda name: self._req("POST", "/api/admin/users/approve",
                                                     {"username": name, "days": int(self.days.get() or 30)}))

    def extend_user(self):
        self._selected_action(lambda name: self._req("POST", "/api/admin/users/extend",
                                                     {"username": name, "days": int(self.days.get() or 30)}))

    def block_user(self):
        self._selected_action(lambda name: self._req("POST", "/api/admin/users/block", {"username": name}))

    def _selected_action(self, fn):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Tunnel Admin", "Selecione um usuário.")
            return
        row = self.users[sel[0]]
        name = row["username"]
        self.status.configure(text=f"processando {name}…", fg=MUTED)
        self.bg_call(fn, lambda r, e: self._after_action(r, e), name)

    def _after_action(self, result, err):
        if err:
            self._status_err(err)
            return
        self.status.configure(text="ok", fg=OK)
        self.load_users()

    def _status_err(self, err):
        self.status.configure(text=f"⚠ {err}", fg=ERR)

    def copy_username(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        row = self.users[sel[0]]
        self.clipboard_clear()
        self.clipboard_append(row["username"])
        self.status.configure(text=f"copiado: {row['username']}", fg=OK)


if __name__ == "__main__":
    AdminApp().mainloop()