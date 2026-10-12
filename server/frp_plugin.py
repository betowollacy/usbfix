"""FRP HTTP server plugin: validate each USB FIX account and its assigned port."""
import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, HTTPException, Request

import database as db

app = FastAPI(title="USB FIX FRP authorization plugin")


@app.on_event("startup")
def startup():
    db.init_db()


def reject(reason: str):
    return {"reject": True, "reject_reason": reason}


def allow(content: dict[str, Any] | None = None):
    if content is None:
        return {"reject": False, "unchange": True}
    return {"reject": False, "unchange": False, "content": content}


def token_from(user: dict[str, Any] | None):
    if not isinstance(user, dict):
        return ""
    metas = user.get("metas")
    if not isinstance(metas, dict):
        return ""
    value = metas.get("token", "")
    return value if isinstance(value, str) else ""


def active_user(token: str):
    if not token:
        return None
    rec = db.get_by_frp_token(token)
    if not rec or db.effective_status(rec) != "active":
        return None
    return rec


@app.post("/handler")
async def handler(request: Request):
    op = request.query_params.get("op", "")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plugin request")
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, dict):
        return reject("invalid request")

    if op == "Login":
        token = token_from({"metas": content.get("metas", {})})
        rec = active_user(token)
        username = content.get("user")
        if not rec or not isinstance(username, str) or not hmac.compare_digest(username, rec["username"]):
            return reject("invalid or inactive USB FIX account")
        # FRP verifies privilege_key after invoking Login plugins. With the
        # server's intentionally empty built-in token, use the expected MD5
        # value for that empty token; account authorization remains enforced
        # by this plugin and the following NewProxy check.
        timestamp = content.get("timestamp")
        if not isinstance(timestamp, int):
            return reject("invalid login timestamp")
        updated = dict(content)
        updated["privilege_key"] = hashlib.md5(str(timestamp).encode("utf-8")).hexdigest()
        return allow(updated)

    if op == "NewProxy":
        user = content.get("user")
        token = token_from(user)
        rec = active_user(token)
        if not rec or not isinstance(user, dict) or user.get("user") != rec["username"]:
            return reject("invalid or inactive USB FIX account")
        expected_name = f"usb-{rec['id']}"
        try:
            remote_port = int(content.get("remote_port", 0))
        except (TypeError, ValueError):
            remote_port = 0
        if (
            content.get("proxy_type") != "tcp"
            or content.get("proxy_name") != expected_name
            or not rec.get("server_port")
            or remote_port != int(rec["server_port"])
        ):
            return reject("proxy does not match this account's assigned port")
        return allow()

    # Fail closed if frps is configured for an operation this plugin doesn't know.
    return reject("unsupported operation")
