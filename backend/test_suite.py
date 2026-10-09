"""
Comprehensive Integration Test Suite for RelayDesk
Tests Phases 0 through 5 end-to-end against the FastAPI backend using TestClient.
"""

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
import models
from auth import hash_password

client = TestClient(app)

def run_tests():
    print("=" * 60)
    print("🚀 RELAYDESK STEP-BY-STEP VERIFICATION SUITE")
    print("=" * 60)

    # ── 1. Phase 0: Auth & Roles ──
    print("\n[Phase 0] Verifying Authentication & Roles...")
    
    # Login as Alice (End-user)
    res_alice = client.post("/auth/login", json={"email": "alice@company.com", "password": "password123"})
    assert res_alice.status_code == 200, f"Alice login failed: {res_alice.text}"
    alice_token = res_alice.json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    print("  ✓ Alice (End-user) logged in successfully")

    # Login as Charlie (Technician)
    res_charlie = client.post("/auth/login", json={"email": "charlie@company.com", "password": "password123"})
    assert res_charlie.status_code == 200, f"Charlie login failed: {res_charlie.text}"
    charlie_token = res_charlie.json()["access_token"]
    charlie_headers = {"Authorization": f"Bearer {charlie_token}"}
    print("  ✓ Charlie (Technician) logged in successfully")

    # Login as Admin
    res_admin = client.post("/auth/login", json={"email": "admin@company.com", "password": "password123"})
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.text}"
    admin_token = res_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  ✓ Eve (Admin) logged in successfully")

    # Verify /auth/me for each
    me_alice = client.get("/auth/me", headers=alice_headers).json()
    assert me_alice["role"] == "enduser"
    me_tech = client.get("/auth/me", headers=charlie_headers).json()
    assert me_tech["role"] == "technician"
    me_admin = client.get("/auth/me", headers=admin_headers).json()
    assert me_admin["role"] == "admin"
    print("  ✓ Role isolation and /auth/me tokens verified")

    # ── 2. Phase 1 & 2 & 3: Ticket Creation, AI Job 1 & 2 ──
    print("\n[Phase 1-3] Testing Ticket Creation, AI Classification & Deflection...")
    ticket_payload = {
        "subject": "Cannot connect to Cisco AnyConnect VPN client",
        "description": "I keep getting error 412 when trying to connect to the corporate VPN from home. I am unable to access internal tools.",
    }
    res_t1 = client.post("/tickets", json=ticket_payload, headers=alice_headers)
    assert res_t1.status_code == 201, f"Create ticket failed: {res_t1.text}"
    t1_data = res_t1.json()
    t1_id = t1_data["id"]
    print(f"  ✓ Ticket #{t1_id} created by Alice")
    print(f"    - Category: {t1_data['category']}")
    print(f"    - Priority: {t1_data['priority']}")
    print(f"    - Suggested Team: {t1_data['suggested_team']}")
    print(f"    - SLA Due: {t1_data['sla_due']}")
    print(f"    - Initial Status: {t1_data['status']}")

    assert t1_data["category"] == "network", f"Expected category 'network', got {t1_data['category']}"
    assert t1_data["priority"] in ["high", "medium", "critical", "low"]
    assert t1_data["sla_due"] is not None

    # Fetch full ticket details to check messages (AI deflection message)
    res_t1_detail = client.get(f"/tickets/{t1_id}", headers=alice_headers)
    assert res_t1_detail.status_code == 200
    t1_detail = res_t1_detail.json()
    messages = t1_detail.get("messages", [])
    print(f"    - Messages count: {len(messages)}")
    ai_msgs = [m for m in messages if m["sender_type"] == "ai"]
    assert len(ai_msgs) > 0, "Expected AI deflection message"
    print(f"  ✓ AI Job 2 Deflection attempted: \"{ai_msgs[0]['body'][:70]}...\"")

    # Test Self-Service Resolution Confirmation (Fixed It) flow on a 2nd ticket
    print("\n[Phase 3] Testing AI Deflection Self-Service Close Flow...")
    res_t2 = client.post("/tickets", json={
        "subject": "How do I reset my company password?",
        "description": "I need instructions to reset my domain password."
    }, headers=alice_headers)
    t2_id = res_t2.json()["id"]
    res_confirm = client.post(f"/tickets/{t2_id}/confirm-resolved", headers=alice_headers)
    assert res_confirm.status_code == 200
    t2_resolved = res_confirm.json()
    assert t2_resolved["status"] == "deflected"
    assert t2_resolved["resolved_at"] is not None
    print(f"  ✓ Ticket #{t2_id} auto-closed as 'deflected' via user confirmation")

    # ── 3. Phase 4: AI Job 3 — Handover Briefing (⭐ Star Feature) ──
    print("\n[Phase 4] Testing Escalation & AI Job 3 Handover Briefing Generation...")
    
    # Alice adds a message saying the fix didn't work
    client.post(f"/tickets/{t1_id}/messages", json={"body": "I tried restarting AnyConnect and flushing DNS, but the error persists."}, headers=alice_headers)
    
    # Alice clicks "Still broken" / Escalate
    res_esc = client.post(f"/tickets/{t1_id}/escalate", headers=alice_headers)
    assert res_esc.status_code == 200, f"Escalate failed: {res_esc.text}"
    t1_esc = res_esc.json()
    assert t1_esc["status"] in ("assigned", "escalated")
    assert t1_esc["assigned_to"] is not None
    print(f"  ✓ Ticket #{t1_id} status escalated & auto-assigned to Technician ID {t1_esc['assigned_to']}")

    # Technician Charlie inspects the ticket
    res_tech_view = client.get(f"/tickets/{t1_id}", headers=charlie_headers)
    assert res_tech_view.status_code == 200
    tech_ticket = res_tech_view.json()
    briefing = tech_ticket.get("briefing")
    assert briefing is not None, "Handover briefing was not attached to ticket!"
    
    print("  ⭐ Handover Briefing Generated Successfully:")
    print(f"    - Summary: {briefing.get('summary')}")
    print(f"    - User Tried: {briefing.get('user_tried')}")
    print(f"    - AI Tried: {briefing.get('ai_tried')}")
    print(f"    - Likely Root Causes: {briefing.get('likely_causes')}")
    print(f"    - Recommended Steps: {briefing.get('suggested_steps')}")
    print(f"    - Related Tickets: {briefing.get('related_ticket_ids')}")

    # Technician updates ticket: Assigns to himself and replies
    res_assign = client.patch(f"/tickets/{t1_id}", json={"assigned_to": me_tech["id"], "status": "assigned"}, headers=charlie_headers)
    assert res_assign.status_code == 200
    assert res_assign.json()["status"] == "assigned"
    print(f"  ✓ Technician assigned Ticket #{t1_id} to self")

    # Technician replies
    res_tech_msg = client.post(f"/tickets/{t1_id}/messages", json={"body": "Hello Alice, I have reviewed your briefing. I have reset your RADIUS gateway profile. Please try reconnecting now."}, headers=charlie_headers)
    assert res_tech_msg.status_code == 201
    
    # Verify status changed to in_progress upon tech reply
    t1_progress = client.get(f"/tickets/{t1_id}", headers=charlie_headers).json()
    assert t1_progress["status"] == "in_progress"
    print(f"  ✓ Ticket #{t1_id} moved to 'in_progress' upon technician reply")

    # Technician resolves ticket
    res_resolve = client.post(f"/tickets/{t1_id}/resolve", headers=charlie_headers)
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "resolved"
    print(f"  ✓ Ticket #{t1_id} resolved by technician")

    # ── 4. Phase 5: Metrics & Performance Dashboard ──
    print("\n[Phase 5] Verifying Metrics API & Analytics...")
    res_metrics = client.get("/metrics", headers=admin_headers)
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    print(f"  ✓ Total Incidents: {metrics_data['total_tickets']}")
    print(f"  ✓ Deflected Count: {metrics_data['deflected']}")
    print(f"  ✓ Deflection Rate: {metrics_data['deflection_rate']}%")
    print(f"  ✓ 7-Day Deflection Rate: {metrics_data['recent_deflection_rate_7d']}%")
    print(f"  ✓ Open Backlog: {metrics_data['open_backlog']}")
    print(f"  ✓ SLA Breached: {metrics_data['sla_breached']}")
    print(f"  ✓ Category Breakdown: {metrics_data['tickets_by_category']}")
    print(f"  ✓ Status Breakdown: {metrics_data['tickets_by_status']}")

    # ── 5. Knowledge Base CRUD ──
    print("\n[Phase 0-5] Verifying Knowledge Base CRUD...")
    kb_res = client.get("/kb", headers=alice_headers)
    assert kb_res.status_code == 200
    assert len(kb_res.json()) >= 5
    print(f"  ✓ KB listing contains {len(kb_res.json())} searchable articles")

    # ── 6. Enterprise Enhancements: CSV Export & Attachments ──
    print("\n[Enterprise Features] Verifying CSV Export & File Attachments...")
    
    # Test CSV Export
    res_export = client.get("/metrics/export", headers=admin_headers)
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")
    assert "Ticket ID" in res_export.text
    assert "SLA Status" in res_export.text
    print("  ✓ CSV Metrics Export generated valid dataset with headers")

    # Test Ticket Creation with Attachment
    att_payload = {
        "subject": "Screen flickering with error dialog",
        "description": "See attached screenshot of error popup.",
        "attachments": [{"name": "error_log.png", "data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "type": "image/png", "size": 1024}],
    }
    res_att_ticket = client.post("/tickets", json=att_payload, headers=alice_headers)
    assert res_att_ticket.status_code == 201
    t_att_data = res_att_ticket.json()
    assert t_att_data.get("attachments") is not None
    assert len(t_att_data["attachments"]) == 1
    assert t_att_data["attachments"][0]["name"] == "error_log.png"
    print(f"  ✓ Ticket #{t_att_data['id']} created with image attachment")

    # Test Message with Attachment
    res_att_msg = client.post(
        f"/tickets/{t_att_data['id']}/messages",
        json={
            "body": "Here is additional diagnostic output",
            "attachments": [{"name": "diag.txt", "data": "data:text/plain;base64,VGVzdCBkaWFnbm9zdGljcw==", "type": "text/plain", "size": 256}],
        },
        headers=charlie_headers,
    )
    assert res_att_msg.status_code == 201
    msg_data = res_att_msg.json()
    assert msg_data.get("attachments") is not None
    assert len(msg_data["attachments"]) == 1
    assert msg_data["attachments"][0]["name"] == "diag.txt"
    print("  ✓ Message with attachment posted and retrieved")

    # ── 7. Top Enterprise IT Features ──
    print("\n[Top IT Features] Testing Device Context, Playbooks & MIM Announcements...")

    # 1. Device Context
    assert t_att_data.get("device_name") is not None
    assert t_att_data.get("ip_address") is not None
    assert t_att_data.get("device_os") is not None
    print(f"  ✓ Device Context verified on Ticket #{t_att_data['id']}: {t_att_data['device_name']} ({t_att_data['ip_address']})")

    # 2. Ping Host Diagnostic
    res_ping = client.post(f"/tickets/{t_att_data['id']}/ping-device", headers=charlie_headers)
    assert res_ping.status_code == 200
    ping_data = res_ping.json()
    assert ping_data["online"] is True
    assert "Ping statistics" in ping_data["raw_output"]
    print(f"  ✓ Host Ping diagnostic verified for {ping_data['device_name']} (Latency: {ping_data['avg_latency_ms']}ms)")

    # 3. Technician Quick-Fix Playbook (Remote DNS Flush)
    res_pb = client.post(
        f"/tickets/{t_att_data['id']}/execute-playbook",
        json={"playbook_id": "remote_dns_flush"},
        headers=charlie_headers,
    )
    assert res_pb.status_code == 200
    pb_data = res_pb.json()
    assert pb_data["status"] == "success"
    assert pb_data["exit_code"] == 0
    assert "ipconfig /flushdns" in pb_data["command_output"]
    print(f"  ✓ One-Click IT Playbook executed: '{pb_data['title']}' (ExitCode: 0)")

    # 4. Technician Quick-Fix Playbook (AD Password Reset)
    res_pb2 = client.post(
        f"/tickets/{t_att_data['id']}/execute-playbook",
        json={"playbook_id": "ad_password_reset"},
        headers=charlie_headers,
    )
    assert res_pb2.status_code == 200
    assert "Set-ADAccountPassword" in res_pb2.json()["command_executed"]
    assert "Password reset executed" in res_pb2.json()["command_output"]
    print("  ✓ AD Password & Temp Passkey Reset playbook executed successfully")

    # 5. Major Incident Management (MIM) Announcements
    res_ann_active = client.get("/announcements/active", headers=alice_headers)
    assert res_ann_active.status_code == 200
    active_anns = res_ann_active.json()
    assert len(active_anns) >= 1
    print(f"  ✓ Active MIM Outage Banners verified ({len(active_anns)} active): '{active_anns[0]['title'][:50]}...'")

    # Create new announcement
    res_new_ann = client.post(
        "/announcements",
        json={
            "title": "⚡ Core Switch Firmware Upgrade",
            "message": "Secondary core switch maintenance in progress.",
            "severity": "maintenance",
            "affected_services": ["HQ Floor 3 Switchstack"],
            "workaround": "Traffic auto-routed to redundant spine.",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert res_new_ann.status_code == 201
    new_ann_id = res_new_ann.json()["id"]
    print(f"  ✓ New MIM Announcement #{new_ann_id} broadcasted by Admin")

    # Toggle announcement to inactive
    res_update_ann = client.patch(
        f"/announcements/{new_ann_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert res_update_ann.status_code == 200
    assert res_update_ann.json()["is_active"] is False
    print(f"  ✓ MIM Announcement #{new_ann_id} resolved & deactivated")

    print("\n" + "=" * 60)
    print("🎉 ALL STEP-BY-STEP PHASES & ENTERPRISE FEATURES VERIFIED AND PASSING!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()


