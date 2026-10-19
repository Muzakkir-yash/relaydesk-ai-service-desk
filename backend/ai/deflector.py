"""
AI Job 2 — Intelligent Deflection & Dynamic IT Resolution Engine
Provides instant self-service resolution using Knowledge Base articles or
context-aware AI technical troubleshooting for any enterprise IT problem.
"""

import json
import math
import os
import re
from functools import lru_cache
from typing import List, Dict, Any, Optional

from ai.client import ai_enabled, complete_json, complete_text

SYSTEM_PROMPT = """\
You are an expert enterprise IT self-service support assistant. You are given a user's problem and available knowledge-base articles.
Provide clear, actionable, step-by-step resolution steps specifically tailored to their exact issue.
- answer: the fix as numbered steps with exact commands, written for a non-technical user
- used_article_ids: the IDs of the articles you relied on (empty if none)
- can_resolve: true only if the steps genuinely address this issue; if unsure, set it to false and
  use answer to ask for the missing detail — never guess at a fix that could make things worse
- confidence: how sure you are the steps will fix it
"""

DEFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "can_resolve": {"type": "boolean"},
        "answer": {"type": "string"},
        "used_article_ids": {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["can_resolve", "answer", "used_article_ids", "confidence"],
    "additionalProperties": False,
}

CHAT_SYSTEM_PROMPT = """\
You are a helpful enterprise IT support assistant in a live chat session.

CRITICAL RULES — follow these strictly:
1. If the user sends ONLY a greeting (e.g. 'hello', 'hi', 'hey', 'good morning') with NO technical problem, respond with ONLY a short, friendly greeting back. Do NOT generate any troubleshooting steps.
2. If the user describes a vague or unclear message that is not a technical problem, ask them to describe their issue.
3. ONLY provide numbered troubleshooting steps when the user has described a REAL, SPECIFIC technical IT problem.
4. Always respond naturally as a human support agent would — match the tone and length of the user's message.
5. Never generate generic catch-all steps when the actual problem is unclear.
"""


STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "my", "your", "his", "her", "its", "our", "their", "me", "you", "him",
    "us", "them", "i", "we", "he", "she", "it", "they", "this", "that",
    "these", "those", "not", "no", "can", "cant", "cannot", "could", "would",
    "should", "please", "help", "need", "issue", "problem", "broken", "company",
    "get", "got", "how", "what", "why", "when", "where", "which", "there",
    "some", "any", "all", "very", "just", "also", "now", "here",
    "work", "works", "working", "worked",
    # Verbs and fillers that say nothing about *which* problem it is
    "show", "shows", "showing", "shown", "say", "says", "saying", "keep", "keeps", "seem", "seems",
    "tried", "trying", "getting", "gets", "something", "anything", "out"
}

NORMALIZATIONS = [
    # Run-together typos: "cameranot work" -> "camera not work"
    (r'\b([a-z]{4,})not\b', r'\1 not'),
    (r'\bweb[\s-]*cam(?:era)?s?\b', 'webcam'),
    (r'\bcam\b', 'camera'),
    (r'\bconnnected\b', 'connected'),
    (r'\bdisconnnected\b', 'disconnected'),
    (r'\bwi-fi\b', 'wifi'),
    (r'\bwlan\b', 'wifi'),
    (r'\bwireless\b', 'wifi'),
    (r'\blap\b', 'laptop'),
    (r'\bpc\b', 'computer'),
    (r'\bpwd\b', 'password'),
    (r'\bpw\b', 'password'),
    (r'\bmic\b', 'microphone'),
    (r'\bbsod\b', 'bluescreen'),
    (r'\bauth\b', 'authenticator'),
    (r'\bmon\b', 'monitor'),
    (r'\bdisp\b', 'display'),
]


def normalize_query(text: str) -> str:
    cleaned = text.lower()
    for pattern, replacement in NORMALIZATIONS:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned


RELATED_TERMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "training", "related_terms.json")


