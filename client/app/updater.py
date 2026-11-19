import hashlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .config import VERSION


def parse_version(text):
    """Extrai a primeira versão numérica de textos como 'v1.2.3' ou '0.6.5'."""
    match = re.search(r"\d+(?:\.\d+)*", (text or "").strip())
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(0).split("."))


def _padded(value, size):
    return value + (0,) * max(0, size - len(value))


def newer(remote):
    if not remote:
        return False
    local = parse_version(VERSION)
    remote_v = parse_version(remote)
    size = max(len(local), len(remote_v))
    return _padded(remote_v, size) > _padded(local, size)


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def current_exe():
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(__file__).resolve().parent.parent / "main.py"


def new_binary_path():
    return current_exe().with_name(current_exe().name + ".new")


def validate_binary(binary):
    """Testa o executável novo antes de permitir a troca do aplicativo atual."""
    binary = Path(binary)
    test_exe = binary.with_name(f".{binary.stem}.validation.exe")
    try:
        shutil.copy2(binary, test_exe)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [str(test_exe), "--selftest"],
            cwd=str(test_exe.parent),
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=flags,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"O novo executável não passou no teste de inicialização "
                f"(código {result.returncode}). {detail}"
            )
        return True
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("O teste do novo executável excedeu 60 segundos.") from exc
    finally:
        try:
            test_exe.unlink(missing_ok=True)
        except Exception:
            pass


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, dest, progress=None, stage=None, sha256=None, retries=3):
    """Baixa o novo binário com progresso, retry e validação.

    ``progress`` recebe (done, total, speed_bps, eta_seconds).
    ``stage`` recebe mensagens de etapa para a interface.
    """
    if not dest.name.endswith(".new"):
        dest = dest.with_name(dest.name + ".new")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    def notify_stage(message):
        if stage:
            try:
                stage(message)
            except Exception:
                pass

    def cleanup():
        for temporary in (part, dest):
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass

    for attempt in range(1, max(1, retries) + 1):
        notify_stage("Conectando ao servidor…" if attempt == 1
                     else f"Nova tentativa {attempt} de {retries}…")
        try:
            cleanup()
            req = urllib.request.Request(
                url, method="GET", headers={"User-Agent": "USB FIX updater"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                started = time.monotonic()
                last_emit = 0.0

                notify_stage("Baixando a nova versão…")
                with open(part, "wb") as fh:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if progress and (now - last_emit >= 0.08 or (total and done == total)):
                            elapsed = max(now - started, 0.001)
                            speed = done / elapsed
                            eta = (total - done) / speed if speed > 0 and total else 0.0
                            progress(done, total, speed, eta)
                            last_emit = now

            if total and done != total:
                raise IOError(f"Download incompleto: {done} de {total} bytes")
            if done < 1024 * 1024:
                raise IOError("Arquivo baixado muito pequeno; atualização cancelada.")
            with open(part, "rb") as fh:
                if fh.read(2) != b"MZ":
                    raise IOError("O arquivo recebido não é um executável Windows válido.")

            expected = (sha256 or "").strip().lower()
            if expected:
                notify_stage("Verificando integridade do arquivo…")
                actual = _sha256_file(part)
                if actual != expected:
                    raise IOError(
                        "O hash do arquivo não confere. A atualização foi cancelada por segurança."
                    )

            notify_stage("Validando o executável…")
            shutil.move(str(part), str(dest))
            validate_binary(dest)
            notify_stage("Pronto. Reiniciando o USB FIX…")
            return dest
        except Exception:
            cleanup()
            if attempt >= max(1, retries):
                raise
            time.sleep(attempt)


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
         name, backup.name, backup.name, name, name)
    bat.write_text(body, encoding="ascii")
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(target.parent),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return bat
