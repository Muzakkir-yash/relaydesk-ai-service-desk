"""End-to-end ticket lifecycle: create → AI classify/deflect → escalate → resolve → rate."""


def test_create_ticket_is_classified_and_answered(client, ticket):
    assert ticket["status"] == "ai_handling"
    assert ticket["category"] == "network"
    assert ticket["priority"] in ("low", "medium", "high", "critical")
    assert ticket["sla_due"] is not None
    senders = [m["sender_type"] for m in ticket["messages"]]
    assert senders[0] == "user" and "ai" in senders


def test_escalate_creates_briefing_and_assigns(client, ticket, enduser):
    res = client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "assigned"
    assert body["assigned_to"] is not None
    assert body["briefing"]["summary"]
    assert body["briefing"]["likely_causes"]


def test_escalating_twice_is_409_not_500(client, ticket, enduser):
    assert client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser).status_code == 200
    again = client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser)
    assert again.status_code == 409
    # The session must still be healthy afterwards
    assert client.get(f"/tickets/{ticket['id']}", headers=enduser).status_code == 200


def test_cannot_confirm_deflection_after_escalation(client, ticket, enduser):
    client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser)
    res = client.post(f"/tickets/{ticket['id']}/confirm-resolved", headers=enduser)
    assert res.status_code == 409


def test_confirm_resolved_marks_deflected(client, ticket, enduser):
    res = client.post(f"/tickets/{ticket['id']}/confirm-resolved", headers=enduser)
    assert res.status_code == 200
    assert res.json()["status"] == "deflected"
    assert res.json()["resolved_at"] is not None


def test_technician_reply_moves_to_in_progress_then_resolve_and_rate(client, ticket, enduser, tech):
    client.post(f"/tickets/{ticket['id']}/escalate", headers=enduser)
    reply = client.post(f"/tickets/{ticket['id']}/messages", json={"body": "Looking into it"}, headers=tech)
    assert reply.status_code == 201
    assert client.get(f"/tickets/{ticket['id']}", headers=tech).json()["status"] == "in_progress"

    # Rating before resolution is refused
    early = client.post(f"/tickets/{ticket['id']}/rate", json={"rating": 5}, headers=enduser)
    assert early.status_code == 409

    assert client.post(f"/tickets/{ticket['id']}/resolve", headers=tech).json()["status"] == "resolved"
    assert client.post(f"/tickets/{ticket['id']}/rate", json={"rating": 9}, headers=enduser).status_code == 422
    rated = client.post(f"/tickets/{ticket['id']}/rate", json={"rating": 5, "comment": "Great"}, headers=enduser)
    assert rated.status_code == 201
    assert client.post(f"/tickets/{ticket['id']}/rate", json={"rating": 4}, headers=enduser).status_code == 400


def test_briefing_cites_similar_resolved_ticket(client, enduser, tech):
    first = client.post("/tickets", json={
        "subject": "Printer spooler stuck on floor 3",
        "description": "Print queue on the floor 3 printer is stuck and jobs never print.",
    }, headers=enduser).json()
    client.post(f"/tickets/{first['id']}/resolve", headers=tech)

    second = client.post("/tickets", json={
        "subject": "Floor 3 printer queue stuck again",
        "description": "The print queue is stuck, nothing prints from the floor 3 printer.",
    }, headers=enduser).json()
    escalated = client.post(f"/tickets/{second['id']}/escalate", headers=enduser).json()
    related = " ".join(escalated["briefing"]["related_ticket_ids"])
    assert f"#{first['id']}" in related


def test_ai_triage_escalate_and_resolve(client, enduser):
    chat = [
        {"sender": "user", "text": "My Outlook will not sync new email"},
        {"sender": "ai", "text": "Try restarting Outlook in safe mode."},
        {"sender": "user", "text": "Still not working"},
    ]
    esc = client.post("/tickets/ai-triage/escalate", json={"messages": chat, "category": "", "priority": "urgent"},
                      headers=enduser)
    assert esc.status_code == 200, esc.text
    data = esc.json()
    assert data["category"] == "other" and data["priority"] == "medium"
    assert data["briefing_summary"]

    res = client.post("/tickets/ai-triage/resolve", json={"messages": chat[:2]}, headers=enduser)
    assert res.status_code == 200
    assert res.json()["status"] == "deflected"


def test_enduser_list_only_shows_own_tickets(client, ticket, enduser, other_user):
    mine = client.get("/tickets", headers=enduser).json()
    theirs = client.get("/tickets", headers=other_user).json()
    assert any(t["id"] == ticket["id"] for t in mine)
    assert all(t["id"] != ticket["id"] for t in theirs)


def test_playbook_is_marked_simulated(client, ticket, tech):
    res = client.post(f"/tickets/{ticket['id']}/execute-playbook", json={"playbook_id": "remote_dns_flush"}, headers=tech)
    assert res.status_code == 200
    assert "Simulated" in res.json()["message"]["body"]


def test_metrics_and_csv_export(client, ticket, tech):
    m = client.get("/metrics", headers=tech).json()
    assert m["total_tickets"] >= 1
    csv = client.get("/metrics/export", headers=tech)
    assert csv.status_code == 200 and csv.text.startswith("Ticket ID")
