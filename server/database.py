import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from config import (
    DB_PATH,
    FRPS_ADDR,
    FRPS_PORT,
    FRPS_TOKEN,
    PORT_RANGE,
    PRICE,
    SUBDOMAIN_HOST,
    SUBDOMAIN_MAX_CHANGES,
    SUBSCRIPTION_DAYS,
    TRIAL_HOURS,
)

PBKDF2_ITERATIONS = 200_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    subdomain TEXT UNIQUE,
    server_port INTEGER UNIQUE,
    token TEXT UNIQUE,
    device_name TEXT,
    valid_until TEXT,
    changes_left INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT NOT NULL,
    approved_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id INTEGER NOT NULL,
    client_ip TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    bytes_up INTEGER NOT NULL DEFAULT 0,
    bytes_down INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    asaas_payment_id TEXT UNIQUE,
    asaas_customer_id TEXT,
    plan_name TEXT NOT NULL,
    value REAL NOT NULL,
    days INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payload TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.execute("UPDATE users SET email = username WHERE email IS NULL OR email = ''")


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


def parsable(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def new_token():
    return secrets.token_hex(32)


# --- senha -------------------------------------------------------------

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return secrets.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def change_password(identifier, new_password):
    identifier = (identifier or "").strip().lower()
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password = ? WHERE (username = ? OR email = ?)",
            (hash_password(new_password), identifier, identifier),
        )


RESET_TTL_HOURS = 24


def create_reset_token(identifier):
    identifier = (identifier or "").strip().lower()
    rec = get_user(identifier)
    if not rec:
        raise ValueError("usuário inválido")
    raw = secrets.token_urlsafe(32)
    with connect() as conn:
        conn.execute("DELETE FROM resets WHERE user_id = ?", (rec["id"],))
        conn.execute(
            "INSERT INTO resets (user_id, token_hash, used, created_at, expires_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (
                rec["id"],
                raw,
                iso(utcnow()),
                iso(utcnow() + timedelta(hours=RESET_TTL_HOURS)),
            ),
        )
    return raw


def get_reset_user(token):
    if not token:
        return None
    row = None
    with connect() as conn:
        row = conn.execute(
            "SELECT r.* FROM resets r WHERE r.token_hash = ? AND r.used = 0",
            (token,),
        ).fetchone()
    if not row:
        return None
    if parsable(row["expires_at"]) <= utcnow():
        return None
    return {"reset_id": row["id"], "user_id": row["user_id"]}


def mark_reset_used(reset_id):
    with connect() as conn:
        conn.execute("UPDATE resets SET used = 1 WHERE id = ?", (reset_id,))


# --- nomes / portas ----------------------------------------------------

def slugify_subdomain(value):
    clean = "".join(c.lower() for c in value if c.isalnum() or c == "-")
    return clean.strip("-")[:32]


def default_subdomain():
    return f"cliente{secrets.randbelow(9000) + 1000}"


def allocate_endpoints(conn, user_id):
    if not conn.execute("SELECT 1 FROM users WHERE id = ? AND subdomain IS NOT NULL", (user_id,)).fetchone():
        sub = default_subdomain()
        while conn.execute("SELECT 1 FROM users WHERE subdomain = ?", (sub,)).fetchone():
            sub = default_subdomain()
        conn.execute("UPDATE users SET subdomain = ? WHERE id = ?", (sub, user_id))
    if not conn.execute("SELECT 1 FROM users WHERE id = ? AND server_port IS NOT NULL", (user_id,)).fetchone():
        used = {r[0] for r in conn.execute("SELECT server_port FROM users WHERE server_port IS NOT NULL").fetchall()}
        pmin, pmax = PORT_RANGE
        port = None
        for p in range(pmin, pmax + 1):
            if p not in used:
                port = p
                break
        if port is None:
            raise RuntimeError("porta esgotada")
        conn.execute("UPDATE users SET server_port = ? WHERE id = ?", (port, user_id))


# --- conta -------------------------------------------------------------

def register_user(identifier, password, email=""):
    identifier = (identifier or "").strip().lower()
    email = (email or "").strip().lower()
    if len(password) < 6:
        raise ValueError("senha muito curta (mínimo 6 caracteres)")
    if "@" in identifier:
        if not EMAIL_RE.match(identifier):
            raise ValueError("e-mail inválido")
        username = identifier
        email = email or identifier
    else:
        if not USERNAME_RE.match(identifier):
            raise ValueError("usuário inválido (use 3 a 32 caracteres: letras, números, . _ -)")
        username = identifier
    if email and not EMAIL_RE.match(email):
        raise ValueError("e-mail inválido")
    now = iso(utcnow())
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ? OR (email IS NOT NULL AND email = ?)",
            (username, email),
        ).fetchone()
        if exists:
            raise ValueError("usuário já cadastrado")
        try:
            conn.execute(
                "INSERT INTO users (username, email, password, status, registered_at) VALUES (?, ?, ?, 'pending', ?)",
                (username, email or None, hash_password(password), now),
            )
        except sqlite3.IntegrityError:
            raise ValueError("usuário já cadastrado")
    return get_user(username)


