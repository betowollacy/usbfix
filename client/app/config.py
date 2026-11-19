import os
import sys
from pathlib import Path

API_BASE = os.getenv("TUNNEL_API", "https://usbfix.site")
APP_NAME = "USB FIX"
APP_ID = "com.usbfix.app"
VERSION = "0.6.8"

DATA_DIR = Path(os.getenv("TUNNEL_DATA_DIR", Path(os.environ.get("APPDATA", Path.home())) / "USBFix"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CREDS_FILE = DATA_DIR / "creds.json"
FRPC_TOML = DATA_DIR / "frpc.toml"
LOG_FILE = DATA_DIR / "frpc.log"

if getattr(sys, "frozen", False):
    _APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    _APP_DIR = Path(__file__).resolve().parent.parent

FRPC_EXE = os.getenv("TUNNEL_FRPC", str(_APP_DIR / "frpc.exe"))
