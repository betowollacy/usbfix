@echo off
title Tunnel API
cd /d "%~dp0server"
set TUNNEL_ADMIN_TOKEN=raiz-secreta-troque
set TUNNEL_SUBDOMAIN_HOST=rootSpectrum.com
set TUNNEL_FRPS_ADDR=127.0.0.1
set TUNNEL_FRPS_TOKEN=tunnel-dev-token
echo Iniciando API do Tunnel em http://0.0.0.0:8000
python -m uvicorn app:app --host 0.0.0.0 --port 8000
pause