def get_user(identifier):
    identifier = (identifier or "").strip().lower()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?", (identifier, identifier)
        ).fetchone()
    return dict(row) if row else None


def get_by_token(token):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def set_username(identifier, new_username):
    identifier = (identifier or "").strip().lower()
    new_username = (new_username or "").strip().lower()
    if not USERNAME_RE.match(new_username):
        raise ValueError("usuário inválido (use 3 a 32 caracteres: letras, números, . _ -)")
    rec = get_user(identifier)
    if not rec:
        raise ValueError("usuário inválido")
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ? AND id != ?",
            (new_username, rec["id"]),
        ).fetchone()
        if exists:
            raise ValueError("usuário já em uso")
        conn.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, rec["id"]))
    return get_user(new_username)


def login_user(raw_identifier, password):
    identifier = (raw_identifier or "").strip().lower()
    rec = get_user(identifier)
    if not rec or not verify_password(password, rec["password"]):
        raise ValueError("usuário ou senha inválidos")
    with connect() as conn:
        if not rec.get("token"):
            conn.execute("UPDATE users SET token = ? WHERE id = ?", (new_token(), rec["id"]))
    return get_user(identifier)


def effective_status(rec):
    if rec["status"] in ("blocked",):
        return "blocked"
    valid = parsable(rec.get("valid_until"))
    if valid and datetime.now(timezone.utc) > valid:
        return "expired"
    return rec["status"]


def public_state(rec):
    endpoint_domain = SUBDOMAIN_HOST
    return {
        "id": rec["id"],
        "username": rec["username"],
        "email": rec.get("email") or rec["username"],
        "deviceName": rec.get("device_name"),
        "subdomain": rec.get("subdomain"),
        "endpoint": f"{rec['subdomain']}.{endpoint_domain}" if rec.get("subdomain") else None,
        "port": rec.get("server_port"),
        "status": effective_status(rec),
        "validUntil": rec.get("valid_until"),
        "changesLeft": rec.get("changes_left"),
        "plan": "Base",
        "price": PRICE,
        "frps": {
            "addr": FRPS_ADDR,
            "port": FRPS_PORT,
            "token": FRPS_TOKEN,
        },
    }


# --- admin -------------------------------------------------------------

def approve_user(raw_username, days):
    username = (raw_username or "").strip().lower()
    rec = get_user(username)
    if not rec:
        raise ValueError("usuário inválido")
    now = utcnow()
    end_iso = iso(now + timedelta(days=days))
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            allocate_endpoints(conn, rec["id"])
            if not rec.get("token"):
                conn.execute("UPDATE users SET token = ? WHERE id = ?", (new_token(), rec["id"]))
            conn.execute(
                "UPDATE users SET status = 'active', valid_until = ?, changes_left = ?, approved_at = ? WHERE id = ?",
                (end_iso, SUBDOMAIN_MAX_CHANGES, iso(now), rec["id"]),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return get_user(username)


def extend_user(raw_username, days):
    username = (raw_username or "").strip().lower()
    rec = get_user(username)
    if not rec:
        raise ValueError("usuário inválido")
    new_end = utcnow() + timedelta(days=days)
    if rec.get("valid_until"):
        current = parsable(rec["valid_until"])
        if current and current > utcnow():
            new_end = current + timedelta(days=days)
    with connect() as conn:
        conn.execute(
            "UPDATE users SET valid_until = ?, status = 'active' WHERE id = ?",
            (iso(new_end), rec["id"]),
        )
    return get_user(username)


def block_user(raw_username):
    username = (raw_username or "").strip().lower()
    rec = get_user(username)
    if not rec:
        raise ValueError("usuário inválido")
    with connect() as conn:
        conn.execute("UPDATE users SET status = 'blocked' WHERE id = ?", (rec["id"],))
    return get_user(username)


def delete_user(raw_username):
    username = (raw_username or "").strip().lower()
    rec = get_user(username)
    if not rec:
        raise ValueError("usuário inválido")
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE key_id = ?", (rec["id"],))
        conn.execute("DELETE FROM payments WHERE username = ?", (rec["username"],))
        conn.execute("DELETE FROM users WHERE id = ?", (rec["id"],))
    return True


def list_users():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY registered_at DESC").fetchall()
    return [dict(r) for r in rows]


# --- sessões -----------------------------------------------------------

def set_subdomain(rec, raw_sub):
    sub = slugify_subdomain(raw_sub)
    if not sub:
        raise ValueError("nome inválido")
    if sub == rec.get("subdomain"):
        return rec
    if (rec.get("changes_left") or 0) <= 0:
        raise ValueError("limite de alterações atingido")
    with connect() as conn:
        try:
            conn.execute(
                "UPDATE users SET subdomain = ?, changes_left = ? WHERE id = ?",
                (sub, (rec.get("changes_left") or 1) - 1, rec["id"]),
            )
        except sqlite3.IntegrityError:
            raise ValueError("nome já em uso")
    return get_user(rec["username"])


def add_session(user_id, client_ip, status="connected"):
    now = iso(utcnow())
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (key_id, client_ip, status, started_at) VALUES (?, ?, ?, ?)",
            (user_id, client_ip, status, now),
        )


