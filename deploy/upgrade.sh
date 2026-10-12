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

# Evita "dubious ownership" quando rodado como root sobre clone criado por outro usuário
git config --global --add safe.directory "$SRC_DIR" 2>/dev/null || true

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
# site/downloads e data/ contêm arquivos locais (exe, banco) que NÃO ficam no git:
# nunca apagar com --delete.
rsync -a --delete \
    --exclude 'site/downloads/' \
    --exclude 'data/' \
    "$SRC_DIR/server/." /opt/tunnel/server/

echo "==> Garantindo token/domínio no frps.toml"
TOML=/opt/tunnel/frps.toml
if [ ! -f "$TOML" ]; then
    cp "$SRC_DIR/server/frps.toml" "$TOML"
fi
get_val() {
    grep "^$1=" /etc/tunnel/env | head -1 | cut -d= -f2- | sed 's/^"//; s/"$//'
}
SUB_DOMAIN="${TUNNEL_SUBDOMAIN_HOST:-$(get_val TUNNEL_SUBDOMAIN_HOST)}"
if [ -n "$FRP_TOKEN" ]; then
    sed -i 's/^auth\.token = .*/auth.token = "'"$FRP_TOKEN"'"/' "$TOML"
fi
if [ -n "$SUB_DOMAIN" ]; then
    sed -i 's|^subdomainHost = .*|subdomainHost = "'"$SUB_DOMAIN"'"|; s|^# subdomainHost = .*|subdomainHost = "'"$SUB_DOMAIN"'"|' "$TOML"
fi

echo "==> Atualizando dependências da API"
/opt/tunnel/venv/bin/pip install -q --upgrade pip
/opt/tunnel/venv/bin/pip install -q -r /opt/tunnel/server/requirements.txt

echo "==> Copiando arquivos de serviço systemd"
cp "$SRC_DIR/deploy/systemd/frps.service" /etc/systemd/system/
cp "$SRC_DIR/deploy/systemd/tunnel-api.service" /etc/systemd/system/
cp "$SRC_DIR/deploy/systemd/frp-auth.service" /etc/systemd/system/
systemctl daemon-reload

echo "==> Salvando scripts de deploy em /opt/tunnel/deploy"
mkdir -p /opt/tunnel/deploy/systemd
cp "$SRC_DIR/deploy/"*.sh /opt/tunnel/deploy/
rsync -a "$SRC_DIR/deploy/systemd/." /opt/tunnel/deploy/systemd/
chmod +x /opt/tunnel/deploy/*.sh

echo "==> Ajustando permissões"
chown -R tunnel:tunnel /opt/tunnel/server /opt/tunnel/deploy /opt/tunnel/data /opt/tunnel/venv
chown tunnel:tunnel /opt/tunnel/frps /opt/tunnel/frps.toml 2>/dev/null || true

echo "==> Fechando a porta pública da API, se houver regra antiga"
ufw delete allow 8000/tcp >/dev/null 2>&1 || true

echo "==> Reiniciando serviços"
systemctl enable frp-auth
systemctl restart frp-auth tunnel-api frps

echo
echo "=================================================================="
echo "  UPGRADE CONCLUÍDO"
echo "  Commit atual: $(git -C "$SRC_DIR" rev-parse --short HEAD)"
echo "  Serviços:     frps + tunnel-api reiniciados"
echo "=================================================================="