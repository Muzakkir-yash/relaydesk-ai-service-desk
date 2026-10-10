"""Public demo mode protects the shared demo accounts."""

import pytest

from config import settings


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)


def _make(client, admin, email):
    res = client.post("/users", json={"name": "Shared Demo", "email": email, "password": "password123",
                                      "role": "technician"}, headers=admin)
    assert res.status_code == 201, res.text
    return res.json()


def test_demo_accounts_cannot_be_changed_or_deleted(client, admin, demo_on):
    demo = _make(client, admin, "shared-demo@company.com")
    assert client.patch(f"/users/{demo['id']}", json={"role": "enduser"}, headers=admin).status_code == 403
    assert client.post(f"/users/{demo['id']}/reset-link", headers=admin).status_code == 403
    assert client.delete(f"/users/{demo['id']}", headers=admin).status_code == 403


def test_demo_account_cannot_change_its_own_password(client, admin, demo_on):
    _make(client, admin, "shared-demo2@company.com")
    token = client.post("/auth/login", json={"email": "shared-demo2@company.com", "password": "password123"}).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    res = client.post("/auth/change-password", json={"current_password": "password123", "new_password": "hijacked123"},
                      headers=headers)
    assert res.status_code == 403


def test_other_accounts_work_normally_in_demo_mode(client, admin, demo_on):
    regular = _make(client, admin, "regular-person@example.com")
    assert client.patch(f"/users/{regular['id']}", json={"team": "network"}, headers=admin).status_code == 200


def test_demo_flag_on_health(client, demo_on):
    assert client.get("/health").json()["demo"] is True


def test_demo_mode_off_by_default(client, admin):
    assert settings.DEMO_MODE is False
    demo = _make(client, admin, "not-protected@company.com")
    assert client.patch(f"/users/{demo['id']}", json={"team": "x"}, headers=admin).status_code == 200
