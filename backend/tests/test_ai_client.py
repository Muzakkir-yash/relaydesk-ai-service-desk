"""Unit tests for AI output parsing and normalisation (no network)."""

import asyncio

from ai.client import extract_json_object, ai_enabled
from ai.classifier import _normalize, _fallback_classify, classify_ticket


def test_extract_plain_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_preamble_and_braces_in_text():
    raw = 'Here you go {not json} then {"category": "network", "tags": ["vpn"]} done'
    assert extract_json_object(raw) == {"category": "network", "tags": ["vpn"]}


def test_extract_returns_none_for_garbage():
    assert extract_json_object("no json here") is None


def test_normalize_rejects_values_outside_db_enums():
    fallback = _fallback_classify("VPN down", "vpn is broken")
    out = _normalize({"category": "networking", "priority": "URGENT", "mood": "Calm", "tags": "x"}, fallback)
    assert out["category"] == fallback["category"]
    assert out["priority"] == fallback["priority"]
    assert out["mood"] == "calm"
    assert out["tags"] == fallback["tags"]


def test_offline_mode_uses_fallback():
    assert not ai_enabled()
    result = asyncio.run(classify_ticket("Printer jammed", "The office printer is jammed"))
    assert result["category"] == "hardware"
