@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean USB-Fix.spec
endlocal