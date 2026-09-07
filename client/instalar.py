import os
import shutil
import subprocess
import sys
from ctypes import windll
from pathlib import Path

APP_DIR_NAME = "USB FIX"
EXE_NAME = "USB-Fix.exe"
ICON_NAME = "USB-Fix.ico"
APP_VERSION = "0.5.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\USB FIX"

MB_OK = 0x0
MB_ICONINFO = 0x40
MB_ICONERROR = 0x10


def msgbox(text, title="USB FIX", icon=MB_ICONINFO):
    windll.user32.MessageBoxW(0, text, title, MB_OK | icon)


def write_uninstaller(app_dir):
    lines = [
        "@echo off",
        "taskkill /f /im USB-Fix.exe >nul 2>&1",
        "timeout /t 1 /nobreak >nul",
        'reg delete "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\USB FIX" /f >nul 2>&1',
        'del /f /q "' + str(app_dir / EXE_NAME) + '" >nul 2>&1',
        'del /f /q "' + str(app_dir / ICON_NAME) + '" >nul 2>&1',
        'del /f /q "' + str(app_dir / "desinstalar.bat") + '" >nul 2>&1',
        'rmdir /q "' + str(app_dir) + '" >nul 2>&1',
        "powershell -NoProfile -NonInteractive -Command \"$d=[Environment]::GetFolderPath('Desktop'); $s=$d+'\\USB FIX.lnk'; if(Test-Path $s){Remove-Item $s -Force}\"",
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

        ps = (
            "$d=[Environment]::GetFolderPath('Desktop');"
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\\USB FIX.lnk');"
            "$s.TargetPath='" + str(app_dir / EXE_NAME) + "';"
            "$s.WorkingDirectory='" + str(app_dir) + "';"
            "$s.IconLocation='" + shortcut_icon + "';"
            "$s.Description='USB FIX - acesso remoto USB';"
            "$s.Save()"
        )
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True)

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