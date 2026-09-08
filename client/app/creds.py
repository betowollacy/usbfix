import base64
import json

from .config import CREDS_FILE


def _obfuscate(text):
    return base64.b64encode(text.encode()).decode()


def _unobfuscate(text):
    return base64.b64decode(text.encode()).decode()


def save(token, username, password="", remember=True):
    data = {}
    with open(CREDS_FILE, "w", encoding="utf-8") as fh:
        data["token"] = _obfuscate(token)
        data["username"] = _obfuscate(username)
        data["password"] = _obfuscate(password)
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


def fields():
    """Usuário/senha salvos para preencher o login, mesmo sem auto-login."""
    try:
        with open(CREDS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {
            "username": _unobfuscate(data.get("username", "")),
            "password": _unobfuscate(data.get("password", "")),
        }
    except Exception:
        return {}


def unremember():
    """Mantém usuário/senha, mas desliga o auto-login (usado no Saír)."""
    creds = fields()
    try:
        with open(CREDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "username": _obfuscate(creds.get("username", "")),
                    "password": _obfuscate(creds.get("password", "")),
                    "remember": False,
                },
                fh,
            )
    except Exception:
        pass


def clear():
    try:
        CREDS_FILE.unlink()
    except Exception:
        pass