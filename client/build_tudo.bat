@echo off
setlocal
cd /d "%~dp0"

if not exist "frpc.exe" (
	echo === Baixando frp ===
	python download_frp.py
	if errorlevel 1 goto :erro
)

echo === Rebuild USB-Fix.exe ===
python -m PyInstaller --noconfirm --clean USB-Fix.spec
if errorlevel 1 goto :erro

echo.
echo === Build instalador ===
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Instalar USB FIX" --icon USB-Fix.ico --add-binary "dist\USB-Fix.exe;." --add-data "USB-Fix.ico;." instalar.py
if errorlevel 1 goto :erro

echo.
echo === Limpando exes antigos ===
if exist "dist\TunnelRedirector.exe" del "dist\TunnelRedirector.exe"
if exist "dist\Tunnelx.exe" del "dist\Tunnelx.exe"
if exist "dist\Instalar USB FIX" rmdir /s /q "dist\Instalar USB FIX"
if exist "dist\Abrir App.bat" del "dist\Abrir App.bat"

echo.
echo Pronto em dist:
dir /b "dist"
endlocal
exit /b 0

:erro
echo Falha no build.
endlocal
exit /b 1