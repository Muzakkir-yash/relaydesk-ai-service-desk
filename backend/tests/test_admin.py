"""Admin screens: user edit/delete, KB edit/delete/feedback, audit log."""

from database import SessionLocal
import models


def _new_user(client, admin, email, role="technician"):
    res = client.post("/users", json={"name": "Temp Person", "email": email, "password": "password123", "role": role},
                      headers=admin)
    assert res.status_code == 201, res.text
    return res.json()


# ── Users ─────────────────────────────────────────────────────────
def test_admin_edits_user(client, admin):
    u = _new_user(client, admin, "edit-me@example.com")
    res = client.patch(f"/users/{u['id']}", json={"name": "Renamed Tech", "support_level": "L3", "team": "network"},
                       headers=admin)
    assert res.status_code == 200
    assert (res.json()["name"], res.json()["support_level"], res.json()["team"]) == ("Renamed Tech", "L3", "network")


def test_non_admin_cannot_edit_users(client, tech):
    assert client.patch("/users/1", json={"role": "admin"}, headers=tech).status_code == 403


def test_delete_user_without_history(client, admin):
    u = _new_user(client, admin, "delete-me@example.com")
    assert client.delete(f"/users/{u['id']}", headers=admin).status_code == 204
    assert client.get(f"/users/{u['id']}", headers=admin).status_code == 404


def test_user_with_tickets_is_kept(client, admin, ticket):
    res = client.delete(f"/users/{ticket['user_id']}", headers=admin)
    assert res.status_code == 409
    assert "ticket history" in res.json()["detail"]


# ── Knowledge base ────────────────────────────────────────────────
def test_kb_edit_normalises_category_and_delete_is_admin_only(client, tech, admin):
    art = client.post("/kb", json={"title": "Dock firmware update", "body": "1. Download the tool.", "category": "VPN"},
                      headers=tech).json()
    assert art["category"] == "network"  # "VPN" is not a real category
    edited = client.patch(f"/kb/{art['id']}", json={"body": "1. Updated steps.", "category": "Hardware"}, headers=tech)
    assert edited.status_code == 200 and edited.json()["category"] == "hardware"
    assert client.delete(f"/kb/{art['id']}", headers=tech).status_code == 403
    assert client.delete(f"/kb/{art['id']}", headers=admin).status_code == 204


def test_kb_feedback_counts_once_per_person_per_day(client, enduser, other_user, tech):
    art = client.post("/kb", json={"title": "Feedback test", "body": "Steps", "category": "software"}, headers=tech).json()
    for _ in range(3):
        assert client.post(f"/kb/{art['id']}/feedback", json={"helpful": True}, headers=enduser).status_code == 204
    client.post(f"/kb/{art['id']}/feedback", json={"helpful": False}, headers=other_user)
    db = SessionLocal()
    row = db.get(models.KBArticle, art["id"])
    assert (row.helpful_count, row.not_helpful_count) == (1, 1)
    db.close()


# ── Audit log ─────────────────────────────────────────────────────
def test_audit_log_filters_and_names(client, admin):
    _new_user(client, admin, "audited@example.com")
    entries = client.get("/metrics/audit-log", params={"action": "user_created", "q": "audited@example.com"},
                         headers=admin).json()
    assert len(entries) == 1
    assert entries[0]["actor_name"] == "Ada Admin" and entries[0]["actor_type"] == "admin"

    techs = client.get("/metrics/audit-log", params={"actor_type": "technician", "limit": 200}, headers=admin).json()
    assert all(e["actor_type"] == "technician" for e in techs)

    page1 = client.get("/metrics/audit-log", params={"limit": 2}, headers=admin).json()
    page2 = client.get("/metrics/audit-log", params={"limit": 2, "offset": 2}, headers=admin).json()
    assert {e["id"] for e in page1}.isdisjoint({e["id"] for e in page2})

    assert "user_created" in client.get("/metrics/audit-log/actions", headers=admin).json()


def test_audit_log_is_admin_only(client, tech):
    assert client.get("/metrics/audit-log", headers=tech).status_code == 403
    assert client.get("/metrics/audit-log/actions", headers=tech).status_code == 403