@lru_cache(maxsize=1)
def _related_patterns() -> List[tuple]:
    """(topic word, regex of its related words) from training/related_terms.json."""
    if not os.path.exists(RELATED_TERMS_FILE):
        return []
    with open(RELATED_TERMS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    patterns = []
    for topic, related in data.items():
        if topic.startswith("_") or not related:
            continue
        words = sorted((re.escape(w.lower()) for w in related), key=len, reverse=True)
        patterns.append((topic, re.compile(r"\b(?:" + "|".join(words) + r")(?:s|es)?\b")))
    return patterns


def expand_related(text: str) -> str:
    """Add the topic word for every related word in `text`, so the knowledge
    search understands the problem even when the user never names it:
    "my inbox is full of junk" is searched as "... email spam"."""
    lowered = (text or "").lower()
    topics = [topic for topic, pattern in _related_patterns()
              if pattern.search(lowered) and not re.search(r"\b" + re.escape(topic) + r"\b", lowered)]
    return f"{text} {' '.join(topics)}" if topics else text


# (words in the query, words in an article title) — a query naming the topic
# gets a +20 boost for articles about that topic
TOPIC_BONUSES = [
    (("wifi",), ("wifi",)),
    (("vpn",), ("vpn",)),
    (("password",), ("password",)),
    (("teams",), ("teams",)),
    (("outlook",), ("outlook",)),
    (("printer",), ("printer",)),
    (("won't turn on", "black screen", "power"), ("won't turn on",)),
    (("monitor", "second screen", "external screen"), ("monitor",)),
    (("bsod", "blue screen", "crash"), ("blue screen",)),
    (("slow", "performance", "lag"), ("slow",)),
    (("shared drive", "mapped drive", "sharepoint"), ("shared",)),
    (("mfa", "2fa", "authenticator"), ("multi-factor",)),
    (("camera", "webcam"), ("camera",)),
    (("battery", "charging", "charger"), ("battery",)),
    (("overheat", "fan", "too hot", "very hot", "so hot", "gets hot", "is hot", "heating up"), ("overheating",)),
    (("keyboard", "keys", "shift", "caps lock", "num lock", "typing wrong", "types wrong"), ("keyboard",)),
    (("mouse", "touchpad", "trackpad", "cursor"), ("mouse",)),
    (("bluetooth", "airpods", "earbuds"), ("bluetooth",)),
    (("sound", "speaker", "can't hear anything", "cant hear anything"), ("no sound",)),
    (("usb",), ("usb device",)),
    (("dock",), ("dock",)),
    (("scan",), ("scan",)),
    (("projector", "meeting room", "conference room"), ("projector",)),
    (("windows update", "updates", "updating"), ("windows update",)),
    (("disk", "storage", "space"), ("disk space",)),
    # Not "office": it usually means the workplace ("office wifi", "office copier")
    (("excel", "word", "powerpoint", "office app", "office 365", "microsoft 365"), ("office",)),
    (("onedrive",), ("onedrive",)),
    (("chrome", "edge", "browser", "website", "web page", "site"), ("browser",)),
    (("pdf", "adobe"), ("pdf",)),
    (("signature",), ("signature",)),
    (("out of office", "automatic repl", "auto repl", "autoreply"), ("out-of-office",)),
    (("spam", "junk"), ("spam",)),
    (("outbox", "bounce", "attachment", "can't send", "cant send", "not sending", "won't send"), ("can't send",)),
    (("calendar", "meeting invite", "shared mailbox"), ("calendar",)),
    (("remote desktop", "rdp"), ("remote desktop",)),
    (("bitlocker", "recovery key"), ("bitlocker",)),
    (("ethernet", "lan cable", "lan port", "network cable", "wired"), ("ethernet",)),
    (("share my screen", "share screen", "screen share", "sharing my screen", "screen sharing"), ("screen sharing",)),
    (("copy", "paste", "clipboard"), ("copy and paste",)),
    (("phone", "iphone", "android", "mobile"), ("phone",)),
    (("hear me", "my voice", "my mic", "microphone"), ("microphone",)),
    (("install",), ("install",)),
]


def keyword_weights(kb_articles: List[Dict[str, Any]]) -> Dict[str, float]:
    """How much each word tells us about *which* article fits (0-1).
    Words found in only a few articles ("bitlocker", "touchpad") keep full
    weight; words found in many ("screen", "laptop", "windows") count less,
    so "second screen not detected" doesn't match "Blue Screen of Death"."""
    n = len(kb_articles)
    if n == 0:
        return {}
    df: Dict[str, int] = {}
    for art in kb_articles:
        text = normalize_query(f"{art.get('title') or ''} {art.get('tags') or ''} {art.get('body') or ''}")
        for word in set(re.findall(r'[a-z0-9]+', text)):
            df[word] = df.get(word, 0) + 1
    full = math.log(1 + n / 3)
    return {word: min(1.0, math.log(1 + n / count) / full) for word, count in df.items()}


def _score_article(tokens: List[str], query_clean: str, art: Dict[str, Any],
                   weights: Optional[Dict[str, float]] = None) -> float:
    title_lower = normalize_query(art.get("title") or "")
    tags_lower = normalize_query(art.get("tags") or "")
    body_lower = normalize_query(art.get("body") or "")

    score = 0.0

    # 1. Exact phrase matching in Title / Tags
    for token in tokens:
        weight = weights.get(token, 1.0) if weights else 1.0
        # Title exact whole-word hit
        if re.search(r'\b' + re.escape(token) + r'\b', title_lower):
            score += 10.0 * weight
        # Tags exact whole-word hit
        if re.search(r'\b' + re.escape(token) + r'\b', tags_lower):
            score += 8.0 * weight
        # Body exact whole-word hit
        if re.search(r'\b' + re.escape(token) + r'\b', body_lower):
            score += 1.0 * weight

    # Two-word phrases from the query ("second screen", "out of office" → "out office")
    for first, second in zip(tokens, tokens[1:]):
        phrase = f"{first} {second}"
        if phrase in title_lower or phrase in tags_lower:
            score += 8.0

    # 2. Multi-word phrase bonuses
    for query_words, title_words in TOPIC_BONUSES:
        if any(re.search(r'\b' + re.escape(w), query_clean) for w in query_words) and any(w in title_lower for w in title_words):
            score += 20.0

    # 3. Domain cross-contamination penalties
    # If query is clearly about WiFi, penalize VPN heavily and vice-versa
    if "wifi" in query_clean and "vpn" not in query_clean:
        if "vpn" in title_lower:
            score -= 50.0
    if "vpn" in query_clean and "wifi" not in query_clean:
        if "wifi" in title_lower:
            score -= 50.0

    # If query is about WiFi on laptop, do NOT match "Laptop Won't Turn On" (which is power/hardware failure)
    if "wifi" in query_clean or "internet" in query_clean or "network" in query_clean:
        if "won't turn on" in title_lower or "hardware" in title_lower:
            score -= 40.0

    # Audio vs Password / Printer
    if any(w in query_clean for w in ["audio", "microphone", "mic", "speaker", "camera", "webcam"]):
        if any(w in title_lower for w in ["password", "printer", "vpn"]):
            score -= 30.0

    # Camera problems vs screen sharing ("my camera shows a black screen in teams")
    if any(w in query_clean for w in ["camera", "webcam"]) and "shar" not in query_clean:
        if "screen sharing" in title_lower:
            score -= 30.0

    # Printer vs Audio / VPN / Password
    if "printer" in query_clean:
        if any(w in title_lower for w in ["audio", "teams", "vpn", "password"]):
            score -= 40.0

    return max(0.0, score)


KB_MATCH_SCORE = 12.0  # an article this strong is shown as the answer


MATCH_CONFIDENCE = 0.25  # article-matcher probability (across all articles) to trust it
MATCH_LEAD = 1.5  # ...and how far ahead of the second-best article it must be


def matcher_ranking(text: str, kb_articles: List[Dict[str, Any]]) -> List[tuple]:
    """(article, probability) from the trained article matcher, best first."""
    if not re.search(r"[a-z]{3,}", (text or "").lower()):
        return []  # "2", "ok", "?" — nothing to match an article on
    from ai.article_matcher import article_matcher  # imports this module
    matcher = article_matcher(kb_articles)
    return matcher.ranking(expand_related(text), plain_text=text) if matcher else []


def _is_confident(ranking: List[tuple]) -> bool:
    if not ranking:
        return False
    runner_up = ranking[1][1] if len(ranking) > 1 else 0.0
    return ranking[0][1] >= MATCH_CONFIDENCE and ranking[0][1] >= MATCH_LEAD * runner_up


def confident_article(text: str, kb_articles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The article the trained matcher is sure answers `text`, else None."""
    ranking = matcher_ranking(text, kb_articles)
    return ranking[0][0] if _is_confident(ranking) else None


KEYWORD_WEIGHT = 0.5  # a keyword score at the cap counts as much as matcher probability 1.0
KEYWORD_CAP = 40.0
FUSED_MIN = 0.4  # combined score an article needs to be shown
KEYWORD_NOISE = 6.0  # keyword scores below this are chance overlaps ("error", "when")


def choose_article(text: str, kb_articles: List[Dict[str, Any]], scored_articles: List[tuple]) -> Optional[Dict[str, Any]]:
    """Pick the article to answer with by combining both signals. The trained
    matcher understands new wording but can latch onto generic phrases
    ("inbox is *full* of spam" → disk full); keyword scoring catches the
    decisive word ("spam") but misreads others ("everything comes out in
    capitals" → email signature). Adding the two lets each correct the other."""
    ranking = matcher_ranking(text, kb_articles)
    probability = {a["id"]: p for a, p in ranking}
    keyword = {}
    for score, art in scored_articles[:5]:
        if score >= KEYWORD_NOISE:
            keyword.setdefault(art["id"], score)
    candidates = {a["id"]: a for a, _ in ranking}
    candidates.update({a["id"]: a for _, a in scored_articles[:5]})

    def fused(article_id):
        return probability.get(article_id, 0.0) + KEYWORD_WEIGHT * min(keyword.get(article_id, 0.0), KEYWORD_CAP) / KEYWORD_CAP

    best = max(candidates, key=fused, default=None)
    if best is None or fused(best) < FUSED_MIN:
        return None
    return candidates[best]


def rank_articles(query_clean: str, kb_articles: List[Dict[str, Any]],
                  weights: Optional[Dict[str, float]] = None) -> List[tuple]:
    """(score, article) pairs scoring above 5, best first."""
    query_clean = expand_related(query_clean)
    tokens = [t for t in re.findall(r'[a-z0-9]+', query_clean) if t not in STOPWORDS and len(t) > 1]
    scored = []
    for art in kb_articles:
        score = _score_article(tokens, query_clean, art, weights)
        if score > 5.0:
            scored.append((score, art))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _generate_dynamic_it_solution(subject: str, description: str) -> dict:
    """
    Expert IT Troubleshooting engine that synthesizes accurate, structured
    remediation steps for any enterprise IT problem when no exact KB article is matched.
    """
    query = normalize_query(f"{subject} {description}")

    # 1. Wi-Fi / Wireless Network Connectivity
    if any(k in query for k in ["wifi", "wi-fi", "wireless", "ssid", "wlan", "hotspot", "no internet", "network disconnected"]):
        title = "Wi-Fi & Wireless Connection Troubleshooting"
        steps = (
            "1. Verify Wi-Fi status:\n"
            "   - Ensure Wi-Fi is turned ON in Windows taskbar and Airplane Mode is OFF.\n"
            "2. Reconnect to the corporate network:\n"
            "   - Disconnect from any personal hotspot and select 'Company-Corp-Secure'.\n"
            "3. Forget and re-authenticate:\n"
            "   - Go to Windows Settings → Network & Internet → Wi-Fi → Manage Known Networks.\n"
            "   - Select 'Company-Corp-Secure' and click 'Forget'. Reconnect and enter your corporate domain credentials.\n"
            "4. Restart the Wireless Network Adapter:\n"
            "   - Press Windows Key + R, type 'ncpa.cpl', and press Enter.\n"
            "   - Right-click 'Wi-Fi' → click 'Disable', wait 10 seconds, then click 'Enable'.\n"
            "5. Reset TCP/IP stack & flush DNS:\n"
            "   - Open Command Prompt as Administrator and run:\n"
            "     ipconfig /release\n"
            "     ipconfig /renew\n"
            "     ipconfig /flushdns\n"
            "6. Restart your laptop to apply updated network lease policies."
        )
    # 2. VPN Connectivity
    elif any(k in query for k in ["vpn", "anyconnect", "globalprotect", "tunnel", "gateway"]):
        title = "Corporate VPN Connection Troubleshooting"
        steps = (
            "1. Verify your local internet connection is active by opening a public webpage.\n"
            "2. Open your VPN Client (Cisco AnyConnect / GlobalProtect), click 'Disconnect', then 'Connect'.\n"
            "3. Ensure your Active Directory domain credentials and MFA token are up to date.\n"
            "4. Toggle connection protocol: In VPN Client Settings, try switching between UDP and TCP.\n"
            "5. Restart the VPN Agent service: Press Win+R, type 'services.msc' → Locate your VPN service → Click 'Restart'.\n"
            "6. Flush local DNS: Open Command Prompt as Admin and run 'ipconfig /flushdns'."
        )
    # 3. Password Reset & Account Lockout
    elif any(k in query for k in ["password", "lockout", "locked out", "expired password", "sso login", "cant login"]):
        title = "Self-Service Password Reset & Account Unlock"
        steps = (
            "1. Navigate to the self-service portal: https://reset.company.com on your phone or workstation.\n"
            "2. Enter your corporate email address (e.g. username@company.com).\n"
            "3. Approve the MFA notification prompt sent to your registered authenticator device.\n"
            "4. Create a new password meeting enterprise standards (12+ characters, upper, lower, number, symbol).\n"
            "5. If your account was temporarily locked due to failed attempts, wait 15 minutes for the automated safety unlock."
        )
    # 4. Multi-Factor Authentication (MFA / 2FA)
    elif any(k in query for k in ["mfa", "2fa", "authenticator", "otp", "verification code", "push notification"]):
        title = "MFA & Authenticator App Troubleshooting"
        steps = (
            "1. Check mobile date & time: In your phone Settings → Date & Time → Ensure 'Set Automatically' is turned ON.\n"
            "2. Ensure your phone has an active data or Wi-Fi connection to receive push approvals.\n"
            "3. Open the Authenticator app manually and pull down to refresh for pending requests.\n"
            "4. Click 'Sign in another way' on the login screen to choose SMS or automated voice call verification.\n"
            "5. If you got a new phone, contact IT Support to re-bind your MFA authenticator profile."
        )
    # 5. External Monitor / Dual Displays
    elif any(k in query for k in ["monitor", "display", "screen", "second screen", "hdmi", "displayport", "dock", "flicker"]):
        title = "External Display & Monitor Troubleshooting"
        steps = (
            "1. Press Windows Key + P and verify that 'Extend' or 'Duplicate' is selected.\n"
            "2. Reseat video cables (HDMI, DisplayPort, USB-C) at both the laptop and monitor ends.\n"
            "3. Power cycle docking station: Unplug dock power adapter for 15 seconds, reconnect, and plug in the USB-C host cable.\n"
            "4. Restart graphics driver instantly: Press Windows Key + Ctrl + Shift + B (the screen will flicker and beep).\n"
            "5. Verify monitor input source (HDMI 1, DP 1) using the physical buttons on the monitor frame."
        )
    # 5b. Camera / Webcam
    elif any(k in query for k in ["camera", "webcam"]):
        title = "Webcam & Camera Troubleshooting"
        steps = (
            "1. Check for a physical privacy shutter or a camera key (often F8/F10 or a key with a camera icon) and make sure it's open/on.\n"
            "2. Check Windows privacy settings: Windows Settings → Privacy & Security → Camera → turn ON 'Camera access' and 'Let apps access your camera'.\n"
            "3. Close every other app that might be using the camera (Teams, Zoom, browser tabs) — only one app can use it at a time.\n"
            "4. Test it in the Windows Camera app. If it works there, select the right camera in your meeting app's Settings → Devices.\n"
            "5. For an external USB webcam, unplug it and plug it into a different USB port (not a hub).\n"
            "6. Reinstall the driver: right-click Start → Device Manager → Cameras → right-click your camera → Uninstall device, then restart your PC."
        )
    # 6. Audio / Microphone / Teams / Zoom
    elif any(k in query for k in ["teams", "zoom", "audio", "microphone", "mic", "speaker", "headset", "sound", "camera", "webcam"]):
        title = "Meeting Audio & Microphone Configuration"
        steps = (
            "1. In Teams/Zoom Settings → Devices: Manually select your headset/microphone and speaker.\n"
            "2. Check Windows privacy settings: Windows Settings → Privacy & Security → Microphone → Ensure access is ON.\n"
            "3. Check physical mute switches on your headset cord or boom arm.\n"
            "4. Make a test call in Teams (Settings → Devices → Make a test call) to verify mic input.\n"
            "5. Fully quit and restart Teams: Right-click Teams in the taskbar tray → click 'Quit', then reopen."
        )
    # 7. Outlook & Email Issues
    elif any(k in query for k in ["outlook", "email", "mailbox", "exchange", "inbox", "mail", "send receive"]):
        title = "Microsoft Outlook & Email Sync Troubleshooting"
        steps = (
            "1. Check Outlook bottom right status bar: If it shows 'Disconnected', click it to re-authenticate.\n"
            "2. Clear cached Office credentials:\n"
            "   - Open Windows Control Panel → Credential Manager → Windows Credentials.\n"
            "   - Remove entries starting with 'MicrosoftOffice16' or 'MS.Outlook'.\n"
            "3. Start Outlook in Safe Mode: Press Win+R, type 'outlook.exe /safe', and press Enter.\n"
            "4. Perform Office Repair: Windows Settings → Apps → Installed Apps → Microsoft 365 Apps → Modify → Quick Repair.\n"
            "5. Verify your mailbox status on the web: https://outlook.office.com."
        )
    # 8. Printer Issues
    elif any(k in query for k in ["printer", "printing", "print", "spooler", "queue", "paper jam"]):
        title = "Network Printer & Print Queue Troubleshooting"
        steps = (
            "1. Clear stuck print queue: Windows Settings → Bluetooth & Devices → Printers & Scanners → Select Printer → Open queue → Cancel all documents.\n"
            "2. Restart Windows Print Spooler:\n"
            "   - Open Command Prompt as Administrator.\n"
            "   - Run: net stop spooler\n"
            "   - Run: net start spooler\n"
            "3. Verify printer power and ensure the Ethernet network cable is firmly seated.\n"
            "4. Re-add printer via IP address found on the physical printer LCD screen."
        )
    # 9. Slow Computer / High CPU / Freezing
    elif any(k in query for k in ["slow", "lag", "freeze", "freezing", "high cpu", "memory", "ram", "disk 100", "unresponsive"]):
        title = "PC Performance & Resource Optimization"
        steps = (
            "1. Check running processes: Press Ctrl + Shift + Esc (Task Manager) and sort by CPU/Memory. End high-resource non-essential apps.\n"
            "2. Disable heavy startup programs: Task Manager → Startup apps tab → Disable non-critical background apps.\n"
            "3. Free up system drive space: Press Win+R, type 'cleanmgr', press Enter → Check 'Temporary files' and clean.\n"
            "4. Check for pending Windows Updates and restart your computer.\n"
            "5. Run Windows System File Checker: Open Command Prompt as Admin and run 'sfc /scannow'."
        )
    # 10. Blue Screen (BSOD) / System Crashes
    elif any(k in query for k in ["bsod", "blue screen", "crash", "rebooting", "dump", "stop code"]):
        title = "Windows Blue Screen (BSOD) Diagnostic Guide"
        steps = (
            "1. Disconnect any newly attached external USB peripherals, external drives, or docks.\n"
            "2. Run system file repair: Open Command Prompt as Admin and run:\n"
            "   DISM.exe /Online /Cleanup-image /Restorehealth\n"
            "   sfc /scannow\n"
            "3. Run Memory Diagnostics: Press Win+R, type 'mdsched.exe', and select 'Restart now and check for problems'.\n"
            "4. Update system hardware drivers via OEM Support Assistant (Dell Command, Lenovo Vantage, HP Assistant).\n"
            "5. If recurring, our technicians will review your crash dump files at C:\\Windows\\Minidump."
        )
    # 11. Shared Drives / SharePoint / Permissions
    elif any(k in query for k in ["shared drive", "network drive", "mapped drive", "sharepoint", "onedrive", "permission", "z drive"]):
        title = "Shared Drive & Network File Access Guide"
        steps = (
            "1. If working remotely, verify that your corporate VPN is connected first.\n"
            "2. Test direct UNC server path: Press Win+R, type '\\\\fileserver.company.internal\\share', and press Enter.\n"
            "3. Remap network drive: Open File Explorer → This PC → '...' → Map network drive → Check 'Reconnect at sign-in'.\n"
            "4. For OneDrive sync: Right-click the OneDrive cloud icon in taskbar → Settings → Pause syncing for 2 hours, then Resume.\n"
            "5. If you receive an 'Access Denied' error, request your team lead to verify your Active Directory folder security group."
        )
    # 12. Bluetooth / Mouse / Keyboard / Peripherals
    elif any(k in query for k in ["mouse", "keyboard", "bluetooth", "trackpad", "usb", "dongle"]):
        title = "Peripheral & Input Device Troubleshooting"
        steps = (
            "1. Check device power: Replace batteries or plug in charging cable for wireless peripherals.\n"
            "2. Try a different USB port directly on the computer (avoid unpowered USB hubs).\n"
            "3. Re-pair Bluetooth device: Windows Settings → Bluetooth & Devices → Remove device → Put device in pairing mode → Add device.\n"
            "4. Restart Bluetooth Support Service: Press Win+R, type 'services.msc' → Right-click 'Bluetooth Support Service' → Restart.\n"
            "5. Refresh Device Manager: Press Win+X → Device Manager → Action → 'Scan for hardware changes'."
        )
    # 13. Application Crashes (Excel, Word, Chrome, etc.)
    elif any(k in query for k in ["excel", "word", "chrome", "edge", "app crash", "software", "install", "license"]):
        title = "Application Diagnostics & Repair Guide"
        steps = (
            "1. Start the application in Safe Mode:\n"
            "   - For Excel: Press Win+R, type 'excel.exe /safe', and press Enter.\n"
            "   - For Word: Press Win+R, type 'winword.exe /safe', and press Enter.\n"
            "2. Disable conflicting Add-ins: File → Options → Add-ins → COM Add-ins → Go → Uncheck third-party add-ins.\n"
            "3. Clear browser / app cache: In Chrome/Edge, press Ctrl+Shift+Del and clear cached images and files.\n"
            "4. Run Application Quick Repair: Windows Settings → Apps → Installed Apps → Select application → Modify → Repair.\n"
            "5. Install approved software via Company Portal / Software Center."
        )
    # If no specific category matches, do NOT produce generic catch-all diagnostic steps
    else:
        return {
            "can_resolve": False,
            "title": "",
            "answer": (
                "I want to make sure you get the exact solution for your issue. "
                "Could you please specify which application, hardware device, or service is affected (e.g., Wi-Fi, VPN, Outlook, password, printer, or screen) and describe the error or symptom you see?\n\n"
                "You can also click **'Still broken — Connect to Human Support'** to transfer directly to a technician."
            ),
            "used_article_ids": [],
            "confidence": "low",
        }

    answer = (
        f"**{title}**\n\n"
        f"Here are the recommended resolution steps for your issue:\n\n"
        f"{steps}\n\n"
        f"**Did this resolve your issue?**\n"
        f"• If this worked, click **'Yes, it's fixed! ✅'**\n"
        f"• If you still need assistance, click **'Still broken — Connect to Human Support ❌'**"
    )

    return {
        "can_resolve": True,
        "answer": answer,
        "used_article_ids": [],
        "confidence": "high",
    }


def _fallback_deflect(subject: str, description: str, kb_articles: List[Dict[str, Any]]) -> dict:
    # 0. If ticket is a greeting or pleasantry, do not generate technical troubleshooting
    if _is_greeting_only(subject) or (not _has_it_problem(subject) and _is_greeting_only(description)):
        return {
            "can_resolve": False,
            "answer": "Hello! Thank you for contacting IT Support. If you are experiencing a technical issue, please describe what's happening so our team can assist you.",
            "used_article_ids": [],
            "confidence": "low",
        }

    query_clean = normalize_query(f"{subject} {description}")
    raw_tokens = [re.sub(r'[^a-z0-9]', '', w) for w in query_clean.split()]
    meaningful_tokens = [w for w in raw_tokens if len(w) >= 3 and w not in STOPWORDS]

    if not meaningful_tokens:
        meaningful_tokens = [w for w in raw_tokens if len(w) >= 2]

    weights = keyword_weights(kb_articles)
    scored_articles = []
    for art in kb_articles:
        score = _score_article(meaningful_tokens, query_clean, art, weights)
        scored_articles.append((score, art))

    scored_articles.sort(key=lambda x: x[0], reverse=True)

    matched = confident_article(f"{subject} {description}", kb_articles)
    if matched is not None:
        scored_articles.insert(0, (KB_MATCH_SCORE, matched))

    if scored_articles:
        best_score, top_art = scored_articles[0]
        # High confidence match (score >= 12)
        if best_score >= KB_MATCH_SCORE:
            return {
                "can_resolve": True,
                "answer": (
                    f"**Knowledge Base Solution: {top_art['title']}**\n\n"
                    f"{top_art['body']}\n\n"
                    f"Please try these steps. If this fixed your problem, click 'Yes, it's fixed!' below. "
                    f"If you still need assistance, click 'Still broken' to connect with a technician."
                ),
                "used_article_ids": [top_art["id"]],
                "confidence": "high" if best_score >= 20.0 else "medium",
            }

    # Only generate dynamic IT solution if user actually described a recognizable IT issue
    return _generate_dynamic_it_solution(subject, description)


async def deflect_ticket(
    subject: str,
    description: str,
    kb_articles: List[Dict[str, Any]],
) -> dict:
    """Run AI Job 2. Returns deflection result dict."""
    articles_text = "\n\n".join(
        f"[Article ID {a['id']}] {a['title']}\n{a.get('tags') or ''}\n{a['body'][:800]}"
        for a in kb_articles
    ) if kb_articles else "No specific knowledge-base articles."

    user_content = (
        f"User Subject: {subject}\nUser Description: {description}\n\n"
        f"--- Available Knowledge Base Articles ---\n{articles_text}\n\n"
        f"Provide the exact, actionable steps the user should follow to fix this specific issue."
    )
    res = await complete_json(
        SYSTEM_PROMPT, user_content, max_tokens=8000, job="deflect", schema=DEFLECT_SCHEMA, effort="medium"
    )
    if not res or not isinstance(res.get("answer"), str) or not res["answer"].strip():
        return _fallback_deflect(subject, description, kb_articles)

    valid_ids = {a["id"] for a in kb_articles}
    used = res.get("used_article_ids")
    return {
        "can_resolve": bool(res.get("can_resolve")),
        "answer": res["answer"],
        "used_article_ids": [i for i in used if i in valid_ids] if isinstance(used, list) else [],
        "confidence": res.get("confidence") if res.get("confidence") in ("low", "medium", "high") else "low",
    }


async def generate_ai_chat_reply(
    subject: str,
    description: str,
    chat_history: List[Dict[str, Any]],
    new_message: str,
) -> str:
    """
    Generates a conversational follow-up response from the AI assistant when the user
    replies in the ticket thread while in 'ai_handling' state.
    """
    # 0. Pure greeting in ticket thread
    if _is_greeting_only(new_message):
        return (
            "Hello! 👋 How can I assist you with this ticket today? "
            "Please let me know if you tried the suggested steps or what error you are seeing."
        )

    msg_clean = normalize_query(new_message)

    # 1. User reports resolution / success
    if any(w in msg_clean for w in ["fixed", "worked", "working now", "resolved", "all good", "thank you", "thanks", "solved"]):
        return (
            "🎉 Fantastic! I'm glad that resolved your issue.\n\n"
            "Please click the green **\"Yes, it's fixed! ✅\"** button above to close this ticket and confirm your self-service resolution."
        )

    # 2. User reports failure or wants a technician
    if any(w in msg_clean for w in ["still broken", "not working", "didnt work", "didn't work", "still not", "failed", "escalate", "human", "technician", "agent"]):
        return (
            "Understood. Since self-service steps haven't resolved this issue, please click the red **\"Still broken — get a technician ❌\"** button above.\n\n"
            "I will immediately assemble a full diagnostic briefing for a technician so they can assist you without asking you to repeat any steps."
        )

    # 3. Use Claude when configured
    if ai_enabled():
        conversation_formatted = "\n".join(
            f"{m.get('sender_type', 'user').upper()}: {m.get('body', '')}"
            for m in chat_history[-6:]
        )
        prompt = (
            f"Ticket Subject: {subject}\n"
            f"Ticket Description: {description}\n\n"
            f"Conversation so far:\n{conversation_formatted}\n\n"
            f"User's newest message: {new_message}\n\n"
            f"Provide a helpful, polite, concise IT support reply to assist the user further or guide next steps."
        )
        reply = await complete_text(CHAT_SYSTEM_PROMPT, prompt, max_tokens=4096, job="chat_reply")
        if reply:
            return reply

    # 4. Contextual smart assistance
    if any(w in msg_clean for w in ["cmd", "command prompt", "terminal", "run", "ncpa", "ipconfig"]):
        return (
            "To run these commands:\n"
            "1. Press **Windows Key + R** to open the Run box.\n"
            "2. Type `cmd` and press **Ctrl + Shift + Enter** to run Command Prompt as Administrator.\n"
            "3. Type or paste the commands (e.g. `ipconfig /flushdns` or `ncpa.cpl`) and press **Enter**.\n\n"
            "Let me know what output you see or if you'd like to connect with a technician!"
        )

    if any(w in msg_clean for w in ["error", "code", "denied", "failed to", "cant find"]):
        return (
            "Thank you for sharing those details. If you encounter specific error messages or access restrictions, this often indicates permission or driver-level constraints.\n\n"
            "You can try restarting your PC once, or click **\"Still broken — get a technician ❌\"** above so an IT specialist can remotely inspect your machine."
        )

    return (
        "Thank you for the update. If you need further assistance with your issue, please reply with any specific error messages, "
        "or click **\"Still broken — get a technician ❌\"** above to connect with a specialist."
    )


def _clean_text_for_greeting(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z\s]', ' ', text or '').lower()
    return ' '.join(cleaned.split())


GREETING_PHRASES = {
    "hello", "hi", "hey", "hiya", "howdy", "helo", "heya", "yo", "sup",
    "good morning", "good afternoon", "good evening", "good day", "greetings",
    "whats up", "what is up", "how are you", "how are you doing", "how are u", "how r u",
    "hello there", "hi there", "hey there", "morning", "afternoon", "evening",
    "hello bot", "hi bot", "hey bot", "hello team", "hi team", "hey team",
    "hello support", "hi support", "hey support", "hello assistant", "hi assistant",
    "hello sir", "hi sir", "hello madam", "hi madam"
}

GREETING_WORDS = {
    "hello", "hi", "hey", "hiya", "howdy", "helo", "heya", "yo", "sup",
    "greetings", "morning", "afternoon", "evening"
}

# Real, specific IT problem tokens (symptoms, systems, or specific failure modes)
IT_PROBLEM_KEYWORDS = {
    # Network / Connectivity
    "wifi", "wi-fi", "wireless", "ssid", "wlan", "hotspot", "no internet", "network disconnected",
    "vpn", "anyconnect", "globalprotect", "tunnel", "gateway", "dns", "ipconfig",
    # Account / Access
    "password", "lockout", "locked out", "expired password", "sso login", "cant login", "cannot login",
    "mfa", "2fa", "authenticator", "otp", "verification code", "push notification",
    # Hardware / Display / Peripherals
    "monitor", "display", "screen", "second screen", "hdmi", "displayport", "dock", "docking",
    "mouse", "keyboard", "bluetooth", "trackpad", "usb", "dongle", "headset", "audio", "microphone", "mic", "speaker",
    "camera", "webcam",
    "printer", "printing", "print", "spooler", "paper jam",
    # System / OS / Software
    "bsod", "blue screen", "crash", "crashing", "crashed", "rebooting", "freeze", "freezing", "frozen",
    "slow", "lag", "high cpu", "memory leak", "ram", "unresponsive",
    "teams", "zoom", "outlook", "email", "mailbox", "exchange", "excel", "word", "chrome", "edge",
    "shared drive", "mapped drive", "sharepoint", "onedrive", "access denied", "permission",
    "error 4", "error 5", "failed to connect", "not working", "won't open", "wont open", "won't start", "wont start",
    "won't turn on", "wont turn on", "black screen", "flicker", "flickering",
    # Everyday hardware
    "battery", "charging", "charger", "overheat", "fan noise", "loud fan", "touchpad", "cursor", "usb", "no sound",
    "brightness", "upside down", "scanner", "scan to", "projector", "no signal", "keys",
    # Windows, files and apps
    "windows update", "update failed", "update error", "updating", "disk space", "storage", "c drive", "onedrive", "deleted", "recover", "browser",
    "website", "web page", "pdf", "adobe", "copy paste", "clipboard", "certificate", "not private", "remote desktop",
    "rdp", "bitlocker", "recovery key", "my pin", "fingerprint", "windows hello", "trust relationship", "log in", "login",
    "signature", "out of office", "spam", "junk", "outbox", "calendar", "shared mailbox", "unlicensed", "activate",
    "ethernet", "network cable", "not responding", "keeps closing", "won't load", "wont load", "screen share",
    "share my screen", "time zone", "clock", "hear me", "can't hear", "cant hear"
}


SECURITY_INCIDENT_WORDS = [
    "phishing", "suspicious email", "suspicious link", "clicked a link", "clicked the link", "clicked on a link",
    "malware", "ransomware", "a virus", "got a virus", "hacked", "compromised", "someone logged into my", "scam email",
    # Lost or stolen devices can expose company data
    "stolen", "got nicked", "lost my laptop", "lost my work laptop", "lost my work phone", "lost my phone", "lost the laptop", "lost my company",
    # Ransomware notes
    "files are encrypted", "files have been encrypted", "files were encrypted", "bitcoin", "ransom", "pay to unlock",
    "pay to get my files",
    # Unknown removable media is a classic malware route
    "found a usb", "usb i found", "found a memory stick", "found a flash drive", "found a pen drive", "unknown usb",
]

HANDS_ON_WORDS = [
    "cracked", "dropped my", "spilled", "shattered", "in pieces", "snapped", "fell off", "knocked off", "water damage", "smashed", "broken screen", "screen is broken",
    "can you install", "please install", "need installed", "install it for me", "need access to", "grant me access",
    "need access for", "new laptop request", "replacement laptop",
    # Electrical damage is a safety issue, never a self-service fix
    "frayed", "sparking", "sparks", "exposed wire", "wires exposed", "wire is exposed", "split and exposed", "cable is split",
    "burning smell", "smells like burning", "smoke", "smoking", "swollen battery", "battery is swollen", "battery bulging",
    # Liquid damage: switch off and get it to a technician, never troubleshoot
    "spilt", "knocked water", "knocked my drink", "knocked coffee", "knocked tea", "water over", "coffee over", "tea over",
    "drink over", "juice over", "liquid on", "liquid in", "got wet", "soaked", "dropped it in water", "fell in water",
]


def has_safety_phrase(text: str) -> bool:
    """A security incident or physical damage: these always go to a person,
    whatever the intent model thinks the message is."""
    cleaned = normalize_query(text)
    return any(w in cleaned for w in SECURITY_INCIDENT_WORDS) or any(w in cleaned for w in HANDS_ON_WORDS)


def _is_greeting_only(text: str) -> bool:
    """Returns True if the message is purely a greeting or pleasantry with no technical problem."""
    cleaned = _clean_text_for_greeting(text)
    if not cleaned:
        return False

    # Exact greeting phrase match
    if cleaned in GREETING_PHRASES:
        return True

    words = cleaned.split()
    # Check if starts with a greeting and has <= 6 words and no IT problem keywords
    if len(words) <= 6:
        first_word = words[0]
        first_two = " ".join(words[:2])
        if first_word in GREETING_WORDS or first_two in {"good morning", "good afternoon", "good evening", "good day", "how are"}:
            if not _has_it_problem(text):
                return True

    # Politeness / pleasantry check: e.g. "hi can you help me"
    if any(words[0] == g for g in GREETING_WORDS) and not _has_it_problem(text):
        return True

    return False


def _has_it_problem(text: str) -> bool:
    """Returns True if the message appears to describe an actual IT problem."""
    cleaned = expand_related(normalize_query(text))
    return any(re.search(r"\b" + re.escape(kw), cleaned) for kw in IT_PROBLEM_KEYWORDS)


async def diagnose_and_triage(
    message: str,
    chat_history: List[Dict[str, Any]],
    kb_articles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyzes an incoming user chat message during ticket submission triage:
    - Detects greetings and responds naturally without generating IT steps
    - Detects if user confirmed resolution (resolved / fixed / worked)
    - Detects if user requested human escalation or reported steps failed
    - Otherwise diagnoses the problem, extracts category/priority, searches KB,
      and provides step-by-step troubleshooting.
    """
    # 0. Pure greeting / social message — reply naturally, no troubleshooting
    if _is_greeting_only(message):
        cleaned = _clean_text_for_greeting(message)
        if "morning" in cleaned:
            greeting_reply = "Good morning! 👋 How can I help you today? Please describe the IT issue or error you're facing."
        elif "afternoon" in cleaned:
            greeting_reply = "Good afternoon! 👋 How can I help you today? Please describe the IT issue or error you're facing."
        elif "evening" in cleaned:
            greeting_reply = "Good evening! 👋 How can I help you today? Please describe the IT issue or error you're facing."
        elif any(w in cleaned for w in ["how are you", "how r u", "how are u"]):
            greeting_reply = "Hello! 👋 I'm doing well, thank you! How can I assist you with your IT needs today?"
        elif any(w in cleaned for w in ["hi", "hey", "hiya"]):
            greeting_reply = "Hi there! 👋 How can I help you today? Please describe the technical issue you're experiencing."
        else:
            greeting_reply = "Hello! 👋 How can I help you today? Please describe the technical issue you're experiencing."

        return {
            "reply": greeting_reply,
            "status_intent": "greeting",
            "can_resolve": False,
            "category": "",
            "priority": "",
            "subject": "",
            "used_articles": []
        }

    msg_clean = normalize_query(message)

    # Detect if this message is a question — if so, skip resolution/escalation shortcircuits
    _question_starters = {"what", "which", "how", "why", "when", "where", "who", "did", "does", "do", "is", "are", "can", "could", "would", "should"}
    _first_word = msg_clean.split()[0] if msg_clean.split() else ""
    _is_question = message.strip().endswith("?") or _first_word in _question_starters

    # Only consider "resolution" signal after at least one AI turn has already occurred
    _ai_has_spoken = any(
        m.get("sender_type") in ("ai", "bot", "assistant") or m.get("sender") in ("ai", "bot", "assistant")
        for m in chat_history
    )

    # 0b. Security incidents go to a human immediately, whatever else was said
    if any(w in msg_clean for w in SECURITY_INCIDENT_WORDS):
        return {
            "reply": (
                "⚠️ This could be a security incident, so I'm escalating it to our IT security team right away.\n\n"
                "While you wait: **don't click anything else in that email or file**, and if you entered your "
                "password anywhere, **change it now from a different device you trust**. Disconnect from the network "
                "if you think malware was installed. A technician will contact you shortly."
            ),
            "status_intent": "escalate",
            "can_resolve": False,
            "category": "access",
            "priority": "high",
            "subject": "Possible security incident",
            "used_articles": [],
        }

    # 1. User indicates resolution — ONLY when not a question and AI has already replied
    RESOLUTION_WORDS = ["fixed", "working now", "resolved", "all good", "it helped", "issue solved", "problem solved",
                        "sorted", "its fixed", "it's fixed", "worked", "works now", "working again", "it works"]
    _negated = any(n in f" {msg_clean} " for n in (" not ", "n't", " didnt ", " never ", " still "))
    if not _is_question and _ai_has_spoken and not _negated and any(w in msg_clean for w in RESOLUTION_WORDS):
        return {
            "reply": (
                "🎉 Fantastic! I'm glad that resolved your issue.\n\n"
                "I will mark this ticket as resolved and deflected so our human technicians know you're all set. Have a wonderful day!"
            ),
            "status_intent": "resolved",
            "can_resolve": True,
            "category": "general",
            "priority": "low",
            "subject": "Self-Service IT Resolution",
            "used_articles": []
        }

    # 2. User indicates failure or requests human support
    is_explicit_human_req = not _is_question and any(w in msg_clean for w in [
        "escalate",
        "talk to human", "real person", "human support", "speak to someone",
        "connect to technician", "transfer me", "speak with someone",
        "get a technician", "need a technician", "want a technician"
    ])
    is_step_failure = not _is_question and any(w in msg_clean for w in [
        "still broken", "still not working", "didnt work", "didn't work",
        "did not work", "steps didn't work", "tried that and failed"
    ]) and len(chat_history) >= 2

    # Physical damage, installs and access grants need a person with admin rights
    # Phrases are specific requests, so "Can you install X?" counts even though it ends in "?"
    needs_hands_on = any(w in msg_clean for w in HANDS_ON_WORDS)
    if needs_hands_on:
        from ai.classifier import _fallback_classify
        cls = _fallback_classify(message, message)
        if cls["category"] in ("other", "general"):
            # Keywords can't tell ("the glass is shattered"); the trained category model can
            from ai.intent_model import category_model
            cls["category"] = category_model().predict(message)[0]
        return {
            "reply": (
                "This needs a technician — it can't be fixed with self-service steps (it needs hands-on repair, "
                "admin rights or an access approval). I'm passing it to the IT team now with everything you've "
                "told me, so you won't need to repeat it."
            ),
            "status_intent": "escalate",
            "can_resolve": False,
            "category": cls["category"],
            "priority": cls["priority"] if cls["priority"] != "low" else "medium",
            "subject": message.strip()[:75],
            "used_articles": [],
        }

    if is_explicit_human_req or is_step_failure:
        return {
            "reply": (
                "Understood. Since self-service troubleshooting hasn't resolved this issue, "
                "I will immediately escalate this to our human IT engineering team.\n\n"
                "I've prepared a full diagnostic handover briefing with everything you've described and tested so you won't have to repeat anything."
            ),
            "status_intent": "escalate",
            "can_resolve": False,
            "category": "other",
            "priority": "medium",
            "subject": "Escalated IT Support Request",
            "used_articles": []
        }

    # 3. Check if user actually described an IT problem — either a known IT
    # keyword, or wording that clearly matches a knowledge-base article
    weights = keyword_weights(kb_articles)
    own_matches = rank_articles(normalize_query(message), kb_articles, weights)
    if (not _has_it_problem(message) and not (own_matches and own_matches[0][0] >= KB_MATCH_SCORE)
            and not confident_article(message, kb_articles)):
        return {
            "reply": (
                "I'm here to help with any technical or IT issues you're experiencing! "
                "Could you please describe what is happening? For example, let me know:\n"
                "• Which application or device has an issue (e.g., Wi-Fi, VPN, Outlook, laptop screen, printer)?\n"
                "• Any error message or symptom you're seeing.\n\n"
                "Or if you prefer, click below to connect directly with an IT specialist."
            ),
            "status_intent": "clarify",
            "can_resolve": False,
            "category": "other",
            "priority": "low",
            "subject": "",
            "used_articles": [],
        }

    # 4. Classify Category & Priority
    from ai.classifier import _fallback_classify
    initial_user_msg = message
    if chat_history:
        for m in chat_history:
            if m.get("sender_type") in ("user", "enduser") or m.get("sender") == "user":
                initial_user_msg = m.get("body") or m.get("text") or message
                break

    clean_subject = initial_user_msg.strip().replace("\n", " ")
    if len(clean_subject) > 75:
        clean_subject = clean_subject[:72] + "..."
    clean_subject = clean_subject[0].upper() + clean_subject[1:] if clean_subject else "IT Support Request"

    classification = _fallback_classify(clean_subject, message)
    category = classification.get("category", "software")
    priority = classification.get("priority", "medium")

    # 5. Search Knowledge Base — with the user's whole description, not just the
    # latest line ("it crashes when I join a meeting" only makes sense after "Teams")
    user_turns = [
        m.get("body") or m.get("text") or ""
        for m in chat_history
        if m.get("sender_type") in ("user", "enduser") or m.get("sender") == "user"
    ]
    context = " ".join(user_turns[-3:] + ([message] if not user_turns or user_turns[-1] != message else []))
    context_clean = normalize_query(context)
    scored_articles = rank_articles(context_clean, kb_articles, weights)
    # The trained matcher knows many wordings of each problem; keyword
    # scoring is the fallback for articles it isn't sure about
    best_art = choose_article(context, kb_articles, scored_articles)

    used_articles = []
    reply_text = ""

    # Use Claude when configured
    if ai_enabled():
        conv_history = "\n".join(
            f"{m.get('sender_type', m.get('sender', 'user')).upper()}: {m.get('body', m.get('text', ''))}"
            for m in chat_history[-6:]
        )
        kb_context = "\n---\n".join([f"KB #{a['id']}: {a['title']}\n{a['body']}" for _, a in scored_articles[:2]])
        prompt = (
            f"You are an expert IT Virtual Assistant. Respond ONLY to what the user actually said.\n"
            f"Issue context: Category={category}, Urgency={priority}\n"
            f"User device/location: Windows enterprise workstation\n"
            f"Conversation history:\n{conv_history}\n\n"
            f"User's newest message: {message}\n\n"
            f"Available Knowledge Base solutions:\n{kb_context if kb_context else 'None'}\n\n"
            f"IMPORTANT RULES:\n"
            f"- If the user describes a real, specific technical problem: provide clear numbered steps to fix ONLY that exact problem.\n"
            f"- Do NOT produce generic catch-all steps that don't relate to the user's actual problem.\n"
            f"- Do NOT add steps for problems the user did not mention.\n"
            f"- Keep the response focused and concise.\n"
            f"- End by asking if the issue is resolved or if they need a human technician."
        )
        reply_text = await complete_text(CHAT_SYSTEM_PROMPT, prompt, max_tokens=4096, job="triage") or ""
        if reply_text and scored_articles:
            used_articles = [scored_articles[0][1]]

    # Fallback if no LLM reply generated
    if not reply_text:
        if best_art is not None:
            used_articles = [best_art]
            reply_text = (
                f"I found a verified Knowledge Base solution for **{best_art.get('title')}**:\n\n"
                f"{best_art.get('body')}\n\n"
                f"**Did this resolve your issue?**\n"
                f"• If this worked, click **\"Yes, it's fixed! ✅\"**\n"
                f"• If it didn't work, click **\"Still broken — Connect to Human Support ❌\"**"
            )
            status_intent = "troubleshoot"
            can_resolve = True
        else:
            dyn = _generate_dynamic_it_solution(clean_subject, message)
            if dyn.get("can_resolve"):
                reply_text = dyn.get("answer", "")
                status_intent = "troubleshoot"
                can_resolve = True
                if scored_articles:
                    used_articles = [scored_articles[0][1]]
            else:
                reply_text = (
                    f"I understand you are experiencing an issue with **{clean_subject}**.\n\n"
                    f"To make sure this is resolved properly, click **\"Connect to Human Support ❌\"** below "
                    f"and I will immediately escalate your ticket to our specialized {category.capitalize()} engineering team."
                )
                status_intent = "clarify"
                can_resolve = False
    else:
        status_intent = "troubleshoot"
        can_resolve = True

    return {
        "reply": reply_text,
        "subject": clean_subject,
        "category": category,
        "priority": priority,
        "status_intent": status_intent,
        "can_resolve": can_resolve,
        "used_articles": used_articles,
    }

