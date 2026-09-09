import re
import socket
import subprocess
import time

SERVICE_NAME = "usbredirectortechssrv"
SERVER_PORT = 32038
USBTECHSH = r"C:\Program Files\USB Redirector Technician Edition\usbtechsh.exe"

_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _sc(*args, timeout=15):
    try:
        return subprocess.run(
            ["sc", *args],
            capture_output=True, timeout=timeout,
            creationflags=_no_window,
        )
    except Exception:
        return None


def list_client_devices():
    """Returns the USB devices currently visible from connected clients.

    Parses `usbtechsh -list devices`. Each entry carries the server and
    device ids needed to connect/disconnect via the CLI:
    {server, device, name, status}
    """
    try:
        proc = subprocess.run(
            [USBTECHSH, "-list", "devices"],
            capture_output=True, timeout=15,
            creationflags=_no_window,
        )
    except Exception:
        return []
    text = (proc.stdout + proc.stderr).decode("latin-1", "replace")
    devices = []
    server = ""
    device = ""
    name = ""
    tree = re.compile(r"^[-\`|\\]*\s*(\d+):\s*(.*)$")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "====" in stripped:
            server, device, name = "", "", ""
            continue
        tm = tree.match(stripped)
        if tm:
            if "USB server at" in stripped:
                server = tm.group(1)
                device, name = "", ""
                continue
            device, name = tm.group(1), tm.group(2).strip()
            continue
        status_match = re.search(r"Status:\s*(\S+)", stripped)
        if status_match:
            status = status_match.group(1).lower()
            if device and status == "connected":
                devices.append({"server": server, "device": device,
                                "name": name, "status": status})
            device, name = "", ""
    return devices


def _cli(*args, timeout=20):
    try:
        proc = subprocess.run(
            [USBTECHSH, *args],
            capture_output=True, timeout=timeout,
            creationflags=_no_window,
        )
        text = (proc.stdout + proc.stderr).decode("latin-1", "replace")
        return (proc.returncode, text)
    except Exception as exc:
        return (-1, str(exc))


def _err_msg(text):
    for line in text.splitlines():
        s = line.strip()
        if not s or "SUCCESSFUL" in s:
            continue
        if s.strip("*").strip("=").strip("-") == "ERROR":
            continue
        if s.upper().startswith("USB REDIRECTOR"):
            continue
        sharp = sum(ch in "*=-" for ch in s)
        if s and sharp >= len(s) * 0.5:
            continue
        return s
    return text.strip().splitlines()[0] if text.strip() else "Erro"


def connect_device(server, device):
    """Connects a remote device using 'usbtechsh -connect <server>-<device>'."""
    rc, text = _cli("-connect", f"{server}-{device}")
    if rc == 0 and "SUCCESSFUL" in text:
        return (True, f"Conectado #{server}-{device}")
    return (False, _err_msg(text))


def disconnect_device(server, device):
    """Disconnects a remote device using 'usbtechsh -disconnect <server>-<device>'."""
    rc, text = _cli("-disconnect", f"{server}-{device}")
    if rc == 0 and "SUCCESSFUL" in text:
        return (True, f"Desconectado #{server}-{device}")
    return (False, _err_msg(text))


def service_running():
    proc = _sc("query", SERVICE_NAME)
    if proc is None:
        return False
    text = (proc.stdout + proc.stderr).decode("latin-1", "replace")
    return "RUNNING" in text.upper()


def start_service():
    _sc("start", SERVICE_NAME)
    for _ in range(40):
        if service_running():
            return True
        time.sleep(0.5)
    return False


def ensure_service_running():
    if service_running():
        return True
    return start_service()


def wait_port_listening(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def check_device(port=SERVER_PORT):
    """Ensures the redirector server service is up and listening on port.

    Returns (ok, message).
    """
    if not ensure_service_running():
        return (False, "Serviço do redirector não iniciou")
    if not wait_port_listening(port, timeout=10):
        return (False, f"Redirector não escutando na porta {port}")
    return (True, "Redirector ativo")