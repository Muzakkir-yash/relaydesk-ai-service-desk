"""Forgot / reset / change password, and resolving outage banners."""

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from routers import auth as auth_router
import models

CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def reset_limits():
    for limiter in (auth_router.forgot_requests_by_ip, auth_router.reset_attempts_by_ip,
                    auth_router.login_failures_by_account, auth_router.login_failures_by_ip,
                    auth_router.registrations_by_ip):
        limiter.clear()


def _user(client, admin, email):
    res = client.post("/users", json={"name": "Reset Me", "email": email, "password": "oldpassword1"}, headers=admin)
    assert res.status_code == 201, res.text
    return res.json()


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _token_from(res):
    return parse_qs(urlparse(res.json()["reset_path"]).query)["token"][0]


def test_forgot_password_never_reveals_accounts(client, admin):
    u = _user(client, admin, "forgot@example.com")
    known = client.post("/auth/forgot-password", json={"email": "forgot@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    flagged = client.get(f"/users/{u['id']}", headers=admin).json()
    assert flagged["password_reset_requested_at"] is not None


def test_full_reset_flow_signs_out_old_sessions(client, admin):
    u = _user(client, admin, "reset-flow@example.com")
    old_session = {"Authorization": f"Bearer {_login(client, u['email'], 'oldpassword1').json()['access_token']}"}
    client.post("/auth/forgot-password", json={"email": u["email"]})

    link = client.post(f"/users/{u['id']}/reset-link", headers=admin)
    assert link.status_code == 200
    token = _token_from(link)
    assert client.get(f"/users/{u['id']}", headers=admin).json()["password_reset_requested_at"] is None

    assert client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword1"}).status_code == 204
    assert client.get("/auth/me", headers=old_session).status_code == 401          # old session signed out
    assert _login(client, u["email"], "oldpassword1").status_code == 401           # old password gone
    assert _login(client, u["email"], "newpassword1").status_code == 200
    again = client.post("/auth/reset-password", json={"token": token, "new_password": "another-pass1"})
    assert again.status_code == 400                                                # single use


def test_reset_link_is_admin_only_and_new_link_cancels_old(client, admin, tech):
    u = _user(client, admin, "two-links@example.com")
    assert client.post(f"/users/{u['id']}/reset-link", headers=tech).status_code == 403
    first = _token_from(client.post(f"/users/{u['id']}/reset-link", headers=admin))
    second = _token_from(client.post(f"/users/{u['id']}/reset-link", headers=admin))
    assert client.post("/auth/reset-password", json={"token": first, "new_password": "newpassword1"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": second, "new_password": "newpassword1"}).status_code == 204


def test_expired_and_bogus_links_rejected(client, admin):
    u = _user(client, admin, "expired@example.com")
    token = _token_from(client.post(f"/users/{u['id']}/reset-link", headers=admin))
    db = SessionLocal()
    db.query(models.PasswordResetToken).filter_by(user_id=u["id"]).update(
        {"expires_at": datetime.utcnow() - timedelta(minutes=1)})
    db.commit()
    db.close()
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword1"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": "x" * 43, "new_password": "newpassword1"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422


def test_reset_tokens_are_stored_hashed(client, admin):
    u = _user(client, admin, "hashed@example.com")
    token = _token_from(client.post(f"/users/{u['id']}/reset-link", headers=admin))
    db = SessionLocal()
    stored = [r.token_hash for r in db.query(models.PasswordResetToken).filter_by(user_id=u["id"])]
    db.close()
    assert token not in stored and all(len(h) == 64 for h in stored)


def test_change_password_keeps_this_browser_signed_in(client, admin):
    u = _user(client, admin, "changer@example.com")
    other_device = {"Authorization": f"Bearer {_login(client, u['email'], 'oldpassword1').json()['access_token']}"}
    browser = TestClient(app)
    browser.post("/auth/login", json={"email": u["email"], "password": "oldpassword1"}, headers=CSRF)

    wrong = browser.post("/auth/change-password", json={"current_password": "nope", "new_password": "newpassword1"},
                         headers=CSRF)
    assert wrong.status_code == 400
    ok = browser.post("/auth/change-password", json={"current_password": "oldpassword1", "new_password": "newpassword1"},
                      headers=CSRF)
    assert ok.status_code == 204
    assert browser.get("/auth/me").status_code == 200            # this browser got a fresh session
    assert client.get("/auth/me", headers=other_device).status_code == 401  # other devices signed out


def test_staff_can_resolve_outage_banner(client, tech, enduser):
    created = client.post("/announcements", json={"title": "Email outage", "message": "Exchange is down"}, headers=tech)
    ann_id = created.json()["id"]
    assert any(a["id"] == ann_id for a in client.get("/announcements/active", headers=enduser).json())
    assert client.patch(f"/announcements/{ann_id}", json={"is_active": False}, headers=enduser).status_code == 403
    assert client.patch(f"/announcements/{ann_id}", json={"is_active": False}, headers=tech).status_code == 200
    assert all(a["id"] != ann_id for a in client.get("/announcements/active", headers=enduser).json())
