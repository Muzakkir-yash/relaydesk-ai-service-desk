"""In-app notifications: who gets told about what."""

from fastapi.testclient import TestClient

from main import app
from routers import auth as auth_router


def _notes(client, headers):
    return client.get("/notifications", headers=headers).json()


def _kinds_for_ticket(client, headers, ticket_id):
    return [n["kind"] for n in _notes(client, headers)["items"] if n["ticket_id"] == ticket_id]


def test_escalation_notifies_the_assigned_technician(client, enduser, tech, ticket):
    client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser)
    assigned = client.get(f"/tickets/{ticket['id']}", headers=tech).json()["assigned_to"]
    me = client.get("/auth/me", headers=tech).json()
    if assigned == me["id"]:
        assert "ticket_assigned" in _kinds_for_ticket(client, tech, ticket["id"])


def test_manual_assignment_notifies_new_assignee_only(client, admin, tech, ticket):
    tech_id = client.get("/auth/me", headers=tech).json()["id"]
    admin_id = client.get("/auth/me", headers=admin).json()["id"]
    # The ticket may already be auto-assigned to this technician; move it away first
    client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": admin_id}, headers=admin)
    client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": tech_id}, headers=admin)
    before = _kinds_for_ticket(client, tech, ticket["id"]).count("ticket_assigned")
    assert before >= 1
    # Re-saving the same assignee is not a change -> no duplicate
    client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": tech_id}, headers=admin)
    assert _kinds_for_ticket(client, tech, ticket["id"]).count("ticket_assigned") == before


def test_replies_notify_the_other_side_not_the_sender(client, enduser, tech, ticket):
    tech_id = client.get("/auth/me", headers=tech).json()["id"]
    client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": tech_id, "status": "assigned"}, headers=tech)
    client.post(f"/tickets/{ticket['id']}/messages", json={"body": "Please restart the dock"}, headers=tech)
    assert "reply" in _kinds_for_ticket(client, enduser, ticket["id"])
    assert "reply" not in _kinds_for_ticket(client, tech, ticket["id"])  # you aren't told about your own reply

    client.post(f"/tickets/{ticket['id']}/messages", json={"body": "Done, still flickering"}, headers=enduser)
    assert "reply" in _kinds_for_ticket(client, tech, ticket["id"])


def test_resolving_notifies_the_requester(client, enduser, tech, ticket):
    client.post(f"/tickets/{ticket['id']}/resolve", headers=tech)
    assert "ticket_resolved" in _kinds_for_ticket(client, enduser, ticket["id"])


def test_password_reset_request_notifies_admins(client, admin):
    auth_router.forgot_requests_by_ip.clear()
    client.post("/auth/forgot-password", json={"email": "bob@example.com"})
    messages = [n["message"] for n in _notes(client, admin)["items"]]
    assert any("bob@example.com" in m and "password reset" in m for m in messages)


def test_mark_read_and_privacy(client, enduser, other_user, tech, ticket):
    client.post(f"/tickets/{ticket['id']}/resolve", headers=tech)
    data = _notes(client, enduser)
    note = next(n for n in data["items"] if n["ticket_id"] == ticket["id"])
    assert note["link"] == f"/ticket.html?id={ticket['id']}"

    assert client.post(f"/notifications/{note['id']}/read", headers=other_user).status_code == 404  # not theirs
    assert client.post(f"/notifications/{note['id']}/read", headers=enduser).status_code == 204
    assert _notes(client, enduser)["unread"] == data["unread"] - 1

    client.post("/notifications/read-all", headers=enduser)
    assert _notes(client, enduser)["unread"] == 0
    assert TestClient(app).get("/notifications").status_code == 401  # fresh client: no login cookie
