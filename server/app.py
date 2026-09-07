import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import database as db

app = FastAPI(title="USB FIX", version="0.5.0")

_attempts = defaultdict(list)


def client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "?"


def rate_limit(ip: str, scope: str, limit: int = 5, window: int = 60):
    key = (ip, scope)
    now = time.time()
    bucket = [t for t in _attempts[key] if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="muitas tentativas, aguarde um pouco")
    bucket.append(now)
    _attempts[key] = bucket[-limit * 3:]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


class RegisterBody(BaseModel):
    email: str = ""
    username: str = ""
    password: str


class LoginBody(BaseModel):
    email: str = ""
    username: str = ""
    password: str
    instance: Optional[str] = None


class SubdomainBody(BaseModel):
    subdomain: str


class PasswordBody(BaseModel):
    current: str = ""
    new: str


class ResetBody(BaseModel):
    token: str
    new: str


class TunnelEventBody(BaseModel):
    status: str
    instance: Optional[str] = None


class UserActionBody(BaseModel):
    username: str
    days: int = 30


class AdminPasswordBody(BaseModel):
    username: str
    password: str


class UsernameBody(BaseModel):
    username: str
    newUsername: str


class MeUsernameBody(BaseModel):
    newUsername: str
    instance: Optional[str] = None


class CheckoutBody(BaseModel):
    name: str
    email: Optional[str] = None
    cpf: str
    planId: str = ""


class DownloadsBody(BaseModel):
    usbClientUrl: Optional[str] = None
    usbServerUrl: Optional[str] = None
    activationKey: Optional[str] = None
    appUrl: Optional[str] = None


class PlanItem(BaseModel):
    id: str
    name: str
    price: float
    days: int


class PlansBody(BaseModel):
    plans: list[PlanItem]


def extract_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="token ausente")
    rec = db.get_by_token(authorization.split(" ", 1)[1].strip())
    if not rec:
        raise HTTPException(status_code=401, detail="token inválido")
    return rec


def require_admin(authorization: Optional[str] = Header(None)):
    if not config.ADMIN_TOKEN:
        raise HTTPException(status_code=501, detail="admin não configurado")
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="não autorizado")


