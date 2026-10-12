import hashlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER_DIR))

import database as db
import frp_plugin


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return TestClient(frp_plugin.app)


def active_account(username="cliente_teste"):
    db.register_user(username, "SenhaSegura123")
    return db.approve_user(username, 30)


def login_payload(rec, token=None):
    return {
        "content": {
            "user": rec["username"],
            "timestamp": 123456789,
            "metas": {"token": token or rec["frp_token"]},
            "privilege_key": "untrusted-value",
        }
    }


def test_login_rejects_unknown_or_wrong_user(client):
    rec = active_account()
    payload = login_payload(rec)
    payload["content"]["metas"]["token"] = "token-invalido"
    response = client.post("/handler?op=Login", json=payload)
    assert response.status_code == 200
    assert response.json()["reject"] is True


def test_login_accepts_valid_per_user_token(client):
    rec = active_account()
    response = client.post("/handler?op=Login", json=login_payload(rec))
    assert response.status_code == 200
    body = response.json()
    assert body["reject"] is False
    assert body["content"]["privilege_key"] == hashlib.md5(
        str(123456789).encode("utf-8")
    ).hexdigest()


def test_new_proxy_only_allows_assigned_port(client):
    rec = active_account()
    user = {"user": rec["username"], "metas": {"token": rec["frp_token"]}}
    good = {
        "content": {
            "user": user,
            "proxy_name": f"usb-{rec['id']}",
            "proxy_type": "tcp",
            "remote_port": rec["server_port"],
        }
    }
    response = client.post("/handler?op=NewProxy", json=good)
    assert response.status_code == 200
    assert response.json()["reject"] is False

    good["content"]["remote_port"] = int(rec["server_port"]) + 1
    response = client.post("/handler?op=NewProxy", json=good)
    assert response.status_code == 200
    assert response.json()["reject"] is True


def test_blocked_account_cannot_login_or_create_proxy(client):
    rec = active_account()
    db.block_user(rec["username"])
    response = client.post("/handler?op=Login", json=login_payload(rec))
    assert response.status_code == 200
    assert response.json()["reject"] is True


def test_expired_account_is_rejected(client):
    rec = active_account()
    with db.connect() as conn:
        conn.execute(
            "UPDATE users SET valid_until = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", rec["id"]),
        )
    response = client.post("/handler?op=Login", json=login_payload(rec))
    assert response.status_code == 200
    assert response.json()["reject"] is True


def test_reset_token_is_hashed_and_consumed_once(client):
    rec = active_account()
    raw = db.create_reset_token(rec["username"])
    with db.connect() as conn:
        row = conn.execute(
            "SELECT token_hash, used FROM resets WHERE user_id = ?", (rec["id"],)
        ).fetchone()
    assert row["token_hash"] != raw
    assert row["used"] == 0

    old_api_token = rec["token"]
    assert db.consume_reset_token(raw, "NovaSenhaSegura456")
    updated = db.get_user(rec["username"])
    assert updated["token"] != old_api_token
    assert db.verify_password("NovaSenhaSegura456", updated["password"])
    assert not db.consume_reset_token(raw, "OutraSenhaSegura789")


def test_reset_rejects_short_password(client):
    rec = active_account()
    raw = db.create_reset_token(rec["username"])
    assert not db.consume_reset_token(raw, "curta")
