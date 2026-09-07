@echo off
setlocal
cd /d "%~dp0"

echo === Rebuild USB-Fix.exe ===
python -m PyInstaller --noconfirm --clean USB-Fix.spec
if errorlevel 1 goto :erro

echo.
echo === Build instalador ===
python -m PyInstaller --noconfirm --clean "Instalar USB FIX.spec"
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