@echo off
title Tunnel Admin - Usuários
cd /d "%~dp0admin"
set TUNNEL_ADMIN_TOKEN=raiz-secreta-troque
set TUNNEL_API=http://127.0.0.1:8000
python gerador_keys.py
pause