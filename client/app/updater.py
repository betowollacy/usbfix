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
    shutil.move(str(part), str(dest))
    return dest


def prepare_relaunch(new_file):
    if not is_frozen():
        return None
    target = current_exe()
    name = target.name
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
        "if %%tries%% gtr 20 (\r\n"
        "    taskkill /F /IM \"%s\" >nul 2>&1\r\n"
        ")\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto wait\r\n"
        ":replace\r\n"
        "move /Y \"%s\" \"%s\" >nul 2>&1\r\n"
        "start \"\" \"%%~dp0%s\"\r\n"
        "start \"\" /b cmd /c \"timeout /t 3 /nobreak >nul & del /q \\\"_update_usbfix.bat\\\"\"\r\n"
        "exit\r\n"
    ) % (name, name, name, new_file.name, name, name)
    bat.write_text(body, encoding="ascii")
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(target.parent),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return bat