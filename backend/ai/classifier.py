"""
AI Job 1 — Classify & Route
Calls Claude to classify the ticket into category, priority, team, and tags.
The reply shape is enforced with a JSON schema (structured outputs).
"""

import re

from ai.client import complete_json

CATEGORIES = {"hardware", "software", "network", "access", "account", "general", "other"}
PRIORITIES = {"low", "medium", "high", "critical"}
MOODS = {"calm", "neutral", "frustrated"}

SYSTEM_PROMPT = """\
You are an IT service-desk triage engine. Given a support ticket, classify it.
suggested_team is a short team or skill name; tags are 2-5 lowercase keywords.
Priority guidance: critical = many users or business-stopping;
high = one user fully blocked; medium = degraded but working;
low = question or minor.
Mood guidance: frustrated = urgent/angry/desperate language; calm = polite/formal; neutral = matter-of-fact.
Language: the language the ticket is written in (e.g. English, Spanish, French).
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["hardware", "software", "network", "access", "account", "other"]},
        "priority": {"type": "string", "enum": sorted(PRIORITIES)},
        "suggested_team": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "mood": {"type": "string", "enum": sorted(MOODS)},
        "language": {"type": "string"},
    },
    "required": ["category", "priority", "suggested_team", "tags", "mood", "language"],
    "additionalProperties": False,
}


def _fallback_classify(subject: str, description: str) -> dict:
    text = f"{subject} {description}".lower()

    if any(w in text for w in ["critical", "outage", "entire team", "whole team", "whole office", "whole floor",
                               "entire floor", "nobody", "everyone", "emergency", "all users", "black screen",
                               "completely black", "won't turn on", "bsod", "blue screen"]):
        priority = "critical"
    elif any(w in text for w in ["urgent", "blocked", "cannot work", "deadline", "expired", "locked out", "asap", "not connecting"]):
        priority = "high"
    elif any(w in text for w in ["slow", "glitch", "degraded", "not working", "fails", "audio", "mic", "printer", "flicker", "wifi"]):
        priority = "medium"
    else:
        priority = "low"

    # Precise category and team routing
    words = set(re.findall(r"[a-z0-9-]+", text))
    if (any(w in text for w in ["wifi", "wi-fi", "wireless", "ssid", "wlan", "vpn", "network", "internet", "dns",
                                "firewall", "ip address", "connection", "router", "gateway"])
            or "ip" in words):
        category = "network"
        team = "network"
        tags = ["network", "wifi" if any(w in text for w in ["wifi", "wi-fi", "wireless", "ssid"]) else "vpn" if "vpn" in text else "connectivity"]
    elif any(w in text for w in ["password", "sso", "login", "account", "locked", "lockout", "mfa", "2fa", "access", "permission", "authenticator"]):
        category = "access"
        team = "access"
        tags = ["access", "security", "mfa" if any(w in text for w in ["mfa", "2fa", "authenticator"]) else "password"]
    elif any(w in text for w in ["install", "uninstall", "license", "software"]):
        # "Install X on my laptop" is a software request, not a hardware fault
        category = "software"
        team = "software"
        tags = ["software", "install"]
    elif any(w in text for w in ["monitor", "display", "screen", "keyboard", "mouse", "headset", "printer", "hardware", "dock", "power", "battery", "laptop", "pc", "charger", "cord"]):
        category = "hardware"
        team = "hardware"
        tags = ["hardware", "equipment"]
    elif any(w in text for w in ["teams", "outlook", "excel", "software", "app", "install", "zoom", "slack", "crash", "license", "word", "onedrive", "sharepoint"]):
        category = "software"
        team = "software"
        tags = ["software", "applications"]
    else:
        category = "other"
        team = "general"
        tags = ["general"]

    # Mood detection
    frustrated_words = ["frustrated", "annoyed", "still broken", "useless", "terrible", "again",
                        "urgent", "asap", "emergency", "critical", "worst", "angry", "fed up", "!!"]
    calm_words = ["please", "kindly", "thank", "appreciate", "when possible", "could you"]
    if any(w in text for w in frustrated_words):
        mood = "frustrated"
    elif any(w in text for w in calm_words):
        mood = "calm"
    else:
        mood = "neutral"

    return {
        "category": category,
        "priority": priority,
        "suggested_team": team,
        "tags": tags,
        "mood": mood,
        "language": "English",
    }


def _normalize(result: dict, fallback: dict) -> dict:
    """Coerce model output onto the DB enums; any bad field keeps the rule-based value."""
    out = dict(fallback)
    if str(result.get("category", "")).lower() in CATEGORIES:
        out["category"] = str(result["category"]).lower()
    if str(result.get("priority", "")).lower() in PRIORITIES:
        out["priority"] = str(result["priority"]).lower()
    if str(result.get("mood", "")).lower() in MOODS:
        out["mood"] = str(result["mood"]).lower()
    if isinstance(result.get("suggested_team"), str) and result["suggested_team"].strip():
        out["suggested_team"] = result["suggested_team"].strip()[:64]
    if isinstance(result.get("tags"), list):
        out["tags"] = [str(t)[:32] for t in result["tags"][:8]]
    if isinstance(result.get("language"), str) and result["language"].strip():
        out["language"] = result["language"].strip()[:64]
    return out


async def classify_ticket(subject: str, description: str) -> dict:
    """Run AI Job 1. Returns a classification dict whose fields are always valid."""
    fallback = _fallback_classify(subject, description)
    result = await complete_json(
        SYSTEM_PROMPT, f"Subject: {subject}\n\nDescription: {description}",
        max_tokens=4096, job="classify", schema=OUTPUT_SCHEMA, effort="low",
    )
    return _normalize(result, fallback) if result else fallback
