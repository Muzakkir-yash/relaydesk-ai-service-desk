"""The trained (free, offline) intent and category models."""

import asyncio
import time

import pytest

import ai.assistant as assistant
from ai.assistant import chat_turn
from ai.intent_model import TextClassifier, category_model, intent_model


def test_models_train_from_the_json_examples():
    start = time.perf_counter()
    model = TextClassifier("intents", use_cache=False)  # real training run, no cache
    assert time.perf_counter() - start < 60
    assert model.size > 400
    assert set(model.labels) >= {"problem", "resolved", "not_fixed", "human", "security", "request", "outage"}


@pytest.mark.parametrize("text, expected", [
    ("i entered my password on a fake login page", "security"),
    ("please can someone from it phone me", "human"),
    ("that sorted it, thanks", "resolved"),
    ("still not working after the restart", "not_fixed"),
    ("nobody on our floor can get online", "outage"),
    ("i need photoshop installed", "request"),
])
def test_intent_examples(text, expected):
    assert intent_model().predict(text)[0] == expected


def test_typos_still_understood():
    label, _ = category_model().predict("vpn keeps disconecting wen i wrk from hom")
    assert label == "network"


def test_low_confidence_defers_to_rules(monkeypatch):
    monkeypatch.setattr(assistant, "MODEL_MIN_CONFIDENCE", 1.01)  # model never confident enough
    result = asyncio.run(chat_turn("could someone call me", [{"sender": "user", "text": "could someone call me"}], []))
    assert result["status_intent"] != "escalate"  # the old keyword rules miss this phrasing


def test_model_routes_security_incident():
    msg = "someone texted me pretending to be the director and asked for my login code"
    result = asyncio.run(chat_turn(msg, [{"sender": "user", "text": msg}], []))
    assert result["status_intent"] == "escalate" and result["priority"] == "high"


def test_resolved_needs_a_prior_suggestion():
    result = asyncio.run(chat_turn("that fixed it", [{"sender": "user", "text": "that fixed it"}], []))
    assert result["status_intent"] != "resolved"
