"""Authorization and input-validation regression tests."""


def test_public_register_cannot_create_admin(client):
    res = client.post("/auth/register", json={
        "name": "Mallory", "email": "mallory@example.com", "password": "longenough1", "role": "admin",
    })
    assert res.status_code == 201
    assert res.json()["role"] == "enduser"


def test_register_rejects_short_password(client):
    res = client.post("/auth/register", json={"name": "Shorty", "email": "short@example.com", "password": "abc"})
    assert res.status_code == 422


def test_login_is_case_insensitive_on_email(client):
    res = client.post("/auth/login", json={"email": "ALICE@example.com", "password": "password123"})
    assert res.status_code == 200


def test_garbage_token_is_401_not_500(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_enduser_cannot_read_someone_elses_ticket(client, ticket, other_user):
    assert client.get(f"/tickets/{ticket['id']}", headers=other_user).status_code == 403


def test_enduser_cannot_set_staff_only_status(client, ticket, enduser):
    res = client.patch(f"/tickets/{ticket['id']}/status", json={"status": "resolved"}, headers=enduser)
    assert res.status_code == 403


def test_invalid_status_value_rejected(client, ticket, tech):
    res = client.patch(f"/tickets/{ticket['id']}", json={"status": "banana"}, headers=tech)
    assert res.status_code == 422


def test_assign_to_enduser_rejected(client, ticket, tech):
    me = client.get("/auth/me", headers=tech).json()
    users_ok = client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": me["id"]}, headers=tech)
    assert users_ok.status_code == 200
    res = client.patch(f"/tickets/{ticket['id']}", json={"assigned_to": ticket["user_id"]}, headers=tech)
    assert res.status_code == 400


def test_enduser_cannot_list_users_or_run_playbooks(client, ticket, enduser):
    assert client.get("/users", headers=enduser).status_code == 403
    res = client.post(f"/tickets/{ticket['id']}/execute-playbook", json={"playbook_id": "edr_scan"}, headers=enduser)
    assert res.status_code == 403


def test_javascript_attachment_url_rejected(client, enduser):
    res = client.post("/tickets", json={
        "subject": "x", "description": "y",
        "attachments": [{"name": "evil", "url": "javascript:alert(1)"}],
    }, headers=enduser)
    assert res.status_code == 422


def test_data_url_attachment_accepted(client, enduser):
    res = client.post("/tickets", json={
        "subject": "Screenshot", "description": "see attached",
        "attachments": [{"name": "a.png", "type": "image/png", "url": "data:image/png;base64,iVBORw0KGgo="}],
    }, headers=enduser)
    assert res.status_code == 201
    assert res.json()["attachments"][0]["name"] == "a.png"


def test_static_mount_hides_tooling(client):
    assert client.get("/package.json").status_code == 404
    assert client.get("/node_modules/.package-lock.json").status_code == 404
    assert client.get("/src/main.jsx").status_code == 404
    assert client.get("/login.html").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/.env").status_code == 404


def test_admin_cannot_demote_self(client, admin):
    me = client.get("/auth/me", headers=admin).json()
    res = client.patch(f"/users/{me['id']}", json={"role": "enduser"}, headers=admin)
    assert res.status_code == 400


def test_admin_can_create_technician(client, admin):
    res = client.post("/users", json={
        "name": "New Tech", "email": "newtech@example.com", "password": "password123",
        "role": "technician", "support_level": "L2",
    }, headers=admin)
    assert res.status_code == 201
    assert res.json()["role"] == "technician"
