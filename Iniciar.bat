@echo off
title Tunnel Redirector - Menu Principal
cd /d "%~dp0"

:inicio
cls
echo ============================================================
echo              TUNNEL REDIRECTOR - MENU
echo ============================================================
echo.
echo   1. Iniciar Servidor        (rode primeiro, deixe aberto)
echo   2. Painel de Chaves        (gerar / vender / bloquear)
echo   3. Abrir App do Cliente    (testar como um cliente)
echo   4. Pasta de Entrega        (onde fica o .exe p/ cliente)
echo   5. Sair
echo.
set /p op=Escolha um numero e tecle Enter: 

if "%op%"=="1" (
    start "Servidor" cmd /c "cd /d %~dp0 && iniciar_api.bat"
    goto inicio
)
if "%op%"=="2" (
    start "Painel de Chaves" cmd /k "cd /d %~dp0 && iniciar_admin.bat"
    goto inicio
)
if "%op%"=="3" (
    call iniciar_app.bat
    goto inicio
)
if "%op%"=="4" (
    explorer "%~dp0client\dist"
    goto inicio
)
if "%op%"=="5" (
    exit
)
goto inicio