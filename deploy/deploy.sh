#!/usr/bin/env bash
# Deploy do Tunnel Redirector em Ubuntu/Debian (root).
# Uso: envie a pasta inteira do projeto para a VPS e rode:
#   sudo bash deploy/deploy.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/deploy/tunnel.env"
set -a; source "$ENV_FILE"; set +a

DOMAIN="${TUNNEL_SUBDOMAIN_HOST:-usbfix.site}"
ADMIN_TOKEN="${TUNNEL_ADMIN_TOKEN:-$(openssl rand -hex 24)}"
FRP_TOKEN="${FRP_TOKEN:-$(openssl rand -hex 24)}"

echo "==> Atualizando sistema e instalando dependências..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl unzip jq ufw openssl

echo "==> Criando usuário e estrutura em /opt/tunnel..."
id -u tunnel >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin tunnel
mkdir -p /opt/tunnel/server /opt/tunnel/data /etc/tunnel
cp -r "$PROJECT_DIR/server/." /opt/tunnel/server/
cp "$PROJECT_DIR/server/frps.toml" /opt/tunnel/frps.toml

if [ -f "$PROJECT_DIR/client/dist/Instalar USB FIX.exe" ]; then
    echo "==> Publicando instalador USB FIX..."
    mkdir -p /opt/tunnel/server/site/downloads
    cp "$PROJECT_DIR/client/dist/Instalar USB FIX.exe" \
        "/opt/tunnel/server/site/downloads/Instalar USB FIX.exe"
fi

if [ -f "$PROJECT_DIR/client/dist/USB-Fix.exe" ]; then
    echo "==> Publicando executável USB FIX..."
    mkdir -p /opt/tunnel/server/site/downloads
    cp "$PROJECT_DIR/client/dist/USB-Fix.exe" \
        "/opt/tunnel/server/site/downloads/USB-Fix.exe"
fi

echo "==> venv + dependências da API..."
python3 -m venv /opt/tunnel/venv
/opt/tunnel/venv/bin/pip install -q --upgrade pip
/opt/tunnel/venv/bin/pip install -q -r /opt/tunnel/server/requirements.txt

echo "==> Baixando frps (linux_amd64)..."
VER="$(curl -fsSL https://api.github.com/repos/fatedier/frp/releases/latest | jq -r .tag_name)"
REL="${VER#v}"
ARCHIVE="/tmp/frp_${REL}_linux_amd64.tar.gz"
curl -fsSL -o "$ARCHIVE" "https://github.com/fatedier/frp/releases/download/${VER}/frp_${REL}_linux_amd64.tar.gz"
tar -xzf "$ARCHIVE" -C /tmp
cp "/tmp/frp_${REL}_linux_amd64/frps" /opt/tunnel/frps
chmod +x /opt/tunnel/frps

echo "==> Gravando token forte e domínio no frps.toml..."
sed -i "s/^auth\.token = .*/auth.token = \"$FRP_TOKEN\"/" /opt/tunnel/frps.toml
sed -i "s|^# subdomainHost = .*|subdomainHost = \"$DOMAIN\"|" /opt/tunnel/frps.toml

if [ -z "${TUNNEL_FRPS_ADDR}" ]; then
    TUNNEL_FRPS_ADDR="$(curl -fsSL --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')"
fi

if [ -z "${TUNNEL_WEBHOOK_SECRET}" ]; then
    TUNNEL_WEBHOOK_SECRET="$(openssl rand -hex 24)"
fi

echo "==> Configurando env da API (/etc/tunnel/env)..."
cat > /etc/tunnel/env <<ENV
TUNNEL_ADMIN_TOKEN=$ADMIN_TOKEN
TUNNEL_SUBDOMAIN_HOST=$DOMAIN
TUNNEL_FRPS_ADDR=$TUNNEL_FRPS_ADDR
TUNNEL_FRPS_PORT=${TUNNEL_FRPS_PORT:-7000}
TUNNEL_FRPS_TOKEN=$FRP_TOKEN
TUNNEL_PORT_MIN=${TUNNEL_PORT_MIN:-40000}
TUNNEL_PORT_MAX=${TUNNEL_PORT_MAX:-49999}
TUNNEL_SUBSCRIPTION_DAYS=${TUNNEL_SUBSCRIPTION_DAYS:-30}
TUNNEL_DATA_DIR=/opt/tunnel/data
TUNNEL_WEBHOOK_SECRET=$TUNNEL_WEBHOOK_SECRET
ASAAS_ACCESS_TOKEN=${ASAAS_ACCESS_TOKEN:-}
ASAAS_BASE_URL=${ASAAS_BASE_URL:-https://www.asaas.com/api/v3}
ENV
chmod 600 /etc/tunnel/env

echo "==> Instalando serviços systemd..."
cp "$PROJECT_DIR/deploy/systemd/frps.service" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/systemd/tunnel-api.service" /etc/systemd/system/
chown -R tunnel:tunnel /opt/tunnel /etc/tunnel
systemctl daemon-reload
systemctl enable --now frps tunnel-api

echo "==> Firewall (ufw)..."
ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null
ufw allow 7000/tcp
ufw allow 8000/tcp
ufw allow proto tcp from any to any port "${TUNNEL_PORT_MIN:-40000}:${TUNNEL_PORT_MAX:-49999}"
ufw --force enable

echo
echo "=================================================================="
echo "  DEPLOY CONCLUÍDO"
echo "  API:          http://$TUNNEL_FRPS_ADDR:8000"
echo "  Token admin:  $ADMIN_TOKEN"
echo "  Domínio:      aponte *.${DOMAIN} -> $TUNNEL_FRPS_ADDR  (ou use IP:porta)"
echo "  Firewall:     OpenSSH + 7000 + 8000 + 40000-49999"
echo
echo "  Para testar a partir do app do cliente:"
echo "    abra o app, botão 'Servidor' -> http://$TUNNEL_FRPS_ADDR:8000"
echo "=================================================================="