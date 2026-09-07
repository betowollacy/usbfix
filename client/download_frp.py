#!/usr/bin/env python
"""Baixa o binário frp (frpc/frps) mais recente do projeto oficial fatedier/frp."""
import json
import platform
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def latest_release():
    req = urllib.request.Request(
        "https://api.github.com/repos/fatedier/frp/releases/latest",
        headers={"User-Agent": "tunnel-setup"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pick_asset(assets, os_name, arch):
    kv = {
        ("Windows", "64bit"): "windows_amd64",
        ("Windows", "32bit"): "windows_386",
        ("Linux", "64bit"): "linux_amd64",
        ("Linux", "arm64"): "linux_arm64",
        ("Darwin", "64bit"): "darwin_amd64",
    }
    key = kv.get((os_name, arch))
    if not key:
        sys.exit(f"plataforma não suportada: {os_name} {arch}")
    for asset in assets:
        if asset["name"].endswith(".zip") and key in asset["name"]:
            return asset
    sys.exit("release não encontrada")


def main():
    os_name = platform.system()
    arch = platform.machine()
    arch = "64bit" if "64" in arch else "32bit"
    release = latest_release()
    asset = pick_asset(release["assets"], os_name, arch)
    dest = Path(__file__).resolve().parent / asset["name"]
    print(f"baixando {asset['name']} ({asset['size'] // 1048576} MB)…")
    urllib.request.urlretrieve(asset["browser_download_url"], dest)
    with zipfile.ZipFile(dest) as zf:
        exe_names = ("frpc.exe", "frps.exe", "frpc", "frps")
        for member in zf.namelist():
            name = Path(member).name
            if name in exe_names:
                target = Path(__file__).resolve().parent / name
                with zf.open(member) as src, open(target, "wb") as out:
                    out.write(src.read())
                print(f"extraído: {target}")
    dest.unlink()
    print("pronto")


if __name__ == "__main__":
    main()