"""The built-in knowledge-base library, the trained article matcher, typo
correction and the guards that keep everyday problems out of escalation."""

import asyncio

import pytest

from ai.assistant import chat_turn
from ai.deflector import expand_related, matcher_ranking
from ai.knowledge import correct_typos
from database import SessionLocal
from kb_library import KB_LIBRARY, sync_kb_library
import models


def _published():
    db = SessionLocal()
    try:
        rows = db.query(models.KBArticle).filter(models.KBArticle.status == "published").all()
        return [{"id": r.id, "title": r.title, "body": r.body, "tags": r.tags, "category": r.category} for r in rows]
    finally:
        db.close()


def _reply(message, articles):
    return asyncio.run(chat_turn(message, [{"sender": "user", "text": message}], articles))


def test_library_articles_are_loaded_on_startup():
    titles = {a["title"] for a in _published()}
    assert {a["title"] for a in KB_LIBRARY} <= titles


def test_sync_never_overwrites_staff_edits():
    db = SessionLocal()
    try:
        article = db.query(models.KBArticle).filter_by(title=KB_LIBRARY[0]["title"]).first()
        article.body = "Edited by the service desk"
        db.commit()
        assert sync_kb_library(db, models) == 0
        db.refresh(article)
        assert article.body == "Edited by the service desk"
        sync_kb_library(db, models, overwrite=True)  # seed.py restores the built-in text
        db.refresh(article)
        assert article.body == KB_LIBRARY[0]["body"]
    finally:
        db.close()


def test_typos_are_corrected_but_names_left_alone():
    articles = _published()
    assert correct_typos("batery not chargin", articles) == "battery not charging"
    assert correct_typos("my printr is ofline", articles) == "my printer is offline"
    assert correct_typos("Sarah from finance says hello", articles) == "Sarah from finance says hello"


@pytest.mark.parametrize("message, title_word", [
    ("the base of my laptop gets really warm and the fan roars", "Overheating"),
    ("everything i type comes out in capital letters", "Keyboard"),
    ("my external hard disk isn't showing up", "USB"),
    ("onedrive has been stuck on processing changes all day", "OneDrive"),
    ("outlook search shows no results", "Outlook Search"),
])
def test_matcher_finds_the_right_article_for_new_wording(message, title_word):
    article, _ = matcher_ranking(message, _published())[0]
    assert title_word in article["title"]


@pytest.mark.parametrize("message, must_mention", [
    ("web cameranot work", "privacy shutter"),            # run-together typo
    ("laptop plugged in but not charging", "powercfg"),
    ("my screen is upside down", "orientation"),
    ("how do I set up out of office", "automatic replies"),
    ("bitlocker is asking for a recovery key", "key id"),
])
def test_chatbot_answers_everyday_problems(message, must_mention):
    result = _reply(message, _published())
    assert result["status_intent"] == "troubleshoot"
    assert must_mention in result["reply"].lower()


def test_unknown_problem_gets_no_made_up_article():
    result = _reply("The Hyperion plugin shows error QW77 when I export a ledger", _published())
    assert not result["used_articles"]


def test_single_user_problem_is_not_an_outage():
    result = _reply("can't access the shared drive", _published())
    assert result["status_intent"] != "escalate"


def test_real_outage_still_escalates():
    result = _reply("nobody on our floor can get online", _published())
    assert result["status_intent"] == "escalate"


@pytest.mark.parametrize("message", [
    "a popup says my files are encrypted and I need to pay bitcoin",
    "my charger cable is frayed and sparking",
])
def test_safety_issues_always_go_to_a_person(message):
    assert _reply(message, _published())["status_intent"] == "escalate"


@pytest.mark.parametrize("message, topic", [
    ("my inbox is full of junk", "spam"),
    ("it takes all day to charge my laptop", "battery"),
    ("laptop is burning hot", "overheating"),
    ("i can't see my face in the meeting", "camera"),
])
def test_related_words_add_the_topic(message, topic):
    assert topic in expand_related(message)


def test_related_words_match_whole_words_only():
    # "hotspot" is not "hot", "fingerprint" is not "print"
    assert "overheating" not in expand_related("my wifi hotspot is off")
    assert "printer" not in expand_related("fingerprint login broken")


@pytest.mark.parametrize("message", [
    "i knocked my coffee over the keyboard",
    "the laptop got soaked in the rain",
])
def test_liquid_damage_goes_to_a_technician(message):
    assert _reply(message, _published())["status_intent"] == "escalate"


def _say(history, message, articles):
    history.append({"sender": "user", "text": message})
    result = asyncio.run(chat_turn(message, history, articles))
    history.append({"sender": "ai", "text": result["reply"]})
    return result


def test_unsure_bot_offers_choices_and_user_picks_one(monkeypatch):
    import ai.assistant as assistant
    articles = _published()
    bitlocker = next(a for a in articles if "BitLocker" in a["title"])
    sign_in = next(a for a in articles if "Sign In to Windows" in a["title"])
    # The bot is unsure between two articles (fixed probabilities, so the test
    # doesn't depend on which models are installed)
    monkeypatch.setattr(assistant, "matcher_ranking", lambda text, arts: [(bitlocker, 0.2), (sign_in, 0.15)])

    async def unsure(message, history, articles, hits):
        return {"reply": "Could you tell me more?", "status_intent": "clarify", "can_resolve": False,
                "category": "other", "priority": "low", "subject": "", "used_articles": []}
    monkeypatch.setattr(assistant, "_offline_turn", unsure)
    history = []
    first = _say(history, "my laptop asks for a recovery key when it starts", articles)
    assert first["status_intent"] == "clarify" and "Is it one of these?" in first["reply"]
    assert "BitLocker" in first["reply"] and "Sign In to Windows" in first["reply"]
    picked = _say(history, "2", articles)
    assert picked["status_intent"] == "troubleshoot" and "Sign In to Windows" in picked["reply"]
    assert picked["used_articles"]


def test_truly_vague_message_gets_no_random_guesses():
    result = _reply("help", _published())
    assert result["status_intent"] == "clarify" and "Is it one of these?" not in result["reply"]


def test_number_without_offered_choices_is_not_a_pick():
    result = _reply("2", _published())
    assert result["status_intent"] != "troubleshoot"