@app.post("/api/register")
def register(body: RegisterBody, request: Request):
    rate_limit(client_ip(request), "register")
    identifier = (body.username or body.email).strip()
    try:
        db.register_user(identifier, body.password, email=(body.email or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "message": "conta criada, aguarde liberação do vendedor"}


@app.post("/api/login")
def login(body: LoginBody, request: Request):
    rate_limit(client_ip(request), "login")
    identifier = (body.email or body.username).strip()
    try:
        rec = db.login_user(identifier, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if (
        body.instance
        and db.effective_status(rec) == "active"
        and db.held_by_other(rec["id"], body.instance)
    ):
        raise HTTPException(
            status_code=403,
            detail="conexão já ativa em outro computador com esta conta. Encerre o app no outro computador para entrar aqui.",
        )
    return {"token": db.get_user(rec["username"])["token"], "user": db.public_state(rec)}


@app.get("/api/me")
def me(rec=Depends(extract_token), instance: Optional[str] = None):
    if (
        instance
        and db.effective_status(rec) == "active"
        and db.held_by_other(rec["id"], instance)
    ):
        raise HTTPException(
            status_code=403,
            detail="conexão já ativa em outro computador com esta conta.",
        )
    return db.public_state(rec)


@app.post("/api/me/username")
def set_my_username(body: MeUsernameBody, rec=Depends(extract_token)):
    if (
        body.instance
        and db.effective_status(rec) == "active"
        and db.held_by_other(rec["id"], body.instance)
    ):
        raise HTTPException(
            status_code=403,
            detail="conexão já ativa em outro computador com esta conta.",
        )
    email = (rec.get("email") or "").strip().lower()
    if not email or str(rec["username"]).strip().lower() != email:
        raise HTTPException(
            status_code=400,
            detail="sua conta já tem um nome de usuário. Para trocar, peça ao suporte.",
        )
    try:
        rec = db.set_username(str(rec["username"]), body.newUsername)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/subdomain")
def set_subdomain(body: SubdomainBody, rec=Depends(extract_token)):
    try:
        rec = db.set_subdomain(rec, body.subdomain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/change-password")
def change_password(body: PasswordBody, rec=Depends(extract_token)):
    if len(body.new) < 6:
        raise HTTPException(status_code=400, detail="nova senha muito curta (mínimo 6 caracteres)")
    if not db.verify_password(body.current, rec["password"]):
        raise HTTPException(status_code=400, detail="senha atual incorreta")
    db.change_password(rec["username"], body.new)
    return {"ok": True, "message": "senha alterada"}


@app.post("/api/reset-password")
def reset_password(body: ResetBody):
    info = db.get_reset_user(body.token)
    if not info:
        raise HTTPException(status_code=400, detail="link inválido ou expirado")
    if len(body.new) < 6:
        raise HTTPException(status_code=400, detail="nova senha muito curta (mínimo 6 caracteres)")
    db.mark_reset_used(info["reset_id"])
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (info["user_id"],)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    db.change_password(row["username"], body.new)
    return {"ok": True, "message": "senha redefinida, faça login"}


@app.get("/api/sessions")
def sessions(rec=Depends(extract_token)):
    return db.user_sessions(rec["id"])


@app.post("/api/tunnel-event")
def tunnel_event(body: TunnelEventBody, rec=Depends(extract_token)):
    status = db.effective_status(rec)
    if status != "active":
        raise HTTPException(status_code=403, detail="assinatura suspensa")
    if body.status == "connect":
        if not db.claim_tunnel(rec["id"], body.instance or "web"):
            raise HTTPException(
                status_code=409,
                detail="conexão já ativa em outro computador com esta conta.",
            )
    else:
        db.end_session(rec["id"], body.instance or None)
    return {"ok": True}


@app.get("/api/downloads")
def downloads(authorization: Optional[str] = Header(None)):
    app_url = db.get_setting("dl.app.url", "/downloads/USB-Fix.exe")
    usb_client = db.get_setting("dl.usb.client.url", "")
    usb_server = db.get_setting("dl.usb.server.url", "")
    result = {
        "app": {"version": "0.5.0", "name": "USB FIX", "url": app_url},
        "usbRedirector": {
            "client": {"name": "USB Redirector (Cliente)", "url": usb_client},
            "server": {"name": "USB Redirector (Servidor)", "url": usb_server},
        },
    }
    try:
        rec = extract_token(authorization)
    except HTTPException:
        rec = None
    if rec and db.effective_status(rec) == "active":
        key = db.get_setting("dl.usb.key", "")
        if key:
            result["activationKey"] = key
    return result


@app.get("/api/version")
def app_version():
    return {"version": config.APP_VERSION, "url": "/downloads/USB-Fix.exe"}


@app.get("/api/admin/downloads")
def admin_get_downloads(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {
        "usbClientUrl": db.get_setting("dl.usb.client.url", ""),
        "usbServerUrl": db.get_setting("dl.usb.server.url", ""),
        "activationKey": db.get_setting("dl.usb.key", ""),
        "appUrl": db.get_setting("dl.app.url", "/downloads/USB-Fix.exe"),
    }


@app.post("/api/admin/downloads")
def admin_set_downloads(body: DownloadsBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if body.usbClientUrl is not None:
        db.set_setting("dl.usb.client.url", body.usbClientUrl.strip())
    if body.usbServerUrl is not None:
        db.set_setting("dl.usb.server.url", body.usbServerUrl.strip())
    if body.activationKey is not None:
        db.set_setting("dl.usb.key", body.activationKey.strip())
    if body.appUrl is not None:
        db.set_setting("dl.app.url", body.appUrl.strip())
    return admin_get_downloads(authorization)


@app.get("/api/health")
def health():
    return {"ok": True}


# --- Asaas (Pix) ------------------------------------------------------

def asaas(method: str, path: str, body=None):
    if not config.ASAAS_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="pagamento não configurado")
    url = config.ASAAS_BASE_URL.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("access_token", config.ASAAS_ACCESS_TOKEN)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "USB FIX/0.5")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise HTTPException(status_code=502, detail=f"asaas: {exc.code} {detail[:300]}")


def ensure_asaas_customer(username, name, email, cpf):
    digits = re.sub(r"\D", "", cpf or "")
    if len(digits) != 11:
        raise HTTPException(status_code=400, detail="CPF inválido")
    resp = asaas("GET", f"/customers?cpfCnpj={digits}")
    data = resp.get("data") or []
    if data:
        return data[0]["id"]
    created = asaas("POST", "/customers", {
        "name": (name or username).strip()[:100],
        "email": (email or "").strip(),
        "cpfCnpj": digits,
        "externalReference": username,
    })
    return created["id"]


@app.post("/api/checkout")
def checkout(body: CheckoutBody, rec=Depends(extract_token)):
    if db.effective_status(rec) == "blocked":
        raise HTTPException(status_code=403, detail="conta bloqueada")
    username = rec["username"]
    plan = plan_for(body.planId)
    customer_id = ensure_asaas_customer(username, body.name, body.email, body.cpf)
    today = datetime.now(timezone.utc).date().isoformat()
    pay = asaas("POST", "/payments", {
        "customer": customer_id,
        "billingType": "PIX",
        "value": plan["price"],
        "dueDate": today,
        "description": f"Plano {plan['name']} - {plan['days']} dias",
        "externalReference": username,
    })
    qr = asaas("GET", f"/payments/{pay['id']}/pixQrCode")
    pid = db.record_payment(
        username, pay["id"], customer_id,
        plan["price"], plan["days"], qr.get("payload"),
        plan_name=plan["name"],
    )
    return {
        "paymentId": pid,
        "asaasPaymentId": pay["id"],
        "plan": plan["name"],
        "price": plan["price"],
        "days": plan["days"],
        "qrCode": {
            "encodedImage": qr.get("encodedImage"),
            "payload": qr.get("payload"),
            "expirationDate": qr.get("expirationDate"),
        },
    }


@app.get("/api/payment/{payment_id}")
def payment_status(payment_id: int, rec=Depends(extract_token)):
    row = db.get_payment_row(payment_id)
    if not row or row["username"] != rec["username"]:
        raise HTTPException(status_code=404, detail="pagamento não encontrado")
    status = row["status"]
    try:
        live = asaas("GET", f"/payments/{row['asaas_payment_id']}")
        live_status = (live.get("status") or "").upper()
        if live_status in ("RECEIVED", "CONFIRMED"):
            db.mark_payment_paid(row["asaas_payment_id"])
            status = "paid"
        else:
            status = live_status.lower()
    except HTTPException:
        pass
    return {
        "paymentId": row["id"],
        "status": status,
        "plan": row["plan_name"],
        "price": row["value"],
        "days": row["days"],
        "paid": status == "paid",
        "paidAt": row.get("paid_at"),
    }


@app.post("/api/webhooks/asaas")
async def asaas_webhook(request: Request):
    secret = request.query_params.get("secret")
    if not config.WEBHOOK_SECRET or secret != config.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    body = await request.json()
    event = (body.get("event") or "").upper()
    payment = body.get("payment") or {}
    payment_id = payment.get("id")
    status = (payment.get("status") or "").upper()
    if payment_id and event in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED") and status in ("CONFIRMED", "RECEIVED"):
        try:
            db.mark_payment_paid(payment_id)
        except ValueError:
            pass
    return {"ok": True}


SITE_DIR = Path(__file__).resolve().parent / "site"
DOWNLOADS_DIR = SITE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(SITE_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(SITE_DIR / "admin.html")


@app.get("/plan")
def plan_info():
    return plan_view()


@app.get("/api/plan")
def api_plan():
    return plan_view()


@app.get("/api/plans")
def api_plans():
    return {"plans": plans_view()}


def plans_view():
    raw = db.get_setting("plans", "")
    if raw:
        try:
            items = json.loads(raw)
            if isinstance(items, list):
                cleaned = []
                for p in items:
                    if not isinstance(p, dict) or not p.get("id") or not p.get("name"):
                        continue
                    try:
                        price = float(p.get("price", 0) or 0)
                        days = int(p.get("days", 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    cleaned.append({"id": str(p["id"]), "name": str(p["name"]), "price": round(price, 2), "days": days})
                if cleaned:
                    return cleaned
        except (json.JSONDecodeError, TypeError):
            pass
    return [dict(p) for p in config.PLANS]


def plan_for(plan_id):
    plans = plans_view()
    for p in plans:
        if p.get("id") == plan_id:
            return p
    return plans[0] if plans else {"id": "30d", "name": "Base", "price": config.PLAN_PRICE, "days": config.PLAN_DAYS}


def plan_view():
    plans = plans_view()
    return dict(plans[0]) if plans else {"id": "30d", "name": "Base", "price": config.PLAN_PRICE, "days": config.PLAN_DAYS}


@app.get("/api/admin/plans")
def admin_get_plans(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"plans": plans_view()}


@app.post("/api/admin/plans")
def admin_set_plans(body: PlansBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    cleaned = []
    for p in body.plans:
        pid = (p.id or "").strip() or "plan"
        cleaned.append({
            "id": pid,
            "name": (p.name or "").strip() or pid,
            "price": max(0.0, round(p.price, 2)),
            "days": int(p.days),
        })
    db.set_setting("plans", json.dumps(cleaned, ensure_ascii=False))
    return {"plans": cleaned}


@app.get("/api/admin/users")
def admin_list_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return [db.public_state(r) | {"username": r["username"], "statusRaw": r["status"]} for r in db.list_users()]


@app.post("/api/admin/users/approve")
def admin_approve(body: UserActionBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        rec = db.approve_user(body.username, max(1, body.days))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/admin/users/extend")
def admin_extend(body: UserActionBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        rec = db.extend_user(body.username, max(1, body.days))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/admin/users/block")
def admin_block(body: UserActionBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        rec = db.block_user(body.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/admin/users/delete")
def admin_delete(body: UserActionBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        db.delete_user(body.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "message": "usuário excluído"}


@app.post("/api/admin/users/username")
def admin_set_username(body: UsernameBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        rec = db.set_username(body.username, body.newUsername)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.public_state(rec)


@app.post("/api/admin/users/reset")
def admin_reset(body: UserActionBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        token = db.create_reset_token(body.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"token": token, "expires": (db.utcnow() + timedelta(hours=db.RESET_TTL_HOURS)).isoformat()}


@app.post("/api/admin/users/password")
def admin_set_password(body: AdminPasswordBody, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    user = db.get_user(body.username)
    if not user:
        raise HTTPException(status_code=400, detail="usuário inválido")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="senha muito curta (mínimo 6 caracteres)")
    db.change_password(user["username"], body.password)
    return {"ok": True, "message": "senha definida pelo admin"}


@app.get("/{path:path}", include_in_schema=False)
def site_static(path: str):
    base = SITE_DIR.resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=404, detail="Not Found")
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Not Found")