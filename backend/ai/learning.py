"""
Continuous learning: turn a technician's fix into a knowledge-base draft.

When an escalated ticket is resolved by a person, the conversation contains
exactly what the chatbot was missing. This module writes that fix up as a
general, reusable KB article. Drafts are saved as "pending_approval"; once a
staff member approves one, the chatbot can use it for every future user
with the same problem.
"""

import logging
from typing import Any, Dict, List, Optional

from ai.client import complete_json

logger = logging.getLogger("relaydesk.learning")

SYSTEM_PROMPT = """\
You turn a resolved IT support ticket into a reusable knowledge-base article for the company's
self-service chatbot. Future employees with the same problem will be shown this article.

Write it for a non-technical employee:
- title: the problem as a user would describe it (e.g. "Outlook stuck on 'Disconnected'")
- body: one sentence on the symptom, then numbered steps the user can follow themselves, then a
  short "If this doesn't work" line. Use exact menu paths and commands from the ticket.
- tags: 3-6 comma-separated lowercase search keywords; category: the best match.
- Remove anything specific to this one person: names, emails, device names, IP addresses, ticket
  numbers, temporary passwords or tokens.
- reusable: false if the fix can't be done by a user (it needed admin rights, a hardware swap, an
  account change only IT can make) or the ticket doesn't show what actually fixed it. Still fill the
  other fields in that case.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "tags": {"type": "string"},
        "category": {"type": "string", "enum": ["hardware", "software", "network", "access", "account", "general", "other"]},
        "reusable": {"type": "boolean"},
    },
    "required": ["title", "body", "tags", "category", "reusable"],
    "additionalProperties": False,
}


def _transcript(messages: List[Dict[str, str]]) -> str:
    labels = {"user": "EMPLOYEE", "ai": "CHATBOT", "technician": "TECHNICIAN"}
    return "\n".join(f"[{labels.get(m['sender_type'], 'OTHER')}] {m['body']}" for m in messages)


def _template_draft(ticket: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Offline draft: the technician's own words, for a person to edit."""
    fix = "\n\n".join(m["body"] for m in messages if m["sender_type"] == "technician")
    return {
        "title": ticket["subject"][:256],
        "body": (
            f"**Problem reported:** {ticket['description'][:600]}\n\n"
            f"**How our technician resolved it:**\n{fix}\n\n"
            "_Draft generated from a resolved ticket — edit into user-facing steps "
            "and remove personal details before approving._"
        ),
        "tags": ", ".join(t for t in (ticket.get("tags") or [])[:6]),
        "category": ticket.get("category") or "general",
        "reusable": True,
    }


async def draft_article(ticket: Dict[str, Any], messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Returns a draft dict, or None when the ticket has nothing worth learning."""
    if not any(m["sender_type"] == "technician" for m in messages):
        return None  # closed without a human fix — nothing new to learn

    user_content = (
        f"Ticket subject: {ticket['subject']}\nCategory: {ticket.get('category') or 'unknown'}\n\n"
        f"Conversation:\n{_transcript(messages)}"
    )
    result = await complete_json(SYSTEM_PROMPT, user_content, max_tokens=8000, job="kb_draft",
                                 schema=OUTPUT_SCHEMA, effort="medium")
    if result is None:
        return _template_draft(ticket, messages)
    if not result.get("reusable") or not str(result.get("body", "")).strip():
        logger.info("Ticket #%s fix is not user-reusable; no KB draft", ticket.get("id"))
        return None
    return result
