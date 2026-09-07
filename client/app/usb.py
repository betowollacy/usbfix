import platform
import re


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


def list_ports():
    if platform.system() == "Windows":
        return sorted(set(_windows_serial_ports()), key=_serial_port_number)
    return []