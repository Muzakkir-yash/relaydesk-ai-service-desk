"""Browser session (httpOnly cookie), CSRF guard and auth rate limiting."""

import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings
from routers import auth as auth_router

CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def reset_limits():
    for limiter in (auth_router.login_failures_by_account, auth_router.login_failures_by_ip,
                    auth_router.registrations_by_ip):
        limiter.clear()
    yield
    for limiter in (auth_router.login_failures_by_account, auth_router.login_failures_by_ip,
                    auth_router.registrations_by_ip):
        limiter.clear()


@pytest.fixture
def browser():
    """A fresh client with its own cookie jar, like a separate browser."""
    return TestClient(app)


def _login(browser, email="alice@example.com", password="password123"):
    return browser.post("/auth/login", json={"email": email, "password": password}, headers=CSRF)


def test_login_sets_httponly_cookie(browser):
    res = _login(browser)
    assert res.status_code == 200
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{settings.AUTH_COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()


def test_cookie_authenticates_reads(browser):
    _login(browser)
    me = browser.get("/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "alice@example.com"


def test_cookie_write_requires_csrf_header(browser):
    _login(browser)
    body = {"subject": "Mouse broken", "description": "My USB mouse stopped working"}
    assert browser.post("/tickets", json=body).status_code == 403
    assert browser.post("/tickets", json=body, headers=CSRF).status_code == 201


def test_logout_clears_session(browser):
    _login(browser)
    assert browser.post("/auth/logout", headers=CSRF).status_code == 204
    assert browser.get("/auth/me").status_code == 401


def test_no_credentials_is_401(browser):
    assert browser.get("/tickets").status_code == 401


def test_repeated_bad_passwords_are_rate_limited(browser):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        assert _login(browser, password="wrong-password").status_code == 401
    blocked = _login(browser, password="wrong-password")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # Even the right password is refused while the account bucket is full
    assert _login(browser).status_code == 429
    # Other accounts from the same IP are unaffected until the IP limit is hit
    assert _login(browser, email="bob@example.com").status_code == 200


def test_successful_login_resets_failure_count(browser):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT - 1):
        _login(browser, password="wrong-password")
    assert _login(browser).status_code == 200
    assert _login(browser, password="wrong-password").status_code == 401  # counter restarted


def test_registration_is_rate_limited_per_ip(browser):
    for i in range(settings.REGISTER_MAX_PER_IP):
        res = browser.post("/auth/register", json={
            "name": f"Signup {i}", "email": f"signup{i}@example.com", "password": "longenough1",
        })
        assert res.status_code == 201, res.text
    blocked = browser.post("/auth/register", json={
        "name": "One more", "email": "onemore@example.com", "password": "longenough1",
    })
    assert blocked.status_code == 429
