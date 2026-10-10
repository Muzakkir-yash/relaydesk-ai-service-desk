"""Tickets created from a chat get a real problem title, never "Hi"."""

from ai.summary import is_good_title, summarize_description, summarize_title


def _chat(*user_turns):
    msgs = []
    for text in user_turns:
        msgs += [{"sender": "user", "text": text}, {"sender": "ai", "text": "Okay, let's look at that."}]
    return msgs


def test_escalated_chat_skips_greeting(client, enduser):
    res = client.post("/tickets/ai-triage/escalate",
                      json={"messages": _chat("hello", "my laptop is didnt open", "laptop screen didnt visible"),
                            "subject": "Hello"},
                      headers=enduser)
    assert res.status_code == 200, res.text
    ticket = client.get(f"/tickets/{res.json()['ticket_id']}", headers=enduser).json()
    assert ticket["subject"] == "My laptop is didnt open — laptop screen didnt visible"
    assert ticket["description"] == "my laptop is didnt open\nlaptop screen didnt visible"


def test_resolved_chat_skips_greeting_and_thanks(client, enduser):
    res = client.post("/tickets/ai-triage/resolve",
                      json={"messages": _chat("hi", "whatsapp voice messages have no audio", "thanks that fixed it")},
                      headers=enduser)
    ticket = client.get(f"/tickets/{res.json()['ticket_id']}", headers=enduser).json()
    assert ticket["subject"] == "Whatsapp voice messages have no audio"
    assert "thanks" not in ticket["description"]


def test_chat_without_a_problem_gets_a_neutral_title(client, enduser):
    res = client.post("/tickets/ai-triage/escalate",
                      json={"messages": _chat("hi", "can I talk to a person"), "subject": "Hi"}, headers=enduser)
    ticket = client.get(f"/tickets/{res.json()['ticket_id']}", headers=enduser).json()
    assert ticket["subject"] == "IT support request (see conversation)"


def test_chat_reply_suggests_problem_title(client, enduser):
    history = [{"sender": "user", "text": "hi"}, {"sender": "ai", "text": "Hi! How can I help?"},
               {"sender": "user", "text": "outlook is not syncing new mail"}]
    res = client.post("/tickets/ai-triage/chat",
                      json={"message": "outlook is not syncing new mail", "chat_history": history}, headers=enduser)
    assert res.json()["subject"] == "Outlook is not syncing new mail"


def test_summary_helpers():
    assert summarize_title(["Hi, my VPN keeps dropping. It started yesterday."], "x") == "My VPN keeps dropping."
    assert summarize_title(["hello", "thanks"], "fallback") == "fallback"
    assert summarize_description(["hi", "printer jammed", "nope same thing"]) == "printer jammed"
    assert not is_good_title("Hello") and is_good_title("Printer jammed on floor 3")
    long_title = summarize_title(["my " + "very " * 40 + "long problem"], "x")
    assert len(long_title) <= 80 and long_title.endswith("…")
