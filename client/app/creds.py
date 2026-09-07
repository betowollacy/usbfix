import base64
import json

from .config import CREDS_FILE


def _obfuscate(text):
    return base64.b64encode(text.encode()).decode()


def _unobfuscate(text):
    return base64.b64decode(text.encode()).decode()


def save(token, username, remember=True):
    data = {}
    with open(CREDS_FILE, "w", encoding="utf-8") as fh:
        data["token"] = _obfuscate(token)
        data["username"] = _obfuscate(username)
        data["remember"] = remember
        json.dump(data, fh)


def load():
    try:
        with open(CREDS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not data.get("remember"):
            return None
        return {"token": _unobfuscate(data["token"]), "username": _unobfuscate(data["username"])}
    except Exception:
        return None


def clear():
    try:
        CREDS_FILE.unlink()
    except Exception:
        pass