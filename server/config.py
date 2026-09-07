import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("TUNNEL_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "tunnel.db"

HOST = os.getenv("TUNNEL_HOST", "0.0.0.0")
PORT = int(os.getenv("TUNNEL_PORT", "8000"))
APP_VERSION = os.getenv("TUNNEL_APP_VERSION", "0.5.0")

TRIAL_HOURS = int(os.getenv("TUNNEL_TRIAL_HOURS", "6"))
SUBSCRIPTION_DAYS = int(os.getenv("TUNNEL_SUBSCRIPTION_DAYS", "30"))
PRICE = os.getenv("TUNNEL_PRICE", "R$ 30/mês")
PORT_RANGE = (int(os.getenv("TUNNEL_PORT_MIN", "40000")), int(os.getenv("TUNNEL_PORT_MAX", "49999")))
SUBDOMAIN_MAX_CHANGES = int(os.getenv("TUNNEL_SUBDOMAIN_CHANGES", "5"))
KEY_FORMAT = "{}-{}-{}-{}"

FRPS_ADDR = os.getenv("TUNNEL_FRPS_ADDR", "127.0.0.1")
FRPS_PORT = int(os.getenv("TUNNEL_FRPS_PORT", "7000"))
FRPS_TOKEN = os.getenv("TUNNEL_FRPS_TOKEN", "tunnel-dev-token")
SUBDOMAIN_HOST = os.getenv("TUNNEL_SUBDOMAIN_HOST", "usbfix.site")

ADMIN_TOKEN = os.getenv("TUNNEL_ADMIN_TOKEN", "")

# Asaas (Pix)
ASAAS_ACCESS_TOKEN = os.getenv("ASAAS_ACCESS_TOKEN", "")
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://www.asaas.com/api/v3")
WEBHOOK_SECRET = os.getenv("TUNNEL_WEBHOOK_SECRET", "")

# Plano vendido no site
PLAN_NAME = os.getenv("TUNNEL_PLAN_NAME", "Base")
PLAN_PRICE = float(os.getenv("TUNNEL_PLAN_PRICE", "30.0"))
PLAN_DAYS = int(os.getenv("TUNNEL_PLAN_DAYS", "30"))

# Planos (base; editáveis no painel /api/admin/plans)
PLANS = [
    {"id": "30d",  "name": "30 dias", "price": 25.0,  "days": 30},
    {"id": "90d",  "name": "90 dias", "price": 70.0,  "days": 90},
    {"id": "365d", "name": "Anual",   "price": 150.0, "days": 365},
]