import os
import shutil
import subprocess
import sys
from ctypes import windll
from pathlib import Path

APP_DIR_NAME = "USB FIX"
EXE_NAME = "USB-Fix.exe"
ICON_NAME = "USB-Fix.ico"
APP_VERSION = "0.6.5"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\USB FIX"

MB_OK = 0x0
MB_ICONINFO = 0x40
MB_ICONERROR = 0x10


def msgbox(text, title="USB FIX", icon=MB_ICONINFO):
    windll.user32.MessageBoxW(0, text, title, MB_OK | icon)


def desktop_folders():
    """Caminhos prováveis da área de trabalho (perfil + OneDrive + Público)."""
    dirs = []
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
        if buf.value:
            dirs.append(buf.value)
    except Exception:
        pass
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            val = winreg.QueryValueEx(key, "Desktop")[0]
        expanded = os.path.expandvars(val).replace("/", "\\")
        if expanded not in dirs:
            dirs.append(expanded)
    except Exception:
        pass
    cands = [
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop"),
        os.path.join(os.path.expandvars("%PUBLIC%"), "Desktop"),
    ]
    for c in cands:
        if c not in dirs:
            dirs.append(c)
    return [d for d in dirs if d and os.path.isdir(d)]


def _create_shortcut(target, workdir, icon):
    """Cria 'USB FIX.lnk' em qualquer pasta de desktop disponível. Retorna True se ao menos um foi criado."""
    created_any = False
    notify = (
        "$r=New-Object -ComObject Shell.Application;"
        "$r.Namespace($d).ParseName('USB FIX.lnk') | Out-Null;"
        "Add-Type -Namespace Win32 -Name Shell -MemberDefinition '[DllImport(\"shell32.dll\")] public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);';"
        "[Win32.Shell]::SHChangeNotify(0x8000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)"
    )
    for folder in desktop_folders():
        ps = (
            "$d='" + folder.replace("'", "''") + "';"
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\\USB FIX.lnk');"
            "$s.TargetPath='" + str(target).replace("'", "''") + "';"
            "$s.WorkingDirectory='" + str(workdir).replace("'", "''") + "';"
            "$s.IconLocation='" + icon.replace("'", "''") + "';"
            "$s.Description='USB FIX - acesso remoto USB';"
            "$s.Save();"
            + notify
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NonInteractive", "-Command", ps],
                check=True, timeout=30,
            )
            if os.path.exists(os.path.join(folder, "USB FIX.lnk")):
                created_any = True
        except Exception:
            continue
    return created_any


def write_uninstaller(app_dir):
    ps_remove_lnk = (
        "$paths=@();"
        "$paths+=([Environment]::GetFolderPath('Desktop'));"
        "$paths+=($env:USERPROFILE+'\\Desktop');"
        "$paths+=($env:USERPROFILE+'\\OneDrive\\Desktop');"
        "$paths+=('C:\\Users\\Public\\Desktop');"
        "$paths+=(Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs');"
        "foreach($p in $paths){"
        "  $l=Join-Path $p 'USB FIX.lnk';"
        "  if(Test-Path $l){Remove-Item $l -Force};"
        "  $l2=Join-Path $p 'USB-Fix.lnk';"
        "  if(Test-Path $l2){Remove-Item $l2 -Force}"
        "}"
    )
    bg = (
        "start \"\" /b cmd /c "
        "\"ping -n 3 127.0.0.1 >nul"
        " & del /f /q \"%APP%\\desinstalar.bat\" >nul 2>&1"
        " & del /f /q \"%APP%\\USB-Fix.exe\" >nul 2>&1"
        " & del /f /q \"%APP%\\USB-Fix.ico\" >nul 2>&1"
        " & rmdir /q \"%APP%\" >nul 2>&1\""
    )
    lines = [
        "@echo off",
        'title Desinstalando USB FIX...',
        "set APP=%~dp0",
        'if "%APP:~-1%"=="\\" set APP=%APP:~0,-1%',
        "taskkill /f /im USB-Fix.exe >nul 2>&1",
        'reg delete "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\USB FIX" /f >nul 2>&1',
        "powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -Command \"" + ps_remove_lnk + "\" >nul 2>&1",
        bg,
        "exit /b 0",
    ]
    try:
        (app_dir / "desinstalar.bat").write_text("\r\n".join(lines), encoding="ascii")
        return True
    except Exception:
        return False


def register_uninstall(app_dir):
    try:
        import winreg
    except Exception:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "USB FIX")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "USB FIX")
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(app_dir / ICON_NAME))
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(app_dir))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, str(app_dir / "desinstalar.bat"))
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            try:
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 0)
            except Exception:
                pass
        return True
    except Exception:
        return False


def main():
    try:
        src = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        app_dir = Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_DIR_NAME
        app_dir.mkdir(parents=True, exist_ok=True)

        exe_src = src / EXE_NAME
        if not exe_src.exists():
            msgbox("Arquivo ausente na pasta de instalação: " + EXE_NAME, icon=MB_ICONERROR)
            return 1
        shutil.copyfile(exe_src, app_dir / EXE_NAME)

        ico_src = src / ICON_NAME
        if ico_src.exists():
            shutil.copyfile(ico_src, app_dir / ICON_NAME)
            shortcut_icon = str(app_dir / ICON_NAME) + ",0"
        else:
            shortcut_icon = str(app_dir / EXE_NAME) + ",0"

        created = _create_shortcut(app_dir / EXE_NAME, app_dir, shortcut_icon)
        if not created:
            msgbox(
                "USB FIX foi instalado, mas o Windows não permitiu criar o atalho.\n\n"
                "Você pode abrir o app em:\n" + str(app_dir / EXE_NAME),
                icon=MB_ICONERROR,
            )

        write_uninstaller(app_dir)
        register_uninstall(app_dir)

        msgbox(
            "USB FIX instalado com sucesso!\n\n"
            "O atalho \"USB FIX\" foi criado na área de trabalho.\n"
            "O app agora aparece em \"Desinstalar programas\" do Windows.",
        )
        return 0
    except Exception as exc:
        msgbox("Erro na instalação:\n" + str(exc), icon=MB_ICONERROR)
        return 1


if __name__ == "__main__":
    sys.exit(main())