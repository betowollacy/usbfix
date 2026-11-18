# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

app_hiddenimports = [
    "app.config",
    "app.creds",
    "app.gui",
    "app.logo",
    "app.redirector",
    "app.api",
    "app.tunnel",
    "app.updater",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=ctk_binaries,
    datas=[("frpc.exe", ".")] + ctk_datas,
    hiddenimports=sorted(set(
        collect_submodules("app")
        + app_hiddenimports
        + ctk_hiddenimports
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
