"""
AI Job 3 — Handover Briefing  ⭐ THE STAR FEATURE
Generates a complete technician briefing when a ticket is escalated.
"""

from typing import List, Dict, Any

from ai.client import complete_json

SYSTEM_PROMPT = """\
You are an IT support handover writer. A ticket is being escalated from the AI
assistant to a human technician. Write a briefing so the technician can start
work immediately WITHOUT asking the user to repeat anything.
You are given: the full ticket conversation, what the AI already tried, and
similar past resolved tickets.
Fields:
- summary: one tight paragraph — what is wrong, for whom, since when
- user_tried: what the user reported already doing
- ai_tried: what the AI assistant already attempted and the result
- likely_causes: ranked, most probable first
- suggested_steps: concrete next actions for the technician
- related_tickets: "#id — one line on how it was resolved", only for the similar tickets given
Be specific and factual. Do not invent details not present in the input.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "user_tried": {"type": "string"},
        "ai_tried": {"type": "string"},
        "likely_causes": {"type": "array", "items": {"type": "string"}},
        "suggested_steps": {"type": "array", "items": {"type": "string"}},
        "related_tickets": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "user_tried", "ai_tried", "likely_causes", "suggested_steps", "related_tickets"],
    "additionalProperties": False,
}

def _fallback_briefing(
    ticket: Dict[str, Any],
    messages: List[Dict[str, Any]],
    ai_tried: str,
    similar_tickets: List[Dict[str, Any]],
) -> dict:
    subject = ticket.get("subject", "IT Incident")
    description = ticket.get("description", "")
    
    # Extract user actions from messages
    user_msgs = [m.get("body", "") for m in messages if m.get("sender_type") in ("user", "enduser")]
    user_actions = "; ".join(user_msgs[1:]) if len(user_msgs) > 1 else "User attempted initial recommended self-service steps and reported failure."
    
    text = f"{subject} {description}".lower()
    
    if "wifi" in text or "wireless" in text or "ssid" in text:
        likely_causes = [
            "Local Wi-Fi adapter driver malfunction or disabled network stack",
            "802.1X corporate RADIUS authentication certificate expired or rejected",
            "DHCP IP address assignment pool exhaustion on local Access Point",
        ]
        suggested_steps = [
            "Verify client 802.1X enterprise network credentials and profile in RADIUS logs",
            "Guide user to reset network adapter via 'ncpa.cpl' and run 'ipconfig /release && ipconfig /renew'",
            "Check local Wireless Controller / AP health and signal coverage for the user's location",
        ]
    elif "vpn" in text:
        likely_causes = [
            "VPN tunnel gateway handshake timeout / certificate issue",
            "Local DNS cache corruption or conflicting network adapter / split tunneling rule",
            "Expired Active Directory / RADIUS network credentials",
        ]
        suggested_steps = [
            "Verify user's RADIUS / Active Directory account status and MFA enrollment",
            "Check VPN concentrator gateway logs for client IP dropouts or cipher mismatch",
            "Request user run 'ipconfig /flushdns' and reinstall client profile",
        ]
    elif "password" in text or "access" in text or "login" in text or "sso" in text or "mfa" in text:
        likely_causes = [
            "Account lockout due to repeated invalid authentication attempts",
            "Single Sign-On (SSO) session token expiry / MFA authenticator desync",
            "Insufficient role permissions assigned in Identity Provider",
        ]
        suggested_steps = [
            "Check Active Directory/Okta directory for account lock status and unlock",
            "Trigger a temporary password reset code to user's secondary contact",
            "Verify group memberships and access permission provisioning",
        ]
    elif "monitor" in text or "display" in text or "screen" in text and ("black" not in text and "power" not in text):
        likely_causes = [
            "Docking station firmware handshake failure or loose DisplayPort/HDMI cable",
            "Display driver resolution / refresh rate mismatch",
            "Windows multi-display projection setting reverted to PC Screen Only",
        ]
        suggested_steps = [
            "Guide user to power-cycle docking station and press Win+Ctrl+Shift+B to reset GPU driver",
            "Verify multi-monitor settings in Windows Display Settings (press Win+P)",
            "Check dock USB-C firmware and install updated DisplayLink / OEM graphics drivers",
        ]
    elif "bsod" in text or "blue screen" in text or "crash" in text:
        likely_causes = [
            "Corrupted device driver (graphics, network, or storage controller)",
            "System file corruption or conflicting recent Windows Update",
            "Hardware memory (RAM) or SSD fault",
        ]
        suggested_steps = [
            "Request user provide stop code / retrieve minidump from C:\\Windows\\Minidump",
            "Run DISM restore health and 'sfc /scannow' via administrative command prompt",
            "Run Windows Memory Diagnostic ('mdsched.exe') and check for driver updates",
        ]
    elif "printer" in text:
        likely_causes = [
            "Windows Print Spooler service crashed or stalled by corrupted print job",
            "Printer IP address changed or printer offline on local VLAN",
            "Outdated or corrupted printer driver package",
        ]
        suggested_steps = [
            "Restart Print Spooler service via 'net stop spooler && net start spooler'",
            "Clear stale queue files in C:\\Windows\\System32\\spool\\PRINTERS",
            "Ping printer IP address and re-bind network port in Printer Properties",
        ]
    elif "laptop" in text or "hardware" in text or "power" in text or "battery" in text:
        likely_causes = [
            "Hardware power delivery failure or battery protection lock",
            "Display cable / dock connectivity fault or GPU driver crash",
            "Motherboard power-cycling protection triggered",
        ]
        suggested_steps = [
            "Perform static discharge (hold power button 30s with AC disconnected)",
            "Test with known-good OEM charger and verify charging indicator LED",
            "Check asset warranty status and arrange hardware dispatch if unresponsive",
        ]
    else:
        likely_causes = [
            "Application configuration conflict or corrupted local cache",
            "Missing environment permissions or background service crash",
            "Network dependency unreachable or pending update requirement",
        ]
        suggested_steps = [
            "Review diagnostic logs and replicate the error on test environment",
            "Clear local cache/preferences and restart dependent services",
            "Contact user to schedule remote desktop diagnostics session",
        ]

    related = [
        f"#{t['id']} — {t['subject']}"
        for t in similar_tickets[:3]
    ]

    return {
        "summary": f"User reported: '{subject}'. Problem description: {description.strip()[:240]}.",
        "user_tried": user_actions or "Self-service steps attempted without success.",
        "ai_tried": ai_tried or "Automated deflection steps were presented to user.",
        "likely_causes": likely_causes,
        "suggested_steps": suggested_steps,
        "related_tickets": related,
    }


async def generate_briefing(
    ticket: Dict[str, Any],
    messages: List[Dict[str, Any]],
    ai_tried: str,
    similar_tickets: List[Dict[str, Any]],
) -> dict:
    """Run AI Job 3. Returns the handover briefing dict."""
    fallback = _fallback_briefing(ticket, messages, ai_tried, similar_tickets)

    thread_text = "\n".join(
        f"[{m.get('sender_type', 'user').upper()} @ {m.get('created_at', '')}]: {m.get('body', '')}"
        for m in messages
    )
    similar_text = "\n".join(
        f"#{t['id']}: {t['subject']} — {(t.get('description') or '')[:200]}"
        for t in similar_tickets
    ) if similar_tickets else "No similar past tickets found."

    user_content = (
        f"=== TICKET ===\n"
        f"Subject: {ticket.get('subject', '')}\n"
        f"Description: {ticket.get('description', '')}\n\n"
        f"=== FULL CONVERSATION THREAD ===\n{thread_text}\n\n"
        f"=== AI ALREADY ATTEMPTED ===\n{ai_tried or 'AI did not attempt a resolution.'}\n\n"
        f"=== SIMILAR PAST RESOLVED TICKETS ===\n{similar_text}"
    )

    result = await complete_json(
        SYSTEM_PROMPT, user_content, max_tokens=12000, job="briefing", schema=OUTPUT_SCHEMA, effort="medium"
    )
    if not result or not isinstance(result.get("summary"), str) or not result["summary"].strip():
        return fallback

    def _str_list(value, default):
        return [str(v) for v in value] if isinstance(value, list) else default

    return {
        "summary": result["summary"],
        "user_tried": str(result.get("user_tried") or fallback["user_tried"]),
        "ai_tried": str(result.get("ai_tried") or fallback["ai_tried"]),
        "likely_causes": _str_list(result.get("likely_causes"), fallback["likely_causes"]),
        "suggested_steps": _str_list(result.get("suggested_steps"), fallback["suggested_steps"]),
        "related_tickets": _str_list(result.get("related_tickets"), fallback["related_tickets"]),
    }
