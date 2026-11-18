@echo off
setlocal
cd /d "%~dp0"

echo [%date% %time%] === Rebuild USB-Fix.exe ===
python -u -m PyInstaller --noconfirm --clean --log-level=INFO USB-Fix.spec
if errorlevel 1 goto :erro

echo.
echo [%date% %time%] === Testar inicializacao do executavel ===
"dist\USB-Fix.exe" --selftest
if errorlevel 1 (
    echo ERRO: USB-Fix.exe falhou no teste de inicializacao. Instalador nao sera gerado.
    goto :erro
)

echo.
echo [%date% %time%] === Build instalador ===
python -u -m PyInstaller --noconfirm --clean --log-level=INFO "Instalar USB FIX.spec"
if errorlevel 1 goto :erro

echo.
echo [%date% %time%] === Limpando exes antigos ===
if exist "dist\TunnelRedirector.exe" del "dist\TunnelRedirector.exe"
if exist "dist\Tunnelx.exe" del "dist\Tunnelx.exe"
if exist "dist\Instalar USB FIX" rmdir /s /q "dist\Instalar USB FIX"
if exist "dist\Abrir App.bat" del "dist\Abrir App.bat"

echo.
echo [%date% %time%] Pronto em dist:
dir /b "dist"
endlocal
exit /b 0

:erro
echo [%date% %time%] Falha no build.
endlocal
exit /b 1