SESSION_LEASE_SECONDS = 90


def _expire_stale(user_id, cutoff):
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ?, status = 'ended' WHERE key_id = ? "
            "AND status = 'connected' AND ended_at IS NULL AND started_at < ?",
            (iso(utcnow()), user_id, cutoff),
        )


def _holder(user_id, cutoff):
    with connect() as conn:
        row = conn.execute(
            "SELECT client_ip FROM sessions WHERE key_id = ? AND status = 'connected' "
            "AND ended_at IS NULL AND started_at >= ? ORDER BY id DESC LIMIT 1",
            (user_id, cutoff),
        ).fetchone()
    return row["client_ip"] if row else None


def held_by_other(user_id, instance_id):
    cutoff = iso(utcnow() - timedelta(seconds=SESSION_LEASE_SECONDS))
    _expire_stale(user_id, cutoff)
    holder = _holder(user_id, cutoff)
    return bool(holder) and holder != instance_id


def claim_tunnel(user_id, instance_id):
    cutoff = iso(utcnow() - timedelta(seconds=SESSION_LEASE_SECONDS))
    _expire_stale(user_id, cutoff)
    holder = _holder(user_id, cutoff)
    if holder:
        if holder == instance_id:
            with connect() as conn:
                conn.execute(
                    "UPDATE sessions SET started_at = ? WHERE key_id = ? "
                    "AND status = 'connected' AND ended_at IS NULL AND client_ip = ?",
                    (iso(utcnow()), user_id, instance_id),
                )
            return True
        return False
    add_session(user_id, instance_id)
    return True


def end_session(user_id, instance_id=None):
    now = iso(utcnow())
    with connect() as conn:
        if instance_id:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, status = 'ended' WHERE key_id = ? "
                "AND ended_at IS NULL AND client_ip = ?",
                (now, user_id, instance_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, status = 'ended' WHERE key_id = ? AND ended_at IS NULL",
                (now, user_id),
            )


def user_sessions(user_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE key_id = ? ORDER BY started_at DESC LIMIT 30", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- pagamentos / plano -----------------------------------------------

def record_payment(username, asaas_payment_id, customer_id, value, days, payload, plan_name="Base"):
    now = iso(utcnow())
    with connect() as conn:
        conn.execute(
            "INSERT INTO payments (username, asaas_payment_id, asaas_customer_id, plan_name, value, days, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, asaas_payment_id, customer_id, plan_name, value, days, payload, now),
        )
        row = conn.execute(
            "SELECT id FROM payments WHERE asaas_payment_id = ?", (asaas_payment_id,)
        ).fetchone()
    return row["id"]


def get_payment_row(payment_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    return dict(row) if row else None


def get_payment_by_asaas(asaas_payment_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM payments WHERE asaas_payment_id = ?", (asaas_payment_id,)).fetchone()
    return dict(row) if row else None


# --- configurações (chave/valor) --------------------------------------

def get_setting(key, default=None):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def mark_payment_paid(asaas_payment_id):
    row = get_payment_by_asaas(asaas_payment_id)
    if not row:
        raise ValueError("pagamento não encontrado")
    if row["status"] == "paid":
        return get_user(row["username"]), True
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rec = conn.execute("SELECT * FROM users WHERE username = ?", (row["username"],)).fetchone()
            if not rec:
                conn.rollback()
                raise ValueError("usuário não encontrado")
            allocate_endpoints(conn, rec["id"])
            now = utcnow()
            if not rec["token"]:
                conn.execute("UPDATE users SET token = ? WHERE id = ?", (new_token(), rec["id"]))
            base = now
            if rec["valid_until"]:
                current = parsable(rec["valid_until"])
                if current and current > now:
                    base = current
            end = iso(base + timedelta(days=row["days"]))
            conn.execute(
                "UPDATE users SET status = 'active', valid_until = ?, approved_at = COALESCE(approved_at, ?), changes_left = ? WHERE id = ?",
                (end, iso(now), SUBDOMAIN_MAX_CHANGES, rec["id"]),
            )
            conn.execute(
                "UPDATE payments SET status = 'paid', paid_at = ? WHERE id = ?",
                (iso(now), row["id"]),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return get_user(row["username"]), False