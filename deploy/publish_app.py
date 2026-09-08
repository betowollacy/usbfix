#!/usr/bin/env python3
"""Publica nova versão do app no servidor.

Uso (na máquina de build, Windows/Linux com PyInstaller + chave SSH):
    python deploy/publish_app.py [--skip-build] [--key PATH]

Fluxo:
  1. Rebuilda USB-Fix.exe (e o instalador via build_tudo.bat, se existir)
  2. Envia USB-Fix.exe e Instalar USB FIX.exe para /opt/tunnel/server/site/downloads/
  3. Confere MD5 local vs remoto
"""
import argparse
import hashlib
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "client"
DIST = CLIENT / "dist"
HOST = "root@178.253.250.178"
DL_DIR = "/opt/tunnel/server/site/downloads"
API_BASE = "https://usbfix.site"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def scp(key, src, dst):
    key_arg = ["-i", str(key)] if key else []
    cmd = ["scp", *key_arg, "-o", "StrictHostKeyChecking=no", str(src), f"{HOST}:{dst}"]
    subprocess.run(cmd, check=True)


def remote_md5(key, remote_path):
    key_arg = ["-i", str(key)] if key else []
    cmd = ["ssh", *key_arg, HOST, f"md5sum '{remote_path}'"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return out.split()[0] if out.strip() else ""


def remote_setting_url(key):
    """Garante que dl.app.url aponte para /downloads/USB-Fix.exe."""
    code = (
        "import sqlite3; c=sqlite3.connect('/opt/tunnel/data/tunnel.db');"
        "c.execute('UPDATE settings SET value=? WHERE key=?',"
        "('/downloads/USB-Fix.exe','dl.app.url')); c.commit()"
    )
    key_arg = ["-i", str(key)] if key else []
    subprocess.run(["ssh", *key_arg, HOST, f"python3 -c \"{code}\""], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-build", action="store_true", help="não rebuilda, usa o dist atual")
    ap.add_argument("--key", default=str(Path.home() / ".ssh" / "id_ed25519_usbfix_deploy"),
                    help="caminho da chave SSH")
    args = ap.parse_args()
    key = Path(args.key) if args.key else None

    if not args.skip_build:
        bat = CLIENT / "build_tudo.bat"
        if bat.exists() and os.name == "nt":
            print("==> Rebuild do app + instalador...")
            subprocess.run(["cmd", "/c", str(bat)], cwd=str(CLIENT), check=True)
        else:
            print("==> Rebuild do app (sem instalador) — use --skip-build se já rodou.")
            subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                            "USB-Fix.spec"], cwd=str(CLIENT), check=True)

        # precisa que o instalador referencie o USB-Fix.exe atual
        instalador_spec = CLIENT / "Instalar USB FIX.spec"
        if instalador_spec.exists():
            print("==> Rebuild do instalador...")
            subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                            str(instalador_spec)], cwd=str(CLIENT), check=True)

    binaries = []
    for name in ("USB-Fix.exe", "Instalar USB FIX.exe"):
        p = DIST / name
        if p.exists():
            binaries.append(p)
        else:
            print(f"!! Aviso: {p} não existe; pulando upload.")

    if not binaries:
        print("!! Nenhum binário em dist/ para publicar.")
        sys.exit(1)

    for p in binaries:
        print(f"==> Enviando {p.name}...")
        scp(key, p, f"{DL_DIR}/{p.name}")

    print("==> Ajustando dl.app.url no banco (aponta para /downloads/USB-Fix.exe)...")
    remote_setting_url(key)

    print("==> Verificando hashes...")
    ok = True
    for p in binaries:
        local = md5(p)
        remote = remote_md5(key, f"{DL_DIR}/{p.name}")
        status = "OK" if local.lower() == remote.lower() else "DIVERGÊNCIA"
        if local.lower() != remote.lower():
            ok = False
        print(f"    {p.name}: local={local[:8]}… remoto={remote[:8]}… [{status}]")

    print()
    print(f"==> API reporta a versão servida:")
    with urllib.request.urlopen(f"{API_BASE}/api/downloads", timeout=30) as resp:
        import json
        data = json.load(resp)
        print(f"    app.version = {data['app']['version']}")
        print(f"    app.url     = {data['app']['url']}")

    print()
    print("   PUBLICAÇÃO CONCLUÍDA" if ok else "   PUBLICAÇÃO COM DIVERGÊNCIAS — confira manualmente")


if __name__ == "__main__":
    main()