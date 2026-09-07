@echo off
title Tunnel Redirector - Cliente
cd /d "%~dp0client"
if exist "dist\TunnelRedirector.exe" (
    start "" "dist\TunnelRedirector.exe"
    exit /b
)
python main.py
pause