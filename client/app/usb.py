import platform
import re
import subprocess


def _windows_serial_ports():
    import winreg

    ports = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
        for i in range(_key_count(key)):
            try:
                _, value, _ = winreg.EnumValue(key, i)
                ports.append(value)
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        pass
    return ports


def _key_count(key):
    import winreg

    try:
        info = winreg.QueryInfoKey(key)
        return info[1]
    except OSError:
        return 0


def _serial_port_number(port):
    match = re.search(r"(\d+)$", port)
    return int(match.group(1)) if match else 0


def _windows_usb_devices():
    script = (
        "$bytes = [System.Text.Encoding]::Unicode.GetBytes((Get-CimInstance Win32_PnPEntity | "
        "Where-Object { $_.Present -and $_.Name -and $_.DeviceID -match 'USB\\\\VID_' } | "
        "Select-Object -ExpandProperty Name -Unique | Sort-Object) -join \"`n\"); "
        "[Console]::OpenStandardOutput().Write($bytes, 0, $bytes.Length)"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = proc.stdout.decode("utf-16-le", errors="replace")
    except Exception:
        return []
    names = [n.strip() for n in out.splitlines() if n.strip()]
    skip = ("Root Hub", "Composite Device", "Host Controller", "Virtual", "HID", "Event Filter")
    return [n for n in names if not any(s in n for s in skip)]


def list_usb_devices():
    if platform.system() == "Windows":
        return _windows_usb_devices()
    return []


def list_ports():
    if platform.system() == "Windows":
        return sorted(set(_windows_serial_ports()), key=_serial_port_number)
    return []