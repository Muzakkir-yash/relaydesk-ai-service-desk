"""Guarantees the project stays strictly free: no paid API is called unless
ENABLE_PAID_AI is deliberately switched on."""

import asyncio
import os
import re

import pytest

import ai.client as client_mod
from ai.assistant import chat_turn
from ai.classifier import classify_ticket
from config import Settings, settings

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ExplodingMessages:
    """Fails the test if anything tries to reach the paid API."""
    async def create(self, **kwargs):
        raise AssertionError("A paid API request was attempted")


@pytest.fixture
def real_looking_key_but_paid_off(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PAID_AI", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-api03-" + "x" * 40)
    client_mod.get_client.cache_clear()
    monkeypatch.setattr(client_mod, "get_client",
                        lambda: type("C", (), {"beta": type("B", (), {"messages": ExplodingMessages()})()})())


def test_paid_ai_is_off_by_default():
    assert Settings.model_fields["ENABLE_PAID_AI"].default is False


def test_key_alone_does_not_enable_paid_ai(real_looking_key_but_paid_off):
    assert client_mod.ai_enabled() is False


def test_ai_jobs_use_free_engine_when_paid_is_off(real_looking_key_but_paid_off):
    result = asyncio.run(classify_ticket("Printer jammed", "The office printer is jammed"))
    assert result["category"] == "hardware"
    reply = asyncio.run(chat_turn("my vpn keeps dropping", [{"sender": "user", "text": "my vpn keeps dropping"}], []))
    assert reply["reply"]


def test_client_cannot_be_built_while_paid_is_off(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PAID_AI", False)
    client_mod.get_client.cache_clear()
    with pytest.raises(RuntimeError):
        client_mod.get_client()


def test_only_the_guarded_module_talks_to_a_paid_api():
    """No other backend file may import the Anthropic SDK or an HTTP client."""
    offenders = []
    pattern = re.compile(r"^\s*(import|from)\s+(anthropic|httpx|httpx2|requests|urllib3|aiohttp|openai)\b", re.M)
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in ("venv", "__pycache__", "tests", "migrations")]
        for name in files:
            path = os.path.join(root, name)
            if name.endswith(".py") and path != os.path.join(BACKEND, "ai", "client.py"):
                if pattern.search(open(path, encoding="utf-8").read()):
                    offenders.append(os.path.relpath(path, BACKEND))
    assert offenders == []
