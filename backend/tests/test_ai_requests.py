"""Request-shape and response-handling tests for the Claude client, using a
fake SDK client so no network call or API key is needed."""

import asyncio
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import ai.client as client_mod
from ai.classifier import classify_ticket
from config import settings


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _message(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=None,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
    )


@pytest.fixture
def fake(monkeypatch):
    # Fake SDK client below — no network call is ever made in these tests
    monkeypatch.setattr(settings, "ENABLE_PAID_AI", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test-key-0123456789abcdef")

    def install(response=None, error=None):
        messages = FakeMessages(response, error)
        monkeypatch.setattr(client_mod, "get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages)))
        return messages

    return install


def test_classify_request_shape(fake):
    reply = {"category": "network", "priority": "high", "suggested_team": "Network Ops",
             "tags": ["vpn"], "mood": "neutral", "language": "English"}
    messages = fake(_message(json.dumps(reply)))

    result = asyncio.run(classify_ticket("VPN down", "Cannot connect to the VPN at all"))

    call = messages.calls[0]
    assert call["model"] == settings.ANTHROPIC_MODEL == "claude-opus-5-5"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in call and "temperature" not in call
    assert result["priority"] == "high" and result["suggested_team"] == "Network Ops"


def test_refusal_uses_rule_based_fallback(fake):
    fake(_message("", stop_reason="refusal"))
    result = asyncio.run(classify_ticket("Printer jammed", "The office printer is jammed"))
    assert result["category"] == "hardware"


def test_truncated_reply_uses_fallback(fake):
    fake(_message('{"category": "net', stop_reason="max_tokens"))
    result = asyncio.run(classify_ticket("Printer jammed", "The office printer is jammed"))
    assert result["category"] == "hardware"


def test_api_error_uses_fallback(fake):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.InternalServerError("boom", response=httpx2.Response(500, request=request), body=None)
    fake(error=error)
    result = asyncio.run(classify_ticket("Printer jammed", "The office printer is jammed"))
    assert result["category"] == "hardware"


def test_fallback_can_be_disabled(fake, monkeypatch):
    monkeypatch.setattr(settings, "AI_REFUSAL_FALLBACK", False)
    messages = fake(_message('{"category": "hardware", "priority": "low", "suggested_team": "x", '
                             '"tags": [], "mood": "calm", "language": "English"}'))
    asyncio.run(classify_ticket("Mouse", "My mouse is broken"))
    assert "fallbacks" not in messages.calls[0] and "betas" not in messages.calls[0]
