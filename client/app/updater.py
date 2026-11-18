import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .config import VERSION


def parse_version(text):
    parts = (text or "").strip().split(".")
    nums = []
    for part in parts:
        buf = ""
        for ch in part:
            if ch.isdigit():
                buf += ch
            else:
                break
        nums.append(int(buf or 0))
    return tuple(nums)


def newer(remote):
    return bool(remote) and parse_version(remote) > parse_version(VERSION)


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def current_exe():
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(__file__).resolve().parent.parent / "main.py"


def new_binary_path():
    return current_exe().with_name(current_exe().name + ".new")


def download(url, dest, progress=None):
    if not dest.name.endswith(".new"):
        dest = dest.with_name(dest.name + ".new")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "USB FIX updater"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(part, "wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        progress(done, total)
        if total and done != total:
            raise IOError(f"Download incompleto: {done} de {total} bytes")
        if done < 1024 * 1024:
            raise IOError("Arquivo baixado muito pequeno; atualização cancelada.")
        with open(part, "rb") as fh:
            if fh.read(2) != b"MZ":
                raise IOError("O arquivo recebido não é um executável Windows válido.")
        shutil.move(str(part), str(dest))
        return dest
    except Exception:
        try:
            part.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def prepare_relaunch(new_file):
    if not is_frozen():
        return None
    target = current_exe()
    name = target.name
    backup = target.with_name(target.name + ".previous")
    bat = target.with_name("_update_usbfix.bat")
    body = (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%%~dp0\"\r\n"
        "set /a tries=0\r\n"
        ":wait\r\n"
        "tasklist /FI \"IMAGENAME eq %s\" 2>nul | findstr /I \"%s\" >nul\r\n"
        "if errorlevel 1 goto replace\r\n"
        "set /a tries+=1\r\n"
        "if %%tries%% gtr 30 goto failed\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto wait\r\n"
        ":replace\r\n"
        "if exist \"%s\" del /q \"%s\"\r\n"
        "if exist \"%s\" move /Y \"%s\" \"%s\" >nul\r\n"
        "move /Y \"%s\" \"%s\" >nul 2>&1\r\n"
        "if errorlevel 1 goto rollback\r\n"
        "start \"\" \"%%~dp0%s\"\r\n"
        "start \"\" /b cmd /c \"timeout /t 5 /nobreak >nul & del /q \\\"_update_usbfix.bat\\\"\"\r\n"
        "exit /b 0\r\n"
        ":rollback\r\n"
        "if exist \"%s\" move /Y \"%s\" \"%s\" >nul\r\n"
        "start \"\" \"%%~dp0%s\"\r\n"
        ":failed\r\n"
        "exit /b 1\r\n"
    ) % (name, name, backup.name, backup.name, name, name, backup.name, new_file.name, name,
         name, backup.name, backup.name, name)
    bat.write_text(body, encoding="ascii")
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(target.parent),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return bat
