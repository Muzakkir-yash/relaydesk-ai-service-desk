"""
Test fixtures. Each test session runs against a fresh temporary SQLite
database with the AI in offline (rule-based fallback) mode, so tests never
touch relaydesk.db or call the Anthropic API.
"""

import os
import sys
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="relaydesk-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp_dir, "test.db").replace(os.sep, "/")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ENABLE_PAID_AI"] = "false"  # tests never call a paid API
os.environ["ENVIRONMENT"] = "development"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from database import SessionLocal  # noqa: E402
from auth import hash_password  # noqa: E402
import models  # noqa: E402

PASSWORD = "password123"

USERS = {
    "enduser": dict(name="Alice User", email="alice@example.com", role="enduser", support_level="L1"),
    "other": dict(name="Bob User", email="bob@example.com", role="enduser", support_level="L1"),
    "tech": dict(name="Charlie Tech", email="charlie@example.com", role="technician", team="network", support_level="L2"),
    "admin": dict(name="Ada Admin", email="admin@example.com", role="admin", support_level="L3"),
}


@pytest.fixture(scope="session", autouse=True)
def seed_users():
    db = SessionLocal()
    try:
        for data in USERS.values():
            db.add(models.User(password_hash=hash_password(PASSWORD), **data))
        db.add(models.KBArticle(
            title="VPN Connection Troubleshooting",
            body="1. Disconnect and reconnect the VPN client.\n2. Flush DNS with ipconfig /flushdns.",
            tags="vpn,network,anyconnect",
            category="network",
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client, key):
    res = client.post("/auth/login", json={"email": USERS[key]["email"], "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="session")
def enduser(client):
    return _login(client, "enduser")


@pytest.fixture(scope="session")
def other_user(client):
    return _login(client, "other")


@pytest.fixture(scope="session")
def tech(client):
    return _login(client, "tech")


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin")


@pytest.fixture
def ticket(client, enduser):
    res = client.post("/tickets", json={
        "subject": "VPN keeps disconnecting",
        "description": "My AnyConnect VPN drops every few minutes when working from home.",
    }, headers=enduser)
    assert res.status_code == 201, res.text
    return res.json()
