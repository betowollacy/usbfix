#!/usr/bin/env bash
# Upgrade do Tunnel Redirector na VPS a partir do GitHub.
# Uso (na VPS, como root):
#   sudo bash deploy/upgrade.sh             # atualiza para a última versão
#   sudo bash deploy/upgrade.sh v1.2.3      # checkout para a tag/commit informada
set -euo pipefail

REPO_URL="https://github.com/betowollacy/usbfix.git"
SRC_DIR="/opt/tunnel/src"
TARGET="${1:-}"

command -v git >/dev/null 2>&1 || { echo "ERRO: git não instalado. Rode: apt-get install -y git"; exit 1; }
command -v rsync >/dev/null 2>&1 || { echo "ERRO: rsync não instalado. Rode: apt-get install -y rsync"; exit 1; }

echo "==> Buscando versão em ${REPO_URL}"

# Garante/clone do repositório em /opt/tunnel/src (upgrade independente da pasta do deploy inicial)
if [ ! -d "$SRC_DIR/.git" ]; then
    echo "==> Clonando repositório em $SRC_DIR"
    git clone --depth 1 "$REPO_URL" "$SRC_DIR"
else
    echo "==> Puxando atualizações em $SRC_DIR"
    git -C "$SRC_DIR" fetch --tags origin
    git -C "$SRC_DIR" checkout main
    git -C "$SRC_DIR" pull --ff-only origin main
fi

if [ -n "$TARGET" ]; then
    echo "==> Checkout para $TARGET"
    git -C "$SRC_DIR" fetch origin "$TARGET" 2>/dev/null || true
    git -C "$SRC_DIR" checkout "$TARGET"
fi

echo "==> Copiando arquivos do servidor para /opt/tunnel/server"
mkdir -p /opt/tunnel/server
rsync -a --delete "$SRC_DIR/server/." /opt/tunnel/server/
cp "$SRC_DIR/server/frps.toml" /opt/tunnel/frps.toml

echo "==> Atualizando dependências da API"
/opt/tunnel/venv/bin/pip install -q --upgrade pip
/opt/tunnel/venv/bin/pip install -q -r /opt/tunnel/server/requirements.txt

echo "==> Atualizando arquivos de serviço systemd"
cp "$SRC_DIR/deploy/systemd/frps.service" /etc/systemd/system/
cp "$SRC_DIR/deploy/systemd/tunnel-api.service" /etc/systemd/system/
systemctl daemon-reload

echo "==> Reiniciando serviços"
systemctl restart frps tunnel-api

echo
echo "=================================================================="
echo "  UPGRADE CONCLUÍDO"
echo "  Commit atual: $(git -C "$SRC_DIR" rev-parse --short HEAD)"
echo "  Serviços:     frps + tunnel-api reiniciados"
echo "=================================================================="