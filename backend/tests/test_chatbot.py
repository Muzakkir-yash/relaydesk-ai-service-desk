"""The support chatbot: knowledge retrieval, the learn-from-technicians loop,
feedback ranking, and the Claude conversation shape (via a fake client)."""

import asyncio
import json
from types import SimpleNamespace

import pytest

import ai.client as client_mod
from ai.assistant import build_messages, chat_turn
from ai.knowledge import KnowledgeIndex, feedback_multiplier
from config import settings
from database import SessionLocal
import models

ARTICLES = [
    {"id": 1, "title": "VPN Connection Troubleshooting", "body": "Reconnect AnyConnect and flush DNS.", "tags": "vpn,network"},
    {"id": 2, "title": "Printer Queue Stuck", "body": "Restart the print spooler service.", "tags": "printer,spooler"},
    {"id": 3, "title": "Outlook Not Syncing", "body": "Restart Outlook in safe mode and repair Office.", "tags": "outlook,email"},
]


# ── Retrieval ─────────────────────────────────────────────────────
def test_bm25_ranks_the_matching_article_first():
    hits = KnowledgeIndex(ARTICLES).search("my vpn keeps disconnecting from home")
    assert hits and hits[0].article["id"] == 1


def test_search_handles_plural_and_tense():
    hits = KnowledgeIndex(ARTICLES).search("printers stuck, queues not printing")
    assert hits[0].article["id"] == 2


def test_unrelated_query_finds_nothing():
    assert KnowledgeIndex(ARTICLES).search("lunch menu for friday") == []


def test_feedback_moves_ranking():
    assert feedback_multiplier(0, 0) == pytest.approx(1.0)
    assert feedback_multiplier(9, 1) > 1.2
    assert feedback_multiplier(0, 8) < 0.75
    # Two equally relevant articles (plus the rest of the KB): the one that has
    # actually fixed users' problems should rank first
    twins = ARTICLES + [
        {"id": 10, "title": "Wifi reset steps", "body": "Forget the network.", "tags": "wifi",
         "helpful_count": 0, "not_helpful_count": 6},
        {"id": 11, "title": "Wifi reset steps", "body": "Forget the network.", "tags": "wifi",
         "helpful_count": 6, "not_helpful_count": 0},
    ]
    assert KnowledgeIndex(twins).search("wifi reset")[0].article["id"] == 11


# ── Learning loop, end to end (offline mode) ─────────────────────
NOVEL_PROBLEM = "SAP GUI shows error ZX42 when I post a vendor invoice"
TECH_FIX = ("Fixed: open SAP GUI Options > Security > Security Configuration, set the default "
            "action to Allow, then restart SAP Logon. The ZX42 invoice error is gone.")


