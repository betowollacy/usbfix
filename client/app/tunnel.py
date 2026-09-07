import subprocess
import threading
import time

from .config import FRPC_EXE, FRPC_TOML, LOG_FILE


def render_frpc_toml(state, local_port):
    user = state.get("user", state)
    proxy_name = "usb-%s" % (user.get("id") or user.get("username") or "dev")
    remote_port = user.get("port") or state.get("port") or 0
    frps = state.get("frps", {})
    addr = frps.get("addr", "127.0.0.1")
    fport = frps.get("port", 7000)
    token = frps.get("token", "")

    lines = [
        f'serverAddr = "{addr}"',
        f"serverPort = {fport}",
        "",
        'auth.method = "token"',
        f'auth.token = "{token}"',
        "",
        "transport.tls.enable = true",
        "",
        'log.to = "console"',
        'log.level = "info"',
        "",
        "[[proxies]]",
        f'name = "{proxy_name}"',
        'type = "tcp"',
        'localIP = "127.0.0.1"',
        f"localPort = {local_port}",
        f"remotePort = {remote_port}",
    ]
    lines.append('metadatas.token = "%s"' % token)
    return "\n".join(lines) + "\n"


class Tunnel:
    def __init__(self):
        self.proc = None
        self._stop = False
        self._thread = None
        self._on_change = None

    def on_change(self, callback):
        self._on_change = callback

    def is_running(self):
        return bool(self.proc) and self.proc.poll() is None

    def start(self, state, local_port):
        if not FRPC_EXE or not __import__("os").path.exists(FRPC_EXE):
            raise FileNotFoundError(f"frpc.exe não encontrado em {FRPC_EXE}")
        self.stop()
        FRPC_TOML.write_text(render_frpc_toml(state, local_port), encoding="utf-8")
        logf = open(LOG_FILE, "a", encoding="utf-8")
        self.proc = subprocess.Popen(
            [FRPC_EXE, "-c", str(FRPC_TOML)],
            stdout=logf,
            stderr=logf,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._stop = False
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()
        self._notify()

    def stop(self):
        self._stop = True
        if self.is_running():
            try:
                self.proc.terminate()
                self.proc.wait(timeout=30)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None
        self._notify()

    def _watch(self):
        while not self._stop and self.is_running():
            time.sleep(0.5)
        self._notify()

    def _notify(self):
        if self._on_change:
            self._on_change(self.is_running())