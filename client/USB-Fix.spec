# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Ensure PyInstaller and its hook helpers resolve the project's local "app"
# package, not an unrelated package with the same name from site-packages.
PROJECT_ROOT = os.path.abspath(os.path.dirname(SPEC))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyInstaller.utils.hooks import collect_all, collect_submodules

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")
certifi_datas, certifi_binaries, certifi_hiddenimports = collect_all("certifi")

app_hiddenimports = [
    "app.config",
    "app.creds",
    "app.gui",
    "app.logo",
    "app.redirector",
    "app.api",
    "app.ssl_context",
    "app.tunnel",
    "app.updater",
]

app_modules = collect_submodules("app", on_error="warn")
if "app.gui" not in app_modules:
    app_modules.append("app.gui")

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=ctk_binaries + certifi_binaries,
    datas=[("frpc.exe", ".")] + ctk_datas + certifi_datas,
    hiddenimports=sorted(set(
        app_modules
        + app_hiddenimports
        + ctk_hiddenimports
        + certifi_hiddenimports
    )),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="USB-Fix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="USB-Fix.ico",
)