def _chat(client, headers, message, history):
    history = history + [{"sender": "user", "text": message}]
    res = client.post("/tickets/ai-triage/chat", json={"message": message, "chat_history": history}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json(), history + [{"sender": "ai", "text": res.json()["reply"]}]


def test_bot_learns_from_a_technician_fix(client, enduser, other_user, tech, admin):
    # 1. The bot has never seen this problem
    first, history = _chat(client, enduser, NOVEL_PROBLEM, [])
    assert not first["used_articles"]

    # 2. User escalates; a technician fixes it and resolves the ticket
    esc = client.post("/tickets/ai-triage/escalate", json={"messages": history, "subject": "SAP invoice error ZX42"},
                      headers=enduser).json()
    ticket_id = esc["ticket_id"]
    assert client.post(f"/tickets/{ticket_id}/messages", json={"body": TECH_FIX}, headers=tech).status_code == 201
    assert client.post(f"/tickets/{ticket_id}/resolve", headers=tech).status_code == 200

    # 3. The AI drafted a KB article — hidden from users and the bot until approved
    drafts = [a for a in client.get("/kb", headers=tech).json() if a["source_ticket_id"] == ticket_id]
    assert len(drafts) == 1 and drafts[0]["status"] == "pending_approval"
    assert "Security Configuration" in drafts[0]["body"]
    assert all(a["id"] != drafts[0]["id"] for a in client.get("/kb", headers=other_user).json())
    still_unknown, _ = _chat(client, other_user, NOVEL_PROBLEM, [])
    assert not still_unknown["used_articles"]

    # 4. Staff approve it; the next user with the same problem gets the fix from the bot
    assert client.patch(f"/kb/{drafts[0]['id']}", json={"status": "published"}, headers=admin).status_code == 200
    learned, _ = _chat(client, other_user, "Getting SAP error ZX42 posting an invoice", [])
    assert [a["id"] for a in learned["used_articles"]] == [drafts[0]["id"]]
    assert "Security Configuration" in learned["reply"]

    # Resolving again doesn't create a duplicate draft
    client.post(f"/tickets/{ticket_id}/resolve", headers=tech)
    assert sum(a["source_ticket_id"] == ticket_id for a in client.get("/kb", headers=tech).json()) == 1


def test_ticket_closed_without_human_fix_teaches_nothing(client, enduser, tech, ticket):
    client.post(f"/tickets/{ticket['id']}/resolve", headers=tech)
    assert all(a["source_ticket_id"] != ticket["id"] for a in client.get("/kb", headers=tech).json())


def test_session_outcomes_feed_article_ranking(client, enduser):
    db = SessionLocal()
    article = db.query(models.KBArticle).filter(models.KBArticle.title == "VPN Connection Troubleshooting").first()
    before = (article.helpful_count, article.not_helpful_count)
    db.close()

    chat = [{"sender": "user", "text": "vpn drops"}, {"sender": "ai", "text": "Try reconnecting."}]
    client.post("/tickets/ai-triage/resolve", json={"messages": chat, "used_article_ids": [article.id]}, headers=enduser)
    client.post("/tickets/ai-triage/escalate", json={"messages": chat, "used_article_ids": [article.id]}, headers=enduser)

    db = SessionLocal()
    after = db.query(models.KBArticle).get(article.id)
    assert (after.helpful_count, after.not_helpful_count) == (before[0] + 1, before[1] + 1)
    db.close()


# ── Claude conversation shape (fake client, no network) ──────────
class FakeMessages:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


@pytest.fixture
def fake_claude(monkeypatch):
    # Fake SDK client below — no network call is ever made in these tests
    monkeypatch.setattr(settings, "ENABLE_PAID_AI", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test-key-0123456789abcdef")

    def install(payload):
        messages = FakeMessages(payload)
        monkeypatch.setattr(client_mod, "get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages)))
        return messages

    return install


def _reply(**overrides):
    base = {"reply": "Try reconnecting AnyConnect.", "intent": "troubleshoot", "subject": "VPN drops",
            "category": "network", "priority": "medium", "used_article_ids": [1]}
    return {**base, **overrides}


def test_claude_gets_a_real_multi_turn_conversation(fake_claude):
    fake = fake_claude(_reply())
    history = [
        {"sender": "ai", "text": "Hi! How can I help?"},  # widget greeting — dropped, must start with user
        {"sender": "user", "text": "vpn issue"},
        {"sender": "ai", "text": "What happens when you connect?"},
        {"sender": "user", "text": "it drops every 5 minutes"},
    ]
    result = asyncio.run(chat_turn("it drops every 5 minutes", history, ARTICLES))

    call = fake.calls[0]
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["user", "assistant", "user"]
    assert "<knowledge>" in call["messages"][-1]["content"] and 'id="1"' in call["messages"][-1]["content"]
    assert call["messages"][-1]["content"].endswith("it drops every 5 minutes")
    assert "<knowledge>" not in call["messages"][0]["content"]  # earlier turns unchanged
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert result["status_intent"] == "troubleshoot" and result["used_articles"][0]["id"] == 1


def test_claude_cannot_mark_resolved_before_suggesting_anything(fake_claude):
    fake_claude(_reply(intent="resolved"))
    result = asyncio.run(chat_turn("fixed", [{"sender": "user", "text": "fixed"}], ARTICLES))
    assert result["status_intent"] == "clarify"


def test_unknown_article_ids_from_claude_are_dropped(fake_claude):
    fake_claude(_reply(used_article_ids=[1, 999]))
    result = asyncio.run(chat_turn("vpn drops", [{"sender": "user", "text": "vpn drops"}], ARTICLES))
    assert [a["id"] for a in result["used_articles"]] == [1]


def test_claude_escalation_passes_through(fake_claude):
    fake_claude(_reply(intent="escalate", reply="A technician will take it from here.", priority="high"))
    result = asyncio.run(chat_turn("I clicked a phishing link", [{"sender": "user", "text": "I clicked a phishing link"}], ARTICLES))
    assert result["status_intent"] == "escalate" and result["priority"] == "high"


def test_build_messages_merges_consecutive_user_turns():
    msgs = build_messages("second", [{"sender": "user", "text": "first"}, {"sender": "user", "text": "second"}], "<knowledge/>")
    assert len(msgs) == 1 and msgs[0]["content"].endswith("first\n\nsecond")
